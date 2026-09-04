# Inventario de `arquitectura-ia-local.drawio`

- Nodos: **9** · Conexiones: **2**
- Tipos detectados: desconocido, nsg, subnet, vm, vnet
- [!] Sin clasificar (5): Azure Cloud, Ollama + Open WebUI (Docker), Usuario interno, Internet, ✕

## Nodos

| nombre | tipo | confianza | contenedor | padre |
|---|---|---|---|---|
| Azure Cloud | desconocido | baja |  |  |
| vnet-ia-local | vnet | alta |  |  |
| subnet-ia | subnet | alta |  |  |
| nsg-ia | nsg | alta |  |  |
| vm-ia-01 | vm | alta |  |  |
| Ollama + Open WebUI (Docker) | desconocido | baja |  |  |
| Usuario interno | desconocido | baja |  |  |
| Internet | desconocido | baja |  |  |
| ✕ | desconocido | baja |  |  |

## Conexiones

| origen | destino | etiqueta |
|---|---|---|
| Usuario interno | vm-ia-01 | HTTPS (solo LAN interna) |
| vm-ia-01 | Internet | egress bloqueado |
