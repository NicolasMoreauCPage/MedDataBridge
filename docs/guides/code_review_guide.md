# Guide de Revue de Code - Réorganisation du Projet

## 🎯 Objectif

Ce guide aide l'équipe à effectuer une revue de code de la nouvelle structure du projet MedData Bridge après la réorganisation complète.

## 📋 Points de vérification

### ✅ Structure des répertoires

- [ ] `data/` contient toutes les données organisées :
  - `archives/` : Archives générales
  - `pam/` : Données PAM (HL7, exports, tests)
  - `tmp/` : Données temporaires
  - `hprim_xml_roundtrip/` : Tests XML HPRIM
  - `one_shot_legacy/` : Code legacy

- [ ] `deployment/` contient les ressources de déploiement :
  - `general/` : Déploiement standard
  - `postgresql/` : Déploiement PostgreSQL
  - `packages/` : Packages hors-ligne

- [ ] `docs/` contient toute la documentation unifiée

- [ ] `scripts/` contient les scripts organisés avec le nouveau sous-répertoire `tools/`

- [ ] `tests/` contient tous les tests unifiés

### ✅ Fonctionnalité

- [ ] Application se lance correctement : `python -c "import app"`
- [ ] CLI fonctionne : `python cli.py --help`
- [ ] Tests passent : `pytest` (>1000 tests)
- [ ] Imports relatifs fonctionnent dans tous les modules

### ✅ CI/CD

- [ ] Workflows GitHub Actions utilisent les bons chemins (`tests/`, `scripts/`)
- [ ] Pas de références aux anciens répertoires (`Deploiement/`, `Doc/`, etc.)
- [ ] Tests automatisés passent en CI

### ✅ Documentation

- [ ] README.md dans chaque répertoire principal
- [ ] Liens vers documentation mis à jour (pas de références à `/docs/`, `/docs/docs/program_docs/`)
- [ ] Scripts documentés dans `scripts/README.md`

## 🔧 Actions correctives

### Si des chemins sont cassés

```bash
# Vérifier les imports
python -c "import app; print('OK')"
python -c "import sys; sys.path.append('.'); import scripts.import.import_hl7_scenarios"

# Vérifier les tests
pytest tests/unit/test_basic.py -v
```

### Si des références aux anciens chemins

```bash
# Chercher les références obsolètes
grep -r "Deploiement\|Doc\|docs/docs/program_docs" --exclude-dir=.git .
```

### Si des scripts ne se lancent pas

```bash
# Vérifier les chemins dans les scripts
head -20 scripts/import/import_hl7_scenarios.py
```

## 📝 Checklist finale

- [ ] Revue de code terminée par au moins 2 développeurs
- [ ] Tests passent en local et en CI
- [ ] Documentation accessible et à jour
- [ ] Équipe formée sur la nouvelle structure
- [ ] Procédures de déploiement testées

## 🚀 Prochaines étapes

1. **Archivage legacy** : Utiliser `scripts/utils/archive_legacy_data.sh`
2. **Nettoyage périodique** : Programmer l'archivage automatique
3. **Formation équipe** : Session de présentation de la nouvelle structure
4. **Mise à jour outils** : IDE, scripts personnels, bookmarks

## 📞 Support

En cas de problème avec la nouvelle structure :

1. Vérifier ce guide
2. Consulter les README.md des répertoires
3. Demander de l'aide à l'équipe
