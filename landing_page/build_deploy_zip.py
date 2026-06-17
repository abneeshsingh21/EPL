#!/usr/bin/env python3
"""Build the curated Azure deploy zip for the EPL playground.

Bundles only the pure-Python `epl/` package (no caches, no binaries) plus
requirements.txt, keeping the upload small (~1 MB) rather than the whole repo.
"""
import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(os.environ.get('TEMP', '/tmp'), 'epl_playground_deploy.zip')


def main():
    count = 0
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'epl')):
            if '__pycache__' in dirpath:
                continue
            for f in files:
                if f.endswith('.pyc'):
                    continue
                full = os.path.join(dirpath, f)
                z.write(full, os.path.relpath(full, ROOT))
                count += 1
        req = os.path.join(ROOT, 'requirements.txt')
        if os.path.exists(req):
            z.write(req, 'requirements.txt')
            count += 1
    print('zip:', OUT)
    print('files: %d  size: %.1f MB' % (count, os.path.getsize(OUT) / 1e6))


if __name__ == '__main__':
    main()
