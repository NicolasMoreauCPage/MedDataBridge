# 📥📤 Phase 4.1 : Import/Export Excel Structure

## 🎯 Objectif
Permettre l'import et l'export de la structure hospitalière complète via fichiers Excel pour faciliter :
- Migration depuis systèmes existants
- Édition en masse de la structure
- Sauvegarde et restauration
- Échange entre établissements

---

## 📋 Fonctionnalités

### 1. Export Excel Structure Complète

**Route** : `/api/structure/export/excel`

#### Contenu du fichier Excel
- **Feuille "Entités Géographiques"** : Liste des EG avec codes, noms, types
- **Feuille "Pôles"** : Pôles avec rattachement EG
- **Feuille "Services"** : Services avec codes, pôles, UM
- **Feuille "Unités Fonctionnelles"** : UF avec codes UM, services
- **Feuille "Unités d'Hébergement"** : UH avec rattachements
- **Feuille "Chambres"** : Chambres avec numéros, UH
- **Feuille "Lits"** : Lits avec numéros, types, chambres

#### Formatage
- En-têtes avec fond bleu et texte blanc
- Colonnes auto-ajustées
- Validation des données (listes déroulantes pour types)
- Instructions dans feuille "README"

### 2. Template Excel Vierge

**Route** : `/api/structure/export/template`

#### Contenu
- Feuilles vides avec structure attendue
- Exemples pré-remplis (1 ligne par feuille)
- Instructions détaillées
- Règles de validation
- Codes UM pré-définis

### 3. Import Excel Structure

**Route** : `POST /api/structure/import/excel`

#### Processus
1. **Upload fichier** : Via formulaire avec drag & drop
2. **Validation** :
   - Format colonnes obligatoires
   - Cohérence codes (pas de doublons)
   - Références valides (service existe avant UF)
   - Types de données corrects
3. **Prévisualisation** : Affichage modifications avant import
4. **Import en base** : Transaction atomique (tout ou rien)
5. **Rapport** : Résumé avec erreurs et warnings

#### Modes d'import
- **Création** : Ajoute uniquement nouveaux éléments
- **Mise à jour** : Modifie éléments existants (match par code)
- **Remplacement** : Supprime tout et recrée (⚠️ dangereux)

### 4. Interface Upload

**Route** : `/structure/import`

#### Composants
- Zone drag & drop pour fichier Excel
- Bouton téléchargement template
- Sélecteur mode d'import
- Barre progression upload
- Tableau prévisualisation avec diff
- Boutons Valider/Annuler

---

## 🏗️ Architecture Technique

### Backend

#### Nouveaux Endpoints

```python
# app/routers/structure_import_export.py

GET /api/structure/export/excel?eg_id=1
- Export structure complète en Excel
- Paramètre optionnel eg_id pour filtrer

GET /api/structure/export/template
- Télécharge template vierge avec exemples

POST /api/structure/import/excel
- Upload: multipart/form-data
- Body: file (Excel), mode (create|update|replace)
- Response: rapport validation + preview

POST /api/structure/import/confirm
- Body: session_id (du preview)
- Execute import en base
- Response: résumé (created, updated, errors)

GET /structure/import (UI)
- Page interface d'import
```

#### Librairies
```python
openpyxl  # Déjà installé (Phase 3.1.4)
pandas    # Pour manipulation données tabulaires (optionnel)
```

#### Modèles de validation
```python
# app/schemas/import_schemas.py

class ExcelRowEG(BaseModel):
    code: str
    nom: str
    type_eg: str
    
class ExcelRowPole(BaseModel):
    code: str
    nom: str
    eg_code: str
    
# ... autres modèles pour chaque type

class ImportPreview(BaseModel):
    to_create: List[dict]
    to_update: List[dict]
    errors: List[dict]
    warnings: List[dict]
```

### Frontend

#### Interface d'import
```html
<!-- app/templates/structure_import.html -->

- Zone drag & drop avec Dropzone.js
- Tableau prévisualisation avec diff coloré
- Boutons action avec confirmations
- Logs temps réel durant import
```

---

## 📊 Format Excel Attendu

