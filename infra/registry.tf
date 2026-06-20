resource "azurerm_container_registry" "main" {
  # ACR names are globally unique and allow only letters/numbers (no dashes).
  name                = "acr${var.prefix}${random_string.kv_suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = false # no shared admin password — use identity-based access
}

# Let the operator (you) push images. With admin disabled, push requires a role.
# The VM's read-only AcrPull role is granted later, in vm.tf (Task 5).
resource "azurerm_role_assignment" "acr_operator_push" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPush"
  principal_id         = data.azurerm_client_config.current.object_id
}
