# Outbox persistante des émissions

L'outbox conserve les émissions sortantes qui doivent être reprises après une
indisponibilité d'endpoint ou un redémarrage. Elle est stockée en BDD dans
`OutboundMessage` ; elle ne dépend pas d'un répertoire local de fichiers.

## Statuts et reprise

| Statut | Signification |
|---|---|
| `pending` | Prêt à être envoyé |
| `retry` | Échec temporaire, nouvelle tentative planifiée |
| `sent` | Envoi confirmé par ACK MLLP positif ou réponse HTTP 2xx |
| `failed` | Nombre maximal de tentatives atteint ; reprise manuelle possible |

Le worker applique un backoff exponentiel, plafonné à une heure. Les ACK MLLP
`AE` et `AR`, ainsi que les réponses FHIR non 2xx, sont traités comme des
échecs. La reprise ne duplique pas une ligne encore ouverte issue du même
`MessageLog`.

## API d'exploitation

| Action | Endpoint |
|---|---|
| Consulter la file | `GET /outbox?status=pending` |
| Récupérer les anciens `MessageLog` sortants en échec | `POST /outbox/recover` |
| Traiter les messages échus | `POST /outbox/process?limit=100` |
| Rejouer une ligne après correction | `POST /outbox/{id}/retry` |

`POST /outbox/process` peut être déclenché par cron, systemd timer ou un
ordonnanceur applicatif. Aucun worker permanent n'est imposé pour les
installations LAN.

## Protocoles pris en charge

- `MLLP` : envoi HL7 et contrôle de l'ACK ;
- `FHIR` : envoi d'un Bundle et contrôle du statut HTTP.

Le contenu, l'endpoint, l'identifiant de corrélation, le nombre de tentatives
et la dernière erreur sont conservés pour permettre le diagnostic et le rejeu.
