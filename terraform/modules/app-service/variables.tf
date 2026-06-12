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

variable "acr_login_server" {
  description = "Login server URL of the Azure Container Registry (e.g. myacr.azurecr.io)"
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
  description = "App Service Plan SKU (must be S1+ for deployment slots)"
  type        = string
  default     = "S1"
}

variable "slot_name" {
  description = "Name of the staging deployment slot"
  type        = string
  default     = "staging"
}

variable "app_port" {
  description = "Port the container listens on"
  type        = number
  default     = 5000
}
