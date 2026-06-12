variable "prefix" {
  default = "umair"
}

variable "environment" {
  default = "lab"
}

variable "location" {
  default = "francecentral"
}

variable "acr_login_server" {
  description = "ACR login server — from main lab terraform output acr_login_server"
  type        = string
}

variable "acr_id" {
  description = "ACR resource ID — from main lab terraform output acr_id"
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault resource ID — from main lab terraform output key_vault_id"
  type        = string
}

variable "key_vault_uri" {
  description = "Key Vault URI — from main lab terraform output key_vault_uri"
  type        = string
}
