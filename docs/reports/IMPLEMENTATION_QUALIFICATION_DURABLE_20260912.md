# Qualification durable et scénarios versionnés

Date : 12 septembre 2026

## Résultat

Le moteur de scénarios utilise désormais une livraison persistante de bout en
bout : chaque `ScenarioDelivery` possède une ligne d'outbox, un payload figé,
un nombre de tentatives, la dernière réponse et un journal d'émission. Une
indisponibilité ne fait donc plus disparaître une livraison lors d'un
redémarrage du programme.

## Fonctions livrées

- politique d'échec du jeu : arrêt, poursuite de toutes les livraisons ou des
  autres cibles ;
- retry identique depuis l'outbox ;
- versions brouillon, publiée et archivée, avec empreinte du contenu ;
- rattachement de chaque jeu à la version publiée exacte ;
- assertions de transport et assertions BDD déclaratives limitées aux modèles
  autorisés ;
- campagnes durables fondées sur les jeux plutôt que sur une tâche volatile ;
- diagnostic JSON portable : source, payload compilé, réponse, erreur et
  nombre de tentatives ;
- comparaison visuelle source/compilé sur le détail du jeu ;
- test mixte PAM + HPRIM sur deux endpoints isolés.

## Utilisation

1. Publier une version depuis le détail du scénario.
2. Définir si nécessaire les préconditions et assertions JSON.
3. Choisir les destinations et la politique d'erreur.
4. Lancer le jeu ou une campagne.
5. Consulter la matrice des livraisons ou télécharger le diagnostic JSON.
6. Utiliser **Réessayer** pour reprendre le même payload ; utiliser **Rejouer
   comme nouveau jeu** pour générer de nouveaux identifiants.

## Vérification

La campagne CI `interop-conformance.yml` couvre l'outbox de scénarios, les
versions, les assertions et le roundtrip mixte PAM/HPRIM.