### Feuille "EntitesGeographiques"
| code | nom | type_eg | adresse | telephone |
|------|-----|---------|---------|-----------|
| EG01 | CHU Nord | CHU | 1 rue... | 01... |

### Feuille "Poles"
| code | nom | eg_code | responsable |
|------|-----|---------|-------------|
| POL1 | Pôle Médecine | EG01 | Dr Dupont |

### Feuille "Services"
| code | nom | pole_code | um_code | telephone |
|------|-----|-----------|---------|-----------|
| SRV1 | Cardiologie | POL1 | MCO | 01... |

### Feuille "UnitésFonctionnelles"
| code | nom | service_code | um_code | type_uf | capacite |
|------|-----|--------------|---------|---------|----------|
| UF01 | Cardio A | SRV1 | MCO | SOINS | 30 |

### Feuille "UnitesHebergement"
| code | nom | uf_code | etage | batiment |
|------|-----|---------|-------|----------|
| UH01 | Aile Est | UF01 | 2 | A |

### Feuille "Chambres"
| numero | uh_code | capacite | type_chambre |
|--------|---------|----------|--------------|
| 201 | UH01 | 2 | DOUBLE |

### Feuille "Lits"
| numero | chambre_numero | uh_code | type_lit | statut |
|--------|----------------|---------|----------|--------|
| 201A | 201 | UH01 | STANDARD | DISPONIBLE |

---

## ✅ Plan de Développement

### Sprint 4.1.1 : Export Excel _(1 jour)_
- [x] Installer dépendances (openpyxl déjà présent)
- [ ] Router `/api/structure/export/excel`
- [ ] Génération 7 feuilles avec données
- [ ] Formatage professionnel (couleurs, largeurs)
- [ ] Template vierge avec exemples

### Sprint 4.1.2 : Import Excel Backend _(2 jours)_
- [ ] Endpoint `POST /import/excel` avec validation
- [ ] Parser Excel → modèles Pydantic
- [ ] Validation cohérence (références, codes)
- [ ] Prévisualisation avec diff
- [ ] Import transactionnel en base

### Sprint 4.1.3 : Interface Upload _(1 jour)_
- [ ] Template `structure_import.html`
- [ ] Drag & drop avec Dropzone.js
- [ ] Tableau prévisualisation
- [ ] Gestion erreurs et succès
- [ ] Téléchargement template depuis UI

### Sprint 4.1.4 : Tests & Validation _(0.5 jour)_
- [ ] Tests import fichier valide
- [ ] Tests erreurs validation
- [ ] Tests modes create/update
- [ ] Documentation utilisateur

---

## 🎨 Design Interface Import

```
┌─ Import Structure ──────────────────────────────────────────┐
│                                                              │
│  📥 Import de structure depuis Excel                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                                                        │ │
│  │         📁 Glissez votre fichier Excel ici            │ │
│  │                 ou cliquez pour parcourir             │ │
│  │                                                        │ │
│  │         Formats acceptés : .xlsx, .xls                │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Mode d'import : ○ Création  ● Mise à jour  ○ Remplacement  │
│                                                              │
│  [ 📥 Télécharger le template vierge ]                       │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│                                                              │
│  📊 Prévisualisation                                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Type         │ Code   │ Nom          │ Action         │ │
│  ├────────────────────────────────────────────────────────│ │
│  │ 🏢 Pôle      │ POL1   │ Médecine     │ ✅ Créer       │ │
│  │ 🏛️ Service   │ SRV1   │ Cardiologie  │ ✅ Créer       │ │
│  │ 🔹 UF        │ UF01   │ Cardio A     │ ⚠️ Dupliquer   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ⚠️ 1 avertissement, 0 erreur                                │
│                                                              │
│  [ Annuler ]                      [ ✅ Valider l'import ]    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📌 Notes Importantes

⚠️ **Import atomique** : Si une erreur survient, aucune donnée n'est modifiée (transaction rollback)

⚠️ **Validation stricte** : Codes uniques, références valides, types corrects

⚠️ **Backup recommandé** : Exporter structure avant import massif

💡 **Performance** : Pour > 10000 lits, import par batch de 1000

🔒 **Sécurité** : Limiter import aux utilisateurs avec rôle "Admin" (Phase 4.2)

---

**Prêt pour implémentation ! 🚀**
