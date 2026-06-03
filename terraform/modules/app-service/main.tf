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
  name                = "app-${var.prefix}-${var.environment}"
  location            = azurerm_resource_group.app_service.location
  resource_group_name = azurerm_resource_group.app_service.name
  service_plan_id     = azurerm_service_plan.this.id

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = true
  }

  app_settings = {
    "KEY_VAULT_URI"              = var.key_vault_uri
    "DOCKER_REGISTRY_SERVER_URL" = "https://${var.acr_login_server}"
    "acrUseManagedIdentityCreds" = "true"
  }
}

resource "azurerm_linux_web_app_slot" "staging" {
  name           = var.slot_name
  app_service_id = azurerm_linux_web_app.this.id

  identity {
    type = "SystemAssigned"
  }

  site_config {
    always_on = true
  }

  app_settings = {
    "KEY_VAULT_URI"              = var.key_vault_uri
    "DOCKER_REGISTRY_SERVER_URL" = "https://${var.acr_login_server}"
    "acrUseManagedIdentityCreds" = "true"
  }

  # Workaround for azurerm 3.x provider bug: it attempts to read storage
  # accounts before the slot is fully propagated, causing a spurious 404.
  lifecycle {
    ignore_changes = [storage_account]
  }
}

# Grant the App Service managed identity read access to Key Vault secrets
resource "azurerm_role_assignment" "app_kv_secrets" {
  scope                = var.key_vault_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_linux_web_app.this.identity[0].principal_id
}
