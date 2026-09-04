#!/usr/bin/env python3
"""
ci_procesar.py — En CI: convierte cada .drawio de diagrama/ en un stack de Terraform.

Determinista (sin LLM): descifrar_drawio + leer_excel + conciliar + generar_terraform.
Busca .drawio (y .xlsx opcional) en:  diagrama/  ·  inbox/  ·  raíz del repo.
Por cada diagrama:
  - genera stacks/<nombre>/*.tf  (+ discrepancias.md, inventario.md, diagrama.drawio)
  - quita el archivo de la carpeta de entrada

Uso:  python scripts/ci_procesar.py
Salida (para GITHUB_OUTPUT):  stacks=stacks/a stacks/b   nuevos=2
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]              # raíz del repo
ENTRADAS = ["diagrama", "inbox", ""]                    # "" = raíz
STACKS = RAIZ / "stacks"
sys.path.insert(0, str(Path(__file__).parent))
import pipeline  # noqa: E402


def _dirs_entrada() -> list[Path]:
    return [(RAIZ / e) if e else RAIZ for e in ENTRADAS]


def _diagramas() -> list[Path]:
    vistos, out = set(), []
    for base in _dirs_entrada():
        if not base.is_dir():
            continue
        for d in sorted(base.glob("*.drawio")):
            if d.resolve() not in vistos and "stacks" not in d.parts:
                vistos.add(d.resolve())
                out.append(d)
    return out


def _slug(nombre: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z._-]+", "-", nombre.strip().lower()).strip("-._")
    s = re.sub(r"^[0-9a-fA-F][0-9a-fA-F-]{18,}_", "", s)   # UUID_ de una subida previa
    return s or "stack"


def _excel_para(drawio: Path) -> Path | None:
    par = drawio.with_suffix(".xlsx")
    if par.is_file():
        return par
    xs = [x for base in _dirs_entrada() if base.is_dir() for x in sorted(base.glob("*.xlsx"))]
    return xs[0] if len(xs) == 1 else None


def procesar_uno(drawio: Path) -> str:
    nombre = _slug(drawio.stem)
    destino = STACKS / nombre
    xl = _excel_para(drawio)
    with tempfile.TemporaryDirectory() as tmp:
        argv = ["--drawio", str(drawio), "--salida", tmp]
        if xl:
            argv += ["--excel", str(xl)]
        rc = pipeline.main(argv)
        if rc != 0:
            raise SystemExit(f"pipeline falló para {drawio.name} (rc={rc})")
        shutil.rmtree(destino, ignore_errors=True)
        destino.mkdir(parents=True)
        for f in (Path(tmp) / "terraform").glob("*"):
            if f.is_file() and not f.name.startswith(".terraform"):
                shutil.copy2(f, destino / f.name)
        for n in ("discrepancias.md", "inventario.md"):
            if (Path(tmp) / n).is_file():
                shutil.copy2(Path(tmp) / n, destino / n)
    shutil.copy2(drawio, destino / "diagrama.drawio")
    if xl:
        shutil.copy2(xl, destino / "datos.xlsx")
    for p in [drawio] + ([xl] if xl else []):
        try:
            subprocess.run(["git", "rm", "-q", "-f", str(p.relative_to(RAIZ))],
                           cwd=RAIZ, check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            p.unlink(missing_ok=True)
    return f"stacks/{nombre}"


def main() -> int:
    hechos = []
    for d in _diagramas():
        print(f"::group::{d.name}")
        hechos.append(procesar_uno(d))
        print("::endgroup::")
    linea = " ".join(hechos)
    salida = os.environ.get("GITHUB_OUTPUT")
    if salida:
        with open(salida, "a", encoding="utf-8") as fh:
            fh.write(f"stacks={linea}\n")
            fh.write(f"nuevos={len(hechos)}\n")
    print(f"generados: {linea or '(ninguno)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
