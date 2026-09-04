# GENERADO automáticamente — revisar antes de aplicar.

resource "azurerm_resource_group" "rg_basico_test" {
  name     = "rg-basico-test"
  location = var.location
  tags     = var.tags
}

resource "azurerm_virtual_network" "vnet_basico" {
  name                = "vnet-basico"
  resource_group_name = azurerm_resource_group.rg_basico_test.name
  location            = azurerm_resource_group.rg_basico_test.location
  address_space       = ["10.20.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "snet_basico" {
  name                 = "snet-basico"
  resource_group_name  = azurerm_resource_group.rg_basico_test.name
  virtual_network_name = azurerm_virtual_network.vnet_basico.name
  address_prefixes     = ["10.20.1.0/24"]
}

resource "azurerm_network_interface" "vm_basico_01_nic" {
  name                = "vm-basico-01-nic"
  resource_group_name = azurerm_resource_group.rg_basico_test.name
  location            = azurerm_resource_group.rg_basico_test.location
  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.snet_basico.id
    private_ip_address_allocation = "Static"
    private_ip_address            = "10.20.1.10"
  }
  tags = var.tags
}

resource "azurerm_linux_virtual_machine" "vm_basico_01" {
  name                  = "vm-basico-01"
  resource_group_name   = azurerm_resource_group.rg_basico_test.name
  location              = azurerm_resource_group.rg_basico_test.location
  size                  = "Standard_B1s"
  admin_username        = var.admin_username
  network_interface_ids = [azurerm_network_interface.vm_basico_01_nic.id]

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.admin_ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }
  tags = var.tags
}
