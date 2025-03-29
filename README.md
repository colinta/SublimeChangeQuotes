ChangeQuotes
============

Converts single to double or double to single quotes.  Attempts to preserve correct escaping, though this could be improved I'm sure.

Installation
------------

Using Package Control, install "ChangeQuotes" or clone this repo in your packages folder.

I recommended you add key bindings for the commands. I've included my preferred bindings below.
Copy them to your key bindings file (⌘⇧,).

Key Bindings
------------

Copy these to your user key bindings file.

<!-- keybindings start -->
    { "keys": ["ctrl+shift+'"], "command": "change_quotes" },
<!-- keybindings stop -->

How to use
----------

Put your cursor inside the text that is in quotes and then execute the command to replace the quotes. No selection needed.

How to customize
----------------

Different languages have different quotes, and this plugin tries to support them all!

Open up `ChangeQuotes.sublime-settings` to see the default config.  You can get
there from the menu bar:
```Preferences > Package Settings > Change Quotes > Settings - Default```

There are two per-language settings you should pay attention to:

`prefixes` - This helps with the string searching; in python, a string can start
with an identifier like `u` or `r`, and these will be "skipped" when changing
quotes.

`quotes` - This list-of-lists defines all the quote characters that can be
cycled.  If you are using ES6, and want to add support for backtick-strings /
interpolation-strings, you just need to add the backtick character to this list!

```json
// without backtick-strings:
"source.js": {
  "quotes": [["'", "\""]]
}
// with backtick-string support (ES6-only):
"source.js": {
  "quotes": [["'", "\"", "`"]]
}
```

Commands
--------

`change_quotes`: Converts from single to double quotes.  Uses the Sublime Text
grammar parsing, so it doesn't always "find" the quotes, for instance MarkDown
doesn't define special "string" syntax, and so this plugin can't be used.  The
upside is we don't have to write / maintain a complex matching quote algorithm.
