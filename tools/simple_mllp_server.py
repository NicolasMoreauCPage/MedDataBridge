#!/usr/bin/env python3
"""
Serveur MLLP simple et robuste pour les tests roundtrip
"""

import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def build_hl7_ack(original_message: str) -> str:
    """Construit un ACK HL7 basique"""
    try:
        # Extraire le control ID du message original
        lines = original_message.split('\r')
        control_id = "UNKNOWN"
        for line in lines:
            if line.startswith('MSH|'):
                fields = line.split('|')
                if len(fields) > 9:
                    control_id = fields[9]  # MSH-10: Control ID
                break

        # Générer timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

        # Construire ACK
        ack = f"MSH|^~\\&|TEST_SERVER|TEST_FACILITY|TEST_CLIENT|TEST_FACILITY|{timestamp}||ACK||{control_id}|P|2.5\r"
        ack += f"MSA|AA|{control_id}"

        return ack

    except Exception as e:
        logger.error(f"Erreur construction ACK: {e}")
        return "MSH|^~\\&|TEST_SERVER|TEST_FACILITY|TEST_CLIENT|TEST_FACILITY|20231201||ACK||UNKNOWN|P|2.5\rMSA|AA|UNKNOWN"


async def handle_mllp_client(reader, writer):
    """Gère une connexion MLLP"""
    addr = writer.get_extra_info('peername')
    logger.info(f"Nouvelle connexion MLLP de {addr}")

    try:
        # Buffer pour accumuler les données
        buffer = b''

        while True:
            # Lire les données
            data = await reader.read(1024)
            if not data:
                break

            buffer += data

            # Chercher le début et la fin du message MLLP
            start_idx = buffer.find(b'\x0b')  # <VT>
            end_idx = buffer.find(b'\x1c')    # <FS>

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                # Extraire le message HL7
                hl7_message = buffer[start_idx+1:end_idx].decode('utf-8', errors='ignore')
                logger.info(f"Message HL7 reçu ({len(hl7_message)} chars): {hl7_message[:50]}...")

                # Construire l'ACK
                ack_message = build_hl7_ack(hl7_message)
                logger.info(f"ACK généré: {ack_message[:50]}...")

                # Encoder en MLLP et envoyer
                mllp_ack = b'\x0b' + ack_message.encode('utf-8') + b'\x1c\r'
                writer.write(mllp_ack)
                await writer.drain()

                logger.info(f"ACK envoyé à {addr}")

                # Vider le buffer
                buffer = buffer[end_idx+2:]

    except Exception as e:
        logger.error(f"Erreur traitement client {addr}: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        logger.info(f"Connexion fermée avec {addr}")


async def start_mllp_server(host='localhost', port=2575):
    """Démarre le serveur MLLP"""
    logger.info(f"Démarrage serveur MLLP sur {host}:{port}")

    try:
        server = await asyncio.start_server(
            handle_mllp_client,
            host,
            port
        )

        logger.info(f"✅ Serveur MLLP actif sur {host}:{port}")
        logger.info("Prêt à recevoir des connexions...")

        async with server:
            await server.serve_forever()

    except KeyboardInterrupt:
        logger.info("Arrêt du serveur demandé")
    except Exception as e:
        logger.error(f"Erreur serveur: {e}")
        raise
    finally:
        logger.info("Serveur MLLP arrêté")


if __name__ == "__main__":
    asyncio.run(start_mllp_server())