#!/usr/bin/env python3
"""Roda os testes de cada serviço, um de cada vez (cada serviço é um projeto próprio).

Uso:  pip install -r requirements-dev.txt
      python scripts/testar_tudo.py
"""
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SERVICOS = ["usuarios", "inventario", "chamados", "notificacoes", "gateway"]


def main() -> int:
    resultados = {}
    for servico in SERVICOS:
        print(f"\n=== {servico} ===", flush=True)
        resultados[servico] = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=RAIZ / servico).returncode == 0
    print("\nResumo:")
    for servico, passou in resultados.items():
        print(f"  {'OK    ' if passou else 'FALHOU'} {servico}")
    return 0 if all(resultados.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
