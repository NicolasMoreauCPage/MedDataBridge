# Objectifs de performance et campagne de mesure

Ce document fixe les objectifs initiaux de latence et de capacité. Ils servent
de seuils de qualification et d'alerte, pas de promesse de débit absolue : le
résultat dépend notamment du matériel, du réseau, de PostgreSQL et des cibles
interopérables.

## Périmètre et objectifs initiaux

Les latences sont mesurées côté client HTTP, hors temps de saisie humaine et
hors indisponibilité d'une cible distante. `p50` décrit le cas courant et `p95`
le plafond visé pour la qualification.

| Parcours | Volume de référence | p50 | p95 | Indicateur complémentaire |
| --- | --- | ---: | ---: | --- |
| Recherche/liste patient ou venue | page de 100 lignes | 150 ms | 500 ms | liste toujours bornée |
| Timeline patient | 20 dossiers, 100 mouvements | 250 ms | 800 ms | au plus 4 `SELECT` |
| Export FHIR structure | 1 000 nœuds de structure | 1 s | 2,5 s | au plus 10 `SELECT` |
| Export FHIR patients, sans cache | page de 500 patients | 750 ms | 2 s | total et page SQL bornés |
| Export FHIR venues, sans cache | page de 500 venues | 1 s | 2,5 s | chargements groupés, sans N+1 |
| Export FHIR patients/venues, cache chaud | même page | 100 ms | 300 ms | clé de cache par page |
| Préparation d'un scénario | 120 messages vers 3 cibles | 5 s | 15 s | 360 livraisons créées |
| Traitement outbox | lot de 100 messages disponibles | 3 s | 10 s | hors délai du transport distant |

Un dépassement isolé est consigné; un dépassement p95 reproductible sur trois
campagnes est un échec de qualification et ouvre une investigation (plan SQL,
taille des pages, contention ou cible réseau).

## Protocole reproductible

1. Utiliser une base PostgreSQL dédiée, appliquée par Alembic, et Redis si la
   mesure couvre le cache. Noter versions, CPU, mémoire, latence réseau et
   paramètres de pool dans le rapport.
2. Charger le jeu de données de référence, puis redémarrer l'application afin
   de ne pas mélanger le coût du seed à la campagne.
3. Exécuter au moins 30 itérations par parcours. La requête de chauffe n'est
   pas comptée. Mesurer séparément les exports FHIR cache froid et cache chaud.
4. Conserver les rapports JSON et texte produits avec le commit testé. Ne pas
   comparer des résultats SQLite à un SLO PostgreSQL : SQLite reste utile pour
   les budgets de requêtes et les non-régressions unitaires.

Pour les exports FHIR :

```bash
python scripts/tools/benchmark_fhir_exports.py \
  --base-url http://localhost:8000 \
  --ej-id 1 \
  --iterations 30 \
  --page-limit 500 \
  --with-cache --without-cache
```

Le script appelle les routes réellement publiées, calcule p50 et p95 par
interpolation linéaire, et écrit les résultats dans `benchmark_results/`.

Les budgets SQL unitaires complètent cette campagne : ils détectent les N+1
sans dépendre de la vitesse de la machine. Ils ne remplacent pas une campagne
HTTP PostgreSQL, qui doit être exécutée en qualification avant mise en service.
