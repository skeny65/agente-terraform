# GENERADO automáticamente — revisar antes de aplicar.

resource "azurerm_resource_group" "principal" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

# TODO: nodo 'Azure Cloud' tipo='desconocido' (confianza baja)
#       etiqueta: Azure Cloud
#       datos: {}
#       Sin plantilla para este tipo. Si NO es infra (actor, anotación, Docker local...) déjalo así.
#       Si SÍ lo es, añade regla en descifrar_drawio.py o plantilla en generar_terraform.py

resource "azurerm_virtual_network" "vnet_ia_local" {
  name                = "vnet-ia-local"
  resource_group_name = azurerm_resource_group.principal.name
  location            = azurerm_resource_group.principal.location
  address_space       = ["10.0.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "subnet_ia" {
  name                 = "subnet-ia"
  resource_group_name  = azurerm_virtual_network.vnet_ia_local.resource_group_name
  virtual_network_name = azurerm_virtual_network.vnet_ia_local.name
  address_prefixes     = ["10.0.2.0/24"]
}

resource "azurerm_network_security_group" "nsg_ia" {
  name                = "nsg-ia"
  resource_group_name = azurerm_resource_group.principal.name
  location            = azurerm_resource_group.principal.location
  # reglas indicadas en el diagrama: inbound=solo LAN interna
  # TODO: traducir a security_rule (ver cerebro/patrones/seguridad y recomendaciones.md)
  tags = var.tags
}

resource "azurerm_network_interface" "vm_ia_01_nic" {
  name                = "vm-ia-01-nic"
  resource_group_name = azurerm_resource_group.principal.name
  location            = azurerm_resource_group.principal.location
  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = azurerm_subnet.subnet_ia.id
    private_ip_address_allocation = "Static"
    private_ip_address            = "10.0.2.10"
  }
  tags = var.tags
}

resource "azurerm_linux_virtual_machine" "vm_ia_01" {
  name                  = "vm-ia-01"
  resource_group_name   = azurerm_resource_group.principal.name
  location              = azurerm_resource_group.principal.location
  size                  = "Standard_B2s"
  admin_username        = var.admin_username
  network_interface_ids = [azurerm_network_interface.vm_ia_01_nic.id]

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

# TODO: nodo 'Ollama + Open WebUI (Docker)' tipo='desconocido' (confianza baja)
#       etiqueta: Ollama + Open WebUI (Docker) localhost:11434
#       datos: {}
#       Sin plantilla para este tipo. Si NO es infra (actor, anotación, Docker local...) déjalo así.
#       Si SÍ lo es, añade regla en descifrar_drawio.py o plantilla en generar_terraform.py

# TODO: nodo 'Usuario interno' tipo='desconocido' (confianza baja)
#       etiqueta: Usuario interno (navegador · LAN)
#       datos: {}
#       Sin plantilla para este tipo. Si NO es infra (actor, anotación, Docker local...) déjalo así.
#       Si SÍ lo es, añade regla en descifrar_drawio.py o plantilla en generar_terraform.py

# TODO: nodo 'Internet' tipo='desconocido' (confianza baja)
#       etiqueta: Internet ❌ SIN SALIDA
#       datos: {}
#       Sin plantilla para este tipo. Si NO es infra (actor, anotación, Docker local...) déjalo así.
#       Si SÍ lo es, añade regla en descifrar_drawio.py o plantilla en generar_terraform.py

# TODO: nodo '✕' tipo='desconocido' (confianza baja)
#       etiqueta: ✕
#       datos: {}
#       Sin plantilla para este tipo. Si NO es infra (actor, anotación, Docker local...) déjalo así.
#       Si SÍ lo es, añade regla en descifrar_drawio.py o plantilla en generar_terraform.py
