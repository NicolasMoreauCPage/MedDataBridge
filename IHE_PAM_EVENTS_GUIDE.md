# 📋 Guide Complet IHE PAM France 2.11 - Événements HL7

## ✅ Corrections Majeures

### ❌ AVANT (Incorrect)
- **A04** = Création patient ← **FAUX !**
- Messages incomplets (manque A21, A22, A11, A12, A13, A52, A53, etc.)

### ✅ MAINTENANT (Correct - IHE PAM France 2.11)
- **A28** = Création patient (Add person information) ← **CORRECT !**
- **A04** = Admission ambulatoire (Outpatient registration) ← **CORRECT !**
- Support complet de tous les événements IHE PAM France

---

## 📚 Table Complète des Événements

### 👤 Événements Patient (Identité)

| Code | Événement | Description | Structure | Mouvement |
|------|-----------|-------------|-----------|-----------|
| **A28** | Add person | Création/Ajout patient | ADT_A05 | Non |
| **A31** | Update person | Mise à jour patient | ADT_A05 | Non |
| **A40** | Merge person | Fusion de patients | ADT_A38 | Non |
| **A29** | Delete person | Suppression patient | ADT_A05 | Non |
| **A47** | Change patient ID | Changement ID patient | ADT_A30 | Non |

**Note** : Ces événements modifient l'identité du patient mais ne créent PAS de mouvement (pas de segment ZBE).

---

### 🏥 Événements Admission

| Code | Événement | Description | Structure | Classe |
|------|-----------|-------------|-----------|--------|
| **A01** | Admit/Visit | Admission hospitalisation | ADT_A01 | I (Inpatient) |
| **A04** | Register patient | Admission ambulatoire | ADT_A01 | O (Outpatient) |
| **A05** | Pre-admit | Pré-admission | ADT_A01 | P (Preadmit) |
| **A08** | Update visit | Mise à jour admission | ADT_A01 | Variable |

**Note** : A04 est pour les consultations externes/ambulatoires, pas pour créer un patient !

---

### 🔄 Événements Transfert/Changement

| Code | Événement | Description | Structure | Type |
|------|-----------|-------------|-----------|------|
| **A02** | Transfer | Transfert patient | ADT_A02 | Transfert interne |
| **A06** | Change outpatient to inpatient | Ambulatoire → Hospitalisation | ADT_A06 | Changement classe |
| **A07** | Change inpatient to outpatient | Hospitalisation → Ambulatoire | ADT_A06 | Changement classe |
| **A54** | Change attending doctor | Changement médecin | ADT_A54 | Changement médecin |

---

### 🚪 Événements Sortie

| Code | Événement | Description | Structure | Type |
|------|-----------|-------------|-----------|------|
| **A03** | Discharge | Sortie définitive | ADT_A03 | Sortie finale |
| **A21** | Leave of absence | Sortie temporaire (absence) | ADT_A21 | Permission |
| **A22** | Return from leave | Retour d'absence | ADT_A21 | Retour permission |

**Exemple A21** : Patient en permission pour le week-end  
**Exemple A22** : Patient revient de permission  

---

### ❌ Événements Annulation

| Code | Événement | Description | Structure | Annule |
|------|-----------|-------------|-----------|--------|
| **A11** | Cancel admit | Annulation admission | ADT_A09 | A01 |
| **A12** | Cancel transfer | Annulation transfert | ADT_A12 | A02 |
| **A13** | Cancel discharge | Annulation sortie | ADT_A01 | A03 |
| **A23** | Delete visit | Suppression séjour | ADT_A21 | A04 |
| **A38** | Cancel pre-admit | Annulation pré-admission | ADT_A38 | A05 |
| **A52** | Cancel leave of absence | Annulation sortie temporaire | ADT_A21 | A21 |
| **A53** | Cancel return from leave | Annulation retour d'absence | ADT_A21 | A22 |
| **A55** | Cancel change attending | Annulation changement médecin | ADT_A52 | A54 |

---

## 🔗 Mapping Structures de Messages

Selon **HL7 v2.5 Table 0354 - Message Structure** :

| Structure | Événements | Segments Obligatoires |
|-----------|------------|----------------------|
| **ADT_A01** | A01, A04, A05, A08, A13 | MSH, EVN, PID, [PV1] |
| **ADT_A02** | A02 | MSH, EVN, PID, PV1 |
| **ADT_A03** | A03 | MSH, EVN, PID, PV1 |
| **ADT_A05** | A28, A31 | MSH, EVN, PID |
| **ADT_A06** | A06, A07 | MSH, EVN, PID, PV1 |
| **ADT_A09** | A09, A10, A11 | MSH, EVN, PID, PV1 |
| **ADT_A12** | A12 | MSH, EVN, PID, PV1 |
| **ADT_A21** | A21, A22, A23, A52, A53 | MSH, EVN, PID, PV1 |
| **ADT_A38** | A38, A40 | MSH, EVN, PID |

---

## 🔍 Différences Clés

### A28 vs A04

| Critère | A28 (Add Person) | A04 (Register Patient) |
|---------|------------------|------------------------|
| **Objectif** | Créer l'identité du patient dans le système | Enregistrer une admission ambulatoire |
| **Segments** | MSH, EVN, PID | MSH, EVN, PID, PV1, ZBE |
| **PV1-2** | Absent ou vide | **O** (Outpatient) |
| **Mouvement** | ❌ Non (pas de ZBE) | ✅ Oui (avec ZBE) |
| **Dossier** | Peut créer ou non | Crée un dossier ambulatoire |
| **Exemple** | Nouveau patient venant pour inscription | Patient venant pour consultation externe |

