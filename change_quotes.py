# coding: utf8
import sublime
import sublime_plugin


MATCH_QUOTE = {
    "'": "'",
    "u'": "'",
    "'''": "'''",
    "u'''": "'''",
    '"': '"',
    'u"': '"',
    '"""': '"""',
    'u"""': '"""',
    u'‘': u'’',
    u'“': u'”',
    u'‹': u'›',
    u'«': u'»',
}


CHANGE_QUOTE = {
    "'": '"',
    "u'": 'u"',
    "'''": '"""',
    "u'''": 'u"""',
    '"': "'",
    'u"': "u'",
    '"""': "'''",
    'u"""': "u'''",
    u'‘': u'“',
    u'’': u'”',
    u'“': u'‘',
    u'”': u'’',
    u'‹': u'«',
    u'›': u'»',
    u'«': u'‹',
    u'»': u'›',
}


class ChangeQuotesCommand(sublime_plugin.TextCommand):
    def run(self, edit, **kwargs):
        e = self.view.begin_edit('change_quotes')
        regions = [region for region in self.view.sel()]

        # any edits that are performed will happen in reverse; this makes it
        # easy to keep region.a and region.b pointing to the correct locations
        def compare(region_a, region_b):
            return cmp(region_b.end(), region_a.end())
        regions.sort(compare)

        for region in regions:
            try:
                error = self.run_each(edit, region, **kwargs)
            except Exception as exception:
                print repr(exception)
                error = exception.message

            if error:
                sublime.status_message(error)
        self.view.end_edit(e)

    def run_each(self, edit, region):
        a = region.begin()
        b = region.end()
        if not (self.view.score_selector(a, 'string') and self.view.score_selector(b, 'string')):
            return self.run_each_find_quotes(edit, region)

        while self.view.score_selector(a - 1, 'string'):
            a -= 1
            if a == 0:
                break

        while self.view.score_selector(b + 1, 'string'):
            b += 1
            if b == self.view.size():
                b -= 1
                break

        if self.view.score_selector(a, 'string.quoted.single.block.python') \
                and self.view.substr(sublime.Region(a, a + 3)) == "'''" \
                and self.view.substr(sublime.Region(b - 2, b + 1)) == "'''":
            quote_a = quote_b = "'''"
        elif self.view.score_selector(a, "string.quoted.double.block.python") \
                and self.view.substr(sublime.Region(a, a + 3)) == '"""' \
                and self.view.substr(sublime.Region(b - 2, b + 1)) == '"""':
            quote_a = quote_b = '"""'
        elif self.view.score_selector(a, 'string.quoted.single.single-line.unicode.python') \
                and self.view.substr(sublime.Region(a, a + 2)) == "u'" \
                and self.view.substr(sublime.Region(b, b + 1)) == "'":
            a += 1
            quote_a = quote_b = "'"
        elif self.view.score_selector(a, "string.quoted.double.single-line.unicode.python") \
                and self.view.substr(sublime.Region(a, a + 2)) == 'u"' \
                and self.view.substr(sublime.Region(b, b + 1)) == '"':
            a += 1
            quote_a = quote_b = '"'
        elif self.view.score_selector(a, 'string.quoted.single.block.unicode.python') \
                and self.view.substr(sublime.Region(a, a + 4)) == "u'''" \
                and self.view.substr(sublime.Region(b - 2, b + 1)) == "'''":
            quote_a = "u'''"
            quote_b = "'''"
        elif self.view.score_selector(a, "string.quoted.double.block.unicode.python") \
                and self.view.substr(sublime.Region(a, a + 4)) == 'u"""' \
                and self.view.substr(sublime.Region(b - 2, b + 1)) == '"""':
            a += 1
            quote_a = quote_b = '"""'
        elif self.view.score_selector(a, 'string.quoted.single.single-line.raw-regex.python') \
                and self.view.substr(sublime.Region(a, a + 2)) == "r'" \
                and self.view.substr(sublime.Region(b, b + 1)) == "'":
            a += 1
            quote_a = quote_b = "'"
        elif self.view.score_selector(a, "string.quoted.double.single-line.raw-regex.python") \
                and self.view.substr(sublime.Region(a, a + 2)) == 'r"' \
                and self.view.substr(sublime.Region(b, b + 1)) == '"':
            a += 1
            quote_a = quote_b = '"'
        elif self.view.score_selector(a, 'string.quoted.single.block.raw-regex.python') \
                and self.view.substr(sublime.Region(a, a + 4)) == "r'''" \
                and self.view.substr(sublime.Region(b - 2, b + 1)) == "'''":
            a += 1
            quote_a = quote_b = "'''"
        elif self.view.score_selector(a, "string.quoted.double.block.raw-regex.python") \
                and self.view.substr(sublime.Region(a, a + 4)) == 'r"""' \
                and self.view.substr(sublime.Region(b - 2, b + 1)) == '"""':
            a += 1
            quote_a = quote_b = '"""'
        else:
            quote_a = self.view.substr(a)
            quote_b = self.view.substr(b)

        b -= len(quote_b) - 1

        if quote_b != MATCH_QUOTE[quote_a]:
            return "Quote characters ({0}, {1}) do not match".format(quote_a, quote_b)

        replacement_a = CHANGE_QUOTE[quote_a]
        replacement_b = CHANGE_QUOTE[quote_b]

        escape = None
        if quote_a == "'":
            escape = '"'
        elif quote_a == '"':
            escape = "'"

        self.view.sel().subtract(region)
        self.view.replace(edit, sublime.Region(a, a + len(replacement_a)), replacement_a)
        self.view.replace(edit, sublime.Region(b, b + len(replacement_b)), replacement_b)

        if escape:
            # escape "escape" with "\escape"
            inside_region = sublime.Region(a + 1, b)
            inside = self.view.substr(inside_region)
            inside = inside.replace("\\" + quote_a, quote_a)
            inside = inside.replace(escape, "\\" + escape)
            self.view.replace(edit, inside_region, inside)

        self.view.sel().add(region)

    def run_each_find_quotes(self, edit, region):
        a = region.begin()
        b = region.end()

        match = None
        while True:
            a -= 1
            if a <= 0:
                break
            quote_a = self.view.substr(a)
            if quote_a in MATCH_QUOTE.keys():
                if quote_a in '\'"':
                    # check for a \\
                    is_escaped = False
                    while a > 0 and self.view.substr(a - 1) == '\\':
                        is_escaped = not is_escaped
                        a -= 1  # keep checking for a backslash
                    if is_escaped:
                        continue
                match = MATCH_QUOTE[quote_a]
                break

        is_escaped = False
        while True:
            b += 1
            if b >= self.view.size():
                return "Could not find matching quote ({0})".format(match)

            quote_b = self.view.substr(b)
            if quote_b == match and not is_escaped:
                break
            elif match in '\'"' and quote_b == '\\':
                is_escaped = not is_escaped
            else:
                is_escaped = False

        replacement_a = CHANGE_QUOTE[quote_a]
        replacement_b = CHANGE_QUOTE[quote_b]

        self.view.sel().subtract(region)

        self.view.replace(edit, sublime.Region(a, a + len(replacement_a)), replacement_a)
        self.view.replace(edit, sublime.Region(b, b + len(replacement_b)), replacement_b)

        # escape "replacement" with "\replacement"
        if replacement_a == replacement_b:
            inside_region = sublime.Region(a + 1, b)
            inside = self.view.substr(inside_region)
            inside = inside.replace("\\" + quote_a, quote_a)
            inside = inside.replace(replacement_a, "\\" + replacement_a)
            self.view.replace(edit, inside_region, inside)

        self.view.sel().add(region)
