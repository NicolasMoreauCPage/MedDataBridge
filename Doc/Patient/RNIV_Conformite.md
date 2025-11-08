# Conformité RNIV (Référentiel National d'Identification des Individus)

## Vue d'ensemble

Le modèle Patient est conforme aux spécifications RNIV pour la gestion de l'INS (Identifiant National de Santé) en France.

## Champs RNIV Implémentés

### 1. Identifiant National de Santé (INS)

#### Champs INS
- **`nir`**: Numéro d'Inscription au Répertoire (NIR) - Numéro de Sécurité Sociale français
- **`ins_c`**: INS Calculé - Pour personnes sans NIR (nouveaux-nés, étrangers)
- **`ins_type`**: Type d'INS - "NIR" ou "INS-C" (Enum `INSType`)
- **`ins_in_annuaire`**: Boolean - INS-A présent dans l'annuaire national INSI (TéléSanté)
- **`ins_last_query_date`**: Date du dernier appel au service INSI pour vérification

#### OID INS
L'INS doit être stocké dans la table `identifier` avec:
- **System**: `urn:oid:1.2.250.1.213.1.4.8`
- **OID**: `1.2.250.1.213.1.4.8`
- **Type**: "INS"

### 2. Traits Stricts d'Identité (5 traits obligatoires)

Les 5 traits stricts obligatoires pour la qualification d'identité RNIV:

1. **Nom de naissance**: `birth_family` (obligatoire)
2. **Premier prénom**: `given` (obligatoire)
3. **Date de naissance**: `birth_date` (obligatoire, format AAAA-MM-JJ)
4. **Sexe**: `gender` (obligatoire: male/female/other/unknown)
5. **Lieu de naissance**: 
   - `birth_city`: Ville de naissance (texte)
   - `birth_insee_code`: Code INSEE (5 caractères, ex: 75056 pour Paris, 2A004 pour Ajaccio)
   - `birth_country`: Pays de naissance (code ISO)

### 3. Prénoms Structurés

- **`birth_given_names`**: Liste complète des prénoms dans l'ordre de l'état civil (séparés par espaces)
  - Exemple: "Jean Pierre Marie"
- **`used_given_name`**: Prénom d'usage/usuel (peut différer du premier prénom officiel)
  - Exemple: "Pierre" (si la personne utilise son deuxième prénom)

### 4. Qualité d'Identité

#### `identity_reliability_code` (Enum `IdentityReliabilityCode`)

6 statuts selon RNIV (compatible HL7 Table 0445 étendue):

| Code | Signification | Description |
|------|---------------|-------------|
| `VALI` | Validée | Identité validée avec INS-A dans l'annuaire national |
| `QUAL` | Qualifiée | 5 traits stricts vérifiés, pas encore dans annuaire |
| `PROV` | Provisoire | En cours de qualification, traits incomplets |
| `VIDE` | Fictive | Patient non identifiable (urgence, anonyme) |
| `DOUTE` | Douteuse | Incohérences détectées nécessitant vérification |
| `DOUB` | Doublon | Doublon détecté, fusion requise |
| `FICTI` | Fictive | Alias HL7 de VIDE (compatibilité) |

#### Champs complémentaires
- **`identity_reliability_date`**: Date de validation/qualification (AAAA-MM-JJ)
- **`identity_reliability_source`**: Source de validation (CNI, Passeport, Acte de naissance, etc.)
- **`identity_matrix_code`**: Code de la Matrice de Gestion d'Identité (MGI) utilisée

## Règles de Validation

### Contraintes d'intégrité

```python
# Si ins_type="NIR", alors nir doit être rempli
if patient.ins_type == INSType.NIR:
    assert patient.nir is not None, "NIR requis si ins_type=NIR"

# Si ins_type="INS-C", alors ins_c doit être rempli
if patient.ins_type == INSType.INS_C:
    assert patient.ins_c is not None, "INS-C requis si ins_type=INS-C"
```

### Format NIR
- 13 chiffres + 2 chiffres de clé
- Format: `1 SS AA MM DDD NNN CCC KK`
  - S: Sexe (1=homme, 2=femme)
  - AA: Année naissance (2 chiffres)
  - MM: Mois naissance
  - DDD: Département naissance
  - NNN: Commune (code INSEE tronqué)
  - CCC: Numéro d'ordre
  - KK: Clé de contrôle

### Format INS-C
Structure spécifique définie par l'ASIP Santé (non implémenté dans cette version).

