#!/usr/bin/env python3
"""Static-site exporter for the EPL landing page.

`epl serve` registers routes as absolute paths (/, /terms, /privacy, /refund).
Those absolute hrefs only resolve under a live server or a host that does folder
routing -- they break when the HTML is opened as a local file (file:///C:/terms)
and on plain static hosts.

This script renders each route exactly as `epl serve` emits it, then rewrites the
internal absolute links to relative .html links. The result works identically
when double-clicked locally AND when deployed to GitHub Pages / Netlify / Azure
Static / Cloudflare Pages -- no server config required.

Usage:
    python landing_page/build_static.py            # -> landing_page/dist/
    python landing_page/build_static.py --out site # custom output dir
"""

import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SOURCE = os.path.join(HERE, 'src', 'main.epl')

# route path -> output filename
ROUTES = {
    '/': 'index.html',
    '/terms': 'terms.html',
    '/privacy': 'privacy.html',
    '/refund': 'refund.html',
}

# absolute-link -> relative-link rewrites (order matters: longest first)
LINK_MAP = [
    ('href="/terms"', 'href="terms.html"'),
    ('href="/privacy"', 'href="privacy.html"'),
    ('href="/refund"', 'href="refund.html"'),
    ('href="/#install"', 'href="index.html#install"'),
    ('href="/"', 'href="index.html"'),
]
# also handle the same paths when they carry a #fragment, e.g. /terms#scope
FRAG_MAP = {
    '/terms': 'terms.html',
    '/privacy': 'privacy.html',
    '/refund': 'refund.html',
    '/': 'index.html',
}


def _free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def rewrite_links(html: str) -> str:
    for src, dst in LINK_MAP:
        html = html.replace(src, dst)

    # href="/terms#anchor" -> href="terms.html#anchor"
    def _frag(m):
        path, frag = m.group(1), m.group(2)
        target = FRAG_MAP.get(path)
        if target is None:
            return m.group(0)
        return f'href="{target}#{frag}"'

    html = re.sub(r'href="(/[a-z]*)#([^"]+)"', _frag, html)
    return html


def main():
    out_dir = os.path.join(HERE, 'dist')
    if '--out' in sys.argv:
        out_dir = os.path.abspath(sys.argv[sys.argv.index('--out') + 1])
    os.makedirs(out_dir, exist_ok=True)

    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, 'main.py', 'serve', SOURCE, '--port', str(port)],
        cwd=REPO,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # wait for the server to come up
        base = f'http://127.0.0.1:{port}'
        up = False
        for _ in range(40):
            try:
                urllib.request.urlopen(base + '/', timeout=1).read()
                up = True
                break
            except Exception:
                time.sleep(0.5)
        if not up:
            print('Error: server did not start', file=sys.stderr)
            return 1

        written = []
        for route, fname in ROUTES.items():
            html = urllib.request.urlopen(base + route, timeout=10).read().decode('utf-8')
            html = rewrite_links(html)
            path = os.path.join(out_dir, fname)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(html)
            written.append((fname, len(html)))

        print(f'Static site exported to: {out_dir}')
        for fname, size in written:
            print(f'  {fname:14} {size:>7,} bytes')
        print('\nOpen dist/index.html directly, or deploy the dist/ folder to any static host.')
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == '__main__':
    raise SystemExit(main())
