# Plan d'Évolution HPRIM - Cotations et Acquittements

## Objectifs
1. **Intégration des cotations dans les interventions** : Les cotations (CCAM, NGAP, UCD, LPP) sont liées aux interventions HPRIM
2. **Gestion des acquittements** : Implémenter la structure d'acquittements selon msgAcquittementsServeurActes2_4.xsd
3. **Révision des IHM cotations** : Améliorer l'interface utilisateur
4. **Action "Voir les cotations"** : Afficher dans les dossiers (liste/détail) si des cotations existent

## Phase 1 : Modèles de données

### 1.1 Modèle HprimIntervention (amélioration)
- **Actuellement** : `identifiant`, `libelle`, `date_intervention`, `medecin`, `acte_principal`, `actes_lies`
- **À ajouter** :
  - `cotations_liees: List[HprimCotation]` - Référence aux cotations
  - `venue_id: Optional[str]` - Venue liée
  - `lieu_execution: Optional[str]` - Lieu d'exécution
  - `statut: str` - actif, clos, annule
  
### 1.2 Modèle HprimCotation (nouveau)
```python
@dataclass
class HprimCotation:
    """Cotation liée à une intervention"""
    identifiant: str
    intervention_id: str  # Référence à l'intervention
    type: str  # CCAM, NGAP, UCD, LPP
    date_cotation: datetime
    cotation_data: Dict[str, Any]  # Données spécifiques (code, montant, etc.)
    statut: str  # brouillon, valide, envoye, acquitte
    valide: bool = False
```

### 1.3 Modèle HprimAcquittement (complet)
```python
@dataclass
class HprimAcquittement:
    """Acquittement selon msgAcquittementsServeurActes2_4.xsd"""
    # Entête
    entete: HprimEnteteMessageAcquittement
    patient: HprimPatient
    venue: Optional[HprimVenue]
    
    # Réponses
    reponses: List[HprimReponse]
    
    # Métadonnées
    id_message_original: str  # ID du message acquitté
    date_acquittement: datetime
    version: str = "2.4"
```

### 1.4 Modèle HprimReponse (nouveau)
```python
@dataclass
class HprimReponse:
    """Réponse à un acte dans l'acquittement"""
    statut: str  # OK, ERREUR, AVERTISSEMENT
    code_erreur: Optional[str]
    acte_ref: Dict[str, Any]  # Ref à l'acte (CCAM, NGAP, LPP, UCD ou Intervention)
    erreur_details: Optional[Dict[str, Any]]
    date_traitement: datetime
```

## Phase 2 : Base de données

### 2.1 Nouvelle table `hprim_intervention`
```sql
CREATE TABLE hprim_intervention (
    id INTEGER PRIMARY KEY,
    dossier_id INTEGER FOREIGN KEY,
    identifiant_hprim VARCHAR(50) UNIQUE,
    libelle VARCHAR(255),
    date_intervention DATETIME,
    medecin_id INTEGER FOREIGN KEY,
    venue_id VARCHAR(50),
    lieu_execution VARCHAR(255),
    statut VARCHAR(20),  -- actif, clos, annule
    created_at DATETIME,
    updated_at DATETIME
);
```

### 2.2 Nouvelle table `hprim_cotation_intervention`
```sql
CREATE TABLE hprim_cotation_intervention (
    id INTEGER PRIMARY KEY,
    hprim_intervention_id INTEGER FOREIGN KEY,
    cotation_id INTEGER FOREIGN KEY,  -- Référence à ccam_act, ngap_act, ucd_act, lpp_act
    cotation_type VARCHAR(10),  -- CCAM, NGAP, UCD, LPP
    statut VARCHAR(20),
    valide BOOLEAN,
    created_at DATETIME
);
```

### 2.3 Nouvelle table `hprim_acquittement`
```sql
CREATE TABLE hprim_acquittement (
    id INTEGER PRIMARY KEY,
    message_id_original VARCHAR(50),
    date_acquittement DATETIME,
    statut VARCHAR(20),
    version VARCHAR(10),
    contenu_xml TEXT,
    created_at DATETIME
);

CREATE TABLE hprim_reponse (
    id INTEGER PRIMARY KEY,
    acquittement_id INTEGER FOREIGN KEY,
    statut_reponse VARCHAR(20),
    code_erreur VARCHAR(10),
    acte_type VARCHAR(10),  -- CCAM, NGAP, LPP, UCD, INTERVENTION
    acte_id INTEGER,
    erreur_details TEXT,
    date_traitement DATETIME
);
```

### 2.4 Colonne optionnelle dans `dossier`
```sql
ALTER TABLE dossier ADD COLUMN (
    has_cotations BOOLEAN DEFAULT FALSE,
    cotations_count INTEGER DEFAULT 0
);
```

## Phase 3 : Convertisseurs

