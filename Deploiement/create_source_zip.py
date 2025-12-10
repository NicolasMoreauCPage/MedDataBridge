#!/usr/bin/env python3
"""Create a zip archive of the repository sources for deployment.

Usage:
  python Deploiement/create_source_zip.py --output meddata-source-YYYYMMDD-HHMMSS.zip

Behavior:
- Walks the repository root and adds files to the zip excluding common
  development artefacts and large deployment bundles.
- Excludes: .git, .venv, venv, __pycache__, *.pyc, Deploiement/dependencies-*, node_modules
"""
import argparse
import os
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))

DEFAULT_EXCLUDES = [
    '.git',
    '.venv',
    'venv',
    '__pycache__',
    'node_modules',
    'dist',
    'build',
]

EXCLUDE_PATTERNS = [
    '.pyc',
    '.pyo',
    '.log',
]


def should_exclude(path, root):
    # Normalize
    rel = os.path.relpath(path, root)
    parts = rel.split(os.sep)
    for ex in DEFAULT_EXCLUDES:
        if parts and parts[0] == ex:
            return True
    # exclude Deploiement dependency bundles
    if rel.startswith('Deploiement' + os.sep) and 'dependencies' in rel:
        return True
    for pat in EXCLUDE_PATTERNS:
        if path.endswith(pat):
            return True
    return False


def collect_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # filter out directories in-place to avoid walking them
        dirnames[:] = [d for d in dirnames if not should_exclude(os.path.join(dirpath, d), root)]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if should_exclude(full, root):
                continue
            files.append(full)
    return files


def make_zip(output_path, root):
    files = collect_files(root)
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = os.path.relpath(f, root)
            zf.write(f, arcname)
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', '-o', help='Output zip path', default=None)
    args = parser.parse_args()
    now = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    default_name = f'meddatabridge-source-{now}.zip'
    out = args.output or os.path.join(os.getcwd(), default_name)
    print(f'Creating source zip: {out}')
    make_zip(out, ROOT)
    print('Done.')


if __name__ == '__main__':
    main()