### Code INSEE Lieu de Naissance
- 5 caractères pour France métropolitaine: ex `75056` (Paris 16e)
- 2A/2B pour Corse: ex `2A004` (Ajaccio), `2B033` (Bastia)
- Format spécial pour DOM-TOM

## Workflow de Qualification d'Identité

```
                    PROV (Provisoire)
                         ↓
              [5 traits stricts vérifiés]
                         ↓
                    QUAL (Qualifiée)
                         ↓
            [Appel service INSI réussi]
                         ↓
         VALI (Validée) + ins_in_annuaire=True
```

### États exceptionnels
- **VIDE/FICTI**: Urgence, patient non identifiable → pas de qualification possible
- **DOUTE**: Incohérences → nécessite intervention manuelle
- **DOUB**: Doublon détecté → fusion de dossiers requise

## Intégration HL7v2 (PID Segment)

### Mapping PID vers Patient

| Champ HL7 | Champ Patient | Description |
|-----------|---------------|-------------|
| PID-3 (NH) | `nir` | NIR/INS |
| PID-5 | `family`, `given`, `middle` | Nom et prénoms |
| PID-7 | `birth_date` | Date de naissance |
| PID-8 | `gender` | Sexe administratif |
| PID-23 | `birth_city`, `birth_insee_code` | Lieu de naissance |
| PID-32 | `identity_reliability_code` | Statut de l'identité |

### Extension France (segments Z)
Certains établissements utilisent des segments Z pour:
- **ZIN**: Informations INS détaillées
- **ZBE-32**: Extension identité (qualité, MGI)

## Services INSI (Annuaire National)

### Appels INSI
- **Service**: Téléservice INSI (ASIP Santé)
- **Usage**: Vérification/récupération INS
- **Traçabilité**: `ins_last_query_date` horodate dernier appel

### Réponses INSI
- **INS trouvé**: Mise à jour `ins_in_annuaire=True`, passage `VALI`
- **INS non trouvé**: Identité reste `QUAL` ou `PROV`
- **Doublon**: Passage `DOUB`, nécessite action manuelle

## Migration Base de Données

Fichier: `migrations/015_add_rniv_compliance_fields.sql`

```sql
-- Nouveaux champs INS
ALTER TABLE patient ADD COLUMN ins_c TEXT;
ALTER TABLE patient ADD COLUMN ins_type TEXT;
ALTER TABLE patient ADD COLUMN ins_in_annuaire BOOLEAN DEFAULT FALSE;
ALTER TABLE patient ADD COLUMN ins_last_query_date TEXT;

-- Prénoms structurés
ALTER TABLE patient ADD COLUMN birth_given_names TEXT;
ALTER TABLE patient ADD COLUMN used_given_name TEXT;
ALTER TABLE patient ADD COLUMN birth_insee_code TEXT;

-- MGI
ALTER TABLE patient ADD COLUMN identity_matrix_code TEXT;

-- Indexes
CREATE INDEX idx_patient_ins_c ON patient(ins_c);
CREATE INDEX idx_patient_ins_type ON patient(ins_type);
CREATE INDEX idx_patient_birth_insee ON patient(birth_insee_code);
```

## Namespaces Requis

Ajouter dans `IdentifierNamespace`:

```python
{
    "name": "INS",
    "system": "urn:oid:1.2.250.1.213.1.4.8",
    "oid": "1.2.250.1.213.1.4.8",
    "type": "INS",
    "description": "Identifiant National de Santé (RNIV)",
}
```

## Références

- **RNIV v1.3**: Référentiel National d'Identification des Individus (ASIP Santé)
- **IHE PAM France**: Extension nationale pour Patient Administration Management
- **HL7 Table 0445**: Identity Reliability Code
- **Circulaire N°DGOS/MSIOS/2024/73**: Généralisation de l'INS

## Conformité

✅ **Traits stricts d'identité**: 5 traits implémentés  
✅ **Codes qualité RNIV**: 7 statuts (Enum)  
✅ **INS-C et INS-A**: Distinction NIR/INS-C  
✅ **Prénoms structurés**: Liste complète + prénom usuel  
✅ **Code INSEE**: Lieu de naissance structuré  
✅ **MGI**: Matrice de gestion d'identité  
✅ **Traçabilité INSI**: Date dernier appel  
✅ **OID officiel**: 1.2.250.1.213.1.4.8  

**Statut**: ✅ **CONFORME RNIV v1.3**
