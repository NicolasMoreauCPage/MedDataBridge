# Analyse Complète HPRIM XML 2.4 - Système de Cotation des Actes Médicaux

## Vue d'Ensemble

Le système HPRIM XML 2.4 constitue le standard français d'interopérabilité pour l'échange de données médicales entre systèmes d'information hospitaliers. Cette analyse couvre l'implémentation complète d'un système de cotation des actes médicaux basé sur les spécifications HPRIM XML 2.4.

## Architecture Générale

### Composants Principaux
- **serveurActivite**: Gestion des actes médicaux (CCAM, NGAP, LPP, UCD)
- **pmsi**: Programmation Médicale des Systèmes d'Information (MCO, SSR, PSY, HAD)
- **serveurEtat**: État des patients et mouvements
- **fraisDivers**: Gestion des frais divers et dépenses

### Standards Techniques
- **Namespace**: `http://www.hprim.org/hprimXML`
- **Encodage**: ISO-8859-1 (Latin-1)
- **Validation**: Schémas XSD complets
- **Transport**: HTTP avec acquittements

## Structure des Actes Médicaux

### 1. Actes CCAM (Classification Commune des Actes Médicaux)

#### Format du Code CCAM
```xml
<ccam>[A-Z]{4}[0-9]{3}</ccam>
```
Exemple: `AAFA001`, `EBLA003`, etc.

#### Structure Complète d'un Acte CCAM
```xml
<acteCCAM action="création">
  <dateAction>2024-01-15T10:30:00</dateAction>
  <acteur>
    <medecin>
      <nom>DOCTEUR</nom>
      <prenom>MARTIN</prenom>
      <numeroRPPS>12345678901</numeroRPPS>
    </medecin>
  </acteur>
  <identifiant>
    <emetteur portee="local">ACTE_001</emetteur>
  </identifiant>
  <codeActe>AAFA001</codeActe>
  <codeActeExtensionPMSI>01</codeActeExtensionPMSI>
  <codeActivite>01</codeActivite>
  <codePhase>00</codePhase>
  <execute>
    <date>2024-01-15</date>
    <heure>10:30:00</heure>
  </execute>
  <executant>
    <medecins>
      <medecin>
        <nom>DOCTEUR</nom>
        <prenom>MARTIN</prenom>
        <numeroRPPS>12345678901</numeroRPPS>
      </medecin>
    </medecins>
  </executant>
  <modificateurs>
    <modificateur statut="nft">K</modificateur>
  </modificateurs>
  <quantite>1</quantite>
  <priseCharge>
    <risque>1</risque>
    <ententePrealable>non</ententePrealable>
  </priseCharge>
  <montant>
    <valeur>25.50</valeur>
    <devise>EUR</devise>
  </montant>
  <commentaire>Acte de consultation cardiologique</commentaire>
</acteCCAM>
```

#### Attributs Obligatoires
- `action`: création, modification, suppression
- `facturable`: oui/non (défaut: oui)
- `valide`: oui/non (défaut: non)
- `facture`: oui/non (défaut: non)

#### Éléments Clés
- **codeActe**: Code CCAM sur 7 caractères
- **codeActivite**: Domaine d'activité (01-99)
- **codePhase**: Phase de l'acte (00-99)
- **executant**: Médecin exécutant avec RPPS
- **modificateurs**: Codes complémentaires (A-Z, 0-9)
- **quantite**: Nombre d'unités
- **montant**: Valorisation financière

### 2. Actes NGAP (Nomenclature Générale des Actes Professionnels)

