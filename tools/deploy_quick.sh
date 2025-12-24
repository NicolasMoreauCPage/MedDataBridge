#!/bin/bash
"""
Script de déploiement rapide pour MedDataBridge
Gère automatiquement la récupération de base de données et l'application des migrations
"""

set -e  # Arrêter en cas d'erreur

echo "🚀 Déploiement rapide MedDataBridge"
echo "==================================="

# Variables
DB_PATH="${1:-meddatabridge.db}"
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"

# Fonction de nettoyage
cleanup() {
    echo "🧹 Nettoyage..."
    # Tuer les processus potentiels
    pkill -f "uvicorn.*meddatabridge" 2>/dev/null || true
    pkill -f "alembic" 2>/dev/null || true
    sleep 2
}

# Fonction de sauvegarde
backup_database() {
    echo "💾 Création d'une sauvegarde..."
    mkdir -p "$BACKUP_DIR"
    if [ -f "$DB_PATH" ]; then
        cp "$DB_PATH" "$BACKUP_DIR/"
        echo "✅ Sauvegarde créée: $BACKUP_DIR/$(basename $DB_PATH)"
    fi
}

# Fonction de récupération de base de données
recover_database() {
    echo "🔧 Vérification de la base de données..."

    if [ -f "$DB_PATH" ]; then
        # Tester l'intégrité
        if python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('$DB_PATH')
    cursor = conn.cursor()
    cursor.execute('PRAGMA integrity_check;')
    result = cursor.fetchone()
    conn.close()
    if result and result[0] == 'ok':
        print('✅ Base de données intacte')
        exit(0)
    else:
        print('❌ Base de données corrompue')
        exit(1)
except Exception as e:
    print(f'❌ Erreur d accès: {e}')
    exit(1)
"; then
            echo "✅ Base de données OK, pas de récupération nécessaire"
            return 0
        else
            echo "❌ Base de données corrompue détectée"
        fi
    else
        echo "ℹ️  Aucune base de données trouvée, elle sera créée"
        return 0
    fi

    # Tentative de récupération
    echo "🔄 Tentative de récupération..."
    backup_database

    # Utiliser le script de récupération amélioré si disponible
    if [ -f "recover_database_v2.py" ]; then
        echo "y" | python3 recover_database_v2.py "$DB_PATH" || true
    elif [ -f "recover_database.py" ]; then
        echo "y" | python3 recover_database.py "$DB_PATH" || true
    fi

    # Supprimer et recréer si nécessaire
    if [ -f "$DB_PATH" ]; then
        echo "🗑️  Suppression forcée de l'ancienne base..."
        rm -f "${DB_PATH}"*
        rm -f /tmp/sqlite_*
    fi
}

# Fonction d'application des migrations
apply_migrations() {
    echo "📦 Application des migrations Alembic..."

    # Vérifier que les migrations existent
    if [ ! -d "alembic/versions" ]; then
        echo "❌ Dossier des migrations introuvable"
        exit 1
    fi

    # Appliquer les migrations
    if alembic upgrade head; then
        echo "✅ Migrations appliquées avec succès"

        # Vérifier la version actuelle
        CURRENT=$(alembic current 2>/dev/null | grep -o '[a-f0-9]\{12\}' || echo "unknown")
        echo "📋 Version actuelle: $CURRENT"

        if [[ "$CURRENT" == *"bdebea0e6af4"* ]]; then
            echo "✅ Migration IHE PAM appliquée"
        fi
    else
        echo "❌ Échec de l'application des migrations"
        exit 1
    fi
}

# Fonction de vérification finale
verify_deployment() {
    echo "🔍 Vérification du déploiement..."

    # Vérifier que la base contient les scénarios
    SCENARIO_COUNT=$(python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('$DB_PATH')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM interopscenario;')
    count = cursor.fetchone()[0]
    conn.close()
    print(count)
except Exception as e:
    print(f'Erreur: {e}')
    print(0)
")

    if [ "$SCENARIO_COUNT" -gt 0 ]; then
        echo "✅ $SCENARIO_COUNT scénarios trouvés en base"
    else
        echo "⚠️  Aucun scénario trouvé - vérifiez les migrations"
    fi
}

# Script principal
main() {
    cleanup
    recover_database
    apply_migrations
    verify_deployment

    echo ""
    echo "🎉 Déploiement terminé avec succès !"
    echo ""
    echo "🚀 Pour démarrer l'application:"
    echo "   uvicorn app.app:app --host 0.0.0.0 --port 8000 --reload"
    echo ""
    echo "📊 Pour vérifier les scénarios:"
    echo "   python3 -c \"import sqlite3; conn = sqlite3.connect('$DB_PATH'); print(len(conn.execute('SELECT * FROM interopscenario;').fetchall())); conn.close()\""
}

# Vérifier les arguments
if [ $# -gt 1 ]; then
    echo "Usage: $0 [database_path]"
    echo "Exemple: $0 /opt/meddatabridge/data/meddatabridge.db"
    exit 1
fi

# Exécuter le script
main "$@"