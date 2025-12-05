# Parsing et transport HL7

Parsing HL7

- Emplacement principal : `app/infrastructure/hl7/parsing/`.

- Chaque parseur gère un segment complexe : `pid_parser.py`, `pv1_parser.py`, `zbe_parser.py`, `mrg_parser.py`.

- Utilitaires : `segment_utils.py` pour fonctions réutilisables (split, composants, répétitions).

- `app/services/hl7_parser.py` et `app/services/adt_parser.py` orchestrent l'extraction des données nécessaires pour la validation et la création d'entités métier.

Comportement

- Parsing ligne-based : séparation par '\r' / '\n' puis split par '|' et '^'.

- Ne gère pas toutes les complexités d'échappement HL7 ; les champs courants (CX, XPN, XTN, TS, XAD) sont supportés.

Comportement

- Parsing ligne-based : séparation par '\r' / '\n' puis split par '|' et '^'.

- Ne gère pas toutes les complexités d'échappement HL7 ; les champs courants (CX, XPN, XTN, TS, XAD) sont supportés.

Transport

- MLLP : `app/services/mllp.py` expose fonctions d'envoi et réception en MLLP; `app/services/mllp_manager.py` gère la mise en écoute et le multiplexage.

- File poller : `app/services/file_poller.py` surveille des répertoires entrants/sortants pour ingestion ou publication.

- FHIR/HTTP transport : `app/services/fhir_transport.py` et `app/services/fhir_export_service.py` pour échanges FHIR.

Robustesse

- Les transporteurs écrivent systématiquement dans `MessageLog` et déclenchent la validation avant persistance/émission.

- Reprise et retry : `app/services/scheduler.py` et jobs de fond gèrent les tâches réessayées.

Sécurité

- Connexions MLLP rarement chiffrées ; privilégier réseau sécurisé ou tunnel.

- Endpoints administratifs protégés par auth (`app/auth.py` et routeurs `app/routers/auth.py`).
