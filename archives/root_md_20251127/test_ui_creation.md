# Guide de Test - Création d'Entités via UI

## Objectif
Créer toutes les entités avec leurs valeurs possibles et valider les messages générés.

## 🎯 Plan de Test

### Phase 1 : Patients (3 scénarios)
**URL**: http://localhost:8000/patients/new

#### Test 1.1 : Patient Homme Validé
```
Nom:                Dupont
Prénom:             Jean
Date de naissance:  1980-05-15
Sexe:               M (Homme)
Qualité identité:   VALI (Identité validée)
```
**Validation attendue**:
- patient_seq = 12 chiffres commençant par 9 (ex: 935907638660)
- Message ADT^A31 généré
- IPP dans PID-2 ou PID-3
- Sexe = M dans PID-8

#### Test 1.2 : Patiente Femme Provisoire
```
Nom:                Martin
Prénom:             Sophie
Date de naissance:  1995-08-20
Sexe:               F (Femme)
Qualité identité:   PROV (Identité provisoire)
```

#### Test 1.3 : Patient Indéterminé sans Identité
```
Nom:                Inconnu
Prénom:             X
Date de naissance:  2000-01-01
Sexe:               U (Indéterminé)
Qualité identité:   VIDE (Aucune pièce d'identité)
```

### Phase 2 : Dossiers (3 types)
**URL**: http://localhost:8000/dossiers/new

#### Test 2.1 : Hospitalisation (IMP → I)
```
Patient:            (sélectionner Test 1.1)
Type venue:         IMP (Hospitalisation)
Date/heure entrée:  2025-01-15 10:00:00
```
**Validation attendue**:
- dossier_seq = 9 chiffres commençant par 9 (ex: 999460610)
- Message ADT^A01 généré
- **PV1-2 = I** (mapping IMP → I)
- NDA dans PV1-19

#### Test 2.2 : Consultation Externe (AMB → O)
```
Patient:            (sélectionner Test 1.2)
Type venue:         AMB (Ambulatoire)
Date/heure entrée:  2025-01-16 14:30:00
```
**Validation attendue**:
- **PV1-2 = O** (mapping AMB → O)
- Message ADT^A01 avec encounter.class = AMB

#### Test 2.3 : Urgences (EMER → E)
```
Patient:            (sélectionner Test 1.3)
Type venue:         EMER (Urgence)
Date/heure entrée:  2025-01-17 22:15:00
```
**Validation attendue**:
- **PV1-2 = E** (mapping EMER → E)
- Message ADT^A01 avec encounter.class = EMER

### Phase 3 : Venues (3 scénarios)
**URL**: http://localhost:8000/venues/new

#### Test 3.1 : Venue Hospitalisation
```
Dossier:            (Test 2.1)
Unité:              (sélectionner)
Chambre:            (sélectionner)
Lit:                (sélectionner)
Date début:         2025-01-15 10:00:00
```

#### Test 3.2 : Venue Externe
```
Dossier:            (Test 2.2)
Unité:              (sélectionner)
Date début:         2025-01-16 14:30:00
```

#### Test 3.3 : Venue Urgence
```
Dossier:            (Test 2.3)
Unité:              (sélectionner - BOX)
Date début:         2025-01-17 22:15:00
```

### Phase 4 : Mouvements (4 types)
**URL**: http://localhost:8000/mouvements/new

#### Test 4.1 : Transfert (A02)
```
Type:               A02 (Transfert)
Dossier:            (Test 2.1)
Unité destination:  (différente de venue actuelle)
Date/heure:         2025-01-16 08:00:00
```
**Validation attendue**:
- Message ADT^A02 généré
- PV1-3 = nouvelle unité

#### Test 4.2 : Sortie (A03)
```
Type:               A03 (Sortie définitive)
Dossier:            (Test 2.2)
Date/heure:         2025-01-16 17:00:00
```
**Validation attendue**:
- Message ADT^A03 généré
- PV1-45 = date/heure sortie

#### Test 4.3 : Mise à jour (A08)
```
Type:               A08 (Mise à jour)
Dossier:            (Test 2.3)
Date/heure:         2025-01-17 23:00:00
```
**Validation attendue**:
- Message ADT^A08 généré
- Champs PID/PV1 mis à jour

#### Test 4.4 : Annulation (A11)
```
Type:               A11 (Annulation admission)
Dossier:            (créer nouveau)
Date/heure:         2025-01-18 10:00:00
```
**Validation attendue**:
- Message ADT^A11 généré
- Admission annulée

## 📊 Script de Validation Rapide

Après chaque création, exécutez :

```bash
# Voir les 5 derniers messages
.venv/bin/python3 -c "
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import MessageLog

with Session(engine) as session:
    messages = session.exec(
        select(MessageLog)
        .order_by(MessageLog.created_at.desc())
        .limit(5)
    ).all()
    
    for msg in messages:
        segments = msg.payload.split('\r') if msg.payload and msg.kind == 'MLLP' else []
        msh = next((s for s in segments if s.startswith('MSH')), '')
        pv1 = next((s for s in segments if s.startswith('PV1')), '')
        
        msg_type = msh.split('|')[8] if msh and len(msh.split('|')) > 8 else 'N/A'
        patient_class = pv1.split('|')[2] if pv1 and len(pv1.split('|')) > 2 else 'N/A'
        
        print(f'ID={msg.id} | {msg_type} | PV1-2={patient_class} | {msg.created_at}')
"
```

## ✅ Checklist de Validation

### Identifiants
- [ ] patient_seq : 12 chiffres, préfixe 9
- [ ] dossier_seq : 9 chiffres, préfixe 9
- [ ] Format timestamp correct

### Mapping Vocabulaire (CRITIQUE)
- [ ] IMP → PV1-2 = **I**
- [ ] AMB → PV1-2 = **O**
- [ ] EMER → PV1-2 = **E**

### Messages HL7
- [ ] ADT^A31 pour patients seuls
- [ ] ADT^A01 pour admissions avec dossier
- [ ] ADT^A02 pour transferts
- [ ] ADT^A03 pour sorties
- [ ] ADT^A08 pour mises à jour
- [ ] ADT^A11 pour annulations

### Segments HL7
- [ ] MSH présent
- [ ] EVN présent
- [ ] PID présent
- [ ] PV1 présent (sauf A31)
- [ ] ZBE présent

### Standards FHIR
- [ ] Bundle type = "message"
- [ ] MessageHeader présent
- [ ] Patient resource conforme
- [ ] Encounter resource (si dossier)
- [ ] Identifiers corrects

## 🚀 Démarrage

1. Ouvrir le navigateur : http://localhost:8000
2. Commencer par Phase 1 (Patients)
3. Valider les messages après chaque création
4. Noter les anomalies dans un fichier TEST_RESULTS.md
5. Continuer avec Phases 2, 3, 4

## 🔧 Commande de Validation Complète

```bash
python validate_messages.py --recent 20
```

Cette commande affichera :
- Types de messages
- Identifiants générés
- Mapping PV1-2
- Validation IHE PAM
- Structures FHIR
