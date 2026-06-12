#!/bin/bash
set -e

echo "================================================"
echo ">>> DESTROYING APP SERVICE"
echo "================================================"

# ── Credentials ──────────────────────────────────────
export SUBSCRIPTION_ID=$(az account show --query id -o tsv 2>/dev/null)

if [ -z "$SUBSCRIPTION_ID" ]; then
  echo ">>> Not logged in to Azure. Logging in..."
  az login
  export SUBSCRIPTION_ID=$(az account show --query id -o tsv)
fi

echo ">>> Subscription: $SUBSCRIPTION_ID"

# ── Read outputs from main lab Terraform ─────────────
# Variables are required by the provider even during destroy.
echo ""
echo ">>> Reading main lab outputs..."
cd ~/azure-devops-lab/terraform

ACR_LOGIN_SERVER=$(terraform output -raw acr_login_server 2>/dev/null || echo "placeholder")
ACR_ID=$(terraform output -raw acr_id 2>/dev/null || echo "placeholder")
KEY_VAULT_ID=$(terraform output -raw key_vault_id 2>/dev/null || echo "placeholder")
KEY_VAULT_URI=$(terraform output -raw key_vault_uri 2>/dev/null || echo "placeholder")

# ── Terraform Destroy ─────────────────────────────────
echo ""
echo ">>> Destroying App Service..."
cd ~/azure-devops-lab/terraform-app-service
terraform init -reconfigure
terraform destroy -auto-approve \
  -var="acr_login_server=$ACR_LOGIN_SERVER" \
  -var="acr_id=$ACR_ID" \
  -var="key_vault_id=$KEY_VAULT_ID" \
  -var="key_vault_uri=$KEY_VAULT_URI"

# ── Verify ───────────────────────────────────────────
echo ""
echo ">>> Verifying App Service resource group is gone..."
RG="rg-umair-appservice-lab"
if [ "$(az group exists --name $RG)" = "false" ]; then
  echo ">>> $RG successfully deleted."
else
  echo ">>> WARNING: $RG still exists. Check Azure portal."
fi

# ── Done ─────────────────────────────────────────────
echo ""
echo "================================================"
echo ">>> APP SERVICE DESTROYED"
echo "================================================"
echo ""
echo "To destroy the full lab: ./scripts/destroy-session.sh"
echo ""
