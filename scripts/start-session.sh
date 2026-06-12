#!/bin/bash
set -e

echo "================================================"
echo ">>> STARTING AZURE DEVOPS LAB SESSION"
echo "================================================"

# ── Credentials ──────────────────────────────────────
export SUBSCRIPTION_ID=$(az account show --query id -o tsv 2>/dev/null)

if [ -z "$SUBSCRIPTION_ID" ]; then
  echo ">>> Not logged in to Azure. Logging in..."
  az login
  export SUBSCRIPTION_ID=$(az account show --query id -o tsv)
fi

echo ">>> Subscription: $SUBSCRIPTION_ID"

# ── Terraform ────────────────────────────────────────
echo ""
echo ">>> Provisioning infrastructure with Terraform..."
cd ~/azure-devops-lab/terraform
terraform init -reconfigure
terraform apply -auto-approve

# ── kubectl ──────────────────────────────────────────
echo ""
echo ">>> Connecting kubectl to AKS..."
az aks get-credentials \
  --resource-group rg-umair-lab \
  --name aks-umair-lab \
  --overwrite-existing

echo ">>> Waiting for nodes to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=180s

echo ">>> Nodes:"
kubectl get nodes

# ── Workload Identity Demo ────────────────────────────
echo ""
echo ">>> Deploying Workload Identity demo..."
export WORKLOAD_IDENTITY_CLIENT_ID=$(terraform output -raw workload_identity_client_id)
export KEY_VAULT_URI=$(terraform output -raw key_vault_uri)

envsubst < ~/azure-devops-lab/k8s/workload-identity/namespace.yaml      | kubectl apply -f -
envsubst < ~/azure-devops-lab/k8s/workload-identity/serviceaccount.yaml | kubectl apply -f -
envsubst < ~/azure-devops-lab/k8s/workload-identity/pod.yaml            | kubectl apply -f -

echo ">>> Workload Identity pod deployed in namespace 'workload-identity-demo'."
echo ">>> Check result: kubectl logs -n workload-identity-demo kv-reader -f"

# ── ArgoCD ───────────────────────────────────────────
echo ""
echo ">>> Installing ArgoCD..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml --server-side --force-conflicts

echo ">>> Waiting for ArgoCD server..."
kubectl wait --for=condition=available --timeout=180s deployment/argocd-server -n argocd

ARGOCD_PASSWORD=$(kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d)
echo ">>> ArgoCD admin password: $ARGOCD_PASSWORD"

# ── Prometheus + Grafana ─────────────────────────────
echo ""
echo ">>> Installing Prometheus + Grafana..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --wait \
  --timeout 10m

# ── ArgoCD Apps ──────────────────────────────────────
echo ""
echo ">>> Applying ArgoCD root app..."
kubectl apply -f ~/azure-devops-lab/apps/root.yml

# ── Done ─────────────────────────────────────────────
echo ""
echo "================================================"
echo ">>> LAB IS READY"
echo "================================================"
echo ""
echo "Run these in separate terminal tabs:"
echo ""
echo "  ArgoCD:     kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "  Grafana:    kubectl port-forward svc/monitoring-grafana -n monitoring 3000:80"
echo "  Prometheus: kubectl port-forward svc/monitoring-kube-prometheus-prometheus -n monitoring 9090:9090"
echo ""
echo "  ArgoCD login: admin / $ARGOCD_PASSWORD"
echo "  Grafana login: admin / prom-operator"
echo ""
echo "App Service (separate — deploy independently):"
echo "  ./scripts/start-app-service.sh"
echo ""
echo "Workload Identity Demo:"
echo "  kubectl logs -n workload-identity-demo kv-reader -f"
echo "  kubectl describe pod -n workload-identity-demo kv-reader"
echo ""