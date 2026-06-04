#!/bin/bash
set -e

echo "================================================"
echo ">>> DESTROYING AZURE DEVOPS LAB SESSION"
echo "================================================"

# ── Credentials ──────────────────────────────────────
export SUBSCRIPTION_ID=$(az account show --query id -o tsv 2>/dev/null)

if [ -z "$SUBSCRIPTION_ID" ]; then
  echo ">>> Not logged in to Azure. Logging in..."
  az login
  export SUBSCRIPTION_ID=$(az account show --query id -o tsv)
fi

echo ">>> Subscription: $SUBSCRIPTION_ID"

# ── Purge soft-deleted Key Vaults ────────────────────
echo ""
echo ">>> Checking for soft-deleted Key Vaults..."
DELETED_KVS=$(az keyvault list-deleted --query "[].name" -o tsv 2>/dev/null)

if [ -z "$DELETED_KVS" ]; then
  echo ">>> No soft-deleted Key Vaults found."
else
  echo "$DELETED_KVS" | while read kv; do
    echo ">>> Purging Key Vault: $kv"
    az keyvault purge --name "$kv" --no-wait
  done
  echo ">>> Waiting for purge to complete..."
  sleep 30
fi

# ── Terraform Destroy ────────────────────────────────
echo ""
echo ">>> Destroying infrastructure with Terraform..."
cd ~/azure-devops-lab/terraform
terraform destroy -auto-approve

# ── Verify ───────────────────────────────────────────
echo ""
echo ">>> Verifying resource groups are gone..."

for RG in rg-umair-lab rg-umair-appservice-lab; do
  RG_EXISTS=$(az group exists --name "$RG")
  if [ "$RG_EXISTS" = "false" ]; then
    echo ">>> $RG successfully deleted."
  else
    echo ">>> WARNING: $RG still exists. Check Azure portal."
  fi
done

# ── Done ─────────────────────────────────────────────
echo ""
echo "================================================"
echo ">>> SESSION DESTROYED"
echo "================================================"
echo ""
echo "Surviving resources (cheap/free):"
echo "  - rg-terraform-state (resource group)"
echo "  - umairdevopsstate (storage account + tfstate)"
echo ""
echo "To start a new session: ./scripts/start-session.sh"
echo ""