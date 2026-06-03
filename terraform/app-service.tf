module "app_service" {
  source = "./modules/app-service"

  prefix              = var.prefix
  environment         = var.environment
  location            = "francecentral"
  resource_group_name = azurerm_resource_group.lab.name

  vnet_id          = azurerm_virtual_network.lab.id
  key_vault_id     = azurerm_key_vault.lab.id
  key_vault_uri    = azurerm_key_vault.lab.vault_uri
  acr_login_server = azurerm_container_registry.lab.login_server
}

# Allow production slot to pull images from ACR
resource "azurerm_role_assignment" "app_service_acr_pull" {
  scope                            = azurerm_container_registry.lab.id
  role_definition_name             = "AcrPull"
  principal_id                     = module.app_service.principal_id
  skip_service_principal_aad_check = true
}

# Allow staging slot to pull images from ACR
resource "azurerm_role_assignment" "app_service_staging_acr_pull" {
  scope                            = azurerm_container_registry.lab.id
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
