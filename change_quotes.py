# coding: utf8
"""ChangeQuotes plugin module."""

import sublime
import sublime_plugin
import re
import itertools

ST3 = int(sublime.version()) >= 3000

global config
config = None  # mute F821 errors from flake8


def reorder_list_settings(list_settings):
    """Reorder the quotes lists and the prefixes list.

    The reordering of the quotes lists is as follows:
      - Each quote list's elements (quotes) are ordered by len(quote)
      - The quote lists's elements (quote_lists) are ordered len(quote_list[0])

    The reordering of the prefix list is as follows:
      - The prefix list's elements (prefixes) are ordered by len(prefix)

    The order is important, because a ''' must take precedence over '
    (otherwise '''foo bar''' will get replaced by ''"foo bar"'')

    Returns the sorted settings.

    """
    for scope, conf in list_settings.items():
        prefixes = conf.get("prefixes", [])
        quote_lists = conf.get("quotes", [])

        # In the sub-lists, place the longest item first
        for ql in quote_lists:
            ql.sort(key=len, reverse=True)

        # In the master list, place the sub-list with the longest item first
        quote_lists.sort(key=lambda x: len(x[0]), reverse=True)
        prefixes.sort(key=len, reverse=True)
        list_settings[scope] = {"prefixes": prefixes, "quotes": quote_lists}

    return list_settings


def build_config(settings):
    """Build a dict from the sublime settings.

    This is required since the original settings need to be reordered
    before they are used, which can't happen directly
    (sublime's settings are immutable)

    Returns a dict representing the reordered settings.

    """
    global config

    config = {}
    config["debug"] = settings.get("debug")
    config["lists"] = reorder_list_settings(settings.get("lists"))


def load_config():
    """Load the plugin settings."""
    settings = sublime.load_settings("ChangeQuotes.sublime-settings")
    build_config(settings)


def plugin_loaded():
    """Invoke load_config() and attach a settings on_change hook.

    Care must be taken to attach the hook just once, hence
    plugin_loaded and load_config are separated.

    """
    settings = sublime.load_settings("ChangeQuotes.sublime-settings")
    settings.add_on_change("lists", load_config)
    build_config(settings)


def debug(msg):
    """Print the given message if the `debug` setting is true."""
    if config["debug"]:
        print("[ChangeQuotes] %s" % str(msg))


