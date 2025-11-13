# ✅ A06/A07 Réception & Validation - Implémentation Complète

**Date**: 13 novembre 2025  
**Status**: ✅ **IMPLÉMENTÉ ET VALIDÉ**

---

## 📋 Résumé des Changements

### 🔧 1. Enrichissement `import_hl7_mouvement.py`

**3 nouvelles fonctions ajoutées:**

#### `extract_nature_from_hl7(pv1, zbe)`
- Extrait la nature (S/H/O/U) du message HL7
- **Priorité 1**: ZBE-2 (PAM France standard)
- **Priorité 2**: PV1-2 (patient class HL7 standard)
  - I → H (Inpatient)
  - O,E → S (Outpatient/Emergency)

#### `validate_a06_a07_coherence(entity, hl7_code, session)`
- Valide la sémantique A06/A07 vs historique
- **A06 (S→H)**: Vérifie qu'il existe mouvement S antérieur
- **A07 (H→S)**: Vérifie qu'il existe mouvement H antérieur
- Retourne message d'erreur si incohérent

#### `import_mouvement_from_hl7(hl7_message, venue, session)` - ENRICHI
- ✅ Extrait maintenant la `nature` du mouvement
- ✅ Valide cohérence A06/A07
- ✅ Log warning si problème sémantique

**Impact**: À la réception, le mouvement est maintenant créé avec sa nature correcte!

---

### 🔍 2. Validation Sémantique `pam_validation.py`

**Nouvelle fonction:**

#### `validate_pam_semantics(hl7_message, venue_id=None, session=None)`
- Validation **supplémentaire** (en plus de la structure HL7)
- Vérifie cohérence A06/A07 avec historique de mouvements
- Retourne: `{is_valid, level, issues[]}`
- ⚠️ **Important**: Ne **rejette pas** (level="warn"), permet révision manuelle

**Cas validés:**
```
A06 reçu + historique S avant → OK
A06 reçu + NO historique → WARNING
A06 reçu + historique H avant → WARNING
A07 reçu + historique H avant → OK
A07 reçu + historique S avant → WARNING
```

---

## ✅ Tests - 13/13 PASSÉS

### Suite de Réception (test_a06_a07_reception_comprehensive.py)

| Test | Scenario | Status |
|------|----------|--------|
| `test_a06_with_correct_history` | A06 reçu avec mouvement S avant | ✅ PASSED |
| `test_a06_without_history` | A06 reçu SANS historique | ✅ PASSED |
| `test_a07_with_correct_history` | A07 reçu avec mouvement H avant | ✅ PASSED |
| `test_extract_from_zbe` | Nature extraite de ZBE-2 | ✅ PASSED |
| `test_extract_from_pv1_fallback` | Nature extraite de PV1-2 (fallback) | ✅ PASSED |
| `test_a06_validation_ok` | A06 valide sémantiquement | ✅ PASSED |
| `test_full_a06_workflow` | Workflow complet import→validation | ✅ PASSED |

### Suites Existantes (pas de régression)

| Suite | Tests | Status |
|-------|-------|--------|
| test_ihms_workflow.py | 1 | ✅ PASSED |
| test_validation_details.py | 1 | ✅ PASSED |
| test_ihe_pam_movements.py | 1 | ✅ PASSED |
| test_a06_a07_auto_detection.py | 3 | ✅ PASSED |

**Total: 13 tests, 0 failures** ✅

---

## 🔄 Flux Complet A06/A07

### RÉCEPTION
```
HL7 ADT^A06 reçu
         ↓
    import_hl7_mouvement()
         ├─ Parse MSH/EVN/PID/PV1/ZBE
         ├─ Extrait type="ADT^A06"
         ├─ Extrait nature depuis ZBE-2 ou PV1-2 ✅ (NEW)
         └─ Valide cohérence A06/A07 ✅ (NEW)
              └─ Log warning si incohérent
         ↓
    Mouvement créé avec nature="H" ✅ (NOUVEAU CHAMP)
    
Puis:
         ↓
    validate_pam_semantics() ✅ (NEW)
         └─ Vérifie histoire vs transition
         └─ Niveau: ok/warn (jamais fail)
```

