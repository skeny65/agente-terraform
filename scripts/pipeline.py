#!/usr/bin/env python3
"""
pipeline.py — Orquesta todo el flujo diagrama -> Terraform. El "agente local".

    diagrama.drawio  (+ datos.xlsx)
          |  descifrar_drawio.py   (determinista, sin LLM)
          v  leer_excel.py         (determinista, sin LLM)
          |  conciliar.py          (determinista, sin LLM)
          v  generar_terraform.py  (plantillas; --con-llm añade solo una revisión)
    <salida>/terraform/*.tf

Uso:
    python pipeline.py --drawio arquitectura.drawio --excel datos.xlsx --salida ./resultado
    python pipeline.py --drawio arquitectura.drawio --salida ./resultado          # sin Excel
    python pipeline.py --drawio a.drawio --excel d.xlsx --salida ./r --con-llm     # + revisión LLM

100% offline. Solo stdlib + openpyxl (opcional).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import descifrar_drawio          # noqa: E402
import leer_excel                # noqa: E402
import conciliar as mod_conc     # noqa: E402
import generar_terraform         # noqa: E402


def _utf8_stdio() -> None:
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="Pipeline diagrama -> Terraform (offline).")
    ap.add_argument("--drawio", type=Path, required=True)
    ap.add_argument("--excel", type=Path, help="Opcional: .xlsx para corroborar IPs/tamaños/nombres")
    ap.add_argument("--salida", type=Path, required=True, help="Carpeta de resultados")
    ap.add_argument("--clave", help="Columna del Excel con el nombre del recurso")
    ap.add_argument("--con-llm", action="store_true", help="Añadir revision-llm.md (Ollama local)")
    ap.add_argument("--modelo", default="qwen2.5-coder:7b")
    ap.add_argument("--patrones", type=Path, help=".md de patrones internos para la revisión LLM")
    a = ap.parse_args(argv)

    if not a.drawio.is_file():
        print(f"error: no existe {a.drawio}", file=sys.stderr)
        return 2
    a.salida.mkdir(parents=True, exist_ok=True)

    # 1) diagrama -> inventario
    print("[1/4] descifrando el diagrama...", file=sys.stderr)
    inv = descifrar_drawio.descifrar(a.drawio)
    (a.salida / "inventario.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    (a.salida / "inventario.md").write_text(descifrar_drawio.a_markdown(inv), encoding="utf-8", newline="\n")
    print(f"      {inv['resumen']['n_nodos']} nodos, {inv['resumen']['n_conexiones']} conexiones"
          + (f"  [!] sin clasificar: {inv['resumen']['nodos_sin_clasificar']}" if inv['resumen']['nodos_sin_clasificar'] else ""),
          file=sys.stderr)

    # 2) excel -> datos
    if a.excel and a.excel.is_file():
        print("[2/4] leyendo el Excel...", file=sys.stderr)
        datos = {"fuente": a.excel.name, "hojas": leer_excel.leer(a.excel)}
        (a.salida / "datos_excel.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        total = sum(len(v) for v in datos["hojas"].values())
        print(f"      {len(datos['hojas'])} hoja(s), {total} fila(s)", file=sys.stderr)
    else:
        print("[2/4] sin Excel — no habrá verificación cruzada de IPs/tamaños", file=sys.stderr)
        datos = {"fuente": None, "hojas": {}}

    # 3) conciliar
    print("[3/4] conciliando diagrama + Excel...", file=sys.stderr)
    conc = mod_conc.conciliar(inv, datos, a.clave)
    (a.salida / "conciliado.json").write_text(json.dumps(conc, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (a.salida / "discrepancias.md").write_text(mod_conc.a_markdown(conc), encoding="utf-8", newline="\n")
    r = conc["resumen"]
    print(f"      emparejados: {r['n_emparejados']}/{r['n_nodos']} · "
          f"sin fila Excel: {r['n_nodos_sin_fila']} · filas sueltas: {r['n_filas_sin_nodo']} · "
          f"conflictos: {r['n_conflictos']}", file=sys.stderr)

    # 4) generar Terraform
    print("[4/4] generando Terraform...", file=sys.stderr)
    gen = generar_terraform.Generador(conc)
    archivos = gen.proyecto()
    destino_tf = a.salida / "terraform"
    destino_tf.mkdir(exist_ok=True)
    for nombre, contenido in archivos.items():
        # newline="\n": HCL siempre con LF (en Windows saldría CRLF y `terraform fmt -check` falla en CI)
        (destino_tf / nombre).write_text(contenido, encoding="utf-8", newline="\n")

    if a.con_llm:
        print("      revisión con el LLM local (puede tardar ~1 min la 1ª vez)...", file=sys.stderr)
        patrones = a.patrones.read_text(encoding="utf-8") if a.patrones and a.patrones.is_file() else ""
        (destino_tf / "revision-llm.md").write_text(
            generar_terraform.revision_llm(archivos, conc, a.modelo, patrones), encoding="utf-8", newline="\n")

    print("", file=sys.stderr)
    print(f"OK -> {a.salida}/", file=sys.stderr)
    print(f"     terraform/         proyecto ({len(archivos)} archivos"
          + (" + revision-llm.md" if a.con_llm else "") + ")", file=sys.stderr)
    print(f"     discrepancias.md   {r['n_nodos_sin_fila'] + r['n_filas_sin_nodo'] + r['n_conflictos']} cosa(s) a revisar", file=sys.stderr)
    print(f"     terraform/GENERADO.md   {len(gen.todos)} suposición(es)", file=sys.stderr)
    print("", file=sys.stderr)
    print("Siguiente: revisa discrepancias.md y terraform/GENERADO.md, luego:", file=sys.stderr)
    print("  cd terraform && terraform fmt && terraform validate && terraform plan", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
