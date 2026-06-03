# Dedicated subnet for App Service VNet integration.
# Requires Microsoft.Web/serverFarms delegation and cannot be shared with AKS.
resource "azurerm_subnet" "app_service" {
  name                 = "snet-appservice"
  resource_group_name  = azurerm_resource_group.lab.name
  virtual_network_name = azurerm_virtual_network.lab.name
  address_prefixes     = ["10.2.0.0/16"]

  delegation {
    name = "app-service-delegation"
    service_delegation {
      name    = "Microsoft.Web/serverFarms"
      actions = ["Microsoft.Network/virtualNetworks/subnets/action"]
    }
  }
}

module "app_service" {
  source = "./modules/app-service"

  prefix              = var.prefix
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.lab.name

  vnet_id       = azurerm_virtual_network.lab.id
  subnet_id     = azurerm_subnet.app_service.id
  key_vault_id  = azurerm_key_vault.lab.id
  key_vault_uri = azurerm_key_vault.lab.vault_uri
}

output "app_service_hostname" {
  value = module.app_service.app_service_hostname
}
