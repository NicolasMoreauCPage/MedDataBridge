# Scripts Directory

Ce répertoire contient tous les scripts utilitaires du projet IntegraSanté, organisés par fonction.

## 📁 Structure

```text
scripts/
├── analyze/          # Scripts d'analyse et diagnostic
├── debug/            # Scripts de debug et développement
├── deployment/       # Scripts de déploiement et infrastructure
├── export/           # Scripts d'export de données
├── generate/         # Scripts de génération automatique
├── import/           # Scripts d'import de données
├── manual/           # Scripts de test et validation manuels
├── setup/            # Scripts de configuration et initialisation
├── tools/            # Outils de développement et maintenance
├── utils/            # Scripts utilitaires divers
└── validation/       # Scripts de validation automatisée
```

## 📋 Description des scripts

### 🔍 analyze/

- `analyze_errors_phase4.py` : Analyse des erreurs de la phase 4
- `analyze_roundtrip_errors.py` : Analyse des erreurs de roundtrip

### 🐛 debug/

- `debug_mfn_generate.py` : Génération de messages MFN pour debug

### 🚀 deployment/

- `deploy.sh` : Script de déploiement principal
- `remote_deploy.sh` : Déploiement sur serveur distant

### 📤 export/

- `export_ihe_pam_direct.py` : Export direct des scénarios IHE PAM
- `export_ihe_pam_scenarios.py` : Export des scénarios IHE PAM
- `export_ihe_pam_simple.py` : Export simplifié IHE PAM
- `export_ihe_pam_via_api.py` : Export IHE PAM via API

### ⚙️ generate/

- `generate_crud_tests.py` : Génération de tests CRUD
- `generate_test_docs.py` : Génération de documentation de tests
- `generate_ui_tests_from_templates.py` : Génération de tests UI depuis templates

### 📥 import/

- `import_hl7_scenarios.py` : Import des scénarios HL7
- `import_hprim_scenarios.py` : Import des scénarios HPRIM
- `import_java_integration_scenarios.py` : Import des scénarios d'intégration Java
- `import_legacy_scenarios.py` : Import des scénarios legacy
- `import_medecins_from_pam_archive.py` : Import des médecins depuis archive PAM
- `import_mfn_test_ght.py` : Import des tests MFN GHT
- `import_pam_archive.py` : Import d'archive PAM
- `import_pam_archive_complet.py` : Import complet d'archive PAM
- `import_pam_archive_local.py` : Import local d'archive PAM
- `import_pam_archive_tests.py` : Tests d'import d'archive PAM
- `import_pam_chronological.py` : Import chronologique PAM

### 🧪 manual/

Scripts de test et validation manuels (25+ scripts pour tests ponctuels, debug, validation manuelle)

### 🔧 setup/

- `setup_file_endpoints.py` : Configuration des endpoints de fichiers
- `seed_data.py` : Seed des données de test

### 🛠️ tools/

Outils de développement et maintenance avancés (50+ scripts pour migrations, benchmarks, debugging avancé, administration système)

### 🛠️ utils/

- `clean_old_namespace_vocab.py` : Nettoyage des anciens vocabulaires
- `hl7_import_validator.py` : Validateur d'import HL7
- `HPRIM_XML_STARTER_CODE.py` : Code de démarrage HPRIM XML
- `mfn_roundtrip.py` : Test roundtrip MFN
- `monitor_flaky_tests.py` : Monitoring des tests instables
- `replay_pam_examples.py` : Rejeu des exemples PAM
- `sample_generate_pam.py` : Génération d'échantillons PAM
- `translate_comments.py` : Traduction des commentaires

### ✅ validation/

- `check_ej_vbf.py` : Vérification EJ/VBF
- `check_last_messages.py` : Vérification des derniers messages
- `check_pam_examples.py` : Vérification des exemples PAM
- `validate_ei.py` : Validation EI
- `validate_pam.py` : Validation PAM
- `validate_pam_examples.py` : Validation des exemples PAM

## 🚀 Utilisation

Tous les scripts sont exécutables depuis la racine du projet :

```bash
# Exemple d'import
python3 scripts/import/import_hl7_scenarios.py

# Exemple d'export
python3 scripts/export/export_ihe_pam_scenarios.py

# Exemple de validation
python3 scripts/validation/validate_pam.py

# Exemple de déploiement
./scripts/deployment/deploy.sh
```

## 📝 Notes

- Les scripts dans `manual/` sont principalement utilisés pour les tests manuels et le debug
- Les scripts dans `validation/` sont utilisés pour la validation automatisée
- Les scripts dans `deployment/` nécessitent souvent des droits d'administration
- Tous les scripts sont idempotents quand possible

## 🤝 Contribution

Pour ajouter un nouveau script :

1. Choisir la catégorie appropriée
2. Ajouter une description dans ce README
3. Documenter l'usage dans le script lui-même
