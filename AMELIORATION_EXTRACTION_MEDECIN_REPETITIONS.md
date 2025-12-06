# Amélioration de l'extraction médecin - Gestion des répétitions HL7

**Date** : 6 décembre 2025  
**Fichier modifié** : `app/services/medecin_extractor.py`  
**Objectif** : Capturer RPPS et ADELI simultanément depuis les messages avec répétitions multiples

---

## 🎯 Problème identifié

Dans les messages IHE PAM de l'archive, le champ **PV1-7** (Attending Doctor) contient souvent **plusieurs répétitions** séparées par `~`, chacune avec un type d'identifiant différent :

### Exemple de PV1-7 avec répétitions

```hl7
PV1||O|7700|R|||101005344^PICQUE^JEAN BAPTISTE^^^^^^ASIP-SANTE-PS&1.2.250.1.71.4.2.1&ISO^L^^^ADELI~10100534436^PICQUE^JEAN BAPTISTE^^^^^^ASIP-SANTE-PS&1.2.250.1.71.4.2.1&ISO^L^^^RPPS
```

**Structure décomposée** :
- **Répétition 1** : `101005344^PICQUE^JEAN BAPTISTE^^^^^^...^^^ADELI` → ADELI
- **Répétition 2** : `10100534436^PICQUE^JEAN BAPTISTE^^^^^^...^^^RPPS` → RPPS

### Comportement initial

L'ancienne version de `extract_medecin_from_pv1_7()` ne traitait que la **première répétition**, ce qui aboutissait à :
- ✅ ADELI capturé : 101005344
- ❌ RPPS ignoré : 10100534436

---

## 🔧 Solution implémentée

### Modification de la fonction `extract_medecin_from_pv1_7()`

**Changements clés** :

1. **Découpage des répétitions** :
   ```python
   repetitions = attending_doctor.split('~')
   ```

2. **Boucle sur toutes les répétitions** :
   ```python
   for xcn_str in repetitions:
       xcn_data = parse_xcn_field(xcn_str)
       rpps, adeli = identify_id_type(xcn_data['id_number'], xcn_data['assigning_authority'])
       
       # Accumuler RPPS et ADELI
       if rpps:
           medecin_data['rpps'] = rpps
       if adeli:
           medecin_data['adeli'] = adeli
   ```

3. **Accumulation des données** :
   - Les champs `rpps` et `adeli` sont remplis indépendamment
   - Le nom/prénom sont pris de la première occurrence non vide
   - Tous les identifiants sont conservés

### Fonction de mise à jour

La fonction `get_or_create_medecin()` existante **met automatiquement à jour** les champs manquants :

```python
if medecin:
    updated = False
    for key, value in medecin_data.items():
        if value and not current_value:
            setattr(medecin, key, value)
            updated = True
```

Cela permet de compléter le RPPS sur un médecin déjà existant avec seulement son ADELI.

---

## ✅ Résultats

### Avant amélioration

| Médecin | RPPS | ADELI |
|---------|------|-------|
| PICQUE | ❌ Absent | ✅ 101005344 |
| KENNOUCHE | ❌ Absent | ✅ 891020646 |
| MOUROT | ❌ Absent | ✅ 891018939 |

### Après amélioration

| Médecin | RPPS | ADELI |
|---------|------|-------|
| PICQUE | ✅ **10100534436** | ✅ 101005344 |
| KENNOUCHE | ✅ **10004414727** | ✅ 891020646 |
| MOUROT | ✅ **10002182102** | ✅ 891018939 |

**Taux de complétude** : 100% (3/3 médecins avec RPPS et ADELI)

---

## 📊 Impact

### Enrichissement des données

- **Avant** : Identifiant unique (ADELI ou RPPS)
- **Après** : Double identifiant (RPPS + ADELI)

### Avantages

1. **Interopérabilité accrue** : Les deux identifiants nationaux sont disponibles
2. **Conformité réglementaire** : RPPS obligatoire pour certains échanges
3. **Recherche facilitée** : Possibilité de retrouver un médecin par RPPS ou ADELI
4. **Qualité des données** : Pas de perte d'information

### Compatibilité

L'amélioration est **rétrocompatible** :
- Les messages avec une seule répétition fonctionnent toujours
- Les messages sans médecin sont gérés correctement
- Les médecins existants sont mis à jour sans doublon

---

## 🧪 Tests

### Test de régression

```bash
.venv/bin/python3 import_medecins_from_pam_archive.py
```

**Résultats** :
- ✅ 359 messages traités
- ✅ 63 messages avec médecin
- ✅ 3 médecins uniques identifiés
- ✅ 3 RPPS capturés (100%)
- ✅ 3 ADELI capturés (100%)
- ✅ Aucun doublon créé

---

## 📝 Format HL7 - Répétitions

### Structure générale

Le séparateur de répétitions HL7 est `~` (tilde). Un champ peut contenir plusieurs valeurs :

```
Field~Repetition1~Repetition2~Repetition3
```

### Cas d'usage dans PV1-7

Les systèmes peuvent envoyer :
- **Plusieurs identifiants** : RPPS + ADELI + Numéro interne
- **Plusieurs médecins** : Médecin traitant + Médecin référent
- **Plusieurs rôles** : Médecin responsable + Médecin prescripteur

Notre implémentation traite le cas **multiple identifiants pour un même médecin**.

---

## 🔄 Flux de traitement

```
Message HL7
    ↓
Extraction PV1-7
    ↓
Split sur '~' → [Répétition1, Répétition2, ...]
    ↓
Pour chaque répétition:
    ↓
    Parse XCN (ID^Nom^Prénom^...^AuthorityType)
    ↓
    Identification RPPS/ADELI (longueur + authority)
    ↓
    Accumulation dans medecin_data
    ↓
get_or_create_medecin()
    ↓
    Recherche par RPPS → ADELI → Nom
    ↓
    Si trouvé: Mise à jour champs manquants
    Si non trouvé: Création
    ↓
MedecinResponsable complet (RPPS + ADELI)
```

---

## 🚀 Prochaines améliorations possibles

1. **Support des rôles multiples** : Parser `ROL` segment pour distinguer les rôles
2. **Historique des identifiants** : Tracker les changements RPPS/ADELI dans le temps
3. **Validation RPPS** : Vérifier la validité via l'annuaire national
4. **Numéros internes** : Capturer aussi les identifiants locaux des établissements

---

## 📄 Fichiers impactés

- ✅ `app/services/medecin_extractor.py` : Fonction `extract_medecin_from_pv1_7()` modifiée
- ✅ `import_medecins_from_pam_archive.py` : Script de test et validation
- ✅ `RAPPORT_IMPORT_MEDECINS_PAM_EJ5.md` : Rapport mis à jour avec RPPS

---

## 🎓 Enseignements

### Ce qui a bien fonctionné

- ✅ Détection automatique RPPS/ADELI par longueur (9 vs 11 chiffres)
- ✅ Logique de mise à jour des champs manquants sans doublon
- ✅ Gestion robuste des répétitions HL7

### Points d'attention

- ⚠️ Assumer que toutes les répétitions concernent le **même médecin** (même nom)
- ⚠️ Ne pas écraser un identifiant existant par un nouveau (conservation prioritaire)
- ⚠️ Logging important pour tracer les choix d'identification

---

**Conclusion** : L'amélioration permet maintenant de capturer **100% des identifiants disponibles** dans les messages HL7, maximisant la qualité et la complétude du référentiel des médecins responsables.
