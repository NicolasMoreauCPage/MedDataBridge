# 📘 Guide Utilisateur Phase 6 – Dossiers & Venues

**Public** : Agents admissions, gestionnaires de séjours, secrétariats médicaux  
**Version** : Phase 6 (6.1 → 6.4)

---

## 1. Créer une admission complète

### 1.1 Depuis la fiche patient
1. Ouvrez la page **Patients**.
2. Recherchez et cliquez sur le patient souhaité.
3. Dans le header moderne du patient, cliquez sur **« Nouveau dossier »**.
4. Le **wizard d'admission** s'ouvre en 3 étapes :
   - Étape 1/3 : Identité patient (rappel et vérification).
   - Étape 2/3 : Dossier administratif (type, UF, médecin, motif).
   - Étape 3/3 : Venue initiale (UF, lit/chambre, dates, service).
5. Naviguez avec les boutons **Suivant / Précédent**.
6. À la dernière étape, cliquez sur **Valider l'admission**.

### 1.2 Champs importants
- **Type de dossier** : détermine les contraintes (ex : UF obligatoire).
- **UF responsabilité** : service responsable administratif du séjour.
- **Médecin responsable** : médecin titulaire du séjour.
- **Dates** : admission et (optionnellement) sortie prévisionnelle.

---

## 2. Gérer les venues d'un dossier

### 2.1 Accéder aux venues d'un dossier
1. Ouvrez **Dossiers** dans le menu.
2. Cliquez sur un dossier dans la liste.
3. Dans la fiche dossier, repérez la section **Venues associées**.
4. Chaque ligne correspond à un **séjour (venue)** avec dates, UF, localisation.

### 2.2 Créer une nouvelle venue depuis un dossier
1. Depuis la fiche dossier, utilisez le bouton **« Nouvelle venue »** dans le header.
2. Le formulaire est **pré-rempli** avec le **dossier courant**.
3. Complétez :
   - UF, service, localisation.
   - Dates de début (et fin si connue).
   - Médecin responsable / motif.
4. Enregistrez la venue.

### 2.3 Naviguer vers les mouvements
- Sur la fiche venue, utilisez les liens **Mouvements** pour voir la timeline.
- Les mouvements (entrées, transferts, sorties) sont listés de manière chronologique.

---

## 3. Utiliser les filtres avancés

Les écrans listant de nombreux éléments (dossiers, venues, mouvements) disposent de **filtres avancés**.

### 3.1 Filtres Dossiers
Accès : menu **Dossiers**.

Filtres disponibles :
- **UF responsabilité** : texte, ex: `CARDIO`.
- **Médecin responsable** : texte (partie du nom).
- **Type de dossier** : liste déroulante.
- **Admission à partir du** : date (AAAA-MM-JJ).
- **Admission jusqu'au** : date (AAAA-MM-JJ).
- **État courant** : texte, ex: `EN_SALLE`, `HOSPITALISE`.

### 3.2 Filtres Venues
Accès : menu **Venues**.

Filtres disponibles :
- **UF** : texte (contient).
- **Service** : texte.
- **Localisation** : texte (chambre, lit…).
- **Début à partir du** : date.
- **Début jusqu'au** : date.

### 3.3 Filtres Mouvements
Accès : menu **Mouvements** (selon configuration).

Filtres disponibles :
- **Type de mouvement** : entrée, transfert, sortie…
- **Statut** : planifié, exécuté, annulé.
- **Localisation** : texte.

### 3.4 Bonnes pratiques de recherche
- Utilisez des **morceaux de texte** (ex: `mart` pour `MARTIN`).
- Combinez les filtres (ex: UF + période) pour affiner.
- Les filtres sont appliqués côté serveur : l'URL est mise à jour.

---

## 4. Raccourcis clavier pour power users

Les raccourcis suivants fonctionnent sur les écrans list/formulaire concernés :

### 4.1 Sur les listings (dossiers, venues, mouvements)
- **Ctrl+N** (ou Cmd+N sur Mac) :
  - Ouvre la page de **création** d'un nouvel élément (dossier, venue, mouvement) selon le contexte.
- **/** (slash) :
  - Met le focus sur le **premier champ de filtre**, si le panneau de filtres est ouvert.
- **Esc** :
  - Ferme le **panneau de filtres** si ouvert.

### 4.2 Sur les formulaires
- **Ctrl+S** (ou Cmd+S sur Mac) :
  - Déclenche la **sauvegarde** du formulaire.
  - Évite l'apparition du dialogue de sauvegarde du navigateur.

### 4.3 Conseils
- Assurez-vous que le **focus** n'est pas déjà dans un champ texte si vous utilisez `/`.
- Les raccourcis ont été pensés pour **ne pas interférer** avec la saisie standard.

---

## 5. Navigation croisée Patient → Dossier → Venue

Exemple de parcours :
1. Menu **Patients** → sélection d'un patient.
2. Depuis la fiche patient, cliquer sur un **dossier** dans la liste.
3. Depuis la fiche dossier, cliquer sur une **venue**.
4. Depuis la fiche venue, accéder aux **mouvements**.

À chaque étape, le header rappelle le **contexte patient** (nom, IPP) et le contexte dossier/venue (NDA, VN, UF, dates).

---

## 6. FAQ (Questions fréquentes)

### 6.1 Je ne trouve pas un dossier par UF
- Vérifiez l'orthographe (ex: `CARDIO`, `CHIRURGIE`).
- Essayez avec **une partie du code** seulement.
- Combinez avec un filtre de **période d'admission**.

### 6.2 Le raccourci Ctrl+S ne fonctionne pas
- Assurez-vous d'être sur un **formulaire**.
- Sous certains navigateurs, il peut rester bloqué par des extensions.
- Essayez **Cmd+S** sur Mac.

### 6.3 Je ne vois pas le bouton "Nouvelle venue"
- Le bouton apparaît sur la **fiche dossier**, pas sur tous les écrans.
- Si le dossier est en lecture seule (cas rare), certaines actions peuvent être cachées.

### 6.4 Comment filtrer sur une période de dates ?
- Renseignez **"Admission à partir du"** et/ou **"jusqu'au"**.
- Le format attendu est `AAAA-MM-JJ` (ex: `2026-01-01`).

---

## 7. Astuces

- Utilisez `Ctrl+N` et `Ctrl+S` pour gagner du temps au quotidien.
- Gardez un onglet avec la **liste des dossiers** et naviguez via les liens internes.
- Combinez filtres + navigation croisée pour retrouver un séjour précis très rapidement.
