output "aks_name" {
  value = azurerm_kubernetes_cluster.lab.name
}

output "acr_login_server" {
  value = azurerm_container_registry.lab.login_server
}

output "resource_group" {
  value = azurerm_resource_group.lab.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.lab.vault_uri
}