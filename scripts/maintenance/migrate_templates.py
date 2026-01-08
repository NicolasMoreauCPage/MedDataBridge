#!/usr/bin/env python3
"""
Script de migration automatique des templates.
Remplace les champs address_* par inherited_address_*.
"""

import os
import re

MIGRATION_TASKS = [
    {
        'template': 'app/templates/eg_detail.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_line1',
        'new_field': 'inherited_address_line1',
        'count': 2
    },
    {
        'template': 'app/templates/eg_detail.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_line2',
        'new_field': 'inherited_address_line2',
        'count': 2
    },
    {
        'template': 'app/templates/eg_detail.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_line3',
        'new_field': 'inherited_address_line3',
        'count': 2
    },
    {
        'template': 'app/templates/eg_detail.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_city',
        'new_field': 'inherited_address_city',
        'count': 1
    },
    {
        'template': 'app/templates/eg_detail.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_postalcode',
        'new_field': 'inherited_address_postalcode',
        'count': 1
    },
    {
        'template': 'app/templates/eg_detail.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_country',
        'new_field': 'inherited_address_country',
        'count': 2
    },
    {
        'template': 'app/templates/contact_form.html',
        'model': 'Inconnu',
        'old_field': 'address_line1',
        'new_field': 'inherited_address_line1',
        'count': 4
    },
    {
        'template': 'app/templates/contact_form.html',
        'model': 'Inconnu',
        'old_field': 'address_line2',
        'new_field': 'inherited_address_line2',
        'count': 4
    },
    {
        'template': 'app/templates/contact_form.html',
        'model': 'Inconnu',
        'old_field': 'address_city',
        'new_field': 'inherited_address_city',
        'count': 4
    },
    {
        'template': 'app/templates/contact_form.html',
        'model': 'Inconnu',
        'old_field': 'address_postalcode',
        'new_field': 'inherited_address_postalcode',
        'count': 4
    },
    {
        'template': 'app/templates/contact_form.html',
        'model': 'Inconnu',
        'old_field': 'address_country',
        'new_field': 'inherited_address_country',
        'count': 4
    },
    {
        'template': 'app/templates/eg_form.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_line1',
        'new_field': 'inherited_address_line1',
        'count': 2
    },
    {
        'template': 'app/templates/eg_form.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_line2',
        'new_field': 'inherited_address_line2',
        'count': 2
    },
    {
        'template': 'app/templates/eg_form.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_line3',
        'new_field': 'inherited_address_line3',
        'count': 2
    },
    {
        'template': 'app/templates/eg_form.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_city',
        'new_field': 'inherited_address_city',
        'count': 2
    },
    {
        'template': 'app/templates/eg_form.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_postalcode',
        'new_field': 'inherited_address_postalcode',
        'count': 2
    },
    {
        'template': 'app/templates/eg_form.html',
        'model': 'EntiteGeographique',
        'old_field': 'address_country',
        'new_field': 'inherited_address_country',
        'count': 3
    },
]

def migrate_template(template_path, migrations):
    """Migre un template spécifique"""

    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    changes_made = False

    for migration in migrations:
        old_pattern = migration['old_field']
        new_pattern = migration['new_field']

        # Patterns plus spécifiques pour Jinja2: geo.address_line1, entite.address_city, etc.
        patterns = [
            rf'(\w+)\.({re.escape(old_pattern)})',  # obj.address_line1
            rf'({re.escape(old_pattern)})',         # address_line1 seul (fallback)
        ]

        for pattern in patterns:
            # Remplacer les occurrences
            new_content = re.sub(pattern, lambda m: m.group(1) + '.' + new_pattern if len(m.groups()) > 1 else new_pattern, content)
            if new_content != content:
                content = new_content
                changes_made = True
                print(f"  • Remplacé {old_pattern} → {new_pattern}")

    if changes_made and content != original_content:
        # Créer une sauvegarde
        backup_path = template_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)

        # Écrire le nouveau contenu
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Migré: {template_path} (sauvegarde: {backup_path})")
        return True

    return False

def main():
    """Migration principale"""

    print("🚀 MIGRATION DES TEMPLATES")
    print("=" * 40)

    # Grouper les migrations par template
    template_migrations = {}
    for task in MIGRATION_TASKS:
        template = task['template']
        if template not in template_migrations:
            template_migrations[template] = []
        template_migrations[template].append({
            'old_field': task['old_field'],
            'new_field': task['new_field']
        })

    migrated_count = 0
    for template_path, migrations in template_migrations.items():
        if os.path.exists(template_path):
            if migrate_template(template_path, migrations):
                migrated_count += 1
        else:
            print(f"⚠️ Template non trouvé: {template_path}")

    print(f"\n🎉 Migration terminée: {migrated_count} templates migrés")

    if migrated_count > 0:
        print("\n📋 PROCHAINES ÉTAPES:")
        print("1. Tester que les templates fonctionnent correctement")
        print("2. Supprimer les sauvegardes .backup si tout est OK")
        print("3. Procéder à la suppression des champs dupliqués")

if __name__ == "__main__":
    main()
