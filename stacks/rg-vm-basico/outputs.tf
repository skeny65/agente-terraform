output "rg_basico_test_id" {
  value = azurerm_resource_group.rg_basico_test.id
}

output "vnet_basico_id" {
  value = azurerm_virtual_network.vnet_basico.id
}

output "vm_basico_01_id" {
  value = azurerm_linux_virtual_machine.vm_basico_01.id
}

