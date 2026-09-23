# BUGFIX: Le module ght est exclu de __init__.py car il y a un problème d'import
# circulaire qui empêche le chargement complet de ses routes. Il est importé
# directement dans app/app.py à la place.
# À FAIRE: Investiguer et résoudre la vraie cause de l'import circulaire

# Les sous-modules sont importés explicitement par les consommateurs (notamment
# ``app.app``). Ne pas les réexporter ici : cela charge tout le graphe des
# routeurs au seul import du paquet et masque les dépendances réelles.
