#!/usr/bin/env python3
"""
descifrar_drawio.py — Extrae la arquitectura de un archivo .drawio SIN usar el LLM.

Parsea el XML de draw.io (mxGraph) y produce un inventario estructurado y determinista:
nodos (con nombre, tipo inferido, geometría, padre) y conexiones (origen -> destino).

Uso:
    python descifrar_drawio.py arquitectura.drawio -o inventario.json
    python descifrar_drawio.py arquitectura.drawio --md            # tabla Markdown por stdout

100% offline. Solo librería estándar de Python.
Formatos admitidos: .drawio / .xml, con el contenido comprimido (deflate+base64) o en claro.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path


# --- 1. Obtener el/los <mxGraphModel> del archivo -----------------------------

def _descomprimir_diagrama(texto: str) -> str:
    """Contenido de un <diagram> comprimido -> XML mxGraphModel en claro."""
    datos = base64.b64decode(texto)
    try:
        xml = zlib.decompress(datos, -15).decode("utf-8")  # raw DEFLATE (sin cabecera zlib)
    except zlib.error:
        xml = zlib.decompress(datos).decode("utf-8")
    return urllib.parse.unquote(xml)


def extraer_modelos(ruta: Path) -> list[tuple[str, ET.Element]]:
    """Devuelve [(nombre_pagina, elemento mxGraphModel), ...]."""
    contenido = ruta.read_text(encoding="utf-8", errors="replace").lstrip("﻿").strip()
    raiz = ET.fromstring(contenido)

    # Caso A: el archivo YA es un <mxGraphModel>
    if raiz.tag == "mxGraphModel":
        return [("Pagina-1", raiz)]

    # Caso B: <mxfile><diagram>...</diagram></mxfile>
    modelos: list[tuple[str, ET.Element]] = []
    for i, diagram in enumerate(raiz.iter("diagram"), start=1):
        nombre = diagram.get("name") or f"Pagina-{i}"
        hijo_modelo = diagram.find("mxGraphModel")
        if hijo_modelo is not None:                      # contenido en claro
            modelos.append((nombre, hijo_modelo))
        elif (diagram.text or "").strip():               # contenido comprimido
            modelos.append((nombre, ET.fromstring(_descomprimir_diagrama(diagram.text.strip()))))
    if not modelos:
        raise ValueError("No se encontró ningún <mxGraphModel> en el archivo.")
    return modelos


# --- 2. Parseo de celdas -----------------------------------------------------

def parsear_estilo(estilo: str) -> dict[str, str]:
    d: dict[str, str] = {}
    for i, parte in enumerate((estilo or "").split(";")):
        parte = parte.strip()
        if not parte:
            continue
        if "=" in parte:
            k, v = parte.split("=", 1)
            d[k.strip()] = v.strip()
        elif i == 0:
            d["_shape"] = parte            # primer token suelto = nombre de forma
    return d


def limpiar_etiqueta(value: str, una_linea: bool = True) -> str:
    """Quita HTML. Con una_linea=False conserva los saltos (útil para parsear 'clave: valor')."""
    if not value:
        return ""
    texto = re.sub(r"<br\s*/?>|</div>|</p>|</li>", "\n", value, flags=re.I)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = html.unescape(texto).replace("\xa0", " ")
    if una_linea:
        return re.sub(r"\s+", " ", texto).strip()
    lineas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in texto.splitlines()]
    return "\n".join(ln for ln in lineas if ln).strip()


_CLAVE_ALIAS = {
    "nombre": "nombre", "name": "nombre",
    "ip privada": "ip", "ip": "ip", "private ip": "ip", "direccion": "ip", "dirección": "ip",
    "tamano": "tamano", "tamaño": "tamano", "size": "tamano", "sku": "tamano", "vm size": "tamano",
    "cidr": "cidr", "rango": "cidr", "prefijo": "cidr", "address space": "cidr", "address prefix": "cidr",
    "so": "so", "os": "so", "sistema operativo": "so", "imagen": "so",
    "subred": "subred", "subnet": "subred",
    "region": "region", "región": "region", "location": "region", "ubicacion": "region",
    "resource group": "resource_group", "rg": "resource_group", "grupo de recursos": "resource_group",
    "inbound": "inbound", "entrada": "inbound", "outbound": "egress", "egress": "egress", "salida": "egress",
}
_RE_PAR = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?:/\d{1,2})?\b")


def extraer_campos(texto: str) -> tuple[str, dict[str, str]]:
    """De una etiqueta multilínea saca (nombre, campos). Ej:
       'VM Ubuntu 22.04\\nNombre: vm-ia-01\\nIP privada: 10.0.2.10\\nTamaño: Standard_B2s'
       -> ('vm-ia-01', {'so':'VM Ubuntu 22.04','ip':'10.0.2.10','tamano':'Standard_B2s'})"""
    campos: dict[str, str] = {}
    segmentos = re.split(r"[\n;]| {2,}", texto)
    resto: list[str] = []
    for seg in segmentos:
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"^([A-Za-zÁÉÍÓÚÜÑáéíóúüñ /]{2,25}?)\s*[:：]\s*(.+)$", seg)
        if m and m.group(1).strip().lower() in _CLAVE_ALIAS:
            campos[_CLAVE_ALIAS[m.group(1).strip().lower()]] = m.group(2).strip()
        else:
            resto.append(seg)
    # CIDR / IP sueltos entre paréntesis o en el texto restante
    todo = texto.replace("\n", " ")
    pars = _RE_PAR.findall(todo)
    if pars and "cidr" not in campos:
        con_mascara = [p for p in pars if "/" in p]
        if con_mascara:
            campos["cidr"] = con_mascara[0]
    if pars and "ip" not in campos:
        solo_ip = [p for p in pars if "/" not in p]
        if solo_ip:
            campos["ip"] = solo_ip[0]
    if re.search(r"sin ip p[uú]blica|no public ip|without public ip", todo, re.I):
        campos["ip_publica"] = "no"

    # nombre: el campo 'nombre' si está; si no, un token con pinta de id (kebab con dígitos/guiones)
    nombre = campos.pop("nombre", "")
    if not nombre:
        cand = re.findall(r"\b[a-z][a-z0-9]+(?:-[a-z0-9]+)+\b", todo)
        nombre = cand[0] if cand else (resto[0] if resto else todo.strip())
    return nombre.strip(" :·-"), campos


# Palabras clave -> (tipo, confianza). Orden = prioridad (lo más específico primero).
_REGLAS_TIPO: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"resource[_ ]?group|grupo de recursos|\brg-", re.I), "resource_group", "media"),
    (re.compile(r"virtual[_ ]?network|\bvnet\b|vnet-", re.I),  "vnet",           "alta"),
    (re.compile(r"subred|subnet|snet-", re.I),                "subnet",         "alta"),
    (re.compile(r"network[_ ]?security[_ ]?group|\bnsg\b|nsg-", re.I), "nsg",    "alta"),
    (re.compile(r"scale[_ ]?set|\bvmss\b", re.I),             "vmss",           "alta"),
    (re.compile(r"virtual[_ ]?machine|m[aá]quina|\bvm\b|vm-|ubuntu|debian|windows server|red\s?hat|centos",
                re.I),                                        "vm",             "alta"),
    (re.compile(r"load[_ ]?balancer|balanceador|\blb\b|lb-", re.I), "load_balancer", "alta"),
    (re.compile(r"application[_ ]?gateway|\bagw\b|app[_ ]?gw", re.I), "app_gateway", "alta"),
    (re.compile(r"api[_ ]?management|\bapim\b", re.I),        "apim",           "alta"),
    (re.compile(r"(?<!sin )public[_ ]?ip|\bpip-|ip[_ ]?p[uú]blica(?! *:? *(no|sin))", re.I),
                                                              "public_ip",      "media"),
    (re.compile(r"storage|almacenamiento|blob|cuenta de almacen", re.I), "storage_account", "media"),
    (re.compile(r"sql|database|base de datos|postgres|mysql|cosmos", re.I), "database", "media"),
    (re.compile(r"key[_ ]?vault", re.I),                      "key_vault",      "alta"),
    (re.compile(r"firewall", re.I),                           "firewall",       "alta"),
    (re.compile(r"bastion", re.I),                            "bastion",        "alta"),
    (re.compile(r"\bdns\b|zona dns", re.I),                   "dns_zone",       "media"),
]


def inferir_tipo(texto: str, estilo: dict[str, str], campos: dict | None = None) -> tuple[str, str]:
    heno = " ".join([texto, estilo.get("_shape", ""), estilo.get("shape", ""),
                     " ".join(f"{k}={v}" for k, v in (campos or {}).items())])
    for patron, tipo, confianza in _REGLAS_TIPO:
        if patron.search(heno):
            return tipo, confianza
    return "desconocido", "baja"


def es_contenedor(estilo: dict[str, str]) -> bool:
    return estilo.get("container") == "1" or estilo.get("group") == "1" or "swimlane" in estilo.get("_shape", "")


# --- 3. Construcción del inventario -----------------------------------------

def procesar_modelo(nombre_pagina: str, modelo: ET.Element) -> dict:
    celdas = {c.get("id"): c for c in modelo.iter("mxCell")}
    nodos, conexiones = [], []

    nombre_por_id: dict[str, str] = {}

    for cid, celda in celdas.items():
        estilo = parsear_estilo(celda.get("style", ""))

        if celda.get("edge") == "1":
            o, d = celda.get("source"), celda.get("target")
            conexiones.append({
                "id": cid,
                "origen_id": o, "destino_id": d,
                "origen": None, "destino": None,          # se rellenan al final con el nombre limpio
                "etiqueta": limpiar_etiqueta(celda.get("value", "")),
            })
            continue

        if celda.get("vertex") != "1":
            continue

        etiqueta_full = limpiar_etiqueta(celda.get("value", ""), una_linea=False)
        etiqueta_1l = etiqueta_full.replace("\n", " ")
        nombre, campos = extraer_campos(etiqueta_full)
        geo = celda.find("mxGeometry")
        tipo, confianza = inferir_tipo(etiqueta_1l, estilo, campos)
        nombre_por_id[cid] = nombre or etiqueta_1l or f"(sin nombre {cid})"
        nodos.append({
            "id": cid,
            "nombre": nombre_por_id[cid],
            "tipo": tipo,
            "tipo_confianza": confianza,
            "campos": campos,
            "etiqueta_completa": etiqueta_1l,
            "es_contenedor": es_contenedor(estilo),
            "padre_id": celda.get("parent") if celda.get("parent") not in (None, "0", "1") else None,
            "geometria": {k: float(geo.get(k)) for k in ("x", "y", "width", "height") if geo is not None and geo.get(k)} if geo is not None else {},
            "forma_drawio": estilo.get("_shape") or estilo.get("shape", ""),
            "crudo_value": celda.get("value", ""),
        })

    for c in conexiones:
        c["origen"] = nombre_por_id.get(c["origen_id"])
        c["destino"] = nombre_por_id.get(c["destino_id"])

    # jerarquía a partir de padre_id
    por_id = {n["id"]: n for n in nodos}
    jerarquia = []
    for n in nodos:
        if n["es_contenedor"]:
            hijos = [m["id"] for m in nodos if m["padre_id"] == n["id"]]
            jerarquia.append({"id": n["id"], "nombre": n["nombre"], "tipo": n["tipo"], "hijos": hijos})

    return {"pagina": nombre_pagina, "nodos": nodos, "conexiones": conexiones, "jerarquia": jerarquia}


def descifrar(ruta: Path) -> dict:
    modelos = extraer_modelos(ruta)
    paginas = [procesar_modelo(nombre, modelo) for nombre, modelo in modelos]
    nodos = [n for p in paginas for n in p["nodos"]]
    conexiones = [c for p in paginas for c in p["conexiones"]]
    jerarquia = [h for p in paginas for h in p["jerarquia"]]
    desconocidos = [n["nombre"] for n in nodos if n["tipo"] == "desconocido"]
    return {
        "fuente": ruta.name,
        "paginas": [p["pagina"] for p in paginas],
        "resumen": {
            "n_nodos": len(nodos),
            "n_conexiones": len(conexiones),
            "tipos": sorted({n["tipo"] for n in nodos}),
            "nodos_sin_clasificar": desconocidos,
        },
        "nodos": nodos,
        "conexiones": conexiones,
        "jerarquia": jerarquia,
    }


# --- 4. Salidas ------------------------------------------------------------

def a_markdown(inv: dict) -> str:
    L = [f"# Inventario de `{inv['fuente']}`", ""]
    r = inv["resumen"]
    L.append(f"- Nodos: **{r['n_nodos']}** · Conexiones: **{r['n_conexiones']}**")
    L.append(f"- Tipos detectados: {', '.join(r['tipos'])}")
    if r["nodos_sin_clasificar"]:
        L.append(f"- [!] Sin clasificar ({len(r['nodos_sin_clasificar'])}): {', '.join(r['nodos_sin_clasificar'])}")
    L += ["", "## Nodos", "", "| nombre | tipo | confianza | contenedor | padre |", "|---|---|---|---|---|"]
    por_id = {n["id"]: n["nombre"] for n in inv["nodos"]}
    for n in inv["nodos"]:
        L.append(f"| {n['nombre']} | {n['tipo']} | {n['tipo_confianza']} | {'sí' if n['es_contenedor'] else ''} | {por_id.get(n['padre_id'], '')} |")
    L += ["", "## Conexiones", "", "| origen | destino | etiqueta |", "|---|---|---|"]
    for c in inv["conexiones"]:
        L.append(f"| {c.get('origen') or c.get('origen_id')} | {c.get('destino') or c.get('destino_id')} | {c.get('etiqueta', '')} |")
    return "\n".join(L) + "\n"


def _utf8_stdio() -> None:
    """La consola de Windows suele ser cp1252; forzamos UTF-8 para no romper con acentos/símbolos."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="Descifra un .drawio a inventario estructurado (sin LLM).")
    ap.add_argument("drawio", type=Path, help="Archivo .drawio o .xml")
    ap.add_argument("-o", "--salida", type=Path, help="Ruta del JSON de salida (por defecto: stdout)")
    ap.add_argument("--md", action="store_true", help="Emitir tabla Markdown en vez de JSON")
    a = ap.parse_args(argv)

    if not a.drawio.is_file():
        print(f"error: no existe {a.drawio}", file=sys.stderr)
        return 2
    try:
        inv = descifrar(a.drawio)
    except (ET.ParseError, ValueError, zlib.error) as e:
        print(f"error al parsear el diagrama: {e}", file=sys.stderr)
        return 1

    salida = a_markdown(inv) if a.md else json.dumps(inv, ensure_ascii=False, indent=2)
    if a.salida:
        a.salida.write_text(salida, encoding="utf-8")
        print(f"escrito: {a.salida}  ({inv['resumen']['n_nodos']} nodos, {inv['resumen']['n_conexiones']} conexiones)", file=sys.stderr)
    else:
        print(salida)
    if inv["resumen"]["nodos_sin_clasificar"]:
        print(f"aviso: {len(inv['resumen']['nodos_sin_clasificar'])} nodo(s) sin clasificar", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