class ChangeQuotesCommand(sublime_plugin.TextCommand):

    """Main plugin class."""

    def run(self, edit, **kwargs):
        """Main plugin function."""
        self.edit = edit

        for region in self.view.sel():
            self.run_each(edit, region, **kwargs)

    def run_each(self, edit, sel_region):
        """Run the command for each selection region."""
        cursor = sel_region.begin()
        self.apply_scope(cursor)
        region = self.expand_region(sel_region)
        if not region:
            return

        text = self.view.substr(region)
        regex_tuples = self.build_regex_tuples()
        match_data, quote_list = self.find_best_match(text, regex_tuples)
        if not match_data:
            return

        quote = match_data.group(1)
        replacement = self.replacement(quote, quote_list)
        regions = self.build_regions(
            region,
            text,
            match_data,
            quote,
            replacement
        )

        # Edge case in which there is no closing quote
        if regions["start"].contains(regions["end"]):
            return

        # Altering the region lengths (e.g. replacing ' with ''') will cause
        # their right boundary to move further to the right, which
        # causes issues as the boundaries no longer match the pre-calculated
        # values.
        #
        # To avoid the issue, it is important to start replacing from
        # the rightmost region (`end`) to the leftmost region (`start`)
        self.replace_quotes(regions["end"], replacement)
        self.escape_unescape(regions["inner"], quote, replacement)
        self.replace_quotes(regions["start"], replacement)

    def apply_scope(self, cursor):
        """Choose the best-matching quote and prefix lists.

        Start by choosing the default ones.
        Then, for syntax-specific lists, evaluate the syntax
        match score and possibly choose them instead.

        Chosen values are stored in self.quotes and self.prefixes.

        No explicit return value.

        """
        self.quote_lists = config["lists"]["default"]["quotes"]
        self.prefix_list = config["lists"]["default"]["prefixes"]
        best = 0

        debug("Working with: %s" % config)
        debug("Scope: %s" % self.view.scope_name(cursor))

        for scope, conf in config["lists"].items():
            score = self.view.score_selector(cursor, scope)
            if score > best:
                self.quote_lists = conf["quotes"]
                self.prefix_list = conf["prefixes"]

        debug("Quotes: %s, Prefixes: %s" % (self.quote_lists,
                                            self.prefix_list))

    def expand_region(self, sel_region):
        """Expand working region to the quote extents.

        Use the cursor position as a starting reference point.
        (cursor is always at `sel_region.b`)

        Two different approaches are used, based on the context:
          1/ string context
          2/ non-string context (e.g. comment)

        Finally, if the expanded region does not entirely contain the
        user selection region (e.g. the selection spans across both
        sides of a string boundary), nothing is returned.

        Returned value is a sublime.Region object.

        """
        # Cursor is always at 'b', use it as a ref
        ref = sel_region.b

        if self.view.score_selector(ref, "string,meta.string"):
            scopes = self.view.scope_name(ref).split()
            debug("Scopes: %s" % str(scopes))

            regex = re.compile(r"^(?:meta.)?string")
            scope = next(x for x in scopes if regex.match(x))

            debug("Chosen scope: %s" % scope)

            region = self.expand_to_scope(ref, scope)
        else:
            region = self.expand_to_match(ref)

        if not region:
            debug("No region found.")
            return

        debug("Operation region: %s" % region)

        # It is unclear what is expected in this case
        if not region.contains(sel_region):
            debug("Selection region exceeds operation region, doing nothing")
            return

        return region

    def expand_to_scope(self, ref, scope):
        """Expand `ref` to a region within the `scope` extents.

        Returned value is a sublime.Region object.

        """
        a = b = ref

        while (self.view.score_selector(a - 1, scope) and a != 0):
            a -= 1

        while (self.view.score_selector(b, scope) and b != self.view.size()):
            b += 1

        region = sublime.Region(a, b)

        return region

    def expand_to_match(self, ref):
        """Expand `ref` to the innermost region, surrounded by quotes.

        Expansion is done by searching for any of the chars in each
        list in self.quote_lists. Search is both to the left and right,
        up to the current scope extents. Then, the constructed regions
        are compared and the one closest to `ref` boundary is returned.

        Escaped quotes are not considered a region boundary by checking if
        an odd amount of backslashes precede the quote. It is not a perfect
        solution, but given the unknown semantics of the current region,
        it should suffice.

        Returned value is a sublime.Region object.

        """
        scope = self.view.extract_scope(ref)

        # flatten -- http://stackoverflow.com/a/952952
        all_quotes = [item for qlist in self.quote_lists for item in qlist]

        # Get strings to the left and to the right of cursor
        # (up to a the scope extent)
        #
        region_left = sublime.Region(scope.begin(), ref)
        substr_left = self.view.substr(region_left)

        region_right = sublime.Region(ref, scope.end())
        substr_right = self.view.substr(region_right)

        matches = []

        # For each quote, build a list of tuples:
        # [
        #   ('"', (3, 4)),
        #   ("'", (1, 8)),
        #   ...
        # ]
        # The sub-tuple contains match distances (left, right) from `ref`
        #
        for q in all_quotes:
            escaped_q = re.escape(q)

            # http://stackoverflow.com/a/11819111
            regex_right = re.compile(r"(?<!\\)(?:\\\\)*(%s)" % escaped_q)

            # left is reversed => escape symbol is *after* the quote
            regex_left = re.compile(r"(%s)(?:\\\\)*(?!\\)" % escaped_q)

            debug("[left] Trying %s with %s" % (q, regex_left.pattern))
            debug("[right] Trying %s with %s" % (q, regex_right.pattern))

            match_left = regex_left.search(substr_left[::-1])
            match_right = regex_right.search(substr_right)

            if match_left and match_right:
                elem = (q, (match_left, match_right))
                matches.append(elem)

        if not matches:
            debug("No matches")
            return

        # Find the tuple with the least match distance
        # (does not matter left or right)
        best = matches[0]

        for m in matches[1:]:
            m_left = m[1][0].start(1)
            m_right = m[1][1].start(1)
            best_left = best[1][0].start(1)
            best_right = best[1][1].start(1)

            debug("Match: %s at (%s, %s)" % (m[0], m_left, m_right))
            debug("Against: %s at (%s, %s)" % (best[0], best_left, best_right))
            if min(m_left, m_right) < min(best_left, best_right):
                best = m

        debug("Best match: %s" % best[0])

        a = ref - (best[1][0].end(1))
        b = ref + (best[1][1].end(1))

        region = sublime.Region(a, b)

        return region

    def build_regex_tuples(self):
        """For each list in self.quote_lists, return a tuple (regex, list).

        Returned value is a list of (_sre.SRE_Pattern, quotes_list) tuples.

        """
        regexes = [(self.build_regex(ql), ql) for ql in self.quote_lists]
        debug("REGEXES: %s" % regexes)

        return regexes

    def build_regex(self, quotes_list):
        """Build a regex matching any quote in `quotes_list`.

        The regex has only one match group -- the matched quote.

        Returned value is a _sre.SRE_Pattern object.

        """
        wrapped_quotes = ["(?:%s)" % (re.escape(q)) for q in quotes_list]
        joined_quotes = "|".join(wrapped_quotes)

        wrapped_prefixes = ["(?:%s)" % (p) for p in self.prefix_list]
        joined_prefixes = "|".join(wrapped_prefixes)

        pattern = "(%s)" % (joined_quotes)

        if self.prefix_list:
            pattern = "^(?:%s)?(%s)" % (joined_prefixes, joined_quotes)
        else:
            pattern = "^(%s)" % (joined_quotes)

        debug("Pattern: %s" % pattern)
        regex = re.compile(pattern)

        return regex

    def find_best_match(self, text, regex_tuples):
        """Find the best match in `text` amongst the `regex_tuples` list.

        `regex_tuples` is a list of (_sre.SRE_Pattern, quotes_list) tuples.

        The "best match" is actually the "closest match" -- i.e. the
        match result with the lowest match-index in `text`.

        The returned value is a (_sre.SRE_Match, quotes_list) tuple.

        """
        matches = [(r[0].match(text), r[1]) for r in regex_tuples]
        debug("Text: %s" % text)
        debug("Matches: %s" % matches)
        matches = [m for m in matches if m[0] is not None]

        if not matches:
            debug("No matches.")
            return (None, None)

        starts = [m[0].start(1) for m in matches]

        best_index = starts.index(min(starts))
        best = matches[best_index]
        debug("Best match: %s" % str(best))

        return best

    def replacement(self, quote, quote_list):
        """Find the replacement of `quote` amongst `quote_list`.

        The replacement is just the "next" quote in `quote_list`.

        Returned value is a string.

        """
        cycle = itertools.cycle(quote_list)
        i = 0

        # Loop until the quote is found.
        # The quote after it is the replacement
        while quote != next(cycle):
            i += 1
            if i > 100:
                raise Exception("Loop detected")

            continue

        return next(cycle)

    def build_regions(self, region, text, match_data, quote, replacement):
        """Divide `region` into 3 sub-regions: start, end and inner.

        The start region contains only the quote chars at the left border.
        The end region contains only the quote chars at the right border.
        The inner region contains the text inbetween.

        Returned value is a dict:
        {
            "start": subime.Region,
            "end": sublime.Region,
            "inner": sublime.Region
        }

        """
        # Offset -- all positions are relative to the region.
        #           By adding the offset, they become absolute for the document
        offset = region.begin()

        # Start region
        start_l, start_r = match_data.span(1)
        start_region = sublime.Region(start_l + offset, start_r + offset)

        # End region
        end_l = text.rfind(quote)
        end_r = end_l + len(quote)
        end_region = sublime.Region(end_l + offset, end_r + offset)

        # Inner region
        inner_region = sublime.Region(start_region.end(), end_region.begin())

        debug("Start region: %s" % start_region)
        debug("End region: %s" % end_region)
        debug("Inner region: %s" % inner_region)

        return {
            "start": start_region,
            "end": end_region,
            "inner": inner_region
        }

    def replace_quotes(self, region, replacement):
        """Replace the contents of a `region` with `replacement`.

        No explicit return value.

        """
        debug("Replace: %s with %s" % (self.view.substr(region), replacement))
        self.view.replace(self.edit, region, replacement)

    def escape_unescape(self, region, quote, replacement):
        r"""In `region`, escape `replacement` and unescape `quote`.

        The escaped values are constructed from `replacement` by prepending
        each of its characters with a backslash. E.g:
        ' becomes \'
        ''' becomes \'\'\'

        The opposite logic is applied when "unescaping" `quote`.

        Already escaped replacements are not escaped twice.
        This means that in a subsequent invocation, the plugin is unable to
        distinguish them from the others:
        (1) 'foo "bar" \"baz\"'   =>
        (2) "foo \"bar\" \"baz\"" =>
        (3) 'foo "bar" "baz"'

        Ideally, (1) and (3) should match, but that is not possible.

        No explicit return value.

        """
        debug("Replace %s with %s in %s" % (quote, replacement, region))
        inner_text = self.view.substr(region)

        # ESCAPE already existing new quotes in the inner region
        unesc_quote = replacement
        unesc_replacement = re.sub(r"(.)", r"\\\g<1>", unesc_quote)
        debug("Escape: replace %s with %s" % (unesc_quote, unesc_replacement))
        inner_text = inner_text.replace(unesc_quote, unesc_replacement)

        # UNESCAPE escaped old quotes in the inner reagion
        esc_quote = re.sub(r"(.)", r"\\\g<1>", quote)
        esc_replacement = quote
        debug("Unesacpe: Replace %s with %s" % (esc_quote, esc_replacement))
        inner_text = inner_text.replace(esc_quote, esc_replacement)

        self.view.replace(self.edit, region, inner_text)


if not ST3:
    plugin_loaded()