### CRÉATION (depuis UI/API)
```
Créer Mouvement(nature="H") manuellement
         ↓
    emit_on_create()
         ├─ detect_a06_a07_from_history()
         │   └─ Trouve S avant? → A06 ✅
         └─ Sinon → A01
         ↓
    HL7 généré avec bon event_code
```

### ÉMISSION
```
Mouvement créé → HL7 généré avec A06/A07 corrects
         ↓
    validate_pam() → vérifie structure HL7 ✅
         ↓
    validate_pam_semantics() → vérifie cohérence ✅
```

---

## 📊 Avant vs Après

| Aspect | AVANT | APRÈS |
|--------|-------|-------|
| **Réception A06/A07** | Crée mouvement, pas de nature | ✅ Extrait nature |
| **Validation sémantique** | ❌ Pas de vérification | ✅ Valide historique |
| **Cohérence S↔H** | ❌ Accepte n'importe quoi | ⚠️ Warn si incohérent |
| **Détection création** | ✅ Auto-détecte | ✅ Auto-détecte (unchanged) |
| **Tests** | 6 tests | **13 tests** ✅ |

---

## 🚀 Impact Utilisateur

### Scénario 1: Réception de médecins externes
```
Reçu: A06 (externe → hospitalisé)
Avant: ❓ Nature inconnue
Après: ✅ Nature="H" extraite, validée, stockée
```

### Scénario 2: Réception de mouvement incohérent
```
Reçu: A06 sans historique externe (S)
Avant: ✅ Accepte (mais incohérent!)
Après: ⚠️ Warn "A06 reçu mais pas de passage S avant"
       → Signale problème sans bloquer
```

### Scénario 3: Création depuis IHM
```
Utilisateur: "Patient admission hospitalisation"
Avant: Crée A01
Après: ✅ Auto-détecte A06 si passage S existe
```

---

## 📚 Fichiers Modifiés

| Fichier | Changes | Impact |
|---------|---------|--------|
| `app/services/import_hl7_mouvement.py` | +3 fonctions, +nature extraction | Réception enrichie |
| `app/services/pam_validation.py` | +validate_pam_semantics() | Validation sémantique |
| `tests/test_a06_a07_reception_comprehensive.py` | NEW (+7 tests) | Coverage réception |

**Total**: 2 fichiers modifiés, 1 nouveau test file, 0 fichiers supprimés

---

## ✨ Prochaines Étapes Optionnelles

### Priorité 1 (Non-bloquant)
- [ ] Ajouter champs dans Mouvement pour warning flags
  - `has_validation_warning: bool`
  - `validation_warning_msg: str`

### Priorité 2 (Amélioration)
- [ ] Dashboard pour afficher les mouvements avec warnings
- [ ] API endpoint pour rejeter manuellement un mouvement

### Priorité 3 (Longe terme)
- [ ] Créer implicitement mouvement(nature=S) si A06 reçu sans historique
- [ ] Integration tests avec vraies bases de données

---

## 🔐 Garanties & Limitations

### ✅ Garanti
- Nature extraite correctement de ZBE-2 ou PV1-2
- A06/A07 validé sémantiquement si historique existe
- Messages incohérents loggés avec warning
- Pas de régression sur tests existants
- Tous les 13 tests passent

### ⚠️ À Connaître
- Validation sémantique nécessite venue_id + session (optionnels)
- Si contexte DB pas dispo → validation structural uniquement
- Messages incohérents **acceptés** (warn, pas fail)
  - Design: Permet override humain si besoin

---

## 📞 Support

**Questions sur A06/A07 réception:**
1. Vérifier `mouvement.nature` est extrait (S/H)
2. Exécuter `validate_pam_semantics()` pour checks
3. Consulter logs pour avertissements
4. Vérifier historique mouvement sur même venue

**Tests à lancer:**
```bash
# Tous les tests réception
pytest tests/test_a06_a07_reception_comprehensive.py -v

# Ensemble complet
pytest tests/test_ihms_workflow.py \
       tests/test_validation_details.py \
       tests/test_ihe_pam_movements.py \
       tests/test_a06_a07_auto_detection.py \
       tests/test_a06_a07_reception_comprehensive.py -v
```

---

**Version**: 1.0  
**Date Implémentation**: 13 novembre 2025  
**Status**: ✅ Production Ready  
**Test Coverage**: 13/13 passing
