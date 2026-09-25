# Livrables de déploiement

La procédure de démarrage maintenue est le
[guide Compose](../docs/deployment/deployment.md). Ce répertoire ne contient
que les éléments nécessaires à la création de livrables ou les traces de
procédures historiques.

Le code applicatif canonique est exclusivement dans `app/`. Les anciennes
copies placées sous `deployment/general/app` et `deployment/postgresql/app`
ont été supprimées afin d'éviter les divergences.

Créer un paquet source depuis la révision courante :

```bash
python3 scripts/build_deployment_bundle.py --output dist/meddata-bridge.zip
```

Pour un environnement hors ligne, ajouter `--with-wheels`. Les roues sont
téléchargées dans le livrable généré et ne sont pas versionnées dans Git.
