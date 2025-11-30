#!/usr/bin/env python3
"""Script minimal pour remplacer certains marqueurs de commentaires en anglais
par des équivalents français dans les fichiers .py du dépôt.

Usage: python scripts/translate_comments.py

Ce script cible uniquement les commentaires en ligne débutant par "#" et
ne modifie pas les docstrings (triple-quoted) de façon sophistiquée.
Il effectue des remplacements simples pour des marqueurs courants afin d'homogénéiser
la langue des commentaires.
"""
from pathlib import Path
import re

REPLACEMENTS = [
    (re.compile(r"\bNOTE:\b", re.I), "REMARQUE:"),
    (re.compile(r"\bNOTE\b", re.I), "REMARQUE"),
    (re.compile(r"\bNote:\b"), "Remarque :"),
    (re.compile(r"\bNote\b"), "Remarque"),
    (re.compile(r"\bTODO:\b", re.I), "À FAIRE :"),
    (re.compile(r"\bTODO\b", re.I), "À FAIRE"),
    (re.compile(r"\bFIXME\b", re.I), "À CORRIGER"),
    (re.compile(r"\bExample(s)?\b", re.I), "Exemple"),
    (re.compile(r"\bReturns?:\b", re.I), "Renvoie :"),
    (re.compile(r"\bReturns?\b", re.I), "Renvoie"),
    (re.compile(r"\bParameters?:\b", re.I), "Paramètres :"),
    (re.compile(r"\bArgs?:\b", re.I), "Paramètres :"),
    (re.compile(r"\bDeprecated\b", re.I), "Obsolète"),
    (re.compile(r"\bFallback\b", re.I), "Solution de repli"),
    (re.compile(r"\bStep(s)?\b", re.I), "Étape"),
    (re.compile(r"Usage Examples", re.I), "Exemples d'utilisation"),
    (re.compile(r"See also", re.I), "Voir aussi"),
    (re.compile(r"Raises", re.I), "Lève"),
]


def is_hash_in_string(line: str, hash_pos: int) -> bool:
    """Détecte si le caractère # à hash_pos se trouve à l'intérieur d'une chaîne
    simple sur la même ligne (approche heuristique basée sur le nombre de guillemets
    avant la position).
    """
    before = line[:hash_pos]
    single = before.count("'") - before.count("\\'")
    double = before.count('"') - before.count('\\"')
    return (single % 2 == 1) or (double % 2 == 1)


def translate_file(path: Path) -> int:
    text = path.read_text(encoding='utf-8')
    changed = 0
    out_lines = []
    for line in text.splitlines(keepends=False):
        if '#' in line:
            hash_pos = line.find('#')
            if not is_hash_in_string(line, hash_pos):
                comment = line[hash_pos:]
                new_comment = comment
                for pattern, repl in REPLACEMENTS:
                    new_comment = pattern.sub(repl, new_comment)
                if new_comment != comment:
                    line = line[:hash_pos] + new_comment
                    changed += 1
        out_lines.append(line)

    if changed:
        path.write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
    return changed


def main():
    root = Path(__file__).resolve().parents[1]
    py_files = list(root.rglob('*.py'))
    total_changes = 0
    modified_files = []
    for p in py_files:
        # skip virtualenv and .git
        if any(part.startswith('.venv') or part.startswith('.git') for part in p.parts):
            continue
        changes = translate_file(p)
        if changes:
            modified_files.append((p.relative_to(root), changes))
            total_changes += changes

    print(f"Fichiers modifiés: {len(modified_files)}, remplacements: {total_changes}")
    for f, c in modified_files:
        print(f" - {f}: {c} changements")


if __name__ == '__main__':
    main()
