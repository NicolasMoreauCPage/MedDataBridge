"""Primitives MLLP (HL7v2) côté serveur et client.

Contenu
- Framing/déframing MLLP: `frame_hl7`, `deframe_hl7`
- Parsing minimal MSH: `parse_msh_fields`
- Construction d'ACK: `build_ack`
- Serveur asyncio: `start_mllp_server` / `stop_mllp_server`
- Client simple: `send_mllp`

Traces
- Activer `MLLP_TRACE=1` pour obtenir des dumps HEX des trames reçues et
    des ACK émis dans les logs (logger "mllp").
"""

import asyncio
import logging
import os
import inspect
from typing import Callable, Awaitable, List
from datetime import datetime
from sqlmodel import Session
from app.models.endpoints import SystemEndpoint
from app.services.pam_profile_fr import expected_structure

logger = logging.getLogger("mllp")
TRACE = os.getenv("MLLP_TRACE", "0") in ("1", "true", "True")

START_BLOCK = b"\x0b"  # VT
END_BLOCK = b"\x1c"  # FS
CARRIAGE_RETURN = b"\x0d"


def _hl7_charset(message: str) -> str:
    """Retourne le codec Python correspondant à MSH-18.

    Le profil France privilégie ``UNICODE UTF-8``. ISO-8859-15 reste pris en
    charge pour les correspondants historiques ; un MSH-18 absent utilise UTF-8.
    """
    msh = next(
        (
            line
            for line in message.replace("\n", "\r").split("\r")
            if line.startswith("MSH|")
        ),
        "",
    )
    parts = msh.split("|")
    declared = parts[17].strip().upper() if len(parts) > 17 else ""
    if declared in {"8859/15", "ISO-8859-15", "ISO 8859/15"}:
        return "iso-8859-15"
    if declared in {"8859/1", "ISO-8859-1", "ISO 8859/1"}:
        return "iso-8859-1"
    return "utf-8"


def frame_hl7(message: str) -> bytes:
    """Encapsule un message HL7 en trame MLLP (VT <msg> FS CR).

    Les octets transmis sont cohérents avec MSH-18, au lieu d'annoncer un jeu
    de caractères puis d'envoyer systématiquement de l'UTF-8.
    """
    return (
        START_BLOCK
        + message.encode(_hl7_charset(message))
        + END_BLOCK
        + CARRIAGE_RETURN
    )


def deframe_hl7(stream: bytes) -> List[str]:
    """Extrait les messages HL7 d'un flux de bytes MLLP.

    Retourne une liste de messages HL7 (déframés, codés en UTF-8). Les
    segments sont séparés par CR (\r) conformément à HL7v2.
    """
    msgs = []
    buf = memoryview(stream)
    while True:
        start = bytes(buf).find(START_BLOCK)
        if start < 0:
            break
        end = bytes(buf).find(END_BLOCK, start + 1)
        if end < 0:
            break
        payload = bytes(buf)[start + 1 : end]
        # MSH est ASCII ; un premier décodage latin-1 permet de lire MSH-18 sans
        # perdre d'octet, puis le contenu est décodé avec le codec annoncé.
        probe = payload.decode("latin-1", errors="replace")
        msg = payload.decode(_hl7_charset(probe), errors="replace")
        cr = bytes(buf).find(CARRIAGE_RETURN, end + 1)
        buf = buf[cr + 1 :] if cr >= 0 else buf[end + 1 :]
        msgs.append(msg)
    return msgs


def parse_msh_fields(message: str) -> dict:
    """Parse rapide de MSH pour extraire quelques champs utiles.

    Champs retournés: enc, sending_app, sending_facility, receiving_app,
    receiving_facility, datetime, msg_type, type, trigger, control_id,
    processing_id, version.
    """
    lines = message.split("\r")
    msh = next(
        (line for line in lines if line.startswith("MSH")), "MSH|^~\\&|||||||||||||"
    )
    parts = msh.split("|")
    enc = parts[1] if len(parts) > 1 and parts[1] else "^~\\&"
    msg_type = parts[8] if len(parts) > 8 else ""
    comp = msg_type.split("^")
    msg_type_family = comp[0] if len(comp) >= 1 else ""
    trigger = comp[1] if len(comp) >= 2 else ""
    return {
        "enc": enc,
        "sending_app": parts[2] if len(parts) > 2 else "",
        "sending_facility": parts[3] if len(parts) > 3 else "",
        "receiving_app": parts[4] if len(parts) > 4 else "",
        "receiving_facility": parts[5] if len(parts) > 5 else "",
        "datetime": parts[6] if len(parts) > 6 else "",
        "msg_type": msg_type,
        "type": msg_type_family,
        "trigger": trigger,
        "control_id": parts[9] if len(parts) > 9 else "",
        "processing_id": parts[10] if len(parts) > 10 else "P",
        "version": parts[11] if len(parts) > 11 else "2.5",
        "country_code": parts[16] if len(parts) > 16 else "",
        "charset": parts[17] if len(parts) > 17 else "",
    }


def build_ack(original: str, ack_code: str = "AA", text: str = "") -> str:
    """Construit un ACK HL7 (MSH+MSA et ERR si AE/AR) en réponse à `original`."""
    f = parse_msh_fields(original)
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    structure = expected_structure(f["trigger"])
    msh9 = (
        f"ACK^{f['trigger']}^{structure}"
        if f["trigger"] and structure
        else (f"ACK^{f['trigger']}" if f["trigger"] else "ACK")
    )
    country_code = f["country_code"] or "FRA"
    charset = f["charset"] or "UNICODE UTF-8"
    msh = "MSH|{enc}|{send_app}|{send_fac}|{recv_app}|{recv_fac}|{ts}||{msh9}|ACK{ts}|{proc}|{ver}|||||{country}|{charset}".format(
        enc=f["enc"],
        send_app=f["receiving_app"],
        send_fac=f["receiving_facility"],
        recv_app=f["sending_app"],
        recv_fac=f["sending_facility"],
        ts=now,
        msh9=msh9,
        proc=f["processing_id"],
        ver=f["version"],
        country=country_code,
        charset=charset,
    )
    msa = f"MSA|{ack_code}|{f['control_id']}|{text or ''}"
    segs = [msh, msa]
    if ack_code in ("AE", "AR"):
        segs.append(f"ERR|||207^{text or 'Application error'}^HL70357|E")
    return "\r".join(segs) + "\r"


