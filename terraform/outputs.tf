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

output "key_vault_id" {
  value = azurerm_key_vault.lab.id
}

output "acr_id" {
  value = azurerm_container_registry.lab.id
}

output "key_vault_name" {
  value = azurerm_key_vault.lab.name
}

output "workload_identity_client_id" {
  value = azurerm_user_assigned_identity.workload.client_id
}

output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}