terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
  # TODO: backend remoto (azurerm) con bloqueo — ver cerebro/conceptos/iac/Terraform - Qué es el estado
}

provider "azurerm" {
  features {}
  # subscription_id / tenant_id via variables de entorno ARM_*
}
