#!/usr/bin/env python3
"""
generar_terraform.py — Inventario conciliado -> proyecto Terraform (azurerm).

DETERMINISTA por defecto: rellena plantillas HCL a partir del JSON conciliado.
El LLM local es OPCIONAL y solo REVISA (--con-llm): nunca genera el HCL principal
ni se aplica solo.

Uso:
    python generar_terraform.py conciliado.json -o proyecto/
    python generar_terraform.py conciliado.json -o proyecto/ --con-llm --modelo qwen2.5-coder:7b

Salida en <proyecto/>:  providers.tf  main.tf  variables.tf  terraform.tfvars
                        outputs.tf  GENERADO.md  [revision-llm.md]

100% offline (el --con-llm usa Ollama en localhost).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# tipo inferido -> recurso azurerm
MAPA = {
    "resource_group": "azurerm_resource_group",
    "vnet": "azurerm_virtual_network",
    "subnet": "azurerm_subnet",
    "nsg": "azurerm_network_security_group",
    "public_ip": "azurerm_public_ip",
    "load_balancer": "azurerm_lb",
    "vm": "azurerm_linux_virtual_machine",
    "vmss": "azurerm_linux_virtual_machine_scale_set",
    "storage_account": "azurerm_storage_account",
    "database": "azurerm_postgresql_flexible_server",
    "apim": "azurerm_api_management",
    "key_vault": "azurerm_key_vault",
    "app_gateway": "azurerm_application_gateway",
    "firewall": "azurerm_firewall",
    "bastion": "azurerm_bastion_host",
    "dns_zone": "azurerm_dns_zone",
}
_RE_CIDR = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}/\d{1,2}\b")
_RE_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def nombre_limpio(nombre: str) -> str:
    """Quita IP/CIDR y ruido de la etiqueta del diagrama para usarlo como nombre de recurso Azure."""
    s = _RE_CIDR.sub("", str(nombre or ""))
    s = _RE_IP.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" -_/")
    return s or str(nombre or "").strip()


def tf_id(nombre: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", nombre_limpio(nombre).lower()).strip("_")
    if not s or s[0].isdigit():
        s = "r_" + s
    return s


def campo(fila: dict | None, *nombres: str, defecto=None):
    if not fila:
        return defecto
    bajo = {k.lower(): v for k, v in fila.items()}
    for n in nombres:
        if n in bajo and str(bajo[n]).strip():
            return bajo[n]
    return defecto


def dato_nodo(nodo: dict, *nombres: str, defecto=None):
    """Busca un valor primero en los campos leídos de la etiqueta del diagrama, luego en el Excel."""
    v = campo(nodo.get("campos"), *nombres)
    if v is None:
        v = campo(nodo.get("datos_excel"), *nombres)
    return defecto if v is None else v


class Generador:
    def __init__(self, conc: dict):
        self.c = conc
        self.nodos = conc.get("nodos", [])
        self.por_id = {n["id"]: n for n in self.nodos}
        self.trazas: list[str] = []
        self.todos: list[str] = []
        self._vnets = [n for n in self.nodos if n["tipo"] == "vnet"]
        self._subnets = [n for n in self.nodos if n["tipo"] == "subnet"]
        self._rgs = [n for n in self.nodos if n["tipo"] == "resource_group"]

    # --- utilidades de topología ---
    def _padre_de_tipo(self, nodo: dict, tipos: set[str]) -> dict | None:
        visto = set()
        actual = nodo
        while actual and actual.get("padre_id") and actual["padre_id"] not in visto:
            visto.add(actual["padre_id"])
            actual = self.por_id.get(actual["padre_id"])
            if actual and actual["tipo"] in tipos:
                return actual
        return None

    def _rg_de(self, nodo: dict) -> dict | None:
        return self._padre_de_tipo(nodo, {"resource_group"}) or (self._rgs[0] if len(self._rgs) == 1 else None)

    def _vnet_de(self, nodo: dict) -> dict | None:
        return self._padre_de_tipo(nodo, {"vnet"}) or (self._vnets[0] if len(self._vnets) == 1 else None)

    def _subnet_de(self, nodo: dict) -> dict | None:
        p = self._padre_de_tipo(nodo, {"subnet"})
        if p:
            return p
        ip = dato_nodo(nodo, "ip", "ip_privada", "private_ip", "direccion")
        if ip:
            try:
                import ipaddress
                a = ipaddress.ip_address(ip.strip())
                for s in self._subnets:
                    c = self._cidr(s)
                    if c and a in ipaddress.ip_network(c, strict=False):
                        return s
            except ValueError:
                pass
        return self._subnets[0] if len(self._subnets) == 1 else None

    def _ref_rg(self, nodo: dict) -> str:
        rg = self._rg_de(nodo)
        return f"azurerm_resource_group.{tf_id(rg['nombre'])}" if rg else "azurerm_resource_group.principal"

    def _cidr(self, nodo: dict) -> str | None:
        for txt in (nodo.get("etiqueta_completa", ""), nodo["nombre"]):
            m = _RE_CIDR.search(txt or "")
            if m:
                return m.group(0)
        return dato_nodo(nodo, "cidr", "rango", "prefijo", "address_space")

    # --- render por tipo ---
    def bloques(self) -> str:
        out = []
        for n in self.nodos:
            fn = getattr(self, f"_r_{n['tipo']}", None)
            rid = tf_id(n["nombre"])
            if fn:
                out.append(fn(n, rid))
                self.trazas.append(f"- `{MAPA[n['tipo']]}.{rid}`  <-  nodo del diagrama `{n['nombre']}`"
                                   + (f" + fila Excel (hoja {n.get('excel_hoja')})" if n.get("datos_excel") else ""))
            else:
                out.append(self._stub(n, rid))
        return "\n\n".join(b for b in out if b)

    def _stub(self, n, rid) -> str:
        self.todos.append(f"nodo `{n['nombre']}` (tipo detectado: {n['tipo']}) — sin plantilla / no es infraestructura")
        datos = json.dumps({**(n.get("campos") or {}), **(n.get("datos_excel") or {})}, ensure_ascii=False)
        etq = n.get("etiqueta_completa", "")
        return (f"# TODO: nodo '{n['nombre']}' tipo='{n['tipo']}' (confianza {n['tipo_confianza']})\n"
                f"#       etiqueta: {etq}\n"
                f"#       datos: {datos}\n"
                f"#       Sin plantilla para este tipo. Si NO es infra (actor, anotación, Docker local...) déjalo así.\n"
                f"#       Si SÍ lo es, añade regla en descifrar_drawio.py o plantilla en generar_terraform.py")

    def _r_resource_group(self, n, rid) -> str:
        return (f'resource "azurerm_resource_group" "{rid}" {{\n'
                f'  name     = "{nombre_limpio(n["nombre"])}"\n'
                f'  location = var.location\n'
                f'  tags     = var.tags\n}}')

    def _r_vnet(self, n, rid) -> str:
        cidr = self._cidr(n) or "10.0.0.0/16"
        if not self._cidr(n):
            self.todos.append(f"vnet `{n['nombre']}` sin CIDR en diagrama ni Excel — puesto 10.0.0.0/16 provisional")
        rg_ref = self._ref_rg(n)
        return (f'resource "azurerm_virtual_network" "{rid}" {{\n'
                f'  name                = "{nombre_limpio(n["nombre"])}"\n'
                f'  resource_group_name = {rg_ref}.name\n'
                f'  location            = {rg_ref}.location\n'
                f'  address_space       = ["{cidr}"]\n'
                f'  tags                = var.tags\n}}')

    def _r_subnet(self, n, rid) -> str:
        vnet = self._vnet_de(n)
        cidr = self._cidr(n) or "10.0.1.0/24"
        if not self._cidr(n):
            self.todos.append(f"subnet `{n['nombre']}` sin CIDR — puesto 10.0.1.0/24 provisional")
        if not vnet:
            self.todos.append(f"subnet `{n['nombre']}` sin vnet clara — referencia a azurerm_virtual_network.principal")
        vnet_ref = f"azurerm_virtual_network.{tf_id(vnet['nombre'])}" if vnet else "azurerm_virtual_network.principal"
        rg = self._rg_de(n)
        rg_ref = f"azurerm_resource_group.{tf_id(rg['nombre'])}.name" if rg else f"{vnet_ref}.resource_group_name"
        return (f'resource "azurerm_subnet" "{rid}" {{\n'
                f'  name                 = "{nombre_limpio(n["nombre"])}"\n'
                f'  resource_group_name  = {rg_ref}\n'
                f'  virtual_network_name = {vnet_ref}.name\n'
                f'  address_prefixes     = ["{cidr}"]\n}}')

    def _r_nsg(self, n, rid) -> str:
        rg_ref = self._ref_rg(n)
        pistas = " ".join(f"{k}={v}" for k, v in (n.get("campos") or {}).items() if k in ("inbound", "egress"))
        nota_reglas = (f'  # reglas indicadas en el diagrama: {pistas}\n' if pistas else "")
        # el comentario rompe el bloque de alineación de `terraform fmt`: `tags` va sin alinear
        return (f'resource "azurerm_network_security_group" "{rid}" {{\n'
                f'  name                = "{nombre_limpio(n["nombre"])}"\n'
                f'  resource_group_name = {rg_ref}.name\n'
                f'  location            = {rg_ref}.location\n'
                f'{nota_reglas}'
                f'  # TODO: traducir a security_rule (ver cerebro/patrones/seguridad y recomendaciones.md)\n'
                f'  tags = var.tags\n}}')

    def _r_public_ip(self, n, rid) -> str:
        rg_ref = self._ref_rg(n)
        return (f'resource "azurerm_public_ip" "{rid}" {{\n'
                f'  name                = "{nombre_limpio(n["nombre"])}"\n'
                f'  resource_group_name = {rg_ref}.name\n'
                f'  location            = {rg_ref}.location\n'
                f'  allocation_method   = "Static"\n'
                f'  sku                 = "Standard"\n'
                f'  tags                = var.tags\n}}')

    def _r_vm(self, n, rid) -> str:
        nom = nombre_limpio(n["nombre"])
        sub = self._subnet_de(n)
        rg_ref = self._ref_rg(n)
        if not sub:
            self.todos.append(f"VM `{n['nombre']}` sin subred clara — referencia a azurerm_subnet.principal")
        sub_ref = f"azurerm_subnet.{tf_id(sub['nombre'])}.id" if sub else "azurerm_subnet.principal.id"
        size = dato_nodo(n, "tamano", "tamaño", "size", "sku", defecto="Standard_B2s")
        ip = dato_nodo(n, "ip", "ip_privada", "private_ip", "direccion")
        nic = tf_id(n["nombre"]) + "_nic"
        if ip:
            ipcfg = ('    private_ip_address_allocation = "Static"\n'
                     f'    private_ip_address            = "{ip}"\n')
        else:
            self.todos.append(f"VM `{n['nombre']}` sin IP — NIC en Dynamic")
            ipcfg = '    private_ip_address_allocation = "Dynamic"\n'
        return (
            f'resource "azurerm_network_interface" "{nic}" {{\n'
            f'  name                = "{nom}-nic"\n'
            f'  resource_group_name = {rg_ref}.name\n'
            f'  location            = {rg_ref}.location\n'
            f'  ip_configuration {{\n'
            f'    name                          = "ipconfig1"\n'
            f'    subnet_id                     = {sub_ref}\n'
            f'{ipcfg}'
            f'  }}\n'
            f'  tags = var.tags\n}}\n\n'
            f'resource "azurerm_linux_virtual_machine" "{rid}" {{\n'
            f'  name                  = "{nom}"\n'
            f'  resource_group_name   = {rg_ref}.name\n'
            f'  location              = {rg_ref}.location\n'
            f'  size                  = "{size}"\n'
            f'  admin_username        = var.admin_username\n'
            f'  network_interface_ids = [azurerm_network_interface.{nic}.id]\n\n'
            f'  admin_ssh_key {{\n'
            f'    username   = var.admin_username\n'
            f'    public_key = var.admin_ssh_public_key\n'
            f'  }}\n\n'
            f'  os_disk {{\n'
            f'    caching              = "ReadWrite"\n'
            f'    storage_account_type = "StandardSSD_LRS"\n'
            f'  }}\n\n'
            f'  source_image_reference {{\n'
            f'    publisher = "Canonical"\n'
            f'    offer     = "0001-com-ubuntu-server-jammy"\n'
            f'    sku       = "22_04-lts"\n'
            f'    version   = "latest"\n'
            f'  }}\n'
            f'  tags = var.tags\n}}'
        )

    def _r_load_balancer(self, n, rid) -> str:
        rg_ref = self._ref_rg(n)
        return (f'resource "azurerm_lb" "{rid}" {{\n'
                f'  name                = "{nombre_limpio(n["nombre"])}"\n'
                f'  resource_group_name = {rg_ref}.name\n'
                f'  location            = {rg_ref}.location\n'
                f'  sku                 = "Standard"\n'
                f'  # TODO: frontend_ip_configuration (public_ip o subnet) + reglas\n'
                f'  tags                = var.tags\n}}\n\n'
                f'resource "azurerm_lb_backend_address_pool" "{rid}_pool" {{\n'
                f'  name            = "{n["nombre"]}-pool"\n'
                f'  loadbalancer_id = azurerm_lb.{rid}.id\n}}')

    # --- ensamblado ---
    def proyecto(self) -> dict[str, str]:
        bloques = self.bloques()
        stubs = ""
        if not self._rgs:
            stubs += ('resource "azurerm_resource_group" "principal" {\n'
                      '  name     = var.resource_group_name\n'
                      '  location = var.location\n'
                      '  tags     = var.tags\n}\n\n')
            self.todos.append("El diagrama no tiene resource group — creado 'azurerm_resource_group.principal' con var.resource_group_name")
        if "azurerm_virtual_network.principal" in bloques and not self._vnets:
            stubs += ('resource "azurerm_virtual_network" "principal" {\n'
                      '  name                = "vnet-principal"\n'
                      '  resource_group_name = azurerm_resource_group.principal.name\n'
                      '  location            = azurerm_resource_group.principal.location\n'
                      '  address_space       = ["10.0.0.0/16"]  # TODO: revisar\n'
                      '  tags                = var.tags\n}\n\n')
            self.todos.append("El diagrama no tiene VNet — creada 'azurerm_virtual_network.principal' provisional")
        if "azurerm_subnet.principal" in bloques and not self._subnets:
            stubs += ('resource "azurerm_subnet" "principal" {\n'
                      '  name                 = "snet-principal"\n'
                      '  resource_group_name  = azurerm_resource_group.principal.name\n'
                      '  virtual_network_name = azurerm_virtual_network.principal.name\n'
                      '  address_prefixes     = ["10.0.1.0/24"]  # TODO: revisar\n}\n\n')
            self.todos.append("El diagrama no tiene subred — creada 'azurerm_subnet.principal' provisional")
        principal = stubs

        providers = (
            'terraform {\n'
            '  required_version = ">= 1.6"\n'
            '  required_providers {\n'
            '    azurerm = {\n'
            '      source  = "hashicorp/azurerm"\n'
            '      version = "~> 4.0"\n'
            '    }\n'
            '  }\n'
            '  # TODO: backend remoto (azurerm) con bloqueo — ver cerebro/conceptos/iac/Terraform - Qué es el estado\n'
            '}\n\n'
            'provider "azurerm" {\n'
            '  features {}\n'
            '  # subscription_id / tenant_id via variables de entorno ARM_*\n'
            '}\n'
        )
        variables = (
            'variable "resource_group_name" {\n  type    = string\n  default = "rg-generado"\n}\n\n'
            'variable "location" {\n  type    = string\n  default = "westeurope"\n}\n\n'
            'variable "admin_username" {\n  type    = string\n  default = "azureadmin"\n}\n\n'
            'variable "admin_ssh_public_key" {\n  type        = string\n  description = "Contenido de la clave pública SSH"\n}\n\n'
            'variable "tags" {\n  type = map(string)\n  default = {\n    origen = "generado-desde-diagrama"\n  }\n}\n'
        )
        tfvars = (
            f'# Generado {date.today().isoformat()} desde {self.c.get("fuente_diagrama")} + {self.c.get("fuente_excel")}\n'
            'location            = "westeurope"\n'
            'resource_group_name = "rg-generado"\n'
            'admin_username      = "azureadmin"\n'
            '# admin_ssh_public_key = "ssh-ed25519 AAAA... (rellenar, NO commitear una clave real)"\n'
        )
        outputs = "".join(
            f'output "{tf_id(n["nombre"])}_id" {{\n  value = {MAPA[n["tipo"]]}.{tf_id(n["nombre"])}.id\n}}\n\n'
            for n in self.nodos if n["tipo"] in ("resource_group", "vnet", "vm")
        ) or "# sin outputs generados automáticamente\n"

        generado_md = self._trazabilidad_md()

        return {
            "providers.tf": providers,
            "main.tf": f"# GENERADO automáticamente — revisar antes de aplicar.\n\n{principal}{bloques}\n",
            "variables.tf": variables,
            "terraform.tfvars": tfvars,
            "outputs.tf": outputs,
            "GENERADO.md": generado_md,
        }

    def _trazabilidad_md(self) -> str:
        L = [f"# Trazabilidad — {date.today().isoformat()}", "",
             f"Diagrama: `{self.c.get('fuente_diagrama')}`  ·  Excel: `{self.c.get('fuente_excel')}`", "",
             "Cada recurso `.tf` y de dónde salió:", ""]
        L += self.trazas or ["_(nada)_"]
        L += ["", "## Suposiciones y pendientes (resolver antes de `terraform apply`)", ""]
        L += [f"- [ ] {t}" for t in self.todos] or ["- (ninguna)"]
        disc = self.c.get("discrepancias", {})
        if any(disc.values()):
            L += ["", "## Discrepancias heredadas de conciliar.py", "",
                  f"- Nodos sin fila Excel: {len(disc.get('nodos_sin_fila_excel', []))}",
                  f"- Filas Excel sin nodo: {len(disc.get('filas_excel_sin_nodo', []))}",
                  f"- Conflictos de valor: {len(disc.get('conflictos', []))}",
                  "", "Ver `discrepancias.md`."]
        L += ["", "## Verificación", "",
              "```bash", "terraform fmt", "terraform validate",
              "terraform plan   # revisar TODOS los valores marcados como provisionales", "```"]
        return "\n".join(L) + "\n"


def revision_llm(proyecto: dict[str, str], conc: dict, modelo: str, patrones: str) -> str:
    import ollama_local
    prompt = (
        "Eres revisor de Terraform. Te doy un main.tf GENERADO automáticamente desde un diagrama, "
        "el inventario conciliado y los patrones internos. NO reescribas el archivo entero: "
        "lista (1) errores de sintaxis o referencias rotas, (2) recursos que faltan según el inventario, "
        "(3) incumplimientos de los patrones de seguridad. Respuesta en español, en viñetas.\n\n"
        f"=== PATRONES INTERNOS ===\n{patrones or '(no se aportaron)'}\n\n"
        f"=== INVENTARIO (resumen) ===\n{json.dumps(conc.get('resumen', {}), ensure_ascii=False)}\n\n"
        f"=== main.tf ===\n{proyecto['main.tf']}\n"
    )
    try:
        obs = ollama_local.generar(prompt, modelo, opciones={"num_ctx": 8192})
    except ollama_local.OllamaNoDisponible as e:
        return f"# Revisión LLM no disponible\n\n{e}\n"
    return (f"# Revisión del LLM local ({modelo}) — {date.today().isoformat()}\n\n"
            "> Observaciones automáticas. NO se han aplicado. Contrástalas tú.\n\n" + obs + "\n")


def _utf8_stdio() -> None:
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    _utf8_stdio()
    ap = argparse.ArgumentParser(description="Genera un proyecto Terraform desde el inventario conciliado.")
    ap.add_argument("conciliado", type=Path, help="JSON de conciliar.py")
    ap.add_argument("-o", "--salida", type=Path, required=True, help="Carpeta destino del proyecto Terraform")
    ap.add_argument("--con-llm", action="store_true", help="Añadir revision-llm.md (Ollama local, solo revisa)")
    ap.add_argument("--modelo", default="qwen2.5-coder:7b")
    ap.add_argument("--patrones", type=Path, help="Archivo .md con patrones internos para la revisión LLM")
    a = ap.parse_args(argv)

    if not a.conciliado.is_file():
        print(f"error: no existe {a.conciliado}", file=sys.stderr)
        return 2

    conc = json.loads(a.conciliado.read_text(encoding="utf-8"))
    gen = Generador(conc)
    archivos = gen.proyecto()

    a.salida.mkdir(parents=True, exist_ok=True)
    for nombre, contenido in archivos.items():
        # newline="\n": HCL siempre con LF (si no, en Windows sale CRLF y `terraform fmt -check` falla en CI)
        (a.salida / nombre).write_text(contenido, encoding="utf-8", newline="\n")

    if a.con_llm:
        patrones = a.patrones.read_text(encoding="utf-8") if a.patrones and a.patrones.is_file() else ""
        sys.path.insert(0, str(Path(__file__).parent))
        (a.salida / "revision-llm.md").write_text(
            revision_llm(archivos, conc, a.modelo, patrones), encoding="utf-8", newline="\n")
        print(f"escrito: {a.salida / 'revision-llm.md'}", file=sys.stderr)

    print(f"proyecto escrito en {a.salida}/  ({len(archivos)} archivos)", file=sys.stderr)
    if gen.todos:
        print(f"aviso: {len(gen.todos)} suposición(es)/pendiente(s) — ver GENERADO.md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
