# IHE PAM France — guide d'utilisation du validateur

MedData Bridge valide, intègre et génère les flux IHE PAM France : ITI-30
(identité patient) et ITI-31 (mouvements), fondés sur HL7 v2.5. Ce document
est un guide d'exploitation ; il ne remplace pas les spécifications IHE France,
HL7 v2.5 et la convention bilatérale du partenaire.

## Contrôles réalisés

- intégrité HL7 de base : séparateurs, `MSH`, version, structure, segments et
  répétitions ;
- cohérence IHE PAM France : `MSH-9`, trigger, segments obligatoires, `PID`,
  `PV1`, `ZBE`, `MRG` et événements ITI-30/ITI-31 ;
- règles françaises et CPage : encodage, identifiants, dates, actions et
  variantes nationales admises ;
- cohérence métier : transition de venue/mouvement et annulations ;
- ACK et diagnostic : les messages invalides sont expliqués par code, sévérité
  et emplacement de champ.

`MSH-18=8859/1`, valeur préconisée par les spécifications PAM France, est
accepté. Le contrôle de complétude de `ZBE-8` est un avertissement : des flux
CPage légitimes le laissent vide. La valeur connue comme erronée de `ZBE-9`
peut être diagnostiquée sans empêcher l'intégration si la politique du flux le
prévoit.

## Politique de réception

Chaque endpoint peut être configuré en mode :

- `warn` : journaliser les écarts et produire un diagnostic sans bloquer le
  flux lorsque le contexte métier le permet ;
- `reject` : retourner un ACK `AE` pour les erreurs bloquantes.

Commencer une intégration partenaire en `warn`, analyser les écarts réels, puis
passer au rejet après recette bilatérale. L'émission applicative est, elle,
bloquée lorsqu'elle échoue à sa validation sortante.

## Preuves disponibles

- [Audit PAM France / CPage](reports/AUDIT_CONFORMITE_IHE_PAM_FRANCE_20260911.md)
  : couverture, corrections et limites de certification ;
- [Roundtrip CPage](reports/ROUNDTRIP_CPAGE_PAM_20260911.md) : injection MLLP
  dans deux GHT et comparaison des BDD ;
- [État des tests](TESTS_STATUS.md) : commandes reproductibles et CI.

## Limites

La conformité technique testée ne vaut ni certification IHE, ni Connectathon,
ni recette bilatérale. Toute extension Z consommée par un partenaire doit être
qualifiée avec son corpus, sa politique de sévérité et ses ACK attendus.
