terraform {
  backend "azurerm" {
    resource_group_name  = "rg-lifeos-tfstate"
    storage_account_name = "stlifeostf18906"
    container_name       = "tfstate"
    key                  = "lifeos.tfstate"
  }
}