### 3.1 Améliorer `converters/hprim_converter.py`
- Adapter la conversion XML → Modèles pour inclure les interventions avec cotations
- Implémenter `parse_acquittement_from_xml(xml_bytes) → HprimAcquittement`

### 3.2 Nouveau : `converters/hprim_acquittement_converter.py`
- Convertir `HprimAcquittement` → XML selon msgAcquittementsServeurActes2_4.xsd
- Valider les réponses

### 3.3 Service : `services/hprim/hprim_intervention_service.py`
- Créer/lire/modifier/supprimer interventions
- Lier cotations aux interventions
- Gérer le statut des interventions

### 3.4 Service : `services/hprim/hprim_acquittement_service.py`
- Créer acquittements
- Persister acquittements reçus
- Associer acquittements aux messages originaux

## Phase 4 : API / Routers

### 4.1 Nouveau router : `routers/hprim_interventions.py`
```
GET    /api/hprim/interventions?dossier_id=X
POST   /api/hprim/interventions
GET    /api/hprim/interventions/{id}
PUT    /api/hprim/interventions/{id}
DELETE /api/hprim/interventions/{id}
GET    /api/hprim/interventions/{id}/cotations
POST   /api/hprim/interventions/{id}/cotations
```

### 4.2 Nouveau router : `routers/hprim_acquittements.py`
```
GET    /api/hprim/acquittements?message_id=X
POST   /api/hprim/acquittements (réception d'acquittement)
GET    /api/hprim/acquittements/{id}
```

### 4.3 Amélioration : `routers/cotation_modern.py`
- Ajouter contexte d'intervention
- Afficher interventions liées
- Lier cotations à interventions

## Phase 5 : IHM

### 5.1 Template : `templates/hprim_interventions_list.html`
- Liste des interventions du dossier
- Cotations par intervention (card collapse)
- Actions : ajouter, modifier, supprimer

### 5.2 Template : `templates/hprim_intervention_detail.html`
- Détail de l'intervention
- Cotations associées (tableau)
- Statut, dates, médecin

### 5.3 Template amélioration : `templates/dossier_detail.html`
- Ajouter section "Cotations liées"
- Bouton "Voir les cotations" (visible si count > 0)
- Afficher résumé : nombre, montant total, statut

### 5.4 Template amélioration : `templates/dossier_list.html` ou list API
- Ajouter colonne/flag "Has Cotations" dans les dossiers
- Icône/badge si cotations présentes

## Phase 6 : Métriques & Validation

### 6.1 Métriques HPRIM (app/metrics.py - existant)
- Ajouter `hprim_interventions_total`
- Ajouter `hprim_acquittements_total` (inbound)
- Ajouter `hprim_acquittement_errors_total`

### 6.2 Validation
- XSD validation des acquittements (réutiliser `xmlschema`)
- Règles métier (cohérence actes/intervention)

## Phase 7 : Récapitulatif des fichiers à modifier/créer

### Créer
- `app/models_hprim_intervention.py` (ou extension hprim_models.py)
- `app/models_hprim_acquittement.py` (ou extension hprim_models.py)
- `app/converters/hprim_acquittement_converter.py`
- `app/services/hprim/hprim_intervention_service.py`
- `app/services/hprim/hprim_acquittement_service.py`
- `app/routers/hprim_interventions.py`
- `app/routers/hprim_acquittements.py`
- `app/templates/hprim_interventions_list.html`
- `app/templates/hprim_intervention_detail.html`

### Modifier
- `app/models.py` : ajouter colonnes `has_cotations`, `cotations_count` à `Dossier`
- `app/hprim_models.py` : enrichir `HprimIntervention`, ajouter `HprimAcquittement`, etc.
- `app/converters/hprim_converter.py` : intégrer interventions/cotations
- `app/metrics.py` : ajouter métriques acquittements
- `app/routers/cotation_modern.py` : ajouter contexte intervention
- `app/templates/dossier_detail.html` : section cotations + bouton
- `app/templates/dossier_list.html` : colonne/flag cotations (ou API)
- `app/app.py` : router d'acquittements si nécessaire

## Séquence d'implémentation recommandée
1. ✅ Phase 1 : Modèles (hprim_models.py)
2. ✅ Phase 2 : Base de données (migrations/scripts)
3. ✅ Phase 3 : Convertisseurs & Services
4. ✅ Phase 4 : API/Routers
5. ✅ Phase 5 : IHM (templates)
6. ✅ Phase 6 : Métriques & Validation
7. ✅ Phase 7 : Tests & Documentation

---

## Priorité utilisateur
1. **CRITICAL** : Voir les cotations d'un dossier (dossier_detail + action)
2. **HIGH** : Gestion acquittements (recevoir + persister)
3. **MEDIUM** : IHM cotations/interventions (amélioration UX)
4. **LOW** : Métriques détaillées

