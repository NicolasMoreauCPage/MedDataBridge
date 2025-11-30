# Règles métier : transitions IHE PAM (`app/state_transitions.py`)

But
- Centraliser les règles qui définissent quelles transitions ADT sont autorisées
  (ex: A01 -> A03 autorisé, A04 -> A03 non autorisé pour consultation externe).

Principes
- `INITIAL_EVENTS` : événements autorisés en début de scénario (A01, A04, A05, A38).
- `ALLOWED_TRANSITIONS` : mapping {previous_event: set(next_events)}.
- Fonctions utilitaires : `get_allowed_transitions`, `is_valid_transition`, `assert_transition`.

Notes spécifiques
- A11 (annulation admission) : après A11 seul A04 ou A05 sont autorisés (nouvelle règle locale).
- Certains Z8x/Z9x (Z80..Z85, Z99) ont règles particulières (peuvent courir seulement en hospitalisation).

Utilisation
- `scenario_validation` appelle `is_valid_transition` pour valider la chaîne d'événements.
- Les handlers métier peuvent appeler `assert_transition` pour lever une exception si transition invalide.

Exemples
- Scénario valide : A05 -> A01 -> A02 -> A03
- Scénario invalide : A04 -> A03 (A03 non autorisé depuis A04 pour outpatient)
