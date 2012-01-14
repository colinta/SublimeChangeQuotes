import sublime
import sublime_plugin


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
            error = self.run_each(edit, region, **kwargs)
            if error:
                sublime.status_message(error)
        self.view.end_edit(e)

    def run_each(self, edit, region):
        if not (self.view.score_selector(region.begin(), 'string') and self.view.score_selector(region.end(), 'string')):
            return 'Cursor is not in a string'

        a = region.begin()
        b = region.end()

        while self.view.score_selector(a, 'string'):
            a -= 1
            if a == 0:
                break
        while self.view.score_selector(b, 'string'):
            b += 1
            if b == self.view.size():
                break
        b -= 1
        a += 1
        quote_a = self.view.substr(a)
        quote_b = self.view.substr(b)
        if quote_a != quote_b:
            return 'Quote characters do not match'

        if quote_a == "'":
            replacement = '"'
        else:
            replacement = "'"

        self.view.sel().subtract(region)

        self.view.replace(edit, sublime.Region(a, a + 1), replacement)
        self.view.replace(edit, sublime.Region(b, b + 1), replacement)

        # escape "replacement" with "\replacement"
        inside_region = sublime.Region(a + 1, b)
        inside = self.view.substr(inside_region)
        inside = inside.replace("\\" + quote_a, quote_a)
        inside = inside.replace(replacement, "\\" + replacement)
        self.view.replace(edit, inside_region, inside)

        self.view.sel().add(region)
