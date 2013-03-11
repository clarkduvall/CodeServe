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
import CGIHTTPServer
import memcache
import os
import re
import SocketServer
import subprocess
import tempfile
import urllib
import urlparse

INCLUDE = ['.']
BASE_PATH = '.'
VIM_ARGS = []
CACHE = None
COLOR_DIR = '/usr/share/vim/vim73/colors/'

BACK_HTML = '''
<div>
  <a style="font-size: 1em; color: inherit" href="/%s%s">Up directory</a>
</div>
'''

COLOR_PICKER_HTML = '''
<form style="float: right; box-shadow: -10px 10px 50px #888; padding: 10px">
  <table>
    <tr>
      <td style="vertical-align: middle">Vim Color Scheme:</td>
      <td><select name="colorscheme" style="font-size: 75%%">
        %s
      </select></td>
    </tr>
    <tr>
      <td style="float: right">Background:</td>
      <td>
          <input %s type="radio" name="bg" value="dark">Dark
          <input %s type="radio" name="bg" value="light">Light
          <input %s type="radio" name="bg" value="">Default
      </td>
    </tr>
    <tr>
      <td style="float: right">Line Numbers:</td>
      <td>
          <input %s type="radio" name="nu" value="on">On
          <input %s type="radio" name="nu" value="off">Off
      </td>
    </tr>
    <tr>
      <td></td>
      <td><input type="submit"
                 value="Refresh"
                 style="font-size: 75%%; width: 150px"></td>
    </tr>
  </table>
  <div>Powered by <a href="https://github.com/clark-duvall/CodeServe"
                     target="_blank"
                     style="font-weight: bold; color: inherit;">CodeServe</a>.
  </div>
</form>
'''

LIST_DIR_HTML = '''
<!DOCTYPE html>
<html>
<body>
  <h2>%s</h2>
  <ul>
    %s
  </ul>
</body>
</html>
'''

def _ReadFile(filename):
  with open(filename) as f:
    return f.read()

def _WriteFile(filename, contents):
  with open(filename, 'w') as f:
    return f.write(contents)

def _UrlExists(url, current=None):
  for include in INCLUDE:
    path = os.path.normpath(os.path.join(BASE_PATH, include, url))
    if os.path.exists(path):
      return (path, url)
  if current is not None:
    path = os.path.normpath(
        os.path.join(BASE_PATH, os.path.dirname(current), url))
    prefix = os.path.commonprefix([path, BASE_PATH])
    link_path = path.replace(prefix, '')
    if os.path.exists(path):
      return (path, link_path)
  return (None, None)

