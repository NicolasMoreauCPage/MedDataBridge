#!/usr/bin/env python3
"""Petit client MLLP pour envoyer un message HL7 à un endpoint.

Usage: python tools/mllp_client.py --host 127.0.0.1 --port 2575 --file Doc/examples/a01.hl7
"""
import socket
import argparse

SB = b"\x0b"  # VT
EB = b"\x1c"  # FS
CR = b"\x0d"

def send_mllp(host: str, port: int, data: bytes) -> bytes:
    framed = SB + data.replace(b"\n", CR) + EB + CR
    with socket.create_connection((host, port), timeout=10) as s:
        s.sendall(framed)
        # try to read a response (ACK)
        try:
            resp = s.recv(65536)
        except Exception:
            resp = b""
    return resp

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=2575)
    p.add_argument("--file", required=True)
    args = p.parse_args()
    data = open(args.file, "rb").read()
    resp = send_mllp(args.host, args.port, data)
    if resp:
        print("Received:", resp)
    else:
        print("No response or empty response")

if __name__ == "__main__":
    main()
