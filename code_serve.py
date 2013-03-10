#!/usr/bin/python

# Copyright 2013 Clark DuVall
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import re
import SimpleHTTPServer
import SocketServer
import subprocess
import tempfile

INCLUDE = ['.']
BASE_PATH = '.'
VIM_ARGS = []

def _ReadFile(filename):
  with open(filename) as f:
    return f.read()

def _WriteFile(filename, contents):
  with open(filename, 'w') as f:
    return f.write(contents)

def _UrlExists(url, current=None):
  for include in INCLUDE:
    path = os.path.join(BASE_PATH, include, url)
    if os.path.exists(path):
      return (path, url)
  if current is not None:
    path = os.path.join(os.path.dirname(current), url)
    if os.path.exists(path):
      return (path, path)
  return (None, None)

def _CheckPathReplace(match, opening, closing, path):
  url, link_path = _UrlExists(match.group(4), current=path)
  if link_path is not None:
    return ('<%s>#include </%s><%s>%s<a style="color: inherit" href="/%s">'
            '%s</a>%s' % (match.group(1), match.group(2), match.group(3),
                          opening, link_path, match.group(4), closing))
  return match.group(0)

def _ParseIncludes(html, path):
  # This will need to change if vim TOhtml ever changes.
  regex = r'<(.*?)>#include </(.*?)><(.*?)>%s(.*)%s'
  quot = '&quot;'
  lt = '&lt;'
  gt = '&gt;'
  subbed_html = re.sub(regex % (quot, quot),
                       lambda x: _CheckPathReplace(x, quot, quot, path),
                       html)
  return re.sub(regex % (lt, gt),
                lambda x: _CheckPathReplace(x, lt, gt, path),
                subbed_html)

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
  def _SendHtmlFile(self, path):
    fd, name = tempfile.mkstemp()
    swap = os.path.join(os.path.dirname(path),
                        '.%s.swp' % os.path.basename(path))
    if os.path.exists(swap):
      os.remove(swap)
    vim = ['vim', path]
    vim.extend(['+%s' % arg for arg in VIM_ARGS])
    vim.extend(['+TOhtml','+w! %s' % name, '+qa!'])

    try:
      subprocess.check_call(vim)
    except subprocess.CalledProcessError as e:
      self.send_error(500, 'Vim error: %s' % e)
      return

    with os.fdopen(fd) as f:
      html = f.read()
    os.remove(name)
    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()
    self.wfile.write(_ParseIncludes(html, path))

  def do_GET(self):
    url = self.path.strip('/')
    if not len(url):
      url = '.'
    path, _ = _UrlExists(url)
    if path is None:
      self.send_error(404, 'Path does not exist :(')
      return
    if os.path.isdir(path):
      if self.path[-1:] != '/':
        self.send_response(301)
        self.send_header('Location', '%s/' % self.path)
        self.end_headers()
      else:
        self.wfile.write(self.list_directory(path).read())
    else:
      self._SendHtmlFile(path)

class Server(SocketServer.TCPServer):
  allow_reuse_address = True

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('-i', '--include', nargs='+',
                      help='include paths to use when searching for code')
  parser.add_argument('-b', '--base-path', default='.',
                      help='the base path to serve code from')
  parser.add_argument('-p', '--port', default=8000, type=int,
                      help='the port to run the server on')
  parser.add_argument('-v', '--vim-args', nargs='+', default=[],
                      help='extra arguments to pass to vim')
  args = parser.parse_args()
  if args.include:
    INCLUDE.extend(args.include)
  BASE_PATH = args.base_path
  VIM_ARGS = args.vim_args
  print('Go to http://localhost:%d to view your source.' % args.port)

  Server(('', args.port), Handler).serve_forever()
