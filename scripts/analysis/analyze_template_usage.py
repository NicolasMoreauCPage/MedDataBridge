#!/usr/bin/env python3
"""
Script d'analyse des templates pour identifier l'utilisation des champs d'adresse.
Prépare la migration des templates vers les propriétés inherited_address_*.
"""

import os
import re
from pathlib import Path

def find_template_files():
    """Trouve tous les fichiers de templates dans le projet"""
    template_dirs = [
        "app/templates",
        "templates"
    ]

    template_files = []
    for template_dir in template_dirs:
        if os.path.exists(template_dir):
            for root, dirs, files in os.walk(template_dir):
                for file in files:
                    if file.endswith(('.html', '.jinja', '.jinja2')):
                        template_files.append(os.path.join(root, file))

    return template_files

def analyze_address_usage_in_templates():
    """Analyse l'utilisation des champs d'adresse dans les templates"""

    template_files = find_template_files()
    print(f"🔍 Analyse de {len(template_files)} fichiers de templates")
    print("=" * 60)

    # Patterns pour les champs d'adresse
    address_patterns = {
        'address_line1': re.compile(r'\baddress_line1\b'),
        'address_line2': re.compile(r'\baddress_line2\b'),
        'address_line3': re.compile(r'\baddress_line3\b'),
        'address_city': re.compile(r'\baddress_city\b'),
        'address_postalcode': re.compile(r'\baddress_postalcode\b'),
        'address_country': re.compile(r'\baddress_country\b'),
    }

    usage_report = {}

    for template_file in template_files:
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            file_usage = {}
            for field, pattern in address_patterns.items():
                matches = pattern.findall(content)
                if matches:
                    file_usage[field] = len(matches)

            if file_usage:
                relative_path = os.path.relpath(template_file)
                usage_report[relative_path] = file_usage

        except Exception as e:
            print(f"⚠️ Erreur lors de la lecture de {template_file}: {e}")

    return usage_report

def generate_migration_plan(usage_report):
    """Génère un plan de migration pour les templates"""

    print("\n📋 PLAN DE MIGRATION DES TEMPLATES")
    print("=" * 60)

    if not usage_report:
        print("✅ Aucun template n'utilise les champs d'adresse - migration non nécessaire")
        return

    total_files = len(usage_report)
    total_usages = sum(sum(fields.values()) for fields in usage_report.values())

    print(f"📊 {total_files} fichiers de templates utilisent des champs d'adresse")
    print(f"📊 {total_usages} utilisations totales de champs d'adresse")
    print()

    # Grouper par type de modèle
    model_patterns = {
        'EntiteGeographique': ['ej_detail.html', 'eg_detail.html', 'eg_form.html'],
        'Pole': ['pole_detail.html', 'pole_form.html'],
        'Service': ['service_detail.html', 'service_form.html'],
        'UniteFonctionnelle': ['uf_detail.html', 'uf_form.html'],
        'UniteHebergement': ['uh_detail.html', 'uh_form.html'],
        'Chambre': ['chambre_detail.html', 'chambre_form.html'],
        'Lit': ['lit_detail.html', 'lit_form.html']
    }

    migration_tasks = []

    for template_path, fields in usage_report.items():
        template_name = os.path.basename(template_path)

        # Déterminer le modèle principal pour ce template
        primary_model = None
        for model, patterns in model_patterns.items():
            if any(pattern in template_name for pattern in patterns):
                primary_model = model
                break

        if not primary_model:
            primary_model = "Inconnu"

        print(f"📄 {template_path} ({primary_model}):")
        for field, count in fields.items():
            new_field = f"inherited_{field}"
            print(f"   • {field} ({count} fois) → {new_field}")
            migration_tasks.append({
                'template': template_path,
                'model': primary_model,
                'old_field': field,
                'new_field': new_field,
                'count': count
            })
        print()

    return migration_tasks

def generate_migration_script(migration_tasks):
    """Génère un script de migration automatique"""

    if not migration_tasks:
        return

    script_content = '''#!/usr/bin/env python3
"""
Script de migration automatique des templates.
Remplace les champs address_* par inherited_address_*.
"""

import os
import re

def migrate_template(template_path, migrations):
    """Migre un template spécifique"""

    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    for migration in migrations:
        old_pattern = migration['old_field']
        new_pattern = migration['new_field']

        # Remplacer les occurrences
        content = re.sub(rf'\\b{re.escape(old_pattern)}\\b', new_pattern, content)

    if content != original_content:
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

    print(f"\\n🎉 Migration terminée: {migrated_count} templates migrés")

if __name__ == "__main__":
    main()
'''

    # Ajouter les tâches de migration
    tasks_str = "MIGRATION_TASKS = [\n"
    for task in migration_tasks:
        tasks_str += f"""    {{
        'template': '{task['template']}',
        'model': '{task['model']}',
        'old_field': '{task['old_field']}',
        'new_field': '{task['new_field']}',
        'count': {task['count']}
    }},\n"""
    tasks_str += "]"

    script_content = script_content.replace("MIGRATION_TASKS = []", tasks_str)

    with open('migrate_templates.py', 'w', encoding='utf-8') as f:
        f.write(script_content)

    print("📝 Script de migration généré: migrate_templates.py")

def main():
    """Fonction principale"""

    print("🔍 ANALYSE DES TEMPLATES - Utilisation des champs d'adresse")
    print("=" * 60)

    usage_report = analyze_address_usage_in_templates()

    if not usage_report:
        print("✅ Aucun template n'utilise les champs d'adresse dupliqués.")
        print("🎉 La migration des templates n'est pas nécessaire !")
        return

    migration_tasks = generate_migration_plan(usage_report)
    generate_migration_script(migration_tasks)

    print("\\n📋 RÉSUMÉ:")
    print(f"• {len(usage_report)} templates à migrer")
    print(f"• {sum(sum(fields.values()) for fields in usage_report.values())} remplacements à effectuer")
    print("\\n🚀 Pour migrer automatiquement: python migrate_templates.py")

if __name__ == "__main__":
    main()