#!/usr/bin/env python3
"""Script pour ajouter entite_juridique_id=ej_id aux créations de Mouvement."""
import re

file_path = "app/services/pam.py"

with open(file_path, "r") as f:
    content = f.read()

# Pattern pour trouver les créations de Mouvement sans entite_juridique_id
# Cherche "Mouvement(" suivi de paramètres, se terminant par ")"
# et n'ayant pas déjà "entite_juridique_id"

lines = content.split('\n')
modified = False
in_mouvement_block = False
mouvement_start_line = -1
indent_level = ""

new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    
    # Détecter le début d'un bloc Mouvement
    if re.search(r'(cancel_)?mouvement = Mouvement\(', line):
        in_mouvement_block = True
        mouvement_start_line = i
        indent_level = re.match(r'^(\s*)', line).group(1)
        new_lines.append(line)
        i += 1
        continue
    
    # Si on est dans un bloc Mouvement
    if in_mouvement_block:
        # Détecter la fin du bloc (ligne avec juste ")" avec l'indentation correcte)
        if re.match(rf'^{indent_level}\s*\)$', line):
            # Vérifier si entite_juridique_id a déjà été ajouté
            block_content = '\n'.join(lines[mouvement_start_line:i+1])
            if 'entite_juridique_id' not in block_content:
                # Ajouter entite_juridique_id=ej_id avant le )
                new_lines.append(f"{indent_level}    entite_juridique_id=ej_id,")
                modified = True
                print(f"Added entite_juridique_id at line {i+1} (mouvement started at line {mouvement_start_line+1})")
            new_lines.append(line)
            in_mouvement_block = False
            mouvement_start_line = -1
            i += 1
            continue
        else:
            new_lines.append(line)
            i += 1
            continue
    
    new_lines.append(line)
    i += 1

if modified:
    with open(file_path, "w") as f:
        f.write('\n'.join(new_lines))
    print(f"\n✅ Modified {file_path}")
else:
    print("✅ All Mouvement creations already have entite_juridique_id")