def _hexdump(b: bytes, width: int = 16) -> str:
    """Représentation hexadécimale lisible d'un buffer bytes (debug)."""
    lines = []
    for i in range(0, len(b), width):
        chunk = b[i : i + width]
        hexs = " ".join(f"{x:02x}" for x in chunk)
        text = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        lines.append(f"{i:04x}  {hexs:<{width * 3}}  {text}")
    return "\n".join(lines)


async def start_mllp_server(
    host: str,
    port: int,
    on_message: Callable[[str, Session, SystemEndpoint], Awaitable[str]],
    endpoint: SystemEndpoint,
    session_factory: Callable[[], Session],
):
    """Démarre un serveur MLLP asyncio.

    - `on_message` est appelé pour chaque message HL7 détramé avec une
      session courte (via `session_factory`). Il doit retourner un ACK HL7.
    - En cas d'erreur applicative, un ACK AE est renvoyé; en erreur
      système, un ACK AR.
    """
    # Extraire les valeurs de l'endpoint avant le handler pour éviter DetachedInstanceError
    endpoint_name = endpoint.name
    endpoint_id = endpoint.id

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        logger.info(f"[MLLP] Connect {peer} -> {host}:{port} ({endpoint_name})")
        try:
            # Read until we have at least one complete MLLP frame (END_BLOCK + CR).
            # Using repeated small reads is robust to partial TCP segments.
            buf = bytearray()
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                buf.extend(chunk)
                # check for END_BLOCK followed by CARRIAGE_RETURN
                end_idx = bytes(buf).find(END_BLOCK)
                if end_idx >= 0:
                    # ensure CR follows END_BLOCK (may be missing if truncated)
                    if (
                        len(buf) > end_idx + 1
                        and bytes(buf)[end_idx + 1 : end_idx + 2] == CARRIAGE_RETURN
                    ):
                        break

            data = bytes(buf)
            logger.info(f"[MLLP] RX {len(data)} bytes from {peer} on {host}:{port}")
            if TRACE:
                logger.debug("[MLLP] RX HEX:\n" + _hexdump(data))

            messages = deframe_hl7(data)
            if not messages:
                # Rien de framé MLLP → renvoyer un AE générique pour tracer la liaison
                logger.warning(f"[MLLP] No MLLP frame from {peer} on {host}:{port}")
                ack = build_ack("MSH|^~\\&||||||||||P|2.5", "AE", "No MLLP frame")
                writer.write(frame_hl7(ack))
                await writer.drain()
            else:
                for idx, msg in enumerate(messages, 1):
                    f = parse_msh_fields(msg)
                    ctrl = f.get("control_id")
                    logger.info(
                        f"[MLLP] Frame {idx}/{len(messages)} MSH-10={ctrl or '∅'} MSH-9={f.get('msg_type')}"
                    )
                    with session_factory() as s:
                        try:
                            # Recharger l'endpoint depuis la session courante pour éviter DetachedInstanceError
                            endpoint_fresh = s.get(SystemEndpoint, endpoint_id)
                            # Support both async callables and sync wrappers that
                            # may return a dict/str. Accept awaitable results.
                            res = on_message(msg, s, endpoint_fresh)
                            if inspect.isawaitable(res):
                                ack = await res
                            else:
                                # sync wrapper returns dict {'status':..., 'ack': '...'} or directly str
                                if isinstance(res, dict):
                                    ack = res.get("ack")
                                else:
                                    ack = res
                            writer.write(frame_hl7(ack))
                            await writer.drain()
                            if TRACE:
                                logger.debug(
                                    "[MLLP] TX ACK:\n" + ack.replace("\r", "\\r\n")
                                )
                        except Exception as e:
                            logger.exception(
                                f"[MLLP] Error processing frame {idx}: {e}"
                            )
                            ack = build_ack(msg, ack_code="AE", text=str(e)[:80])
                            writer.write(frame_hl7(ack))
                            await writer.drain()
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as exc:
                logger.debug("Optional operation skipped", exc_info=exc)
            logger.info(f"[MLLP] Disconnect {peer} from {host}:{port}")

    try:
        server = await asyncio.start_server(handle, host=host, port=port)
        # logger.info(f"✅ MLLP {endpoint.name} listening on {sockname[0]}:{sockname[1]}")
        return server
    except OSError as e:
        logger.error(f"❌ Cannot bind MLLP {endpoint.name} on {host}:{port} — {e}")
        raise


async def send_mllp(host: str, port: int, message: str, timeout: float = 10.0) -> str:
    """Envoie un message HL7 en MLLP et retourne le premier ACK reçu."""
    reader, writer = await asyncio.open_connection(host, port)
    writer.write(frame_hl7(message))
    await writer.drain()
    data = await asyncio.wait_for(reader.read(65536), timeout=timeout)
    writer.close()
    await writer.wait_closed()
    frames = deframe_hl7(data)
    return frames[0] if frames else ""


async def stop_mllp_server(server: asyncio.base_events.Server) -> None:
    """Ferme proprement le serveur créé par asyncio.start_server."""
    if server is None:
        return
    server.close()
    await server.wait_closed()
