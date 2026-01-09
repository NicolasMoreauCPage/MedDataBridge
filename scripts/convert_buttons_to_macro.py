#!/usr/bin/env python3
"""
Convert simple button/anchor patterns to the components.button macro in templates.

This handles simple cases like:
  <a class="btn btn-primary" href="/path">Label</a>
  <button class="btn btn-primary" type="submit">Label</button>

It will not attempt to convert complex Jinja2 expressions, icons, or i18n wrappers.

Backups are created with suffix `.bak`.
Generates a report `scripts/convert_buttons_report.txt` listing changed files and ambiguous matches.
"""
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
PRIORITY_KEYWORDS = ['list', 'form', 'patient', 'dossier', 'cotation']

LINK_BTN_RE = re.compile(r'<a\s+([^>]*class="[^"]*btn[^"]*"[^>]*)>([^<]+)</a>')
BUTTON_BTN_RE = re.compile(r'<button\s+([^>]*)>([^<]+)</button>')

def is_simple_text(s):
    # avoid Jinja expressions inside label
    return '{{' not in s and '{%' not in s

def replace_in_text(text, report_lines, path):
    changed = False

    def repl_link(m):
        nonlocal changed
        attrs = m.group(1)
        label = m.group(2).strip()
        if not is_simple_text(label):
            report_lines.append(f'AMBIG: {path} link label dynamic: {label}')
            return m.group(0)
        # try to capture href
        href_m = re.search(r'href="([^"]+)"', attrs)
        if not href_m:
            report_lines.append(f'AMBIG: {path} link no href: {m.group(0)[:80]}')
            return m.group(0)
        href = href_m.group(1)
        # Use json.dumps to safely quote label and href (produces double-quoted strings)
        label_q = json.dumps(label)
        href_q = json.dumps(href)
        changed_local = '{{ button(' + label_q + ', href=' + href_q + ') }}'
        changed = True
        return changed_local

    text = LINK_BTN_RE.sub(repl_link, text)

    def repl_button(m):
        attrs = m.group(1)
        label = m.group(2).strip()
        if not is_simple_text(label):
            report_lines.append(f'AMBIG: {path} button label dynamic: {label}')
            return m.group(0)
        # look for type=submit -> convert to macro with type
        type_m = re.search(r'type="([^"]+)"', attrs)
        type_attr = type_m.group(1) if type_m else None
        if type_attr == 'submit':
            nonlocal changed
            label_q = json.dumps(label)
            changed_local = "{{ button(" + label_q + ", type='submit') }}"
            # Note: using single quotes for type argument to match macro signature
            changed = True
            return changed_local
        # otherwise ambiguous
        report_lines.append(f'AMBIG: {path} button unknown attrs: {attrs[:80]}')
        return m.group(0)

    text = BUTTON_BTN_RE.sub(repl_button, text)
    return text, changed


def main():
    files = [p for p in TEMPLATES.rglob('*.html') if any(k in p.name for k in PRIORITY_KEYWORDS) or any(k in str(p) for k in PRIORITY_KEYWORDS)]
    report_lines = []
    changed_files = []
    for f in files:
        text = f.read_text(encoding='utf-8')
        new_text, changed = replace_in_text(text, report_lines, f)
        if changed:
            bak = f.with_suffix(f.suffix + '.bak')
            bak.write_text(text, encoding='utf-8')
            f.write_text(new_text, encoding='utf-8')
            changed_files.append(str(f))
            print(f'Converted buttons in {f}')

    out = ROOT / 'scripts' / 'convert_buttons_report.txt'
    with out.open('w', encoding='utf-8') as fh:
        fh.write('Changed files:\n')
        fh.write('\n'.join(changed_files))
        fh.write('\n\nAmbiguous cases:\n')
        fh.write('\n'.join(report_lines))

    print('Done. Report at', out)


if __name__ == '__main__':
    main()
