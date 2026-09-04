# Trazabilidad — 2026-09-04

Diagrama: `arquitectura-ia-local.drawio`  ·  Excel: `None`

Cada recurso `.tf` y de dónde salió:

- `azurerm_virtual_network.vnet_ia_local`  <-  nodo del diagrama `vnet-ia-local`
- `azurerm_subnet.subnet_ia`  <-  nodo del diagrama `subnet-ia`
- `azurerm_network_security_group.nsg_ia`  <-  nodo del diagrama `nsg-ia`
- `azurerm_linux_virtual_machine.vm_ia_01`  <-  nodo del diagrama `vm-ia-01`

## Suposiciones y pendientes (resolver antes de `terraform apply`)

- [ ] nodo `Azure Cloud` (tipo detectado: desconocido) — sin plantilla / no es infraestructura
- [ ] nodo `Ollama + Open WebUI (Docker)` (tipo detectado: desconocido) — sin plantilla / no es infraestructura
- [ ] nodo `Usuario interno` (tipo detectado: desconocido) — sin plantilla / no es infraestructura
- [ ] nodo `Internet` (tipo detectado: desconocido) — sin plantilla / no es infraestructura
- [ ] nodo `✕` (tipo detectado: desconocido) — sin plantilla / no es infraestructura
- [ ] El diagrama no tiene resource group — creado 'azurerm_resource_group.principal' con var.resource_group_name

## Discrepancias heredadas de conciliar.py

- Nodos sin fila Excel: 1
- Filas Excel sin nodo: 0
- Conflictos de valor: 0

Ver `discrepancias.md`.

## Verificación

```bash
terraform fmt
terraform validate
terraform plan   # revisar TODOS los valores marcados como provisionales
```
