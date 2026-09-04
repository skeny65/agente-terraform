#!/usr/bin/env python3
"""
conciliar.py — Cruza el inventario del diagrama con los datos del Excel. SIN LLM.

Empareja por nombre (normalizado) cada nodo del .drawio con su fila del .xlsx,
adjunta los datos y produce un informe de discrepancias:
  - nodos del diagrama sin fila en el Excel
  - filas del Excel sin nodo en el diagrama
  - valores en conflicto (p. ej. una IP/CIDR escrita en la etiqueta del diagrama
    que no coincide con la del Excel)

Uso:
    python conciliar.py inventario.json datos.json -o conciliado.json --md discrepancias.md

100% offline.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Tipos que normalmente se corresponden 1:1 con una fila de inventario (VM, etc.)
TIPOS_INSTANCIABLES = {"vm", "vmss", "database", "storage_account", "public_ip", "load_balancer", "apim"}

_CABECERAS_NOMBRE = ("nombre", "name", "hostname", "host", "vm", "recurso", "resource")
_RE_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b")


def norm(s: str) -> str:
    return re.sub(r"[\s\-_./]+", "", str(s or "").strip().lower())


def aplanar_filas(datos_excel: dict) -> list[dict]:
    filas = []
    for hoja, registros in datos_excel.get("hojas", {}).items():
        for r in registros:
            r = dict(r)
            r["_hoja"] = hoja
            filas.append(r)
    return filas


def detectar_col_nombre(filas: list[dict]) -> str | None:
    if not filas:
        return None
    cols = list(filas[0].keys())
    for c in cols:
        if c.lower() in _CABECERAS_NOMBRE:
            return c
    for c in cols:                     # heurística: primera columna no vacía
        if c != "_hoja":
            return c
    return None


def conciliar(inv: dict, datos_excel: dict, col_nombre: str | None) -> dict:
    filas = aplanar_filas(datos_excel)
    col = col_nombre or detectar_col_nombre(filas)
    idx_filas = {norm(f.get(col, "")): f for f in filas} if col else {}

    usados: set[str] = set()
    nodos_out = []
    sin_fila = []
    conflictos = []

    for nodo in inv.get("nodos", []):
        # el nombre puede venir como "vm-web-01" o "vnet-prod 10.10.0.0/16"
        nombre_limpio = re.sub(_RE_IP, "", nodo["nombre"]).strip()
        clave = norm(nombre_limpio) or norm(nodo["nombre"])
        fila = idx_filas.get(clave)
        registro = dict(nodo)

        if fila:
            usados.add(clave)
            registro["datos_excel"] = {k: v for k, v in fila.items() if k != "_hoja"}
            registro["excel_hoja"] = fila["_hoja"]
            # conflicto: IPs/CIDR en la etiqueta del diagrama vs. valores del Excel
            ips_diagrama = set(_RE_IP.findall(nodo["nombre"]))
            ips_excel = {m for v in fila.values() for m in _RE_IP.findall(str(v))}
            faltan = ips_diagrama - ips_excel
            if ips_diagrama and faltan:
                conflictos.append({
                    "nodo": nodo["nombre"],
                    "en_diagrama": sorted(ips_diagrama),
                    "en_excel": sorted(ips_excel),
                    "detalle": f"IP/CIDR del diagrama sin coincidencia en el Excel: {sorted(faltan)}",
                })
        else:
            registro["datos_excel"] = None
            if nodo["tipo"] in TIPOS_INSTANCIABLES:
                sin_fila.append({"nodo": nodo["nombre"], "tipo": nodo["tipo"]})

        nodos_out.append(registro)

    filas_sin_nodo = [
        {k: v for k, v in f.items() if k != "_hoja"} | {"hoja": f["_hoja"]}
        for f in filas
        if col and norm(f.get(col, "")) and norm(f.get(col, "")) not in usados
    ]

    return {
        "fuente_diagrama": inv.get("fuente"),
        "fuente_excel": datos_excel.get("fuente"),
        "columna_nombre_excel": col,
        "resumen": {
            "n_nodos": len(nodos_out),
            "n_emparejados": sum(1 for n in nodos_out if n.get("datos_excel")),
            "n_nodos_sin_fila": len(sin_fila),
            "n_filas_sin_nodo": len(filas_sin_nodo),
            "n_conflictos": len(conflictos),
        },
        "nodos": nodos_out,
        "conexiones": inv.get("conexiones", []),
        "jerarquia": inv.get("jerarquia", []),
        "discrepancias": {
            "nodos_sin_fila_excel": sin_fila,
            "filas_excel_sin_nodo": filas_sin_nodo,
            "conflictos": conflictos,
        },
    }


def a_markdown(c: dict) -> str:
    r = c["resumen"]
    L = [f"# Discrepancias — `{c['fuente_diagrama']}` vs `{c['fuente_excel']}`", ""]
    L.append(f"- Nodos: {r['n_nodos']} · emparejados con Excel: **{r['n_emparejados']}**")
    L.append(f"- Nodos sin fila en Excel: **{r['n_nodos_sin_fila']}** · "
             f"Filas de Excel sin nodo: **{r['n_filas_sin_nodo']}** · "
             f"Conflictos de valor: **{r['n_conflictos']}**")
    L.append(f"- Columna de nombre usada en el Excel: `{c['columna_nombre_excel']}`")

    d = c["discrepancias"]
    L += ["", "## Nodos del diagrama SIN fila en el Excel", ""]
    L += [f"- `{x['nodo']}` ({x['tipo']})" for x in d["nodos_sin_fila_excel"]] or ["_ninguno_"]

    L += ["", "## Filas del Excel SIN nodo en el diagrama", ""]
    L += [f"- {json.dumps(x, ensure_ascii=False)}" for x in d["filas_excel_sin_nodo"]] or ["_ninguna_"]

    L += ["", "## Conflictos de valor (diagrama vs Excel)", ""]
    if d["conflictos"]:
        for x in d["conflictos"]:
            L.append(f"- **{x['nodo']}**: {x['detalle']}  \n  diagrama={x['en_diagrama']}  excel={x['en_excel']}")
    else:
        L.append("_ninguno_")

    L += ["", "> Revisa y resuelve TODO lo de arriba antes de generar Terraform. "
          "El Excel es la fuente de verdad de IPs/tamaños; el diagrama, de la topología.", ""]
    return "\n".join(L) + "\n"


def _utf8_stdio() -> None:
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="Cruza inventario del diagrama con datos del Excel (sin LLM).")
    ap.add_argument("inventario", type=Path, help="JSON de descifrar_drawio.py")
    ap.add_argument("datos_excel", type=Path, help="JSON de leer_excel.py")
    ap.add_argument("-o", "--salida", type=Path, help="conciliado.json (por defecto: stdout)")
    ap.add_argument("--md", type=Path, help="Escribir el informe de discrepancias en Markdown")
    ap.add_argument("--clave", help="Columna del Excel con el nombre del recurso (por defecto: autodetectar)")
    a = ap.parse_args(argv)

    for p in (a.inventario, a.datos_excel):
        if not p.is_file():
            print(f"error: no existe {p}", file=sys.stderr)
            return 2

    inv = json.loads(a.inventario.read_text(encoding="utf-8"))
    datos = json.loads(a.datos_excel.read_text(encoding="utf-8"))
    resultado = conciliar(inv, datos, a.clave)

    texto = json.dumps(resultado, ensure_ascii=False, indent=2, default=str)
    if a.salida:
        a.salida.write_text(texto, encoding="utf-8")
        print(f"escrito: {a.salida}", file=sys.stderr)
    else:
        print(texto)

    if a.md:
        a.md.write_text(a_markdown(resultado), encoding="utf-8")
        print(f"escrito: {a.md}", file=sys.stderr)

    r = resultado["resumen"]
    if r["n_nodos_sin_fila"] or r["n_filas_sin_nodo"] or r["n_conflictos"]:
        print(f"aviso: hay discrepancias (sin_fila={r['n_nodos_sin_fila']}, "
              f"sin_nodo={r['n_filas_sin_nodo']}, conflictos={r['n_conflictos']})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
