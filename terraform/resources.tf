# Resource Group
resource "azurerm_resource_group" "lab" {
  name     = "rg-${var.prefix}-${var.environment}"
  location = var.location
}

# Virtual Network
resource "azurerm_virtual_network" "lab" {
  name                = "vnet-${var.prefix}-${var.environment}"
  location            = var.location
  resource_group_name = azurerm_resource_group.lab.name
  address_space       = ["10.0.0.0/8"]
}

# Subnet for AKS
resource "azurerm_subnet" "aks" {
  name                 = "snet-aks"
  resource_group_name  = azurerm_resource_group.lab.name
  virtual_network_name = azurerm_virtual_network.lab.name
  address_prefixes     = ["10.1.0.0/16"]
}

# Azure Container Registry
resource "azurerm_container_registry" "lab" {
  name                = "${var.prefix}labacr"
  resource_group_name = azurerm_resource_group.lab.name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = false
}

# AKS Cluster
resource "azurerm_kubernetes_cluster" "lab" {
  name                = "aks-${var.prefix}-${var.environment}"
  location            = var.location
  resource_group_name = azurerm_resource_group.lab.name
  dns_prefix          = "${var.prefix}-${var.environment}"

  oidc_issuer_enabled = true

  default_node_pool {
    name           = "system"
    node_count     = 1
    vm_size        = "Standard_B2s"
    vnet_subnet_id = azurerm_subnet.aks.id

    upgrade_settings {
      max_surge = "10%"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin = "azure"
    network_policy = "azure"
  }
}

# Allow AKS to pull from ACR
resource "azurerm_role_assignment" "aks_acr" {
  principal_id                     = azurerm_kubernetes_cluster.lab.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.lab.id
  skip_service_principal_aad_check = true
}

# Key Vault
resource "azurerm_key_vault" "lab" {
  name                = "${var.prefix}-lab-kv"
  location            = var.location
  resource_group_name = azurerm_resource_group.lab.name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  soft_delete_retention_days = 7
  purge_protection_enabled   = false  # must be false to allow purge

  lifecycle {
    prevent_destroy = false
  }
}

data "azurerm_client_config" "current" {}