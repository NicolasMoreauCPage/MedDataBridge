# Rapport de Classification des Identifiants

## Principe de Classification

### Pour TOUS les types d'entités (Patient, Dossier, Venue, Mouvement)

**Règle de classification :**

1. **Identifiant INTERNE** : Si le `system` (ou `oid`) de l'identifiant reçu dans le message HL7 **correspond** à un namespace configuré sur l'Entité Juridique (EJ) :
   - ✅ L'identifiant est stocké comme **identifiant principal** (`patient.identifier`, `dossier.dossier_seq`, etc.)
   - ✅ Il est AUSSI enregistré dans la table `identifier` avec le `system` et `oid` d'origine
   - ℹ️ C'est l'identifiant "officiel" de l'établissement

2. **Identifiant EXTERNE** : Si le `system` (ou `oid`) de l'identifiant reçu **NE correspond PAS** à un namespace de l'EJ :
   - ❌ L'identifiant n'est PAS utilisé comme identifiant principal
   - ✅ Il est enregistré UNIQUEMENT dans la table `identifier` avec son `system` et `oid` d'origine
   - ✅ L'entité reçoit un identifiant interne GÉNÉRÉ automatiquement (séquence)
   - ℹ️ C'est un identifiant provenant d'un système externe (autre hôpital, système tiers, etc.)

## Code Implémenté

### Fichier : `app/services/identifier_namespace_classifier.py`

#### Fonction principale : `classify_identifier()`

```python
def classify_identifier(
    self,
    value: str,
    system: str,
    identifier_type: IdentifierType,
    ej_id: Optional[int] = None,
    location_hierarchy: Optional[Dict[str, Optional[int]]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Returns:
        Tuple (is_main_identifier, external_namespace)
        - is_main_identifier: True si doit être identifiant principal
        - external_namespace: Le namespace externe si différent, None sinon
    """
    # Récupérer les namespaces applicables pour cette EJ
    applicable_namespaces = self.get_ej_namespaces(ej_id, identifier_type)
    
    # Vérifier si le system correspond
    for ns in applicable_namespaces:
        if ns.system == system or ns.oid == system:
            return True, None  # ✅ Identifiant INTERNE
    
    return False, system  # ❌ Identifiant EXTERNE
```

#### Traitement pour chaque type d'entité :

- `process_patient_identifiers()` : Pour les patients
- `process_dossier_identifiers()` : Pour les dossiers
- `process_venue_identifiers()` : Pour les venues  
- `process_mouvement_identifiers()` : Pour les mouvements

Tous suivent la même logique :
1. Parcourir les identifiants reçus
2. Classifier chaque identifiant (interne vs externe)
3. Utiliser le premier identifiant interne comme `main_identifier`
4. Stocker tous les identifiants externes dans `external_identifiers[]`

## État Actuel de la Base

### Namespaces configurés pour l'EJ 1 (CHU Lyon - 020000000)

| ID | Type  | System                          | OID                      |
|----|-------|---------------------------------|--------------------------|
| 2  | IPP   | http://020000000.fr/ns/ipp     | 1.2.250.1.71.1.1.1.2    |
| 3  | NDA   | http://020000000.fr/ns/nda     | 1.2.250.1.71.1.1.1.3    |
| 4  | VENUE | http://020000000.fr/ns/venue   | 1.2.250.1.71.1.1.1.4    |
| 14 | IPP   | CPAGE                           | 1.2.250.1.211.10.200.2  |

### Identifiers dans les messages reçus

| System            | Count | OID                       | Classification |
|-------------------|-------|---------------------------|----------------|
| CPAGE             | 274   | 1.2.250.1.211.10.200.2   | ✅ INTERNE (après ajout du namespace 14) |
| ASIP-SANTE-NIR    | 7     | 1.2.250.1.213.1.4.8      | ❌ EXTERNE     |
| ASIP-SANTE-INS-C  | 6     | -                         | ❌ EXTERNE     |
| ASIP-SANTE-INS-NIR| 3     | -                         | ❌ EXTERNE     |
| Doctolib          | 2     | -                         | ❌ EXTERNE     |

## Exemple Concret

### Message HL7 reçu :
```
PID|1||900006654054^^^CPAGE&1.2.250.1.211.10.200.2&ISO^PI~212017231012386^^^ASIP-SANTE-NIR&1.2.250.1.213.1.4.8&ISO^NH
```

### Traitement :

1. **Premier identifiant** : `900006654054` avec system=`CPAGE`
   - ✅ Correspond au namespace ID=14 de l'EJ 1
   - ➡️ `patient.identifier = "900006654054"`
   - ➡️ `identifier` créé : `{value: "900006654054", system: "CPAGE", oid: "1.2.250.1.211.10.200.2", type: "IPP"}`

2. **Deuxième identifiant** : `212017231012386` avec system=`ASIP-SANTE-NIR`
   - ❌ Ne correspond à aucun namespace de l'EJ 1
   - ➡️ Pas d'impact sur `patient.identifier`
   - ➡️ `identifier` créé : `{value: "212017231012386", system: "ASIP-SANTE-NIR", oid: "1.2.250.1.213.1.4.8", type: "NDA"}`

### Résultat en base :

```sql
-- Table patient
patient_id | identifier    | external_id   | entite_juridique_id
1          | 900006654054  | 900006654054  | 1

-- Table identifier
id | patient_id | value            | system           | oid                      | type
1  | 1          | 900006654054     | CPAGE            | 1.2.250.1.211.10.200.2  | IPP
30 | 1          | 212017231012386  | ASIP-SANTE-NIR   | 1.2.250.1.213.1.4.8     | NDA
```

## Vérification

### Avant ajout du namespace CPAGE (ID=14)

❌ **PROBLÈME** : Aucun identifiant n'était reconnu comme interne !
- Les patients avaient `identifier = "900006654054"` (premier identifiant reçu)
- Mais ce n'était PAS reconnu comme namespace de l'EJ
- Donc techniquement, c'était traité comme un identifiant externe utilisé comme principal

### Après ajout du namespace CPAGE (ID=14)

✅ **CORRECT** : Les identifiants CPAGE sont maintenant reconnus comme internes
- `system="CPAGE"` correspond au namespace ID=14 de l'EJ 1
- Les identifiants sont correctement classifiés
- Les autres identifiants (NIR, INS, Doctolib) restent externes

## Prochaines Actions

Pour que la classification fonctionne à 100% sur les NOUVEAUX imports :

1. ✅ Namespace CPAGE créé (ID=14)
2. ⚠️ Les patients/dossiers/venues/mouvements EXISTANTS ont déjà été créés
3. 🔄 Pour un nouveau import, la classification fonctionnera correctement
4. 📝 Si besoin de reclassifier les entités existantes, il faudrait un script de migration

## Conclusion

**OUI, nous sommes d'accord sur le principe :**

> "Pour les patients, si l'identifiant reçu a le même namespace que celui paramétré sur l'EJ, alors on intègre le code comme identifiant interne. Sinon, on l'enregistre comme identifiant externe et on stocke le namespace/oid associé (et dans ce cas, l'identifiant interne est différent de l'identifiant du message)."

✅ Ce principe s'applique à : **Patient, Dossier, Venue, Mouvement**

✅ Le code est implémenté correctement dans `identifier_namespace_classifier.py`

✅ Les OID sont maintenant extraits et stockés (commit b8521d5)

✅ Les namespaces manquants ont été ajoutés (CPAGE pour l'EJ 1)
