# Documentation HPRIM XML

Ce document regroupe les informations techniques et fonctionnelles sur la gestion, la génération, la validation et l'intégration des messages HPRIM XML dans MedData Bridge.

## Sommaire
- [Vue d'ensemble](#vue-densemble)
- [Spécifications HPRIM XML](#spécifications-hprim-xml)
- [Génération et roundtrip](#génération-et-roundtrip)
- [Validation XSD](#validation-xsd)
- [Exemples de messages](#exemples-de-messages)
- [Liens utiles](#liens-utiles)

## Vue d'ensemble
HPRIM XML est un format d'échange de données médicales utilisé pour l'interopérabilité entre systèmes d'information hospitaliers. MedData Bridge prend en charge la génération, la validation et l'import de messages HPRIM XML pour différents types de cotations (CCAM, NGAP, UCD, LPP).

## Spécifications HPRIM XML
- Respect des schémas XSD officiels (CCAM, NGAP, UCD, LPP)
- Encodage UTF-8, conformité aux contraintes de structure et de contenu

## Génération et roundtrip
- Endpoints API pour générer et valider des messages HPRIM XML
- Tests automatisés de roundtrip (génération → validation → parsing)

## Validation XSD
- Utilisation de `lxml` et `xmlschema` pour la validation stricte
- Gestion des erreurs de conformité et des cas limites (notamment LPP)

## Exemples de messages
- Voir le dossier `examples/` ou utiliser l'API `/messages/send` pour générer des exemples dynamiques

## Liens utiles
- [HPRIM_XML_ANALYSIS_COMPLETE.md](../HPRIM_XML_ANALYSIS_COMPLETE.md)
- [HPRIM_XML_IMPLEMENTATION_TODO.md](../HPRIM_XML_IMPLEMENTATION_TODO.md)
- [HPRIM_XML_EXECUTIVE_SUMMARY.md](../HPRIM_XML_EXECUTIVE_SUMMARY.md)
- [HPRIM_XML_STARTER_CODE.py](../HPRIM_XML_STARTER_CODE.py)

Pour toute question ou contribution, contactez l'équipe technique MedData Bridge.