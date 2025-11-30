# Introduction — objectif et périmètre

But du programme
- Valider, router et tracer les messages HL7 v2.5 (principalement ADT) échangés
  entre des systèmes de production et les endpoints configurés sur la plateforme.
- Garantir la conformité IHE PAM France tout en offrant un mécanisme contrôlé
  d'acceptation d'exceptions issues de messages de production.

Principes opérationnels
- Les messages reçus de systèmes de production sont considérés comme la vérité ;
  le validateur doit rapporter les non-conformités plutôt que de modifier les
  messages.
- Les exceptions autorisées sont gérées via allow-lists et variables d'environnement
  documentées et traçables.

Public visé
- Développeurs, intégrateurs, équipes d'exploitation et auditeurs qui doivent
  comprendre le comportement de validation et les règles métier IHE PAM.

Livrables de l'itération 1
- Ce lot inclut : introduction, architecture synthétique, documentation détaillée
  du validateur `pam_validation.py` (règles, codes d'issue, procédure d'exploitation).