#### Structure d'un Acte NGAP
```xml
<acteNGAP action="création">
  <dateAction>2024-01-15T10:30:00</dateAction>
  <acteur>
    <medecin>
      <nom>DOCTEUR</nom>
      <prenom>MARTIN</prenom>
      <numeroRPPS>12345678901</numeroRPPS>
    </medecin>
  </acteur>
  <identifiant>
    <emetteur portee="local">NGAP_001</emetteur>
  </identifiant>
  <lettreCle>C</lettreCle>
  <coefficient>1.0</coefficient>
  <denombrement>1</denombrement>
  <execute>
    <date>2024-01-15</date>
    <heure>10:30:00</heure>
  </execute>
  <prestataire>
    <medecin>
      <nom>DOCTEUR</nom>
      <prenom>MARTIN</prenom>
      <numeroRPPS>12345678901</numeroRPPS>
    </medecin>
  </prestataire>
  <montant>
    <valeur>25.50</valeur>
    <devise>EUR</devise>
  </montant>
</acteNGAP>
```

#### Éléments Spécifiques NGAP
- **lettreCle**: Lettre clé de la NGAP (A-Z)
- **coefficient**: Coefficient numérique
- **denombrement**: Quantité
- **prestataire**: Professionnel effectuant l'acte

### 3. Actes LPP (Lettres Clés de Pathologie Professionnelle)

#### Structure LPP
```xml
<evenementServeurLPP>
  <dateAction>2024-01-15T10:30:00</dateAction>
  <acteur>
    <medecin>
      <nom>DOCTEUR</nom>
      <prenom>MARTIN</prenom>
      <numeroRPPS>12345678901</numeroRPPS>
    </medecin>
  </acteur>
  <patient>
    <identifiant>
      <id>123456789</id>
      <clef>123456789</clef>
    </identifiant>
    <nom>MARTIN</nom>
    <prenom>JEAN</prenom>
    <dateNaissance>1980-05-15</dateNaissance>
  </patient>
  <LPPs>
    <LPP>
      <code portee="n">1234567890123</code>
      <libelle>Consultation de médecine générale</libelle>
      <prixUnitaire>25.50</prixUnitaire>
      <quantite>1</quantite>
      <montantTotal>25.50</montantTotal>
    </LPP>
  </LPPs>
</evenementServeurLPP>
```

### 4. Actes UCD (Unités Commune de Dispensation)

#### Structure UCD
```xml
<evenementServeurUCD>
  <dateAction>2024-01-15T10:30:00</dateAction>
  <acteur>
    <medecin>
      <nom>DOCTEUR</nom>
      <prenom>MARTIN</prenom>
      <numeroRPPS>12345678901</numeroRPPS>
    </medecin>
  </acteur>
  <patient>
    <identifiant>
      <id>123456789</id>
      <clef>123456789</clef>
    </identifiant>
  </patient>
  <UCDs>
    <UCD>
      <code>3400932345678</code>
      <designation>PARACETAMOL 500MG CPR</designation>
      <quantite>30</quantite>
      <prixUnitaire>0.15</prixUnitaire>
      <montantTotal>4.50</montantTotal>
    </UCD>
  </UCDs>
</evenementServeurUCD>
```

## Structure des Messages

### En-tête de Message (enteteMessage)
```xml
<enteteMessage>
  <emetteur>
    <id>FINESS_123456789</id>
    <nom>EHPAD LES ROSIERS</nom>
  </emetteur>
  <destinataire>
    <id>FINESS_987654321</id>
    <nom>CENTRE HOSPITALIER</nom>
  </destinataire>
  <dateEmission>2024-01-15T10:30:00</dateEmission>
  <message>
    <id>MSG_20240115_001</id>
    <type>evenementsServeurActes</type>
  </message>
</enteteMessage>
```

### Types d'Événements
- **evenementServeurIntervention**: Interventions médicales
- **evenementServeurActe**: Actes CCAM/NGAP
- **evenementServeurLPP**: Actes LPP
- **evenementServeurUCD**: Actes UCD
- **evenementFusionIntervention**: Fusion d'interventions

## Système d'Acquittements

