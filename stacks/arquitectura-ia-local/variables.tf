variable "resource_group_name" {
  type    = string
  default = "rg-generado"
}

variable "location" {
  type    = string
  default = "westeurope"
}

variable "admin_username" {
  type    = string
  default = "azureadmin"
}

variable "admin_ssh_public_key" {
  type        = string
  description = "Contenido de la clave pública SSH"
}

variable "tags" {
  type = map(string)
  default = {
    origen = "generado-desde-diagrama"
  }
}
