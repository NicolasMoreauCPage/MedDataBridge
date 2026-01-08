#!/bin/bash
# Script d'archivage des données legacy
# À exécuter périodiquement pour nettoyer les données obsolètes

set -e

echo "🗂️  Vérification des données candidates à l'archivage..."

# Fonction pour archiver un répertoire
archive_dir() {
    local dir=$1
    local archive_name="${dir}_$(date +%Y%m%d_%H%M%S).tar.gz"

    if [ -d "$dir" ] && [ "$(ls -A $dir 2>/dev/null)" ]; then
        echo "📦 Archivage de $dir vers $archive_name"
        tar -czf "$archive_name" "$dir"
        echo "🗑️  Suppression du répertoire $dir"
        rm -rf "$dir"
        echo "✅ $dir archivé avec succès"
    else
        echo "ℹ️  $dir est vide ou n'existe pas, ignoré"
    fi
}

# Archiver les données temporaires si elles sont anciennes (> 30 jours)
echo "🔍 Vérification des données temporaires..."
find data/tmp/ -type f -mtime +30 -exec ls -la {} \; | head -5 || echo "Aucune donnée temporaire ancienne trouvée"

# Archiver les données legacy si elles ne sont plus utilisées
echo "🔍 Vérification des données legacy..."
if [ -d "data/one_shot_legacy" ]; then
    echo "⚠️  Données legacy détectées dans data/one_shot_legacy/"
    echo "   À archiver manuellement si elles ne sont plus nécessaires"
    echo "   Commande: $0 --archive-legacy"
fi

# Option pour archiver les données legacy
if [ "$1" = "--archive-legacy" ]; then
    echo "🗄️  Archivage des données legacy..."
    archive_dir "data/one_shot_legacy"
fi

# Nettoyer les fichiers de log anciens
echo "🧹 Nettoyage des logs anciens..."
find . -name "*.log" -type f -mtime +90 -exec rm -f {} \; 2>/dev/null || true

echo "✅ Nettoyage terminé"