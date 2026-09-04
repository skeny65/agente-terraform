# Trazabilidad — 2026-09-04

Diagrama: `rg-vm-basico.drawio`  ·  Excel: `None`

Cada recurso `.tf` y de dónde salió:

- `azurerm_resource_group.rg_basico_test`  <-  nodo del diagrama `rg-basico-test`
- `azurerm_virtual_network.vnet_basico`  <-  nodo del diagrama `vnet-basico`
- `azurerm_subnet.snet_basico`  <-  nodo del diagrama `snet-basico`
- `azurerm_linux_virtual_machine.vm_basico_01`  <-  nodo del diagrama `vm-basico-01`

## Suposiciones y pendientes (resolver antes de `terraform apply`)

- (ninguna)

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
