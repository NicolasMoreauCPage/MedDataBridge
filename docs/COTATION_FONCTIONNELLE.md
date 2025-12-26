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
- Saisie des informations requises :
  - Code nomenclature
  - Date et heure d'exécution
  - Quantité/coeffficient
  - Intervenant (médecin/infirmier)
  - Modificateurs éventuels

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

**Version : 1.0**  
**Date : 26 décembre 2025**  
**Responsable : Équipe MedData Bridge**
