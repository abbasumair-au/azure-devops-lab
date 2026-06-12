#!/bin/bash
set -e

echo "================================================"
echo ">>> STARTING APP SERVICE"
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
echo ""
echo ">>> Reading main lab outputs..."
cd ~/azure-devops-lab/terraform

ACR_LOGIN_SERVER=$(terraform output -raw acr_login_server)
ACR_ID=$(terraform output -raw acr_id)
KEY_VAULT_ID=$(terraform output -raw key_vault_id)
KEY_VAULT_URI=$(terraform output -raw key_vault_uri)

echo ">>> ACR: $ACR_LOGIN_SERVER"
echo ">>> Key Vault: $KEY_VAULT_URI"

# ── Terraform App Service ─────────────────────────────
echo ""
echo ">>> Provisioning App Service..."
cd ~/azure-devops-lab/terraform-app-service
terraform init -reconfigure
terraform apply -auto-approve \
  -var="acr_login_server=$ACR_LOGIN_SERVER" \
  -var="acr_id=$ACR_ID" \
  -var="key_vault_id=$KEY_VAULT_ID" \
  -var="key_vault_uri=$KEY_VAULT_URI"

APP_SERVICE_HOST=$(terraform output -raw app_service_hostname)
APP_SERVICE_STAGING_HOST=$(terraform output -raw app_service_staging_hostname)

# ── Done ─────────────────────────────────────────────
echo ""
echo "================================================"
echo ">>> APP SERVICE IS READY"
echo "================================================"
echo ""
echo "  Production: https://$APP_SERVICE_HOST"
echo "  Staging:    https://$APP_SERVICE_STAGING_HOST"
echo ""
