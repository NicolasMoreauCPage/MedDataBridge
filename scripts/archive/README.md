# Scripts de seeding archivés

Ces scripts ont été consolidés dans `scripts/maintenance/init_db.py` qui offre maintenant toutes leurs fonctionnalités.

## Scripts archivés :

- `init_full.py` : Fonctionnalités intégrées dans init_db.py avec les options --minimal, --rich, --demo-scenarios
- `seed_demo_complete.py` : Fonctionnalités de seeding riche intégrées, cotations médicales disponibles via --with-cotations
- `seed_hl7_scenarios.py` (2 versions) : Intégrés dans init_db.py et inclus par défaut (partie intégrante du programme)

## Migration :

Tous ces scripts peuvent être remplacés par des appels à `scripts/maintenance/init_db.py` avec les options appropriées :

- Seed minimal : `python scripts/maintenance/init_db.py --minimal`
- Seed riche : `python scripts/maintenance/init_db.py --rich`
- Scénarios démo : `python scripts/maintenance/init_db.py --demo-scenarios`
- Init complète avec tous les scénarios : `python scripts/maintenance/init_db.py` (comprend tous les scénarios HL7/HPRIM par défaut)
- Init sans scénarios : `python scripts/maintenance/init_db.py --skip-scenarios`

**Note importante :** Les scénarios HL7/HPRIM font maintenant partie intégrante du programme et sont inclus par défaut. Utilisez `--skip-scenarios` seulement si vous voulez une init sans scénarios.

Ces scripts sont conservés pour référence mais ne devraient plus être utilisés directement.