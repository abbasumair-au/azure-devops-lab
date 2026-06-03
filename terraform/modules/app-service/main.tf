resource "azurerm_resource_group" "app_service" {
  name     = "rg-${var.prefix}-appservice-${var.environment}"
  location = var.location
}

resource "azurerm_service_plan" "this" {
  name                = "asp-${var.prefix}-${var.environment}"
  location            = azurerm_resource_group.app_service.location
  resource_group_name = azurerm_resource_group.app_service.name
  os_type             = "Linux"
  sku_name            = var.sku_name
}

resource "azurerm_linux_web_app" "this" {
  name                      = "app-${var.prefix}-${var.environment}"
  location                  = azurerm_resource_group.app_service.location
  resource_group_name       = azurerm_resource_group.app_service.name
  service_plan_id           = azurerm_service_plan.this.id
  virtual_network_subnet_id = var.subnet_id

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = true
  }

  app_settings = {
    "KEY_VAULT_URI" = var.key_vault_uri
  }
}

# Grant the App Service managed identity read access to Key Vault secrets
resource "azurerm_role_assignment" "app_kv_secrets" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.this.identity[0].principal_id
}
