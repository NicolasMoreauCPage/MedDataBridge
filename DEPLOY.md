# Instructions de déploiement sur Render.com

## Prérequis
- Compte Render.com (gratuit)
- Repository GitHub public ou privé

## Configuration Render

1. **Créer un nouveau Web Service sur Render**
   - Aller sur https://dashboard.render.com
   - Cliquer "New +" → "Web Service"
   - Connecter votre repository GitHub `MedDataBridge`
   - Sélectionner la branche `main`

2. **Configuration du service**
   ```
   Name: meddata-bridge
   Region: Frankfurt (EU Central)
   Branch: main
   Runtime: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn app.app:app --host 0.0.0.0 --port $PORT
   ```

3. **Variables d'environnement**
   Dans Render Dashboard → Environment :
   ```
   SESSION_SECRET_KEY=<générer une clé aléatoire>
   DATABASE_URL=sqlite:///./medbridge.db
   ```

4. **Plan gratuit**
   - Free tier : 750h/mois gratuit
   - Le service se met en veille après 15 min d'inactivité
   - Redémarre automatiquement à la première requête

## Workflow de développement

### Branches locales (développement)
```bash
# Créer une branche feature
git checkout -b feature/nouvelle-fonctionnalite

# Travailler localement
# ... modifications ...

# Commits locaux
git add .
git commit -m "feat: nouvelle fonctionnalité"

# Tests locaux
pytest tests/ -v

# NE PAS PUSH sur GitHub (reste local)
```

### Branche main (production)
```bash
# Fusionner feature dans main
git checkout main
git merge feature/nouvelle-fonctionnalite

# Tester avant push
pytest tests/test_identifier_generator.py -v

# Push vers GitHub → Déploiement automatique
git push origin main
```

## Vérification du déploiement

1. GitHub Actions : https://github.com/NicolasMoreauCPage/MedDataBridge/actions
2. Render Dashboard : https://dashboard.render.com/
3. Logs en temps réel sur Render

## URLs

- **Production** : https://meddata-bridge.onrender.com
- **API Docs** : https://meddata-bridge.onrender.com/docs
- **Health Check** : https://meddata-bridge.onrender.com/

## Rollback en cas de problème

```bash
# Sur Render Dashboard
# → Manual Deploy → Sélectionner commit précédent

# Ou en local
git revert HEAD
git push origin main
```
