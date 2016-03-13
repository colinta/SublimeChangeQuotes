# coding: utf8

import sublime
import sublime_plugin
import re

ST3 = int(sublime.version()) >= 3000

def normalize_settings(settings):
    for scope, conf in settings.items():
        prefixes = conf.get("prefixes", [])
        quote_lists = conf.get("quotes", [])

        # In the sub-lists, place the longest item furst
        for ql in quote_lists:
            ql.sort(key=len, reverse=True)

        # In the master list, place the sub-list with the longest item first
        quote_lists.sort(key=lambda x: len(x[0]), reverse=True)
        prefixes.sort(key=len, reverse=True)

        # print(prefixes)
        # print(quote_lists)
        settings[scope] = { "prefixes": prefixes, "quotes": quote_lists }

def plugin_loaded():
    global config
    config = sublime.load_settings('ChangeQuotes.sublime-settings').get('quote_lists')
    normalize_settings(config)

class ChangeQuotesCommand(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        self.edit = edit

        for region in self.view.sel():
            error = self.run_each(edit, region, **kwargs)

    def apply_scope(self, cursor):
        self.quotes = config["default"]["quotes"]
        self.prefixes = config["default"]["prefixes"]
        best = 0

        print("Working with: %s" % config)
        for scope, conf in config.items():
            score = self.view.score_selector(cursor, scope)
            if score > best:
                self.quotes = conf["quotes"]
                self.prefixes = conf["prefixes"]

        # print("Quotes: %s, Prefixes: %s" % (self.quotes, self.prefixes))

    def run_each(self, edit, sel_region):
        cursor = sel_region.begin()
        self.apply_scope(cursor)
        region = self.expand_region(sel_region)
        if not region: return


        text = self.view.substr(region)
        regexes = self.build_regexes()
        match_data, quotes = self.find_best_match(text, regexes)
        if not match_data: return

        substr = match_data.group(1)
        replacement = self.replacement(substr, quotes)
        regions = self.build_regions(region, text, match_data, substr, replacement)

        self.replace_quotes(regions, substr, replacement)
        self.escape_unescape(regions, substr, replacement)

    def expand_region(self, sel_region):
        # Cursor is always at 'b', use it as a ref
        ref = sel_region.b

        if self.view.score_selector(ref, 'string,meta.string'):
            region = self.expand_to_scope(ref, 'string,meta.string')
        else:
            region = self.expand_to_match(ref)

        if not region:
            # print("No region found.")
            return

        # print("Operation region: %s" % region)

        # It is unclear what is expected in this case
        if not region.contains(sel_region):
            # print("Selection region exceeds operation region, doing nothing")
            return

        return region

    def expand_to_scope(self, ref, scope):
        a = b = ref

        while (self.view.score_selector(a - 1, scope) and
                a != 0):
            a -= 1

        while (self.view.score_selector(b, scope) and
                b != self.view.size()):
            b += 1

        region = sublime.Region(a, b)

        return region

    def expand_to_match(self, ref):
        scope = self.view.extract_scope(ref)
        flattened_quotes = [item for sublist in self.quotes for item in sublist]

        # Get strings to the left and to the right of cursor
        # (up to a the scope extent)
        #
        region_left = sublime.Region(scope.begin(), ref)
        substr_left = self.view.substr(region_left)

        region_right = sublime.Region(ref, scope.end())
        substr_right = self.view.substr(region_right)

        # http://stackoverflow.com/a/11819111
        matches = []

        # Return a list of tuples:
        # [
        #   ('"', (3, 4)),
        #   ("'", (1, 8)),
        #   ...
        # ]
        # The sub-tuple contains match positions (left, right)
        #
        for q in flattened_quotes:
            # http://stackoverflow.com/a/11819111
            regex_right = re.compile(r'(?<!\\)(?:\\\\)*(%s)' % q)

            # left is reversed => escape symbol is *after* the quote
            regex_left = re.compile(r'(%s)(?:\\\\)*(?!\\)' % q)

            # print("[left] Trying %s with %s" % (q, regex_left.pattern))
            # print("[right] Trying %s with %s" % (q, regex_right.pattern))

            match_left = regex_left.search(substr_left[::-1])
            match_right = regex_right.search(substr_right)

            if match_left and match_right:
                elem = (q, (match_left, match_right))
                matches.append(elem)

        if not matches:
            # print("No matches")
            return

        # Find the tuple with the closest match position
        # (does not matter left or right)
        best = None

        for m in matches:
            m_left = m[1][0].start(1)
            m_right = m[1][1].start(1)

            # print("Match: %s (at (%s, %s))" % (m[0], m_left, m_right))

            if best is None:
                best = m
            else:
                best_left = best[1][0].start(1)
                best_right = best[1][1].start(1)
                # print("Against: %s (at (%s, %s))" % (best[0], best_left, best_right))
                if min(m_left, m_right) < min(best_left, best_right):
                    best = m

        # print("Best match: %s" % best[0])

        a = ref - (best[1][0].end(1))
        b = ref + (best[1][1].end(1))

        region = sublime.Region(a, b)

        return region

    def build_regexes(self):
        regexes = [(self.build_regex(q), q) for q in self.quotes]
        # print("REGEXES: %s" % regexes)

        return regexes

    def build_regex(self, quotes):
        wrapped_quotes = ['(?:%s)' % (q) for q in quotes]
        joined_quotes = '|'.join(wrapped_quotes)

        wrapped_prefixes = ['(?:%s)' % (p) for p in self.prefixes]
        joined_prefixes = '|'.join(wrapped_prefixes)

        pattern = '(%s)' % (joined_quotes)

        if self.prefixes:
            pattern = '^(?:%s)?(%s)' % (joined_prefixes, joined_quotes)
        else:
            pattern = '^(%s)' % (joined_quotes)

        # print("Pattern: %s" % pattern)
        regex = re.compile(pattern)

        return regex

    def find_best_match(self, text, regexes):
        matches = [(r[0].match(text), r[1]) for r in regexes]
        # print("Text: %s" % text)
        # print("Matches: %s" % matches)
        matches = [m for m in matches if m[0] is not None]

        if not matches:
            # print("No matches.")
            return (None, None)

        starts = [m[0].start(1) for m in matches]

        best_index = starts.index(min(starts))
        best = matches[best_index]
        # print("Best match: %s" % str(best))

        return best


    def replacement(self, substr, quotes):
        ind = quotes.index(substr)
        if len(quotes) == ind + 1:
          replacement = quotes[0]
        else:
          replacement = quotes[ind + 1]

        return replacement

    def build_regions(self, region, text, match_data, substr, replacement):
        # Offset -- as we operate with the substring, all positions
        #           are relative -- by adding the offset, they become
        #           absolute for the document.
        offset = region.begin()

        start, end = match_data.span(1)
        start_region = sublime.Region(start + offset, end + offset)

        # One more time offset -- if start_region is replaced by a longer string
        replacement_offset = len(replacement) - len(substr)
        offset += replacement_offset
        end_start = text.rfind(substr)
        end_region = sublime.Region(end_start + offset, end_start + len(substr) + offset)

        inner_region = sublime.Region(start_region.end() + replacement_offset, end_region.begin())

        # print(start_region)
        # print(end_region)
        # print(inner_region)

        return {"start": start_region, "end": end_region, "inner": inner_region}

    def replace_quotes(self, regions, substr, replacement):
        # print("Replacing %s with %s within regions %s and %s of <the text>" % (substr, replacement, regions["start"], regions["end"]))
        # print("Start region contents: %s" % self.view.substr(regions["start"]))
        self.view.replace(self.edit, regions["start"], replacement)
        # print("End region contents: %s" % self.view.substr(regions["end"]))
        self.view.replace(self.edit, regions["end"], replacement)

    def escape_unescape(self, regions, substr, replacement):
        inner_text = self.view.substr(regions["inner"])

        # ESCAPE already existing new quotes in the inner region
        unescaped_substr = replacement
        unescaped_replacement = re.sub(r'(.)', r'\\\g<1>', unescaped_substr)
        # print("[escape] Replace %s with %s in %s" % (unescaped_substr, unescaped_replacement, inner_text))
        inner_text = inner_text.replace(unescaped_substr, unescaped_replacement)

        # UNESCAPE escaped old quotes in the inner reagion
        escaped_substr = re.sub(r'(.)', r'\\\g<1>', substr)
        escaped_replacement = substr
        # print("[unesc]  Replace %s with %s in %s" % (unescaped_substr, unescaped_replacement, inner_text))
        inner_text = inner_text.replace(escaped_substr, escaped_replacement)

        self.view.replace(self.edit, regions["inner"], inner_text)


if not ST3:
    plugin_loaded()
