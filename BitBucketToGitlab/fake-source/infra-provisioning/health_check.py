#!/usr/bin/env python3
"""Vérifie qu'un port répond. Idiome data/API glue (procédural)."""
import sys
import socket


def check(port: int, host: str = "127.0.0.1", timeout: float = 2.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    ok = check(port)
    print(f"health: port {port} {'OK' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)
