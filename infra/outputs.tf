# Values Terraform prints after apply, for convenience. Read one with:
#   terraform output -raw <name>
# We add to this file as new resources are created.

output "key_vault_name" {
  description = "Name of the Key Vault (has a random suffix)."
  value       = azurerm_key_vault.main.name
}

output "acr_login_server" {
  description = "ACR login server, e.g. acrlifeosXXXX.azurecr.io — used to tag/push images."
  value       = azurerm_container_registry.main.login_server
}

output "vm_public_ip" {
  description = "Public IP of the VM — ssh azureuser@<this>."
  value       = azurerm_public_ip.vm.ip_address
}

output "app_insights_connection_string" {
  description = "Application Insights connection string — consumed by Plan 3 (custom bot metrics)."
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true # contains an instrumentation key; never print in plain logs.
}

output "ci_client_id" {
  description = "Client ID of the CI managed identity → GitHub Variable AZURE_CI_CLIENT_ID."
  value       = azurerm_user_assigned_identity.ci.client_id
}

output "rollout_client_id" {
  description = "Client ID of the rollout managed identity → GitHub Variable AZURE_ROLLOUT_CLIENT_ID."
  value       = azurerm_user_assigned_identity.rollout.client_id
}

output "tenant_id" {
  description = "Entra tenant ID → GitHub Variable AZURE_TENANT_ID."
  value       = data.azurerm_client_config.current.tenant_id
}

output "acr_name" {
  description = "ACR registry name (no domain) → GitHub Variable ACR_NAME."
  value       = azurerm_container_registry.main.name
}

output "subscription_id" {
  description = "Subscription ID → GitHub Variable AZURE_SUBSCRIPTION_ID."
  value       = var.subscription_id
}