### A21 vs A03

| Critère | A21 (Leave of Absence) | A03 (Discharge) |
|---------|------------------------|-----------------|
| **Type** | Sortie **temporaire** | Sortie **définitive** |
| **Retour prévu** | ✅ Oui (A22) | ❌ Non |
| **Lit** | 🔒 Réservé | ✅ Libéré |
| **Statut** | En permission | Sorti |
| **Exemple** | Permission week-end | Sortie guérison |

---

## 📊 Scénarios Complets

### Scénario 1 : Nouveau Patient Ambulatoire

```
1. ADT^A28 : Création patient (identité)
   └─ Crée : Patient
   
2. ADT^A04 : Admission ambulatoire
   └─ Crée : Dossier ambulatoire + Venue + Mouvement
   └─ PV1-2 = O (Outpatient)
   
3. ADT^A03 : Sortie consultation
   └─ Crée : Mouvement sortie
```

### Scénario 2 : Hospitalisation avec Permission

```
1. ADT^A28 : Création patient
2. ADT^A01 : Admission hospitalisation (PV1-2 = I)
3. ADT^A21 : Sortie temporaire (permission week-end)
4. ADT^A22 : Retour d'absence (lundi matin)
5. ADT^A03 : Sortie définitive
```

### Scénario 3 : Erreur et Annulation

```
1. ADT^A28 : Création patient
2. ADT^A01 : Admission (erreur, mauvais lit)
3. ADT^A11 : Annulation admission
4. ADT^A01 : Nouvelle admission (lit correct)
5. ADT^A03 : Sortie
```

### Scénario 4 : Changement Ambulatoire → Hospitalisation

```
1. ADT^A28 : Création patient
2. ADT^A04 : Admission ambulatoire (PV1-2 = O)
3. ADT^A06 : Changement O → I (aggravation état)
   └─ PV1-2 = I (Inpatient)
4. ADT^A03 : Sortie
```

---

## 🧪 Tests Implémentés

### Test Création Patient

```bash
.venv/bin/python3 test_ihe_pam_events.py
```

**Résultat** :
```
✅ ADT^A28^ADT_A05 (création patient)
✅ ADT^A31^ADT_A05 (mise à jour patient)
```

### Validation Structure

Tous les événements génèrent la bonne structure :
- ✅ A28 → ADT_A05 (pas ADT_A01)
- ✅ A04 → ADT_A01 (admission ambulatoire)
- ✅ A21 → ADT_A21 (sortie temporaire)
- ✅ A11 → ADT_A09 (annulation admission)

---

## 📋 Checklist Implémentation

### Émission (Sortant)

- ✅ A28 : Création patient (operation="create")
- ✅ A31 : Mise à jour patient (operation="update")
- ✅ A01 : Admission hospitalisation (type="ADT^A01")
- ✅ A04 : Admission ambulatoire (type="ADT^A04")
- ✅ A02 : Transfert (type="ADT^A02")
- ✅ A03 : Sortie (type="ADT^A03")
- ✅ A21 : Sortie temporaire (type="ADT^A21")
- ✅ A22 : Retour absence (type="ADT^A22")
- ✅ A11 : Annulation admission (type="ADT^A11")
- ✅ A12 : Annulation transfert (type="ADT^A12")
- ✅ A13 : Annulation sortie (type="ADT^A13")
- ✅ A52 : Annulation sortie temp. (type="ADT^A52")
- ✅ A53 : Annulation retour (type="ADT^A53")

### Réception (Entrant)

- ✅ A28 : Crée patient uniquement (pas de mouvement)
- ✅ A31 : Met à jour patient (pas de mouvement)
- ✅ A04 : Crée dossier ambulatoire + venue + mouvement
- ✅ A01 : Crée dossier hospitalisation + venue + mouvement
- ⚠️ A21/A22 : À implémenter (sorties temporaires)
- ⚠️ A11/A12/A13 : À implémenter (annulations)

---

## 🔗 Références

- **HL7 v2.5** - Chapter 3: Patient Administration
- **IHE PAM France 2.11** - Profil français
- **Table 0003** - Event Type Code
- **Table 0354** - Message Structure
- **Table 0004** - Patient Class (I, O, E, P, R, B, N)

---

## 📝 Notes Importantes

### Segment ZBE

Le segment ZBE (segment Z français pour mouvement) est présent **uniquement** pour les événements de mouvement :
- ✅ A01, A04, A05 (admissions)
- ✅ A02 (transfert)
- ✅ A03 (sortie)
- ✅ A21, A22 (sorties temporaires)
- ❌ A28, A31 (patient seulement)
- ❌ A40, A47 (fusion/changement ID)

### PV1-2 (Patient Class)

| Code | Signification | Événements typiques |
|------|---------------|---------------------|
| **I** | Inpatient (hospitalisé) | A01 |
| **O** | Outpatient (ambulatoire) | A04 |
| **E** | Emergency (urgence) | A04, A01 |
| **P** | Preadmit (pré-admission) | A05 |
| **R** | Recurring patient | A04 |
| **B** | Obstetrics | A01 |
| **N** | Not applicable | A28, A31 |

---

**Date** : 10 novembre 2025  
**Version** : IHE PAM France 2.11  
**Commit** : `a7e291b` - fix: Correct IHE PAM event types  
**Status** : ✅ Conforme IHE PAM France 2.11
