# CodeServe: Simple source browser
CodeServe is a simple server that will serve beautiful looking source code.
## Features
- Syntax highlighting
  - Uses vim syntax highlighter
  - Change vim colorscheme client side and server side
- Browse directories
- Link include files in C/C++

## How to Use
Run CodeServe with:

    code_serve.py

To see options run:

    code_serve.py --help


## Requirements
CodeServe requires

- vim
- Python 2.7
- memcached
- python2-memcached

## Known Issues
- The colorschme dropdown hides the options menu on some versions of Chrome/Chromium
    - [Bug](https://code.google.com/p/chromium/issues/detail?id=115649)

## Author
[Clark DuVall](http://clarkduvall.com)
