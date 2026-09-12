# Itération fonctionnelle — catalogue et exploitation des scénarios

Date : 12 septembre 2026

## Objectif

Rendre le catalogue de scénarios portable, qualifier explicitement les cas
positifs et négatifs, puis rendre les exécutions longues reprenables sans
perdre leur preuve d'exécution.

## Réalisations

- Le catalogue administré est exporté dans une ressource versionnée et injecté
  idempotemment par Alembic sur une installation vide : 289 scénarios, 1 230
  étapes, 289 décisions de revue, 15 thèmes et 238 rattachements.
- Les scénarios portent désormais un contrat de résultat attendu. Un cas
  négatif peut attendre un `AE` ou `AR` sur une étape donnée et devient alors
  réussi si le rejet attendu est effectivement obtenu.
- Les campagnes sont mises en file, avancent étape par étape et se reprennent
  après un arrêt. Le détail conserve la progression et la preuve de chaque
  item déjà joué.
- L'outbox est reprise périodiquement, y compris pour les dépôts FILE, SFTP et
  FTP. Le poller d'entrée prend en compte les endpoints FILE et SFTP.
- Le détail d'une exécution affiche une différence sémantique entre le
  template et le message compilé : segments et champs HL7, chemins JSON/FHIR
  ou éléments XML/HPRIM.
- Les exports/imports de scénarios conservent commentaires, prérequis,
  assertions et contrat de résultat.
- Le parseur ADT utilise `PID-18` comme identifiant de dossier lorsqu'il est
  présent, avec repli sur `PV1-19`. Ce comportement assure le roundtrip des
  scénarios qui régénèrent dossier et venue séparément.

## Vérifications

- Migration Alembic réelle sur une base SQLite vide : catalogue présent et
  migration idempotente.
- Tests unitaires du seed, des résultats attendus, des campagnes reprenables,
  de l'outbox, des transports SFTP/FTP, du diff et de l'import/export.
- Roundtrips HPRIM XML, FHIR de structure et scénarios à deux GHT.

## Limites volontairement conservées

Le catalogue actif ne contient que les scénarios approuvés. Les scénarios
réparables, doublons et cas non qualifiés sont conservés pour édition et
qualification, mais désactivés afin qu'une émission de masse ne les joue pas
par erreur.
