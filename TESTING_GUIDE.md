# Guide de Test - Création d'Entités et Validation des Messages

## 🎯 Objectif

Tester toutes les entités avec l'ensemble de leurs valeurs possibles et valider les messages générés dans tous les standards (HL7v2 IHE PAM, FHIR).

## 🚀 Démarrage

1. **Serveur en cours** : Vérifier que le serveur FastAPI est actif sur http://localhost:8000

2. **Script de validation** : Utiliser `validate_messages.py` pour vérifier les messages après chaque création

```bash
# Valider tous les messages
python validate_messages.py

# Voir uniquement les 5 derniers messages
python validate_messages.py --recent 5
```

## 📋 Scénarios de Test

### 1. PATIENTS - Création

**URL** : http://localhost:8000/patients/new

#### Scénario A : Patient Hospitalisé Homme Validé
- **Nom** : MARTIN
- **Prénom** : Jean
- **Date naissance** : 1980-05-15
- **Genre** : M (Masculin)
- **Adresse** : 123 Rue de la République
- **Ville** : Paris
- **Code postal** : 75001
- **Pays** : FR
- **Téléphone** : 0123456789
- **Email** : jean.martin@email.fr
- **NIR** : 1800515999123
- **Fiabilité identité** : VALI (Validée)
- **Statut marital** : M (Marié)
- **Nationalité** : Française

**Messages attendus** : Aucun (les patients seuls ne génèrent pas de messages)

#### Scénario B : Patiente Externe Femme Provisoire
- **Nom** : DUBOIS
- **Prénom** : Marie
- **Date naissance** : 1992-12-03
- **Genre** : F (Féminin)
- **Fiabilité identité** : PROV (Provisoire)
- **Statut marital** : S (Célibataire)

#### Scénario C : Patient Urgence Indéterminé
- **Nom** : BERNARD
- **Prénom** : Alex
- **Date naissance** : 2000-01-01
- **Genre** : U (Indéterminé)
- **Fiabilité identité** : VIDE (Non qualifiée)

### 2. DOSSIERS - Admission (A01)

**URL** : http://localhost:8000/dossiers/new

#### Scénario D : Hospitalisation Complète (encounter_class = IMP)
- **Patient** : Jean MARTIN (créé précédemment)
- **Type dossier** : hospitalise
- **UF responsabilité** : MCO-CARDIO
- **Source admission** : Domicile
- **Médecin responsable** : Dr. DUPONT
- **Date admission** : [Date/heure actuelle]

**Messages attendus** :
- HL7v2 : `ADT^A01` (Admission)
- Segments : MSH, EVN, PID, PV1, ZBE
- **PV1-2** : `I` (Inpatient) ← Vérifie mapping encounter_class='IMP' → patient_class='I'
- **ZBE-1** : Numéro de dossier (9 chiffres commençant par 9)

#### Scénario E : Consultation Externe (encounter_class = AMB)
- **Patient** : Marie DUBOIS
- **Type dossier** : externe
- **UF responsabilité** : CONSULT-NEURO
- **Date admission** : [Date/heure actuelle]

**Messages attendus** :
- HL7v2 : `ADT^A04` ou `ADT^A01`
- **PV1-2** : `O` (Outpatient) ← Vérifie mapping encounter_class='AMB' → patient_class='O'

#### Scénario F : Urgence (encounter_class = EMER)
- **Patient** : Alex BERNARD
- **Type dossier** : urgence
- **UF responsabilité** : URG-ADULT
- **Source admission** : SAMU
- **Date admission** : [Date/heure actuelle]

**Messages attendus** :
- HL7v2 : `ADT^A01`
- **PV1-2** : `E` (Emergency) ← Vérifie mapping encounter_class='EMER' → patient_class='E'

### 3. VENUES - Mouvements dans le dossier

**URL** : http://localhost:8000/venues/new

#### Scénario G : Venue Hospitalisation
- **Dossier** : [ID du dossier hospitalisation]
- **UF responsabilité** : MCO-CARDIO
- **Localisation** : Chambre 123, Lit A
- **Date début** : [Date/heure actuelle]
- **Médecin** : Dr. DUPONT
- **Service** : Cardiologie

**Messages attendus** :
- Peut générer `ADT^A01` ou être associé au dossier

#### Scénario H : Venue Consultation
- **Dossier** : [ID du dossier externe]
- **UF responsabilité** : CONSULT-NEURO
- **Date début** : [Date/heure actuelle]

### 4. MOUVEMENTS - Événements

**URL** : http://localhost:8000/mouvements/new

#### Scénario I : Transfert (A02)
- **Venue** : [ID venue hospitalisation]
- **Type** : ADT^A02
- **Trigger event** : A02
- **Type mouvement** : transfer
- **De** : MCO-CARDIO
- **Vers** : MCO-NEURO
- **Date** : [Date/heure actuelle]

**Messages attendus** :
- HL7v2 : `ADT^A02` (Transfer)
- **PV1-2** : Code correspondant au type de dossier
- **PV1-6** : Localisation précédente
- **PV1-3** : Nouvelle localisation

