# Legacy Behavior & Fallbacks

Ce document détaille les comportements de repli pour supporter des anciens messages ou des partenaires partiellement conformes au profil IHE PAM FR.

## Objectifs

- Permettre ingestion de messages incomplets sans bloquer les flux critiques.
- Conserver un niveau de traçabilité pour distinguer données normalisées vs adaptées.
- Faciliter mise à niveau progressive des émetteurs.

## Fallbacks Implémentés

| Élément | Situation legacy | Comportement | Sévérité (future classification) |
|---------|------------------|-------------|----------------------------------|
| ZBE-8 UF soins manquant | Segment ZBE sans XON soins | Champ vide dans ZBE, aucun arrêt | Warning |
| Action invalide (ZBE-4) | Valeur non dans {INSERT,UPDATE,CANCEL} | Fallback `INSERT` | Warning |
| UPDATE/CANCEL sans ZBE-6 | ZBE-6 absent | Fallback sur `trigger_event` du mouvement | Warning (strict: Error) |
| Nature invalide (ZBE-9) | Code non dans {S,H,M,L,D,SM} | Recalcul nature via mapping trigger | Warning |
| Historique absent (ZBE-5) | Champ vide | Fallback `N` (non historique) | Warning |

## Champs Non Fallback

| Élément | Raison |
|---------|--------|
| ZBE-1 identifiant mouvement | Indispensable pour ciblage UPDATE/CANCEL |
| Date/heure ZBE-2 | Nécessaire pour cohérence chronologique |

## Recommandations Émetteurs

1. Fournir systématiquement ZBE-6 pour toute action UPDATE/CANCEL.
2. Initialiser progressivement UF soins pour garantir traçabilité complète des unités.
3. Vérifier mapping Nature pour correspondre aux triggers utilisés.

## Traçabilité Interne

- Les warnings doivent être journalisés avec code (ex: `WARN_ZBE8_MISSING`).
- La compliance matrix inclura le ratio messages avec fallback vs conformes.

## Évolutions Futures

- Ajout seuil de rejet configurable: au-delà de X% messages avec fallback sur une fenêtre temps, alerte.
- Mode STRICT par EJ désactivant certains fallbacks (ex: ZBE-6 obligatoire -> Error).

Dernière mise à jour automatique.
