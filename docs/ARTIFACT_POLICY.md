# Politique des artefacts de qualification

Les corpus de normes et les exemples source nécessaires à la lecture des tests
peuvent rester versionnés. En revanche, les résultats produits par une
exécution (bases SQLite, archives, captures, rapports JSON compressés,
exports temporaires) ne sont pas des sources : ils vont dans `artifacts/`,
ignoré par Git et publié par la CI avec son nom de workflow et sa révision.

Les rapports Markdown de `docs/reports/` restent courts, reproductibles et
référencent l'artefact CI au lieu d'y incorporer des données ou bases brutes.
Toute exception doit préciser son origine, son empreinte et sa raison de
conservation dans le rapport concerné.

Cette règle réduit les clones et évite que des données de test ou de recette
soient confondues avec le code livré.