#### Scénario J : Sortie (A03)
- **Venue** : [ID venue]
- **Type** : ADT^A03
- **Trigger event** : A03
- **Type mouvement** : discharge
- **Localisation** : MCO-NEURO
- **Disposition** : Domicile
- **Date** : [Date/heure actuelle]

**Messages attendus** :
- HL7v2 : `ADT^A03` (Discharge)
- **PV1-36** : Discharge disposition

#### Scénario K : Mise à jour (A08)
- **Venue** : [ID venue]
- **Type** : ADT^A08
- **Trigger event** : A08
- **Type mouvement** : update

**Messages attendus** :
- HL7v2 : `ADT^A08` (Update patient information)

#### Scénario L : Annulation (A11)
- **Type** : ADT^A11
- **Trigger event** : A11
- **Type mouvement** : cancel_admit

**Messages attendus** :
- HL7v2 : `ADT^A11` (Cancel admit/visit)

## 🔍 Points de Validation

### Pour chaque message HL7v2 :

1. **Structure** :
   - ✅ Présence des segments obligatoires : MSH, EVN, PID, PV1
   - ✅ Segment ZBE présent (spécifique IHE PAM France)
   - ✅ Délimiteurs corrects : | ^ ~ \ &

2. **Identifiants** :
   - ✅ PID-3 : IPP patient (12 chiffres, préfixe 9)
   - ✅ ZBE-1 : NDA dossier (9 chiffres, préfixe 9)
   - ✅ PV1-19 : VN venue (si applicable)

3. **Mapping Vocabulaire PV1-2** :
   - ✅ `I` (Inpatient) ↔ `IMP` (FHIR)
   - ✅ `O` (Outpatient) ↔ `AMB` (FHIR)
   - ✅ `E` (Emergency) ↔ `EMER` (FHIR)

4. **Validation IHE PAM** :
   - ✅ Message valide selon spécifications IHE PAM France
   - ✅ Cardinalités respectées
   - ✅ Champs obligatoires présents

### Pour les messages FHIR :

1. **Structure Bundle** :
   - ✅ resourceType: "Bundle"
   - ✅ type: "transaction" ou "collection"
   - ✅ entry[] contient les ressources

2. **Ressources** :
   - ✅ Patient avec identifiers
   - ✅ Encounter avec class (IMP/AMB/EMER)
   - ✅ Location si applicable

3. **Conformité FHIR R4 FR** :
   - ✅ Extensions françaises si nécessaires
   - ✅ Identifiants structurés

## 📊 Commandes de Validation

### Validation après création
```bash
# Valider tous les messages
python validate_messages.py

# Voir les 10 derniers messages
python validate_messages.py --recent 10
```

### Inspection de la base de données
```bash
# Via Python
python -c "
from sqlmodel import Session, select
from app.db import engine
from app.models_shared import MessageLog

with Session(engine) as session:
    count = len(session.exec(select(MessageLog)).all())
    print(f'Total messages: {count}')
"
```

## 🎓 Matrice de Test Complète

| Entité | Type | encounter_class | PV1-2 | Event | Statut |
|--------|------|----------------|-------|-------|---------|
| Patient | Homme | - | - | - | ⬜ À tester |
| Patient | Femme | - | - | - | ⬜ À tester |
| Patient | Autre | - | - | - | ⬜ À tester |
| Dossier | Hospitalisé | IMP | I | A01 | ⬜ À tester |
| Dossier | Externe | AMB | O | A04 | ⬜ À tester |
| Dossier | Urgence | EMER | E | A01 | ⬜ À tester |
| Mouvement | Transfert | - | - | A02 | ⬜ À tester |
| Mouvement | Sortie | - | - | A03 | ⬜ À tester |
| Mouvement | Mise à jour | - | - | A08 | ⬜ À tester |
| Mouvement | Annulation | - | - | A11 | ⬜ À tester |

## 🔧 Dépannage

### Aucun message généré
- Vérifier que les listeners d'événements sont actifs (logs serveur)
- Vérifier que `entity_events.py` est chargé
- Redémarrer le serveur FastAPI

### Erreurs de validation
- Vérifier les logs du validateur PAM
- Vérifier la présence des segments obligatoires
- Vérifier les cardinalités

### Mappings incorrects
- Vérifier la table `VocabularyMapping`
- Vérifier `vocabulary_translate.py`
- Vérifier les fonctions `map_code()` et `reverse_map_code()`

## ✅ Checklist de Validation Finale

- [ ] Tous les types de patients créés
- [ ] Tous les types de dossiers créés
- [ ] Tous les types de mouvements testés
- [ ] Messages HL7v2 validés IHE PAM
- [ ] Messages FHIR générés et valides
- [ ] Mappings de vocabulaire corrects (PV1-2 ↔ encounter_class)
- [ ] Identifiants timestamp corrects (12 et 9 chiffres avec préfixe 9)
- [ ] Tous les segments obligatoires présents
- [ ] Validation PAM réussie pour tous les messages

Bonne chance pour les tests ! 🚀
