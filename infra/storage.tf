# App-data storage: holds one Life-OS map blob per identity (Telegram chat id -> user id).
# Separate from the Terraform-state account (least privilege, different lifecycle).

resource "random_string" "storage_suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_storage_account" "data" {
  name                     = "st${var.prefix}data${random_string.storage_suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

resource "azurerm_storage_container" "maps" {
  name                  = "maps"
  storage_account_id    = azurerm_storage_account.data.id
  container_access_type = "private"
}

# The VM identity may READ+WRITE map blobs (data-plane RBAC, no account keys).
resource "azurerm_role_assignment" "vm_storage" {
  scope                = azurerm_storage_account.data.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_virtual_machine.main.identity[0].principal_id
}

# Aroosh's own user may also READ+WRITE map blobs, so maps can be pushed/pulled with `mapctl`
# from his laptop via `az login` (AAD, no account keys). Being subscription Owner is
# control-plane only and does NOT grant blob data access — this explicit data-plane grant does.
# The object id is a fixed, non-secret AAD id (az ad signed-in-user show --query id -o tsv).
resource "azurerm_role_assignment" "map_admin_storage" {
  scope                = azurerm_storage_account.data.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = "b8466139-f869-4cf2-993e-46807ae4fa09"
}
