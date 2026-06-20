#!/usr/bin/env bash
# One-time: creates the Resource Group + Storage Account + container that hold
# Terraform's remote state. Run once, before `terraform init`.
set -euo pipefail

LOCATION="germanywestcentral"
RG="rg-lifeos-tfstate"
# Storage account names: 3-24 chars, lowercase letters/numbers, globally unique.
SA="stlifeostf$RANDOM"
CONTAINER="tfstate"

az group create --name "$RG" --location "$LOCATION"
az storage account create --name "$SA" --resource-group "$RG" \
  --location "$LOCATION" --sku Standard_LRS --encryption-services blob
az storage container create --name "$CONTAINER" --account-name "$SA"

echo "----------------------------------------------------------"
echo "Backend created. Put these into infra/backend.tf:"
echo "  resource_group_name  = \"$RG\""
echo "  storage_account_name = \"$SA\""
echo "  container_name       = \"$CONTAINER\""
echo "  key                  = \"lifeos.tfstate\""
echo "----------------------------------------------------------"
