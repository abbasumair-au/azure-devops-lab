variable "prefix" {
  description = "Naming prefix used across all resources"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g. lab, prod)"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group to deploy App Service resources into"
  type        = string
}

variable "vnet_id" {
  description = "ID of the existing Virtual Network (for reference/tagging)"
  type        = string
}

variable "key_vault_id" {
  description = "ID of the existing Key Vault (used for role assignment)"
  type        = string
}

variable "key_vault_uri" {
  description = "URI of the existing Key Vault (used in app settings)"
  type        = string
}

variable "sku_name" {
  description = "App Service Plan SKU"
  type        = string
  default     = "F1"
}
