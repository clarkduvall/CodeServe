#!/usr/bin/python

import argparse
import os
import re
import SimpleHTTPServer
import SocketServer
import subprocess
import sys

INCLUDE = [ '.' ]
BASE_PATH = '.'
DARK = False

def _ReadFile(filename):
  with open(filename) as f:
    return f.read()

def _WriteFile(filename, contents):
  with open(filename, 'w') as f:
    return f.write(contents)

def _UrlExists(url):
  for include in INCLUDE:
    path = os.path.join(BASE_PATH, include, url)
    if os.path.exists(path):
      return path
  return None

def _CheckPathReplace(match):
  if _UrlExists(match.group(4)):
    return ('<%s>#include </%s><%s>&quot;<a style="color: inherit" href="/%s">'
            '%s</a>&quot;' % (match.group(1), match.group(2), match.group(3),
                              match.group(4), match.group(4)))
  return match.group(0)

def _ParseIncludes(html):
  # This will need to change if vim TOhtml ever changes.
  return re.sub(r'<(.*?)>#include </(.*?)><(.*?)>&quot;(.*)&quot;',
                _CheckPathReplace,
                html)

def _CreateHtmlFile(path, html_path):
  ext = os.path.splitext(path)[1].strip('.')
  swap = '.%s.swp' % path
  if os.path.exists(swap):
    os.remove(swap)
  subprocess.call('vim %s "+TOhtml" "+w %s" \'+qa!\'' % (path, html_path),
                  shell=True)
  html = _ReadFile(html_path)
  if DARK:
    html = (html.replace('background-color: #ffffff', 'background-color: #000')
                .replace('color: #000000', 'color: #fff'))
  os.remove(html_path)
  return _ParseIncludes(html)

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
  def do_GET(self):
    url = self.path.strip('/')
    if not len(url):
      url = '.'
    path = _UrlExists(url)
    if path is None:
      self.wfile.write('Path does not exist :(')
      return
    if os.path.isdir(path):
      self.wfile.write(self.list_directory(path).read())
      return
    html_path = '%s.html' % path
    if os.path.exists(html_path):
      os.remove(html_path)
    self.wfile.write(_CreateHtmlFile(path, html_path))

class Server(SocketServer.TCPServer):
  allow_reuse_address = True

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('-i', '--include', nargs='+',
                      help='include paths to use when searching for code')
  parser.add_argument('-b', '--base-path', default='.',
                      help='the base path to serve code from')
  parser.add_argument('-d', '--dark', action='store_true',
                      help='dark color scheme')
  args = parser.parse_args()
  if args.include:
    INCLUDE.extend(args.include)
  BASE_PATH = args.base_path
  DARK = args.dark
  print 'Go to http://localhost:8000 to view your source.'

  Server(("", 8000), Handler).serve_forever()
