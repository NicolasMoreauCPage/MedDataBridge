#!/usr/bin/env python3
"""Simple MLLP test client.

Usage: python tools/send_mllp_test.py [host] [port]

Sends a sample ADT^A01 HL7 message and prints received ACK.
"""
import socket
import sys

START = b"\x0b"
END = b"\x1c"
CR = b"\x0d"

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 2200

HL7 = (
    "MSH|^~\\&|SENDER|SENDER_FAC|RECV|RECV_FAC|202512101630||ADT^A01|1001|P|2.5\r"
    "PID|1||12345^^^HOSP\r"
)

def frame(msg: str) -> bytes:
    return START + msg.encode("utf-8") + END + CR

def deframe(data: bytes) -> str:
    try:
        start = data.index(START) + 1
        end = data.index(END, start)
        return data[start:end].decode("utf-8", errors="replace")
    except Exception:
        return data.decode("utf-8", errors="replace")

def main():
    print(f"Sending to {HOST}:{PORT}")
    with socket.create_connection((HOST, PORT), timeout=10) as s:
        s.sendall(frame(HL7))
        data = s.recv(65536)
        print("Raw RX:", data)
        print("Deframed ACK:\n", deframe(data))

if __name__ == "__main__":
    main()
