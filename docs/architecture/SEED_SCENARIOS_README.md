# Seed des Scénarios d'Intégration HL7/HPRIM

Ce répertoire contient les scripts pour initialiser une base de données avec tous les scénarios de test d'intégration HL7 IHE PAM et HPRIM XML.

## 📁 Fichiers

- `scenarios_seed_data.json` - Données de seed exportées depuis la base de données actuelle
- `seed_scenarios_from_db.py` - Script principal pour importer les scénarios
- `demo_seed_usage.py` - Script de démonstration (utilise une remise à zéro destructive)

## 🚀 Utilisation

### Initialisation d'une nouvelle base de données

```bash
# Copiez les fichiers dans votre projet
cp scenarios_seed_data.json seed_scenarios_from_db.py /chemin/vers/votre/projet/

# Exécutez le script de seed
cd /chemin/vers/votre/projet/
python seed_scenarios_from_db.py
```

### Fonctionnalités du script

- ✅ **Détection automatique des doublons** : Le script vérifie si les scénarios existent déjà
- ✅ **Import sécurisé** : Utilise des transactions SQLAlchemy pour garantir l'intégrité
- ✅ **Vérification d'intégrité** : Compare les données seed avec la base de données
- ✅ **Gestion d'erreurs** : Signale les problèmes sans interrompre l'import complet

## 📊 Contenu du seed

- **159 scénarios** au total
- **99 scénarios HL7 IHE PAM** (mouvements patients ADT)
- **60 scénarios HPRIM XML** (cotations d'actes médicaux)
- **648 étapes** séquentielles (messages HL7 + XML HPRIM)

### Catégories de scénarios

#### HL7 IHE PAM
- Mouvements patients (admissions, sorties, transferts)
- Urgences et hospitalisations
- Identités et modifications patient
- Maternité et néonatalogie
- Mutations et changements de statut

#### HPRIM XML
- Création d'actes CCAM (Classification Commune des Actes Médicaux)
- Création d'actes NGAP (Nomenclature Générale des Actes Professionnels)
- Création d'UCD (Unités Commune de Dispensation)
- Modifications et suppressions d'actes
- Scénarios complexes multi-étapes

## 🔧 Structure des données

### InteropScenario
```python
{
    "key": "hl7_admission_simple",           # Clé unique
    "name": "Admission Simple",              # Nom lisible
    "description": "Scénario d'admission...", # Description
    "category": "IHE_PAM",                   # Catégorie (IHE_PAM|HPRIM_COTATION)
    "protocol": "HL7",                       # Protocole (HL7|MIXED)
    "source_path": "/path/to/file.hl7",       # Chemin source (optionnel)
    "tags": "pam,hl7,integration,adt"        # Tags pour recherche
}
```

### InteropScenarioStep
```python
{
    "order_index": 1,                        # Ordre d'exécution
    "name": "HL7 A01",                       # Nom de l'étape
    "description": "Message d'admission",     # Description
    "message_format": "hl7",                  # Format (hl7|xml)
    "message_type": "ADT^A01",                # Type de message
    "payload": "MSH|^~\\&|..."               # Contenu du message
}
```

## 🛡️ Sécurité et intégrité

- Le script utilise des transactions SQLAlchemy pour garantir l'atomicité
- Vérification automatique des doublons par clé unique
- Rollback automatique en cas d'erreur sur un scénario
- Validation de l'intégrité des données après import

## 📝 Personnalisation

Pour modifier le seed :

1. **Ajouter des scénarios** : Éditez `scenarios_seed_data.json`
2. **Modifier la logique** : Éditez `seed_scenarios_from_db.py`
3. **Exporter depuis une autre BDD** : Utilisez le script d'export dans `seed_scenarios_from_db.py`

## 🔍 Dépannage

### Le script ne trouve pas le fichier JSON
- Vérifiez que `scenarios_seed_data.json` est dans le même répertoire
- Vérifiez les permissions de lecture

### Erreur de base de données
- Vérifiez que la base de données est accessible
- Vérifiez que les tables `interopscenario` et `interopscenariostep` existent
- Consultez les logs d'erreur détaillés

### Import partiel
- Le script continue même en cas d'erreur sur un scénario
- Vérifiez les logs pour identifier les scénarios problématiques
- Les scénarios déjà importés ne sont pas re-importés

## 📈 Métriques d'import

Après exécution réussie, le script affiche :
- Nombre de scénarios créés
- Nombre de scénarios ignorés (déjà existants)
- Nombre total d'étapes importées
- Résumé par catégorie (HL7/HPRIM)

---

**Note** : Ce seed est basé sur les données actuelles de la base de données au moment de l'export. Pour mettre à jour le seed avec de nouveaux scénarios, réexécutez le script d'export depuis une base de données à jour.