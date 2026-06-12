terraform {
  backend "azurerm" {
    resource_group_name  = "rg-terraform-state"
    storage_account_name = "umairdevopsstate"
    container_name       = "tfstate"
    key                  = "app-service.terraform.tfstate"
  }
}
