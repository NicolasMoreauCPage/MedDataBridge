# Auto-transmission HPRIM pour Cotations

## 🎯 Objectif

Implémenter l'auto-transmission HPRIM pour les actes de cotation (CCAM, NGAP, UCD, LPP), alignant le comportement sur PAM/FHIR qui transmettent automatiquement les entités (patient, venue, mouvement).

## ✅ Implémentation Complète

### 1. Modification de `emit_on_create.py`

**Changements apportés :**

- **Signature étendue** : `entity_type` accepte maintenant `"ccam_act"`, `"ngap_act"`, `"ucd_act"`, `"lpp_act"` en plus des types d'entités existants
- **Logique HPRIM modifiée** : 
  - Ancien comportement : Skip tous les types sauf cotations (mais pas implémenté)
  - Nouveau comportement : Traite uniquement les actes de cotation
  - Génère automatiquement le XML HPRIM `evenementsServeurActes`
  - Crée un MessageLog pour traçabilité

**Code clé (lignes 1838-1970 environ) :**

```python
if endpoint.kind == "HPRIM":
    # Only process cotation acts for HPRIM endpoints
    if entity_type not in ["ccam_act", "ngap_act", "ucd_act", "lpp_act"]:
        logger.debug(f"[HPRIM] Skipping {entity_type} - reserved for cotation acts only")
        continue
    
    # Generate HPRIM XML message
    # - Load dossier and patient
    # - Build HprimMessage with entete, patient, acte
    # - Generate XML via HprimXmlService
    # - Create MessageLog with status="pending"
```

### 2. Modification de `cotations_saisie.py`

**Changements apportés :**

Ajout d'appels à `emit_to_senders_async` après chaque `session.commit()` dans :
- `create_ccam_acte()` (ligne ~392)
- `create_ngap_acte()` (ligne ~607)
- `create_ucd_acte()` (ligne ~655)
- `create_lpp_acte()` (ligne ~704)

**Code type ajouté :**

```python
session.add(acte)
session.commit()
session.refresh(acte)

# Auto-émission HPRIM si endpoints configurés
try:
    from app.services.emit_on_create import emit_to_senders_async
    emit_to_senders_async(acte, "ccam_act", session, operation="insert")
except Exception as e:
    logger.warning(f"Erreur auto-émission HPRIM pour acte CCAM {acte.id}: {e}")

logger.info(f"Acte CCAM créé: {acte.code_acte} (ID: {acte.id})")
```

### 3. Génération XML HPRIM

Utilise les services existants :
- `app.services.hprim.hprim_xml.HprimXmlService` pour génération XML
- `app.hprim_models` pour les modèles de données HPRIM
- Construit un message `evenementsServeurActes` conforme HPRIM XML v2.4

**Structure du message :**
```xml
<evenementsServeurActes version="2.4" acquittementAttendu="oui">
  <enteteMessage>
    <identifiantMessage>COTATION-{act_id}-{timestamp}</identifiantMessage>
    <dateHeureProduction>{datetime}</dateHeureProduction>
    <emetteur><!-- MEDBRIDGE --></emetteur>
    <destinataire><!-- Remote System --></destinataire>
  </enteteMessage>
  <evenementServeurActe>
    <patient><!-- IPP, nom, prénom, etc. --></patient>
    <actesCCAM><!-- ou actesNGAP, etc. --></actesCCAM>
  </evenementServeurActe>
</evenementsServeurActes>
```

## 🔧 Configuration Requise

### Créer un Endpoint HPRIM

Pour que l'auto-émission fonctionne, vous devez configurer au moins un endpoint HPRIM :

```python
# Via l'interface /endpoints ou directement en DB
endpoint = SystemEndpoint(
    name="Système de Facturation HPRIM",
    kind="HPRIM",  # Type obligatoire
    role="sender",  # ou "both" pour bidirectionnel
    is_enabled=True,
    host="facturation.hopital.local",
    port=8080,
    
    # Filtrage par type d'acte (sélectif)
    emit_hprim_ccam=True,   # Émet les actes CCAM
    emit_hprim_ngap=True,   # Émet les actes NGAP
    emit_hprim_ucd=False,   # N'émet PAS les UCD
    emit_hprim_lpp=False,   # N'émet PAS les LPP
    
    # Optionnel : Contexte
    entite_juridique_id=1,  # Si spécifique à une EJ
    ght_context_id=None,    # ou GHT si différent
)
```

**⚙️ Filtrage granulaire par type d'acte :**

Le système permet de configurer **finement** quels types d'actes sont émis par endpoint :

