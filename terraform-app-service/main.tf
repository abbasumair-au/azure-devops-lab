terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

module "app_service" {
  source = "../terraform/modules/app-service"

  prefix           = var.prefix
  environment      = var.environment
  location         = var.location
  acr_login_server = var.acr_login_server
  key_vault_id     = var.key_vault_id
  key_vault_uri    = var.key_vault_uri
}

resource "azurerm_role_assignment" "app_service_acr_pull" {
  scope                            = var.acr_id
  role_definition_name             = "AcrPull"
  principal_id                     = module.app_service.principal_id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "app_service_staging_acr_pull" {
  scope                            = var.acr_id
  role_definition_name             = "AcrPull"
  principal_id                     = module.app_service.staging_slot_principal_id
  skip_service_principal_aad_check = true
}

output "app_service_hostname" {
  value = module.app_service.app_service_hostname
}

output "app_service_staging_hostname" {
  value = module.app_service.staging_slot_hostname
}
