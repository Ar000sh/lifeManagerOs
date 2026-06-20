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
