#!/usr/bin/env python3
"""
Test roundtrip ultra-simple pour vérifier l'intégration réseau
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))


def decode_hl7_payload(payload: str) -> str:
    """Décode un payload HL7 avec séquences d'échappement"""
    if not payload:
        return payload
    return payload.replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t')


async def send_hl7_message(message: str, host='localhost', port=2575):
    """Envoie un message HL7 et retourne la réponse"""
    try:
        # Encoder le message en MLLP
        mllp_message = b'\x0b' + message.encode('utf-8') + b'\x1c\r'

        reader, writer = await asyncio.open_connection(host, port)

        # Envoyer le message
        writer.write(mllp_message)
        await writer.drain()

        # Lire la réponse
        response_data = await reader.read(1024)
        response = response_data.decode('utf-8', errors='ignore')

        writer.close()
        await writer.wait_closed()

        return response.strip()
    except Exception as e:
        return f"ERROR: {e}"


async def test_basic_hl7_message():
    """Test avec un message HL7 basique"""
    print("🧪 Test message HL7 basique")

    # Message HL7 simple
    hl7_message = """MSH|^~\\&|TEST_APP|TEST_FACILITY|TARGET_APP|TARGET_FACILITY|20231201||ADT^A31|TEST001|P|2.5
EVN||20231201120000|||TEST^USER
PID|||123456^^^TEST^PI||DOE^JOHN^^^MR.||19800101|M"""

    print(f"📤 Envoi message ({len(hl7_message)} chars)")
    print(f"Message: {hl7_message[:100]}...")

    response = await send_hl7_message(hl7_message)
    print(f"📥 Réponse: {response[:200]}...")

    # Valider la réponse
    if 'MSA|AA|' in response:
        print("✅ ACK positif reçu - Intégration réseau OK")
        return True
    elif 'ERROR' in response:
        print(f"❌ Erreur réseau: {response}")
        return False
    else:
        print(f"⚠️ Réponse inattendue: {response[:50]}...")
        return False


async def test_scenario_payloads():
    """Test avec des payloads réels de scénarios (sans DB)"""
    print("\n🧪 Test payloads réels de scénarios")

    # Payloads HL7 extraits manuellement (pour éviter les problèmes DB)
    test_payloads = [
        # A31 simple
        r"MSH|^~\&|CPAGE|CPAGE|SILLAGE|SILLAGE|20210622173518||ADT^A31^ADT_A05|1000064485|P|2.5^FRA^2.9|||||FRA|8859/1\rEVN||20210622173518|||PAT^ADMIN PAT-Cpage I^ADM PAT^^^^^^CPAGE&1.2.250.1.154&ISO|20210622173518\rPID|||000010265731^^^CPAGE&1.2.250.1.211.10.200.2&L^PI~0010265731^^^CPAGE^MR||ADRTROIS^TOUSSAINT^TOUSSAINT^^M.^^D~ADRTROIS^TOUSSAINT^TOUSSAINT^^M.^^L||19600101|M|||Rue Du GAPwhhd^^DIJON^^21000^FRA^H~^^AREGNO^20020^20220^FRA^BDL^^20020|||||U||||||||N||FRA^ISO 3166 alpha-3||||N||VALI\rPD1||||||",

        # A28 simple
        r"MSH|^~\&|CPAGE|CPAGE|SILLAGE|SILLAGE|20210622173518||ADT^A28^ADT_A05|1000064484|P|2.5^FRA^2.9|||||FRA|8859/1\rEVN||20210622173518|||PAT^ADMIN PAT-Cpage I^ADM PAT^^^^^^CPAGE&1.2.250.1.154&ISO|20210622173518\rPID|||000000386279^^^CPAGE&1.2.250.1.211.10.200.2&L^PI~2100083^^^CPAGE^MR||AUTOINT^PAUL^^^M.^^D~AUTOINT^PAUL^^^M.^^L||19820202|M|||Route Des Chats^^DIJON^^21000^FRA^H|||||M|||||||||1|||||N|||||||||"
    ]

    success_count = 0

    for i, payload in enumerate(test_payloads, 1):
        print(f"\n  Test {i}/{len(test_payloads)}:")

        # Décoder le payload
        decoded = decode_hl7_payload(payload)
        print(f"    📤 Envoi payload décodé ({len(decoded)} chars)")

        response = await send_hl7_message(decoded)
        print(f"    📥 Réponse: {response[:100]}...")

        if 'MSA|AA|' in response:
            print("    ✅ ACK positif")
            success_count += 1
        else:
            print(f"    ❌ Pas d'ACK positif: {response[:50]}...")

    print(f"\n📊 Résultat: {success_count}/{len(test_payloads)} payloads réussis")
    return success_count == len(test_payloads)


async def main():
    """Fonction principale"""
    print("🚀 Test roundtrip complet - Vérification intégration réseau")

    # Test 1: Message basique
    basic_ok = await test_basic_hl7_message()

    # Test 2: Payloads réels
    payloads_ok = await test_scenario_payloads()

    # Résumé
    print("\n" + "="*60)
    print("📊 RÉSULTATS TEST ROUNDTRIP COMPLET")
    print("="*60)

    print(f"Message HL7 basique: {'✅ OK' if basic_ok else '❌ ÉCHEC'}")
    print(f"Payloads réels: {'✅ OK' if payloads_ok else '❌ ÉCHEC'}")

    if basic_ok and payloads_ok:
        print("\n🎉 INTÉGRATION COMPLÈTE VALIDÉE !")
        print("✅ Communication MLLP fonctionnelle")
        print("✅ Messages HL7 envoyés et reçus")
        print("✅ ACKs générés correctement")
        print("✅ Parsing et décodage HL7 opérationnel")
    else:
        print("\n⚠️ Problèmes d'intégration détectés")


if __name__ == "__main__":
    asyncio.run(main())