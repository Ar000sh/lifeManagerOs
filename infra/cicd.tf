# CI/CD identities for GitHub Actions (Plan 2).
#
# These are USER-ASSIGNED MANAGED IDENTITIES (azurerm), not Entra app registrations.
# Why: creating an app registration needs Entra *directory* privileges that a
# student/university tenant typically denies (you hit "Authorization_RequestDenied"
# 403 on apply). A user-assigned managed identity is an ordinary Azure RESOURCE in
# your own resource group — you create it as the subscription Owner, no directory
# rights needed — and it supports the SAME GitHub OIDC federated credentials.
#
# APPLIED LOCALLY (the bootstrap) — never by CI itself, to avoid self-escalation.

locals {
  github_repo = "Ar000sh/lifeManagerOs"
  # The Terraform state lives in a SEPARATE resource group (created by
  # bootstrap-backend.sh, outside Terraform). Built as a string so plan needs no
  # control-plane read on that RG before the Reader role below exists.
  tfstate_rg_id = "/subscriptions/${var.subscription_id}/resourceGroups/rg-lifeos-tfstate"
}

# ---------------------------------------------------------------------------
# CI identity — Job 1: lint/test/build/push + terraform plan. Read + push only.
# ---------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "ci" {
  name                = "id-${var.prefix}-ci"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

# Trust GitHub OIDC tokens from the main branch of this repo.
resource "azurerm_federated_identity_credential" "ci" {
  name                = "github-main"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.ci.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${local.github_repo}:ref:refs/heads/main"
}

resource "azurerm_role_assignment" "ci_acr_push" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPush"
  principal_id         = azurerm_user_assigned_identity.ci.principal_id
}

resource "azurerm_role_assignment" "ci_rg_reader" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.ci.principal_id
}

# State access: Reader (control-plane — refresh the cicd.tf resources + read state
# metadata) + Storage Blob Data Contributor (data-plane — read/lock/write the state
# blob over Azure AD instead of a storage key).
resource "azurerm_role_assignment" "ci_state_reader" {
  scope                = local.tfstate_rg_id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.ci.principal_id
}

resource "azurerm_role_assignment" "ci_state_blob" {
  scope                = local.tfstate_rg_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.ci.principal_id
}

# ---------------------------------------------------------------------------
# Rollout identity — Job 2 (gated): terraform apply + az vm run-command deploy.
# Bound to the GitHub *environment* "production" — the approval gate.
# ---------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "rollout" {
  name                = "id-${var.prefix}-rollout"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

resource "azurerm_federated_identity_credential" "rollout" {
  name                = "github-env-production"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.rollout.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${local.github_repo}:environment:production"
}

resource "azurerm_role_assignment" "rollout_rg_contributor" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "Contributor" # includes runCommand for the VM deploy
  principal_id         = azurerm_user_assigned_identity.rollout.principal_id
}

resource "azurerm_role_assignment" "rollout_rg_uaa" {
  scope                = azurerm_resource_group.main.id
  role_definition_name = "User Access Administrator" # apply manages role assignments
  principal_id         = azurerm_user_assigned_identity.rollout.principal_id
}

resource "azurerm_role_assignment" "rollout_state_reader" {
  scope                = local.tfstate_rg_id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.rollout.principal_id
}

resource "azurerm_role_assignment" "rollout_state_blob" {
  scope                = local.tfstate_rg_id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.rollout.principal_id
}
