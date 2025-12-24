# Rapport d'implémentation des intervalles temporels réalistes

## Résumé

✅ **IMPLÉMENTÉ AVEC SUCCÈS**: Système d'intervalles temporels réalistes pour les scénarios hospitaliers

### 🎯 Objectif atteint

> *"dans les scénarios, je veux aussi que les dates soient changées à la volée et ca doit refletait des encart de temps entre les messages qui soit realistes pour un passage à l'hopital, en fonction du scenario"*

## 📊 Statistiques

- **20 scénarios** analysés et configurés
- **19 scénarios** nouvellement configurés avec des timings réalistes
- **1 scénario** déjà configuré (Materialized IHE hospitSimple)
- **100% de succès** dans l'application des configurations

## 🏥 Types de workflows hospitaliers détectés

### 1. Emergency Admission (Urgences)

- **Scénarios**: 1 (Materialized IHE hospitSimple)
- **Caractéristiques**:
  - Séquence: A05 → A01 → A02 → A02 → A03
  - Ancrage: admission_minus_days (1 jour)
  - Jitter: 2-15 minutes
  - **Intervalles réalistes**: Consultation → Admission rapide (30min-2h), Transferts fréquents

### 2. Planned Admission (Hospitalisation programmée)

- **Scénarios**: 2,3,5,8,9,10,11,12,13,14,15,16,17,18,19,20 (15 scénarios)
- **Caractéristiques**:
  - Codes: A28, A31, A01, A11 (admissions programmées)
  - Ancrage: admission_minus_days (2 jours)
  - Jitter: 10-45 minutes
  - **Intervalles réalistes**: Délais plus longs entre événements (1-5 jours)

### 3. Consultation Only (Consultations externes)

- **Scénarios**: 4,6 (2 scénarios)
- **Caractéristiques**:
  - Codes: A05, A04 (consultations/arrivées)
  - Ancrage: now (jour même)
  - Jitter: 5-20 minutes
  - **Intervalles réalistes**: Consultation dans la journée (15min-1h30)

### 4. Long Stay (Séjours longs)

- **Scénarios**: 7 (1 scénario)
- **Caractéristiques**:
  - Codes: A06 (changements d'unité)
  - Ancrage: admission_minus_days (7 jours)
  - Jitter: 30-120 minutes  
  - **Intervalles réalistes**: Longs intervalles entre transferts (2-7 jours)

## 🔧 Implémentation technique

### Nouveaux composants créés

1. **`app/services/scenario_realistic_timeplan.py`**
   - Détection automatique de workflows hospitaliers
   - Configurations prédéfinies pour chaque type de parcours
   - Générateur de `TimeShiftConfig` adaptés

2. **Endpoints API**
   - `POST /scenarios/{id}/suggest-realistic-timing` : Analyse et suggestion
   - `POST /scenarios/{id}/apply-realistic-timing` : Application automatique

3. **Interface utilisateur**
   - Bouton "Timing réaliste" dans les détails de scénario
   - Confirmation avec analyse du workflow détecté

4. **Scripts d'automatisation**
   - `configure_realistic_timing_bulk.py` : Configuration en masse
   - `test_realistic_timing_demo.py` : Tests et démonstrations

### Intégration avec l'existant

- ✅ **Compatible** avec le système `scenario_timeplan.py` existant
- ✅ **Détection automatique** vs configuration manuelle
- ✅ **Fallback intelligent** : utilise `message_type` si `payload` vide
- ✅ **Préservation** des intervalles relatifs entre messages

### 🆕 Identités patient réalistes

- **Service dédié** : `app/services/scenario_identity_generator.py` génère à la volée un profil patient complet (nom, adresse, NIR, téléphones, etc.) basé sur des jeux de données français.
- **Injection HL7** : `_send_hl7_step` applique automatiquement le profil sur les segments PID avant la régénération des identifiants IPP/NDA, garantissant une cohérence multi-étapes.
- **Réutilisation UI/API** : `send_step`, `send_scenario` et les envois unitaires depuis l’interface utilisent tous la même identité par exécution, alignant scénarios, captures et démonstrations.
- **Tests unitaires** : `tests/test_scenario_identity_generator.py` valide la reproductibilité (seed) et l’injection propre des champs sensibles.

## 📈 Bénéfices apportés

### Pour les tests réalistes

- **Timestamps cohérents** avec les workflows hospitaliers
- **Variabilité contrôlée** via jitter adapté au contexte
- **Ancrage temporel** intelligent (urgence = récent, séjour long = ancien)

### Pour l'utilisateur

- **Configuration automatique** : plus de réglage manuel fastidieux
- **Workflows reconnus** : le système comprend le contexte médical
- **Application en masse** : configuration de 19 scénarios en une commande
- **Identités fraîches** : chaque exécution de scénario bénéficie d’une identité unique et réaliste, sans préparation manuelle.

### Pour le développement  

- **Tests plus représentatifs** de la réalité hospitalière
- **Détection de bugs temporels** dans des conditions réalistes
- **Validation** des interfaces avec des données temporelles cohérentes
- **Couverture renforcée** : le générateur dispose de tests dédiés pour prévenir les régressions sur la structure des segments PID.

## 🎪 Démonstration

```bash
# Voir les suggestions pour tous les scénarios
python test_realistic_timing_demo.py

# Appliquer la configuration automatique
python configure_realistic_timing_bulk.py --apply

# Test individuel via API
curl -X POST "http://localhost:8000/scenarios/1/suggest-realistic-timing" | jq .

# Interface web avec bouton "Timing réaliste"
http://localhost:8000/scenarios/1
```

## ✅ Validation complète des scénarios enrichis

1. **Lancer un scénario HL7 complet** via l'UI (bouton "Envoyer" sur la fiche scénario) ou `cli.py scenarios send` afin de propager l'identité réaliste nouvellement injectée.
2. **Surveiller le système destinataire** (serveur MLLP ou EMR de test) et les `MessageLog` locaux pour confirmer l'acceptation des champs PID enrichis (noms, adresses, NIR, PID-32...).
3. **Comparer une trace avant/après** en exportant le message HL7 depuis `MessageLog` pour vérifier que les identités restent cohérentes sur toutes les étapes d'une même exécution.
4. **Archiver le résultat** (ACK HL7 AA/AE + captures d'écran destinataire) dans `ROUNDTRIP_SESSION_SUMMARY.md` afin de tracer l'impact de ces données réalistes sur les workflows aval.

## 🔮 Exemples d'intervalles générés

### Urgence (Scénario 1)

```text
A05 (Consultation urgence) 
  ↓ 30min-2h
A01 (Admission) 
  ↓ 1h-4h  
A02 (Transfert service) 
  ↓ 2h-8h
A02 (Autre transfert)
  ↓ 4h-12h
A03 (Sortie)
```

### Hospitalisation programmée (Scénarios 2,3,5...)

```text
A01 (Admission programmée)
  ↓ 4h-12h
A02 (Transfert éventuel) 
  ↓ 1-5 jours
A03 (Sortie)
```

### Consultation (Scénarios 4,6)

```text
A04 (Arrivée)
  ↓ 15min-1h
A05 (Consultation)
  ↓ 30min-1h30  
A08 (Départ)
```

## ✨ Résultat final

Le système génère maintenant automatiquement des **dates et heures réalistes** qui reflètent fidèlement les **écarts de temps authentiques** entre les messages d'un passage hospitalier, en fonction du type de scénario détecté.

**Mission accomplie !** 🎉
