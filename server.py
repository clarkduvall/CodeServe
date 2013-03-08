#!/usr/bin/python

import os
import re
import SimpleHTTPServer
import SocketServer
import subprocess
import sys

def _ReadFile(filename):
  with open(filename) as f:
    return f.read()

def _ParseIncludes(html):
  return re.sub(r'#include "(.*)"', '#include "<a href="\1">\1</a>', html)

def _CreateHtmlFile(path, html_path):
  contents = _ReadFile(path)
  swap = '.%s.swp' % path
  if os.path.exists(swap):
    os.remove(swap)
  subprocess.call('vim %s "+TOhtml" "+w %s" "+qa!"' % (path, html_path),
                  shell=True)
  html = (_ReadFile(html_path).replace('background-color: #ffffff',
                                       'background-color: #000')
                              .replace('color: #000000',
                                       'color: #fff'))
  return _ParseIncludes(html)

class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
  def do_GET(self):
    path = self.path.strip('/')
    if os.path.exists(path):
      html_path = '%s.html' % path
      if os.path.exists(html_path):
        os.remove(html_path)
      self.wfile.write(_CreateHtmlFile(path, html_path))

class Server(SocketServer.TCPServer):
  allow_reuse_address = True

if __name__ == '__main__':
  print 'Go to http://localhost:8000 to view your source.'

  Server(("", 8000), Handler).serve_forever()
