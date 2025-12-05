# Gestion Intelligente des Scénarios - Statut d'Exécution

## Vue d'ensemble

Les scénarios sont maintenant équipés d'un système intelligent de **suivi du dernier statut d'exécution** avec:

- **Indicateurs visuels** (✅ ⚠️ ❌ ⏹️) affichés sur l'IHM
- **Filtrage des scénarios** par statut de dernier ACK
- **Filtrage par EJ** avec identification des scénarios échoués
- **API JSON** pour intégrations tierces

## Statuts possibles

| Indicateur | Statut | Description | Couleur |
|-----------|--------|-------------|---------|
| ✅ | `all_aa` | Tous les messages ont reçu un ACK AA | Vert |
| ⚠️ | `some_aa` | Certains messages ont reçu un ACK AA | Jaune |
| ❌ | `error` | Présence d'erreurs (AE, AR) ou status "error" | Rouge |
| ⏹️ | `unknown` / `no_run` | Jamais exécuté ou statut inconnu | Gris |

## Pages et Fonctionnalités

### 1. Liste des Scénarios (`/scenarios`)

Affiche tous les scénarios avec leur dernier statut d'exécution.

**Colonnes:**
- Indicateur visuel (✅/⚠️/❌/⏹️)
- Nom du scénario
- Protocole
- Nombre d'étapes
- ACK du dernier run (ex: "AA", "AA(1/2)", "AE/AR(2/3)")
- Date/heure du dernier envoi

**Filtrage:**
```
- Tous les scénarios
- ✅ Succès (tous AA)
- ⚠️ Partiel (certains AA)
- ❌ Erreurs
- ⏹️ Jamais exécutés
```

Utilisation: Sélectionner un filtre dans le dropdown `Filtrer par statut`

### 2. Scénarios par EJ (`/scenarios/ej-status`)

Vue organisée **par Entité Juridique** montrant l'état de tous les scénarios sur chaque EJ.

**Fonctionnalités:**
- Sélection d'une EJ
- Case à cocher "Voir seulement les en-cours/erreurs"
- Statistiques d'exécution (Total, Succès, Partiel, Erreurs)
- Tableau détaillé avec actions de dépannage

**Colonnes du tableau:**
- Statut (indicateur visuel)
- Nom du scénario
- Code ACK (avec couleur)
- Messages (ex: "1/3" = 1 succès sur 3)
- Dernière exécution
- Actions (Détail, Erreurs)

## API Endpoints

### Récupérer le statut d'un scénario

```bash
GET /scenarios/api/scenario/{scenario_id}/status
```

**Réponse JSON:**
```json
{
  "scenario_id": 1,
  "scenario_name": "IHE PAM - Admission (1 msg)",
  "status": "all_aa",
  "ack_code": "AA",
  "is_success": true,
  "has_errors": false,
  "visual_indicator": "✅",
  "last_run_at": "2025-12-05T14:30:00",
  "success_steps": 1,
  "total_steps": 1
}
```

### Récupérer les statuts pour une EJ

```bash
GET /scenarios/api/ej/{ej_id}/scenarios-status?only_failed=false
```

**Réponse JSON:**
```json
{
  "ej_id": 1,
  "count": 124,
  "scenarios": [
    {
      "scenario_id": 1,
      "scenario_name": "IHE PAM - Admission (1 msg)",
      "status": "all_aa",
      "ack_code": "AA",
      "is_success": true,
      "has_errors": false,
      "visual_indicator": "✅",
      "last_run_at": "2025-12-05T14:30:00",
      "success_steps": 1,
      "total_steps": 1
    },
    ...
  ]
}
```

**Query params:**
- `only_failed=true`: Retourner seulement les scénarios en erreur/sans ACK AA

## Architecture du Code

### Service: `app/services/scenario_status_service.py`

**Classes:**
- `ScenarioStatus`: Représente le statut d'un scénario
  - `is_success`: True si tous les AA
  - `is_partial`: True si certains AA
  - `has_errors`: True si erreurs
  - `visual_indicator`: Emoji (✅ ⚠️ ❌ ⏹️)
  - `css_class`: Classes Tailwind pour styling

**Fonctions:**
- `get_last_scenario_status()`: Récupère le statut du dernier run
- `get_scenarios_status_for_ej()`: Récupère tous les statuts pour une EJ
- `get_scenarios_with_status()`: Récupère tous les scénarios avec statut

### Routes: `app/routers/scenarios.py`

**Modifiées:**
- `GET /scenarios`: Ajoute colonnes statut + filtre
- `GET /scenarios/ej-status`: Nouvelle page par EJ

**Nouvelles:**
- `GET /scenarios/api/scenario/{scenario_id}/status`: API statut unique
- `GET /scenarios/api/ej/{ej_id}/scenarios-status`: API statuts par EJ

### Templates

- `app/templates/list.html`: Mise à jour pour afficher les statuts
- `app/templates/scenarios/ej_scenarios_status.html`: Nouvelle page EJ

## Utilisation

### Pour identifier rapidement les scénarios en succès:

1. Aller à `/scenarios`
2. Sélectionner "✅ Succès (tous AA)" dans le filtre
3. Tous les scénarios avec ACK AA uniquement s'affichent

### Pour voir les scénarios en erreur sur une EJ spécifique:

1. Aller à `/scenarios/ej-status`
2. Sélectionner une EJ dans le dropdown
3. Cocher "Voir seulement les en-cours/erreurs"
4. Voir les stats + tableau des problèmes

### Pour utiliser l'API:

```bash
# Obtenir le statut du scénario 1
curl http://localhost:8000/scenarios/api/scenario/1/status

# Obtenir tous les statuts en erreur pour l'EJ 1
curl 'http://localhost:8000/scenarios/api/ej/1/scenarios-status?only_failed=true'
```

## Intégration Future

L'API peut être utilisée pour:
- **Alertes**: Déclencher des notifications sur erreurs
- **Dashboard**: Afficher les KPIs en temps réel
- **Orchestration**: Rejouer automatiquement les scénarios en erreur
- **Monitoring**: Suivre la santé globale des scénarios par EJ
