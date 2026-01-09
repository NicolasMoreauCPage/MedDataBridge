# Déploiement vers qualifinterop.cpage.cloud

Ce document décrit comment déployer l'application depuis votre poste de travail `cici` vers le serveur `cpage@qualifinterop.cpage.cloud`.

Pré-requis
- Sur la machine locale: Python + script `create_deployment_zip.py` (présent dans le repo), OpenSSH (`scp`/`ssh`) ou PuTTY (`pscp`/`plink`).
- Sur le serveur: `unzip`, `systemd` et un service `meddata-bridge.service` configuré pour démarrer l'application.

Fichiers ajoutés
- `scripts/deploy_to_qualifinterop.ps1` : script PowerShell d'automatisation.
- `scripts/remote_deploy.sh` : script exécuté côté serveur (décompression et restart).

Flux de déploiement automatique (recommandé)

1. Depuis le dépôt local, régénérer l'archive si nécessaire :

```powershell
python create_deployment_zip.py
```

2. Lancer le script PowerShell (depuis la racine du repo) :

```powershell
./scripts/deploy_to_qualifinterop.ps1
# Exemple avec paramètres
./scripts/deploy_to_qualifinterop.ps1 -RemoteUser cpage -RemoteHost qualifinterop.cpage.cloud
```

Le script :
- détecte l'archive `meddatabridge-deployment-*.zip` la plus récente
- upload le zip sur `/tmp` du serveur
- exécute à distance `sudo unzip -o /tmp/<zip> -d /opt/meddata-bridge/`
- redémarre le service `meddata-bridge` via `sudo systemctl restart meddata-bridge`

Notes de sécurité
- Le script demande le mot de passe SSH et l'utilise pour `scp`/`ssh` et pour fournir le mot de passe à `sudo`. Préférez utiliser une paire de clés SSH pour éviter de distribuer des mots de passe en clair.

Commandes manuelles (si vous préférez tout faire à la main)

```bash
# Sur la machine locale
python create_deployment_zip.py
scp meddatabridge-deployment-*.zip cpage@qualifinterop.cpage.cloud:/tmp/

# Sur le serveur
sudo unzip -o /tmp/meddatabridge-deployment-*.zip -d /opt/meddata-bridge/
sudo systemctl restart meddata-bridge

# Vérifier le statut
sudo systemctl status meddata-bridge --no-pager
```

Dépannage
- Si `scp`/`ssh` n'est pas disponible sur Windows, installez l'OpenSSH client ou utilisez PuTTY (`pscp`/`plink`).
- Si le service ne démarre pas, consulter les logs du service :

```bash
sudo journalctl -u meddata-bridge -n 200 --no-pager
```

Répétabilité
- Le script PowerShell est conçu pour être réutilisé pour les déploiements futurs. Vous pouvez le placer dans un pipeline CI/CD (en adaptant l'authentification) pour automatiser entièrement le déploiement.

### Actions récentes effectuées (2025-12-18)

- Mise à jour de `scripts/remote_deploy.sh` :
	- Création automatique du répertoire de backups `/opt/meddata-bridge-backups` si absent.
	- Les backups conservent les fichiers de base de données avec propriété `meddata:meddata` lorsqu'un utilisateur `meddata` existe sur la machine.
	- Lors d'une restauration, les fichiers `medbridge.db`, `medbridge.db-wal`, `medbridge.db-shm` sont restaurés depuis le dernier backup et reçoivent la propriété `meddata:meddata` (ou `root:root` si l'utilisateur `meddata` est absent).

- Création d'une sauvegarde manuelle du déploiement courant sur le serveur dans `/opt/meddata-bridge-backups/`.

- Correction des permissions pour les fichiers SQLite existants :
	- `medbridge.db` : `meddata:meddata` et mode `0640`
	- `medbridge.db-wal`, `medbridge.db-shm` : `meddata:meddata` et mode `0660`

Ces changements assurent que la base SQLite n'est pas laissée sous la propriété `root` et permettent un rollback plus sûr lorsque des backups sont présents.
