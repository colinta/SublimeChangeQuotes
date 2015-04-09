ChangeQuotes
============

Converts single to double or double to single quotes.  Attempts to preserve correct escaping, though this could be improved I'm sure.

Installation
------------

1. Using Package Control, install "ChangeQuotes"

Or:

1. Open the Sublime Text Packages folder
    - OS X: ~/Library/Application Support/Sublime Text 3/Packages/
    - Windows: %APPDATA%/Sublime Text 3/Packages/
    - Linux: ~/.Sublime Text 3/Packages/ or ~/.config/sublime-text-3/Packages

2. clone this repo
3. Install keymaps for the commands (see Example.sublime-keymap for my preferred keys)

### Sublime Text 2

1. Open the Sublime Text 2 Packages folder
2. clone this repo, but use the `st2` branch

       git clone -b st2 git@github.com:colinta/SublimeChangeQuotes

How to use
----------

Put your cursor inside the text that is in quotes and then execute the command to replace the quotes. No selection needed.

Commands
--------

`change_quotes`: Converts from single to double quotes.  Uses the Sublime Text grammar parsing, so it doesn't always "find" the quotes.
