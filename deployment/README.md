# Déploiement IntegraSanté

Ce répertoire contient tous les fichiers et scripts nécessaires au déploiement du projet.

## Structure

### `general/`

Scripts et documentation de déploiement généraux :

- Guides d'installation (NGINX, OpenSSL, Python)
- Scripts de déploiement
- Checklists de déploiement
- Configuration Alembic

### `postgresql/`

Déploiement spécifique PostgreSQL :

- Scripts adaptés pour PostgreSQL
- Configuration spécifique
- Checklists PostgreSQL

### `packages/`

Packages Python hors-ligne pour déploiement :

- `packages/` : Packages standards
- `packages-prod/` : Packages de production
- `packages-server/` : Packages serveur
- `pip_pkgs/` : Cache pip

## Utilisation

### Déploiement standard

```bash
cd deployment/general
# Suivre INSTALLATION_RAPIDE.md
```

### Déploiement PostgreSQL

```bash
cd deployment/postgresql
# Suivre CHECKLIST.md
```

### Installation hors-ligne

```bash
pip install --no-index --find-links=deployment/packages/packages-prod -r requirements-production.txt
```