def _CheckPathReplace(match, opening, closing, path):
  url, link_path = _UrlExists(match.group(4), current=path)
  if link_path is not None:
    return ('<%s>#include </%s><%s>%s<a style="color: inherit" class="include" '
            'href="/%s">%s</a>%s' %
                (match.group(1), match.group(2), match.group(3),
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

def _InsertHtml(html, to_insert, before):
  parts = html.split(before)
  parts[0] = '%s%s' % (parts[0], before)
  parts.insert(1, to_insert)
  return ''.join(parts)

def _GetColorSchemeHtml(current):
  return ''.join('<option %s value="%s">%s</option>' %
      ('selected' if name[:-4] == current else '', name[:-4], name[:-4])
          for name in os.listdir(COLOR_DIR) if name.endswith('.vim'))

class _VimQueryArgs(object):
  _VALID_COMMANDS = ['colorscheme']
  _VALID_OPTIONS = ['bg']
  _VALID_TOGGLES = ['nu']
  def __init__(self, query):
    self._query = dict((k, v[0]) for k, v in query.iteritems())

  def GetVimArgs(self):
    # Separate commands and options so commands can be done before options.
    commands = []
    options = []
    for name, arg in self._query.iteritems():
      if name in self._VALID_COMMANDS:
        commands.append('+%s %s' % (name, arg))
      if name in self._VALID_OPTIONS:
        options.append('+set %s=%s' % (name, arg))
      if name in self._VALID_TOGGLES:
        options.append('+set %s%s' % (name, '' if arg == 'on' else '!'))
    return commands + options

  def GetColorPickerHtml(self):
    return (COLOR_PICKER_HTML %
        (_GetColorSchemeHtml(self._query.get('colorscheme', '')),
         'checked' if self._query.get('bg', '') == 'dark' else '',
         'checked' if self._query.get('bg', '') == 'light' else '',
         'checked' if self._query.get('bg', '') == '' else '',
         'checked' if self._query.get('nu', '') == 'on' else '',
         'checked' if self._query.get('nu', '') == 'off' else ''))

  def GetBackHtml(self, path):
    link = os.path.dirname(path)
    return BACK_HTML % ('%s/' % link if len(link) else '', self.QueryString())

  def QueryString(self):
    return ('?%s' % urllib.urlencode(self._query).strip('/')
        if len(self._query) else '')

  def __str__(self):
    return str(sorted(filter(lambda x: len(x[1]), self._query.iteritems())))


class _Cache(object):
  def __init__(self, no_cache):
    if no_cache:
      self._memcache = None
    else:
      self._memcache = memcache.Client(['127.0.0.1:11211'])

  def Get(self, key):
    if self._memcache is None:
      return None
    return self._memcache.get(key.replace(' ', ''))

  def Set(self, key, value):
    if self._memcache is not None:
      self._memcache.set(key.replace(' ', ''), value)

def _AddQueryToLinks(html, prefix, query):
  return re.sub(r'%shref="(.*?)"' % prefix,
                r'%shref="\1%s"' % (prefix, query),
                html)

class Handler(CGIHTTPServer.CGIHTTPRequestHandler):
  def _SendHtmlFile(self, path, url, query_args):
    cache_path = '%s%s' % (path, query_args)
    html = CACHE.Get(cache_path)
    if html is None:
      fd, name = tempfile.mkstemp()
      swap = os.path.join(os.path.dirname(path),
                          '.%s.swp' % os.path.basename(path))
      if os.path.exists(swap):
        os.remove(swap)
      vim = ['vim', path]
      vim.extend(['+%s' % arg for arg in VIM_ARGS])
      vim.extend(query_args.GetVimArgs())
      vim.extend(['+TOhtml','+w! %s' % name, '+qa!'])

      try:
        subprocess.check_call(vim)
      except subprocess.CalledProcessError as e:
        self.send_error(500, 'Vim error: %s' % e)
        return

      with os.fdopen(fd) as f:
        html = f.read()
      html = _InsertHtml(html, query_args.GetColorPickerHtml(), '<body>')
      html = _InsertHtml(html, query_args.GetBackHtml(url), '<body>')
      html = _ParseIncludes(html, path)
      os.remove(name)
      CACHE.Set(cache_path, html)

    self.send_response(200)
    self.send_header('Content-type', 'text/html')
    self.end_headers()
    self.wfile.write(_AddQueryToLinks(html,
                                      'class="include" ',
                                      query_args.QueryString()))

  def _ListDirectory(self, path, url):
    return LIST_DIR_HTML % (url,
        ''.join('<li><a href="/%s%s">%s</a></li>' %
            (os.path.join(url, name),
             '/' if os.path.isdir(os.path.join(path, name)) else '',
             name) for name in sorted(os.listdir(path))))

  def do_GET(self):
    parse_result = urlparse.urlparse(self.path)
    query_args = _VimQueryArgs(urlparse.parse_qs(parse_result.query))
    url = parse_result.path.strip('/')
    if not len(url):
      url = '.'
    path, _ = _UrlExists(url)
    if path is None:
      self.send_error(404, 'Path does not exist :(')
      return
    if os.path.isdir(path):
      if parse_result.path[-1:] != '/':
        self.send_response(301)
        self.send_header('Location', '%s/?%s' %
            (path, query_args.QueryString()))
        self.end_headers()
      else:
        listing = _AddQueryToLinks(
            self._ListDirectory(path, url), '', query_args.QueryString())
        listing = _InsertHtml(listing, query_args.GetBackHtml(url), '<body>')
        self.wfile.write(listing)
    else:
      self._SendHtmlFile(path, url, query_args)

class Server(SocketServer.TCPServer):
  allow_reuse_address = True

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('-i', '--include', nargs='+',
                      help='include paths to use when searching for code, '
                           'relative to the base path')
  parser.add_argument('-b', '--base-path', default=BASE_PATH,
                      help='the base path to serve code from')
  parser.add_argument('-p', '--port', default=8000, type=int,
                      help='the port to run the server on')
  parser.add_argument('-v', '--vim-args', nargs='+', default=[],
                      help='extra arguments to pass to vim')
  parser.add_argument('-c', '--color-dir', default=COLOR_DIR,
                      help='the directory to find vim color schemes')
  parser.add_argument('--no-cache', default=False, action='store_true',
                      help='prevent caching of the pages')
  args = parser.parse_args()
  if args.include:
    INCLUDE.extend(args.include)
  BASE_PATH = '%s/' % os.path.normpath(args.base_path)
  VIM_ARGS = args.vim_args
  CACHE = _Cache(args.no_cache)
  COLOR_DIR = args.color_dir
  print('Go to http://localhost:%d to view your source.' % args.port)

  Server(('', args.port), Handler).serve_forever()
