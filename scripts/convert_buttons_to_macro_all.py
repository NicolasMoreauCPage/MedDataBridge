#!/usr/bin/env python3
"""
Run the convert_buttons_to_macro replacement on all templates (Batch B).
This imports the logic from convert_buttons_to_macro.py to avoid duplication.
"""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
MOD = SCRIPTS / 'convert_buttons_to_macro.py'

spec = importlib.util.spec_from_file_location('convert_buttons', MOD)
mod = importlib.util.module_from_spec(spec)
sys.modules['convert_buttons'] = mod
spec.loader.exec_module(mod)

def main():
    # temporarily override PRIORITY_KEYWORDS to include everything
    mod.PRIORITY_KEYWORDS = []
    mod.main()

if __name__ == '__main__':
    main()