| Champ | Description | Défaut |
|-------|-------------|--------|
| `emit_hprim_ccam` | Émettre actes CCAM (Classification Commune des Actes Médicaux) | `False` |
| `emit_hprim_ngap` | Émettre actes NGAP (Nomenclature Générale des Actes Professionnels) | `False` |
| `emit_hprim_ucd` | Émettre actes UCD (Unité Commune de Dispensation - médicaments) | `False` |
| `emit_hprim_lpp` | Émettre actes LPP (Liste des Produits et Prestations - dispositifs) | `False` |

**💡 Cas d'usage :**
- **Endpoint facturation chirurgie** : `emit_hprim_ccam=True`, autres à `False` → Seulement les actes CCAM
- **Endpoint pharmacie** : `emit_hprim_ucd=True`, `emit_hprim_lpp=True` → Seulement médicaments et dispositifs
- **Endpoint facturation globale** : Tous à `True` → Tous les types d'actes

**📋 Exemple de configuration multi-endpoints :**

```python
# Endpoint 1 : Facturation bloc opératoire (CCAM uniquement)
endpoint_bloc = SystemEndpoint(
    name="Facturation Bloc - CCAM",
    kind="HPRIM",
    role="sender",
    is_enabled=True,
    host="facturation-bloc.hopital.local",
    emit_hprim_ccam=True,  # ✅ CCAM seulement
    emit_hprim_ngap=False,
    emit_hprim_ucd=False,
    emit_hprim_lpp=False,
    entite_geo_id=5  # Bloc opératoire uniquement
)

# Endpoint 2 : Pharmacie (UCD + LPP uniquement)
endpoint_pharma = SystemEndpoint(
    name="Pharmacie - Médicaments et Dispositifs",
    kind="HPRIM",
    role="sender",
    is_enabled=True,
    host="pharmacie.hopital.local",
    emit_hprim_ccam=False,
    emit_hprim_ngap=False,
    emit_hprim_ucd=True,   # ✅ Médicaments
    emit_hprim_lpp=True,   # ✅ Dispositifs
    entite_juridique_id=1  # Toute l'EJ
)

# Endpoint 3 : Archive centrale (tous types)
endpoint_archive = SystemEndpoint(
    name="Archive Centrale",
    kind="HPRIM",
    role="sender",
    is_enabled=True,
    outbox_path="/archives/hprim",
    emit_hprim_ccam=True,  # ✅ Tout
    emit_hprim_ngap=True,  # ✅ Tout
    emit_hprim_ucd=True,   # ✅ Tout
    emit_hprim_lpp=True,   # ✅ Tout
    # Pas de contexte = global
)
```

**Types de destination :**
- **FILE** : Écriture dans un répertoire (outbox_path)
- **HTTP** : Envoi via POST HTTP (en développement)

## 📊 Vérification et Tests

### Script de vérification

```bash
.venv/bin/python3 test_hprim_auto_emission.py
```

Affiche :
- Nombre d'endpoints HPRIM configurés
- Dossiers avec actes
- Messages HPRIM émis récemment

### Surveillance des logs

```bash
tail -f logs/app.log | grep HPRIM
```

Messages attendus :
```
[HPRIM] Generated XML for ccam_act 42 to endpoint 5
[HPRIM] Queued ccam_act emission for endpoint 5
```

### Vérification en base

```sql
-- Messages HPRIM émis
SELECT * FROM messagelog 
WHERE entity_type IN ('ccam_act', 'ngap_act', 'ucd_act', 'lpp_act')
ORDER BY created_at DESC;

-- Endpoints HPRIM actifs
SELECT * FROM systemendpoint 
WHERE kind = 'HPRIM' AND is_enabled = 1;
```

## 🎯 Flux Complet

### Flux 1 : Création locale d'actes (Interface utilisateur)

```
┌─────────────────────────────────────────────────────────────┐
│  1. Utilisateur saisit un acte CCAM via l'interface        │
│     http://localhost:8000/cotation-modern/dossiers/10      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  2. POST /cotations/api/ccam                                │
│     → create_ccam_acte() dans cotations_saisie.py          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  3. session.add(acte) + session.commit()                    │
│     → Acte sauvegardé en DB                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  4. emit_to_senders_async(acte, "ccam_act", session)       │
│     → Appel automatique après commit                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Boucle sur les endpoints HPRIM actifs                   │
│     - Filtrage par EJ/GHT si configuré                      │
│     - Skip si entity_type != cotation                       │
│     - ⚙️ Filtrage par type d'acte (emit_hprim_ccam, etc.)  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Génération XML HPRIM                                    │
│     - Load dossier + patient                                │
│     - Build HprimMessage                                    │
│     - HprimXmlService.generate_xml()                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  7. Create MessageLog                                       │
│     - status="pending"                                      │
│     - payload=hprim_xml                                     │
│     - entity_type="ccam_act"                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  8. FILE poller ou HTTP sender transmet le message          │
│     → Système distant reçoit l'événement HPRIM              │
└─────────────────────────────────────────────────────────────┘
```

