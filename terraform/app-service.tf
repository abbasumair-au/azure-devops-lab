module "app_service" {
  source = "./modules/app-service"

  prefix              = var.prefix
  environment         = var.environment
  location            = "francecentral"
  resource_group_name = azurerm_resource_group.lab.name

  vnet_id       = azurerm_virtual_network.lab.id
  key_vault_id  = azurerm_key_vault.lab.id
  key_vault_uri = azurerm_key_vault.lab.vault_uri
}

output "app_service_hostname" {
  value = module.app_service.app_service_hostname
}

output "app_service_staging_hostname" {
  value = module.app_service.staging_slot_hostname
}
