# Documentation Fonctionnelle — Cotation MedData Bridge

## Vue d'ensemble

La cotation dans MedData Bridge représente l'ensemble des **actes médicaux et prestations** réalisés pour un patient lors de son séjour à l'hôpital. Cette fonctionnalité permet la saisie, la gestion et la validation des éléments facturables liés aux soins prodigués.

## Concepts métier

### Acte médical
Un acte médical est une intervention ou procédure réalisée par un professionnel de santé :
- **Consultation** : Examen clinique par un médecin
- **Intervention chirurgicale** : Opération ou acte invasif
- **Examen complémentaire** : Radiologie, biologie, etc.
- **Soins infirmiers** : Pansements, injections, surveillance

### Rattachement aux séjours
Chaque acte est systématiquement rattaché à :
- **Un patient** (identité du bénéficiaire)
- **Un séjour** (période d'hospitalisation)
- **Une venue** (séquence spécifique dans le séjour)
- **Un intervenant** (professionnel de santé exécutant)

## Parcours utilisateur

### 1. Accès à la cotation
```
Accueil → Patients → [Sélection patient] → Dossiers → [Sélection séjour] → Cotation
```

### 2. Consultation des actes existants
- Liste chronologique des actes du séjour
- Groupement par journée/intervention
- Statut de validation (provisoire/définitif)
- Montants calculés automatiquement

### 3. Ajout d'un nouvel acte
- Sélection du type d'acte (CCAM, NGAP, UCD, LPP)
- Saisie des informations requises selon le type :
  
  **CCAM** (Classification Commune des Actes Médicaux) :
  - Code CCAM (ex: HBMD001)
  - Date et heure d'exécution
  - Exécutant (médecin RPPS)
  - Modificateurs éventuels (Z1, K50, etc.)
  - Quantité (par défaut 1)
  
  **NGAP** (Nomenclature Générale des Actes Professionnels) :
  - Lettre-clé (A, AMI, APC, etc.)
  - Coefficient multiplicateur
  - Date et heure d'exécution
  - Prestataire
  - Dénombrement
  
  **UCD** (Unité Commune de Dispensation - médicaments) :
  - Code UCD (code CIP à 13 chiffres)
  - Quantité administrée
  - Date et heure d'administration
  - Voie d'administration (PO, IV, IM, SC, etc.)
  - Prescripteur (médecin RPPS)
  
  **LPP** (Liste des Produits et Prestations - dispositifs médicaux) :
  - Code LPP (7 chiffres)
  - Libellé du dispositif
  - Date de pose/utilisation
  - Quantité
  - Montant unitaire
  - Poseur/utilisateur (professionnel RPPS)

### 4. Édition d'un acte existant
- Modification des informations saisies
- Gestion des statuts (provisoire → définitif)
- Historique des modifications

### 5. Validation et facturation
- Contrôle de cohérence des données
- Calcul automatique des montants
- Export vers systèmes de facturation

## Structure des données

### Acte CCAM (Classification Commune des Actes Médicaux)
```json
{
  "code": "HBMD001",
  "libelle": "Échographie cardiaque",
  "date_execution": "2025-12-26T10:30:00",
  "executant_rpps": "12345678901",
  "modificateurs": ["Z1", "K50"],
  "quantite": 1,
  "montant": 45.50
}
```

### Acte NGAP (Nomenclature Générale des Actes Professionnels)
```json
{
  "lettre_cle": "A",
  "coefficient": 1.5,
  "date_execution": "2025-12-26T14:15:00",
  "prestataire_id": 42,
  "denombrement": 1
}
```

### Acte UCD (Unité Commune de Dispensation)
```json
{
  "code_ucd": "3400936050501",
  "libelle": "DOLIPRANE 1000MG CPR SEC BT 8",
  "date_administration": "2025-12-26T08:00:00",
  "quantite": 2,
  "voie_administration": "PO",
  "prescripteur_rpps": "12345678901"
}
```

### Acte LPP (Liste des Produits et Prestations)
```json
{
  "code_lpp": "1234567",
  "libelle": "Prothèse de hanche",
  "date_pose": "2025-12-26T14:30:00",
  "quantite": 1,
  "montant_unitaire": 2500.00,
  "poseur_rpps": "98765432109"
}
```

## Workflows métier

### Workflow standard d'ajout d'acte
1. **Sélection du contexte** : Patient + séjour actif
2. **Choix du type d'acte** : CCAM/NGAP/UCD/LPP
3. **Saisie des données** : Code, date, intervenant
4. **Validation automatique** : Cohérence des données
5. **Enregistrement** : Stockage avec statut "provisoire"
6. **Validation finale** : Passage en "définitif" par autorisation

### Workflow de modification
1. **Sélection de l'acte** : Depuis la liste du séjour
2. **Édition des champs** : Modification autorisée selon droits
3. **Revalidation** : Contrôle automatique des modifications
4. **Traçabilité** : Historique des changements conservé

## Rôles et permissions

### Médecin
- Saisie des actes médicaux (consultations, interventions)
- Validation des actes personnels
- Consultation de tous les actes du séjour

### Infirmier
- Saisie des soins infirmiers
- Consultation des actes du séjour
- Modification limitée des actes personnels

### Administratif
- Validation et correction des actes
- Export pour facturation
- Gestion des nomenclatures

### Gestionnaire
- Supervision de tous les actes
- Validation des montants
- Statistiques et reporting

## Intégration HPRIM XML

### Structure d'échange
```xml
<evenementsServeurActes>
  <acte>
    <code>HBMD001</code>
    <libelle>Échographie cardiaque</libelle>
    <date>2025-12-26</date>
    <heure>10:30</heure>
    <executant>
      <nom>MARTIN</nom>
      <prenom>Marie</prenom>
      <numeroRPPS>12345678901</numeroRPPS>
    </executant>
    <montant>
      <total>45.50</total>
      <unite>€</unite>
    </montant>
  </acte>
</evenementsServeurActes>
```

### Mapping avec l'interface
- **Écran de saisie** ↔ **Structure XML HPRIM**
- **Validation métier** ↔ **Contraintes de schéma XML**
- **Export facturation** ↔ **Génération de flux HPRIM**

## Modules techniques

### Module CCAM (`app/routers/ccam.py`)
- **Endpoint** : `/ccam`
- **Tags** : `["CCAM"]`
- **Fonctionnalités** :
  - Recherche de codes CCAM
  - Détail d'un acte CCAM
  - Calcul des montants avec modificateurs
  - Validation des combinaisons de codes

### Module UCD (`app/routers/ucd.py`)
- **Endpoint** : `/ucd`
- **Tags** : `["UCD"]`
- **Fonctionnalités** :
  - Recherche de médicaments par code CIP ou nom
  - Détail d'une UCD (composition, dosage, forme)
  - Gestion des voies d'administration
  - Traçabilité des prescriptions
- **Schémas** : `app/schemas/ucd.py`
- **API REST** : `app/api/ucd.py`
- **Services** : `app/services/ucd_service.py`
- **Modèles** : `app/models.py` (classe `UCDAct`)

### Module LPP (`app/routers/lpp.py`)
- **Endpoint** : `/lpp`
- **Tags** : `["LPP"]`
- **Fonctionnalités** :
  - Recherche de dispositifs médicaux
  - Détail d'un code LPP
  - Gestion des tarifs et remboursements
  - Traçabilité des poses/utilisations
- **Schémas** : `app/schemas/lpp.py`
- **API REST** : `app/api/lpp.py`
- **Services** : `app/services/lpp_service.py`
- **Modèles** : `app/models.py` (classe `LPPAct`)

### Module NGAP
- **Service** : `app/services/ngap_service.py`
- **Fonctionnalités** :
  - Gestion des lettres-clés et coefficients
  - Calcul des montants
  - Validation des actes NGAP

### Cotation moderne (`app/routers/cotation_modern.py`)
- **Endpoint** : `/cotation-modern`
- **Tags** : `["cotation_moderne"]`
- **Fonctionnalités** :
  - Interface moderne de cotation
  - Sélection de dossiers pour cotation
  - Saisie multi-actes (CCAM, NGAP, UCD, LPP)
  - Validation en temps réel
  - Export pour facturation
- **Sélecteur** : `app/routers/cotation_selector.py`

## Points d'attention

### Cohérence des données
- Unicité des codes par nomenclature
- Chronologie respectée (date acte ≤ date séjour)
- Intervenant habilité pour le type d'acte

### Performance
- Pagination pour les séjours avec nombreux actes
- Cache des nomenclatures fréquemment utilisées
- Validation asynchrone pour les gros volumes

### Sécurité
- Traçabilité complète des modifications
- Autorisations par rôle et périmètre
- Chiffrement des données sensibles

---

**Version : 1.1**  
**Date : 5 janvier 2026**  
**Dernière mise à jour** : Ajout des modules UCD, LPP, NGAP et cotation moderne  
**Responsable : Équipe MedData Bridge**