### Flux 2 : Réception et relai d'actes HPRIM (Messages entrants)

```
┌─────────────────────────────────────────────────────────────┐
│  1. Message HPRIM reçu (evenementsServeurActes)            │
│     → Stocké dans MessageLog                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  2. POST /hprim-cotation/message/{id}/import-ccam          │
│     → import_ccam_acts() dans hprim_messages.py            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Parse HPRIM XML → Extraction actes CCAM                 │
│     → HprimXmlService.parse_xml()                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Recherche dossier via NDA                               │
│     → Vérification doublons                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  5. session.add(acte) + session.commit()                    │
│     → Acte importé sauvegardé en DB                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  6. emit_to_senders_async(acte, "ccam_act", session)       │
│     → RELAI automatique vers autres endpoints HPRIM         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  7. Génération XML HPRIM pour le relai                      │
│     → Nouveau message HPRIM créé                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  8. Transmission vers endpoints secondaires                 │
│     → Architecture hub-and-spoke ou multi-sites             │
└─────────────────────────────────────────────────────────────┘
```

**💡 Cas d'usage du relai :**
- **Hub hospitalier** : Reçoit les cotations de plusieurs établissements et les consolide vers un système de facturation central
- **Multi-sites** : Un site reçoit les actes et les redistribue aux autres sites du GHT
- **Archivage** : Relai automatique vers un système d'archivage légal
- **Intégration** : Transmission vers un ERP, un data warehouse ou un système décisionnel

## 🆚 Comparaison Avant/Après

### Avant (Manuel)

1. Utilisateur saisit des actes dans l'interface
2. Clique sur "Transmettre (HPRIM)"
3. **Problème** : Le bouton n'avait aucun handler JavaScript !
4. Rien ne se passait

### Après (Automatique)

1. Utilisateur saisit un acte dans l'interface
2. **Auto-transmission immédiate** dès la sauvegarde
3. Cohérent avec PAM/FHIR (mouvements, patients)
4. Traçabilité complète via MessageLog

## 📝 Notes Importantes

### Support par type d'acte

| Type | Statut | Notes |
|------|--------|-------|
| CCAM | ✅ Implémenté | Génération XML complète avec modificateurs |
| NGAP | ✅ Implémenté | Génération XML avec coefficient, denombrement |
| UCD  | ⚠️ Partiel | Auto-émission ajoutée, génération XML à compléter |
| LPP  | ⚠️ Partiel | Auto-émission ajoutée, génération XML à compléter |

### Gestion des erreurs

L'auto-émission utilise un try/except pour ne **pas bloquer** la sauvegarde de l'acte si l'émission échoue :

```python
try:
    emit_to_senders_async(acte, "ccam_act", session, operation="insert")
except Exception as e:
    logger.warning(f"Erreur auto-émission HPRIM pour acte CCAM {acte.id}: {e}")
# L'acte est quand même sauvegardé !
```

### Contexte EJ/GHT

Les endpoints HPRIM respectent le filtrage par contexte :
- **Endpoint global** (pas de EJ/GHT) : Reçoit tous les actes
- **Endpoint EJ** : Reçoit uniquement les actes des dossiers de cette EJ
- **Endpoint GHT** : Reçoit uniquement les actes des dossiers de ce GHT

## 🔮 Évolutions Futures

1. **Support HTTP** : Envoi direct via POST au lieu de FILE
2. **UCD/LPP** : Compléter la génération XML HPRIM
3. **Modifications d'actes** : Ajouter `emit_to_senders_async` dans les routes UPDATE (quand elles seront créées)
4. **Suppressions d'actes** : Émettre avec `action="suppression"`
5. **Batch emission** : Regrouper plusieurs actes dans un même message HPRIM

## 📚 Références

- **HPRIM XML v2.4** : Spécification dans `docs/HPRIM_XML/`
- **Code source** :
  - [emit_on_create.py](../app/services/emit_on_create.py) lignes 1390-1970
  - [cotations_saisie.py](../app/routers/cotations_saisie.py) lignes 350-710
  - [hprim_xml.py](../app/services/hprim/hprim_xml.py)
- **Models** :
  - [hprim_models.py](../app/hprim_models.py) : HprimMessage, HprimActeCCAM, etc.
  - [models.py](../app/models.py) : CCAMAct, NGAPAct, UCDAct, LPPAct

---

**Date de mise en œuvre** : 2026-01-08  
**Version** : 1.1.0-dev  
**Auteur** : GitHub Copilot & Nicolas