### Structure d'Acquittement
```xml
<acquittementsServeurActes version="2.4">
  <enteteMessage>
    <!-- En-tête de réponse -->
  </enteteMessage>
  <acquittement>
    <statut>OK</statut>
    <messageIdOriginal>MSG_20240115_001</messageIdOriginal>
    <dateAcquittement>2024-01-15T10:30:05</dateAcquittement>
  </acquittement>
</acquittementsServeurActes>
```

### Codes d'Erreur
- **ccamAsnp0001**: Code acte CCAM invalide
- **ccamIdtf0001**: Identifiant acte manquant
- **ccamUnif0001**: Unité fonctionnelle invalide

## Intégration avec MedData Bridge

### Points d'Intégration
1. **API REST Endpoints**:
   - `POST /api/hprim/actes/emission`: Émission d'actes
   - `POST /api/hprim/actes/reception`: Réception d'actes
   - `GET /api/hprim/actes/{id}`: Consultation d'acte
   - `POST /api/hprim/acquittements`: Gestion des acquittements

2. **Modèles de Données**:
   - Intégration avec `Dossier` model existant
   - Extension des modèles patient et professionnel
   - Historique des actes par dossier

3. **Validation et Conformité**:
   - Validation XSD complète
   - Contrôle des formats (RPPS, FINESS, etc.)
   - Vérification des nomenclatures

### Architecture Technique

#### Services à Implémenter
```
app/services/
├── hprim_coding.py          # Service principal HPRIM
├── hprim_validator.py       # Validation XSD
├── hprim_parser.py          # Parseur XML
├── hprim_generator.py       # Générateur XML
└── hprim_transport.py       # Gestion transport HTTP
```

#### Modèles de Données
```python
@dataclass
class HprimActeCCAM:
    code_acte: str
    code_activite: str
    code_phase: str
    execute_date: datetime
    executant_rpps: str
    modificateurs: List[str]
    quantite: int
    montant: Decimal

@dataclass
class HprimMessage:
    id: str
    type: str
    emetteur: str
    destinataire: str
    contenu: str
    acquittement_attendu: bool
```

## Plan de Développement

### Phase 1: Infrastructure de Base
- [ ] Implémentation des modèles de données Python
- [ ] Configuration validation XSD
- [ ] Service de génération XML de base
- [ ] Service de parsing XML

### Phase 2: Actes CCAM
- [ ] Endpoint émission actes CCAM
- [ ] Endpoint réception actes CCAM
- [ ] Validation complète CCAM
- [ ] Intégration base de données

### Phase 3: Actes NGAP et LPP
- [ ] Support actes NGAP
- [ ] Support actes LPP
- [ ] Gestion modificateurs et compléments

### Phase 4: Acquittements et Transport
- [ ] Système d'acquittements
- [ ] Transport HTTP sécurisé
- [ ] Gestion des erreurs et retry

### Phase 5: Interface Utilisateur
- [ ] Interface cotation actes
- [ ] Recherche et sélection actes
- [ ] Validation temps réel
- [ ] Historique par dossier

### Phase 6: Intégration et Tests
- [ ] Intégration complète dossiers
- [ ] Tests end-to-end
- [ ] Validation conformité HPRIM
- [ ] Performance et sécurité

## Conformité et Standards

### Nomenclatures Utilisées
- **CCAM**: Classification Commune des Actes Médicaux
- **NGAP**: Nomenclature Générale des Actes Professionnels
- **LPP**: Lettres Clés de Pathologie Professionnelle
- **UCD**: Unités Commune de Dispensation
- **RPPS**: Répertoire Partagé des Professionnels de Santé
- **FINESS**: Fichier National des Établissements Sanitaires

### Contraintes Techniques
- Encodage strict ISO-8859-1
- Validation XSD obligatoire
- Acquittements systématiques
- Traçabilité complète des échanges

Cette analyse constitue la base complète pour l'implémentation du système HPRIM XML dans MedData Bridge.</content>
<parameter name="filePath">/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/HPRIM_XML_ANALYSIS_COMPLETE.md