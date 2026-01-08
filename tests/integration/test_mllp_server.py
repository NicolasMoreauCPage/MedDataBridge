#!/usr/bin/env python3
"""
Serveur MLLP de test simple pour les tests de roundtrip

Ce serveur accepte les connexions MLLP sur le port 2575 (port MLLP standard)
et retourne un ACK HL7v2 basique pour chaque message reçu.

Usage:
    python test_mllp_server.py [--port PORT] [--host HOST]

Arguments:
    --port PORT : Port d'écoute (défaut: 2575)
    --host HOST : Adresse d'écoute (défaut: localhost)
"""

import asyncio
import logging
import argparse
from datetime import datetime

from app.services.mllp import deframe_hl7, frame_hl7, parse_msh_fields

logger = logging.getLogger("test_mllp_server")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def build_ack_message(original_msh: str) -> str:
    """Construit un message ACK HL7v2 basique"""
    # Parser le MSH original
    msh_fields = parse_msh_fields(original_msh)

    # Générer un timestamp pour l'ACK
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # Construire le message ACK
    ack_message = f"""MSH|^~\\&|TEST_ACK|TEST_FACILITY|TARGET_APP|TARGET_FACILITY|{timestamp}||ACK^{msh_fields.get('control_id', 'UNKNOWN')}|ACK_{msh_fields.get('control_id', 'UNKNOWN')}|P|2.5
MSA|AA|{msh_fields.get('control_id', 'UNKNOWN')}"""

    return ack_message

async def handle_mllp_connection(reader, writer):
    """Gère une connexion MLLP entrante"""
    addr = writer.get_extra_info('peername')
    logger.info(f"Connexion MLLP reçue de {addr}")

    try:
        # Lire les données MLLP
        data = await reader.read(65536)
        if not data:
            logger.warning(f"Aucune donnée reçue de {addr}")
            return

        logger.info(f"Données reçues ({len(data)} bytes) de {addr}")

        # Déframer le message HL7
        messages = deframe_hl7(data)
        if not messages:
            logger.warning(f"Aucun message HL7 valide reçu de {addr}")
            return

        logger.info(f"{len(messages)} message(s) HL7 reçu(s)")

        # Traiter chaque message
        for i, message in enumerate(messages, 1):
            logger.info(f"Traitement du message {i}: {message[:100]}...")

            # Construire l'ACK
            ack_message = build_ack_message(message)
            logger.info(f"ACK généré: {ack_message[:100]}...")

            # Encoder et envoyer l'ACK
            ack_data = frame_hl7(ack_message)
            writer.write(ack_data)
            await writer.drain()

            logger.info(f"ACK envoyé à {addr}")

    except Exception as e:
        logger.error(f"Erreur lors du traitement de la connexion {addr}: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        logger.info(f"Connexion fermée avec {addr}")

async def start_test_mllp_server(host: str = "localhost", port: int = 2575):
    """Démarre le serveur MLLP de test"""
    logger.info(f"Démarrage du serveur MLLP de test sur {host}:{port}")

    server = await asyncio.start_server(
        handle_mllp_connection,
        host,
        port
    )

    logger.info(f"✅ Serveur MLLP de test démarré sur {host}:{port}")
    logger.info("Serveur actif - prêt à recevoir des connexions MLLP")

    try:
        async with server:
            # Servir indéfiniment jusqu'à interruption
            await server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Arrêt du serveur demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur du serveur: {e}")
    finally:
        server.close()
        await server.wait_closed()
        logger.info("Serveur MLLP de test arrêté")

def main():
    parser = argparse.ArgumentParser(description="Serveur MLLP de test pour les tests de roundtrip")
    parser.add_argument("--host", default="localhost", help="Adresse d'écoute (défaut: localhost)")
    parser.add_argument("--port", type=int, default=2575, help="Port d'écoute (défaut: 2575)")

    args = parser.parse_args()

    try:
        asyncio.run(start_test_mllp_server(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("Serveur arrêté")

if __name__ == "__main__":
    main()