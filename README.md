ChangeQuotes for Sublime Text 2
===============================

Converts single to double or double to single quotes.  Attempts to preserve correct escaping, though this could be improved I'm sure.

Installation
------------

1. Using Package Control, install "ChangeQuotes"

Or:

1. Open the Sublime Text 2 Packages folder

    - OS X: ~/Library/Application Support/Sublime Text 2/Packages/
    - Windows: %APPDATA%/Sublime Text 2/Packages/
    - Linux: ~/.Sublime Text 2/Packages/

2. clone this repo
3. Install keymaps for the commands (see Example.sublime-keymap for my preferred keys)

Commands
--------

`change_quotes`: Converts from single to double quotes.  Uses the Sublime Text grammar parsing, so it doesn't always "find" the quotes.
