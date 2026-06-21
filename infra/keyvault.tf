# Identity of whoever is currently running terraform (you). Provides tenant_id and
# object_id, used for the vault's tenant and to grant yourself write access.
data "azurerm_client_config" "current" {}

# Key Vault names must be globally unique, so append a short random suffix.
# Reused for the container registry name in Task 4.
resource "random_string" "kv_suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_key_vault" "main" {
  name                       = "kv-${var.prefix}-${random_string.kv_suffix.result}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  purge_protection_enabled   = false
  soft_delete_retention_days = 7
}

# Let the operator (you, running terraform) write secrets into the vault.
# The VM's read access (Key Vault Secrets User) is granted later, in vm.tf (Task 5).
resource "azurerm_role_assignment" "kv_operator" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id

  # Pin to whoever first applied (you). Without this, a `terraform apply` run by a
  # DIFFERENT principal (e.g. the CI managed identity) re-points this grant to itself
  # and replaces it every run. The operator grant should stay with the human.
  lifecycle {
    ignore_changes = [principal_id]
  }
}
