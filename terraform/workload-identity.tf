# ── User-Assigned Managed Identity ───────────────────────────────────────────
resource "azurerm_user_assigned_identity" "workload" {
  name                = "mi-${var.prefix}-workload"
  location            = var.location
  resource_group_name = azurerm_resource_group.lab.name
}

# ── Federated Identity Credential ────────────────────────────────────────────
# Links the Managed Identity to the Kubernetes Service Account via OIDC.
# Subject must exactly match namespace:serviceaccount used in k8s/workload-identity/.
resource "azurerm_federated_identity_credential" "workload" {
  name                = "fed-aks-kv-reader"
  resource_group_name = azurerm_resource_group.lab.name
  parent_id           = azurerm_user_assigned_identity.workload.id
  issuer              = azurerm_kubernetes_cluster.lab.oidc_issuer_url
  audience            = ["api://AzureADTokenExchange"]
  subject             = "system:serviceaccount:workload-identity-demo:kv-reader-sa"
}

# ── KV RBAC: Terraform runner can create secrets ──────────────────────────────
resource "azurerm_role_assignment" "kv_admin" {
  principal_id         = data.azurerm_client_config.current.object_id
  role_definition_name = "Key Vault Secrets Officer"
  scope                = azurerm_key_vault.lab.id
}

# ── KV RBAC: Managed Identity can read secrets ────────────────────────────────
resource "azurerm_role_assignment" "kv_workload" {
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
  role_definition_name = "Key Vault Secrets User"
  scope                = azurerm_key_vault.lab.id
}

# ── Wait for RBAC to propagate before creating the secret ─────────────────────
resource "time_sleep" "kv_rbac_propagation" {
  depends_on      = [azurerm_role_assignment.kv_admin]
  create_duration = "30s"
}

# ── Demo secret ───────────────────────────────────────────────────────────────
resource "azurerm_key_vault_secret" "demo" {
  name         = "lab-demo-secret"
  value        = "Hello from Key Vault via Workload Identity — no credentials in code!"
  key_vault_id = azurerm_key_vault.lab.id
  depends_on   = [time_sleep.kv_rbac_propagation]
}
