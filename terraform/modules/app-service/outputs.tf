output "app_service_id" {
  description = "Resource ID of the App Service"
  value       = azurerm_linux_web_app.this.id
}

output "app_service_hostname" {
  description = "Default hostname of the App Service"
  value       = azurerm_linux_web_app.this.default_hostname
}

output "app_service_plan_id" {
  description = "Resource ID of the App Service Plan"
  value       = azurerm_service_plan.this.id
}

output "principal_id" {
  description = "Object ID of the App Service system-assigned managed identity"
  value       = azurerm_linux_web_app.this.identity[0].principal_id
}

output "resource_group_name" {
  description = "Resource group created for App Service resources"
  value       = azurerm_resource_group.app_service.name
}

output "staging_slot_hostname" {
  description = "Default hostname of the staging deployment slot"
  value       = azurerm_linux_web_app_slot.staging.default_hostname
}

output "staging_slot_principal_id" {
  description = "Object ID of the staging slot system-assigned managed identity"
  value       = azurerm_linux_web_app_slot.staging.identity[0].principal_id
}
