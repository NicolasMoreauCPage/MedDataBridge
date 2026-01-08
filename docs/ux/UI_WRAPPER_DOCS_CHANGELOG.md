# Enveloppe UI pour Documentation HTML - Résumé du changement

## 📋 Problème identifié

Les fichiers HTML du dossier `/Doc` servaient comme fichiers statiques bruts et manquaient:

1. **Bandeau (header)** avec logo, contexte GHT/EJ/Patient
2. **Menu de navigation** principal
3. **Pied de page (footer)** du programme
4. **Style cohérent** avec le reste du programme (Tailwind, thème light/dark)
5. **Breadcrumb** de navigation

**Résultat**: Les docs depuis le menu "Ressources" avaient une apparence complètement différente du reste du programme.

## ✅ Solution implémentée

### Nouveaux fichiers créés

#### 1. `app/routers/doc_wrapper.py` (89 lignes)

- Routeur FastAPI qui intercepte les requêtes `/docs/{file_path:path}`
- Enveloppe les fichiers HTML avec le template `base.html`
- Sert les fichiers non-HTML (images, CSS, etc.) directement
- Gère la sécurité (path traversal prevention)

**Logique**:
```python
@router.get("/docs/{file_path:path}")
async def serve_wrapped_doc(request, file_path):
    # Validations de sécurité
    # Si .html → envelopper dans doc_wrapper.html
    # Si non-.html → servir comme FileResponse
```

#### 2. `app/templates/doc_wrapper.html` (85 lignes)
- Template qui enveloppe le contenu HTML
- Étend `base.html` pour avoir le header, menu, footer
- Inclut breadcrumb de navigation
- Ajoute styling cohérent pour les éléments HTML (headings, tables, code, etc.)
- Supporte le thème light/dark via CSS variables

**Éléments inclus**:
- Header avec contexte
- Navigation complète
- Breadcrumb: Accueil > Documentation > nom_fichier
- Contenu HTML du document
- Styles pour cohérence (h1, h2, tables, code, blockquotes, etc.)

### Modifications à `app/app.py`

1. **Import du nouveau routeur** (ligne 63):
   ```python
   from app.routers import (..., doc_wrapper)
   ```

2. **Inclusion du routeur** (ligne 258, avant documentation):
   ```python
   app.include_router(doc_wrapper.router)  # Wrapper pour docs HTML statiques
   ```

3. **Retrait du montage StaticFiles** (lignes 153-156):
   ```python
   # NOTE: Montage du dossier /Doc retiré - les documentations HTML sont maintenant
   # servies via le routeur doc_wrapper qui les enveloppe dans le template base.html
   # pour garantir une cohérence de style et de navigation avec le reste du programme.
   ```

## 🎯 Résultat

### Avant
- `/docs/user_guide.html` → Fichier HTML brut sans bandeau ni menu
- Styles génériques du fichier HTML original
- Pas de navigation cohérente

### Après ✅
- `/docs/user_guide.html` → Enveloppé dans base.html
- Bandeau complet avec logo MD et contexte
- Menu de navigation complet
- Breadcrumb de navigation
- Styles cohérents (Tailwind, thème light/dark)
- Pied de page du programme

## 📊 Pages affectées

Tous les fichiers HTML du menu "Ressources" section "Programme":
- ✅ `/docs/PROGRAM_DOCUMENTATION.html`
- ✅ `/docs/architecture.html`
- ✅ `/docs/FHIR_API.html`
- ✅ `/docs/models_reference.html`
- ✅ `/docs/user_guide.html`
- ✅ `/docs/SCENARIOS_DOCUMENTATION.html`
- ✅ `/docs/AUTHENTICATION.html`
- ✅ `/docs/IHE_PAM_INTEGRATION_COMPLETE_FR.html`
- ✅ `/docs/IHE_PAM_WORKFLOWS_FR.html`
- ✅ `/docs/IHE_PAM_TECHNIQUE.html`
- Et tous les autres fichiers `.html` du dossier `/Doc`

## 🔧 Détails techniques

### Ordre d'exécution du routeur
1. Requête `/docs/user_guide.html`
2. Router `doc_wrapper` intercepte (avant StaticFiles)
3. Vérification de sécurité (no path traversal)
4. Si `.html` → enveloppe dans `doc_wrapper.html`
5. Si autre format → retourne FileResponse

### Template `doc_wrapper.html`
- Étend `base.html` pour hériter de toute la structure
- Breadcrumb en haut
- Contenu enveloppé avec `{{ doc_content | safe }}`
- CSS personnalisé pour style des éléments HTML
- Support du thème light/dark via `var(--color-*)`

### Sécurité
- Vérification path traversal (`..` check)
- Résolution de chemin vérifiée
- Validation que le fichier est dans `/Doc`

## 📈 Avantages

✅ **Cohérence UI**: Tous les documents ont maintenant l'apparence du programme
✅ **Navigation**: Breadcrumb et menu présents sur chaque page
✅ **Contexte**: Affichage du contexte GHT/EJ/Patient même dans les docs
✅ **Thème**: Support complet du mode light/dark
✅ **Performance**: Fichiers statiques toujours servis rapidement
✅ **Maintenabilité**: Une seule source de vérité pour le style UI

## 🚀 Déploiement

- Aucune migration de données requise
- Compatible avec tous les navigateurs
- Pas de dépendances nouvelles
- Changement transparent pour l'utilisateur

## 📝 Notes

- Les fichiers non-HTML (`.png`, `.jpg`, `.css`, etc.) du dossier `/Doc` sont toujours servis directement
- La route `/docs/{filename}.md` (markdown) continue à fonctionner séparément
- Les pages comme `/examples/*` et `/tools/*` avaient déjà le template, donc pas de changement
