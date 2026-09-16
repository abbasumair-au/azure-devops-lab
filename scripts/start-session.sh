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
export KEY_VAULT_NAME=$(terraform output -raw key_vault_name)
export TENANT_ID=$(terraform output -raw tenant_id)

envsubst < ~/azure-devops-lab/k8s/workload-identity/namespace.yaml      | kubectl apply -f -
envsubst < ~/azure-devops-lab/k8s/workload-identity/serviceaccount.yaml | kubectl apply -f -
envsubst < ~/azure-devops-lab/k8s/workload-identity/pod.yaml            | kubectl apply -f -

echo ">>> Workload Identity pod deployed in namespace 'workload-identity-demo'."
echo ">>> Check result: kubectl logs -n workload-identity-demo kv-reader -f"

# ── Dapr ─────────────────────────────────────────────
# Must be up before the ArgoCD root app is applied below — myapp's
# Deployment carries dapr.io/* annotations that only mean anything once the
# sidecar-injector webhook exists, and its Components/Configuration
# (state, pub/sub, secrets, tracing) need to exist before myapp's Pod
# starts asking its sidecar to use them.
echo ""
echo ">>> Installing Dapr..."
helm repo add dapr https://dapr.github.io/helm-charts/
helm repo update
helm upgrade --install dapr dapr/dapr \
  --namespace dapr-system \
  --create-namespace \
  --wait \
  --timeout 5m

echo ">>> Deploying Redis (backs Dapr state + pub/sub) and Dapr components..."
kubectl apply -f ~/azure-devops-lab/k8s/dapr/redis.yaml
kubectl wait --for=condition=available --timeout=120s deployment/redis-dapr -n default

envsubst < ~/azure-devops-lab/k8s/dapr/components/secretstore.yaml | kubectl apply -f -
kubectl apply -f ~/azure-devops-lab/k8s/dapr/components/statestore.yaml
kubectl apply -f ~/azure-devops-lab/k8s/dapr/components/pubsub.yaml
kubectl apply -f ~/azure-devops-lab/k8s/dapr/tracing-config.yaml

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
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --wait \
  --timeout 10m

# ── Tempo ────────────────────────────────────────────
echo ""
echo ">>> Installing Tempo..."
helm repo add grafana https://grafana.github.io/helm-charts 2>/dev/null || true
helm repo update
helm upgrade --install tempo grafana/tempo \
  --namespace monitoring \
  --set tempo.storage.trace.backend=local \
  --wait \
  --timeout 5m

# ── OTel Collector ────────────────────────────────────
echo ""
echo ">>> Installing OpenTelemetry Collector..."
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  --namespace monitoring \
  -f ~/azure-devops-lab/helm-charts/otel-collector-values.yaml \
  --wait \
  --timeout 5m

# ── Loki + Promtail ──────────────────────────────────
echo ""
echo ">>> Installing Loki + Promtail..."
helm upgrade --install loki grafana/loki-stack \
  --namespace monitoring \
  --set grafana.enabled=false \
  --set prometheus.enabled=false \
  --wait \
  --timeout 5m

# loki-stack crée un ConfigMap datasource avec isDefault:true qui entre en conflit
# avec le datasource Prometheus de kube-prometheus-stack → Grafana crashloop
kubectl delete configmap -n monitoring loki-loki-stack --ignore-not-found

# ── cert-manager ─────────────────────────────────────
echo ""
echo ">>> Installing cert-manager..."
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true \
  --wait \
  --timeout 5m

# ── NGINX Gateway Fabric (Gateway API) ───────────────
echo ""
echo ">>> Installing Gateway API CRDs (standard channel)..."
kubectl kustomize "https://github.com/nginx/nginx-gateway-fabric/config/crd/gateway-api/standard?ref=v2.7.0" \
  | kubectl apply -f -

echo ">>> Installing NGINX Gateway Fabric..."
helm upgrade --install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric \
  --namespace nginx-gateway \
  --create-namespace \
  --wait \
  --timeout 5m

# ── Gateway + TLS for myapp ──────────────────────────
echo ""
echo ">>> Creating ClusterIssuer and Gateway..."
kubectl apply -f ~/azure-devops-lab/k8s/gateway/clusterissuer.yaml
kubectl apply -f ~/azure-devops-lab/k8s/gateway/gateway.yaml

echo ">>> Waiting for NGINX Gateway Fabric public IP..."
until [ -n "$(kubectl get svc myapp-gateway-nginx -n nginx-gateway -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)" ]; do
  sleep 5
done

GATEWAY_IP=$(kubectl get svc myapp-gateway-nginx -n nginx-gateway \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
export APP_HOST="myapp.$GATEWAY_IP.nip.io"

envsubst < ~/azure-devops-lab/k8s/gateway/certificate.yaml | kubectl apply -f -
echo ">>> myapp Gateway ready: https://$APP_HOST"
echo ">>> HTTPRoute is delivered by the myapp Helm chart (httpRoute.enabled=true)."

# ── Patch myapp's Helm values with this session's Managed Identity ───────
# The client-id changes every session (the identity is destroyed and
# recreated by terraform destroy/apply), so — same reasoning as
# k8s/workload-identity/pod.yaml already had to deal with — this has to be
# re-patched and re-committed every time. ArgoCD (syncPolicy.automated with
# selfHeal) reads myapp's config only from git, so the patch has to land
# there for the running Pod (and its Dapr sidecar) to pick it up.
echo ""
echo ">>> Patching helm-charts/myapp/values.yaml with this session's Managed Identity..."
cd ~/azure-devops-lab
VALUES=helm-charts/myapp/values.yaml
sed -i "s|^\(\s*azure.workload.identity/client-id:\).*|\1 \"${WORKLOAD_IDENTITY_CLIENT_ID}\"|" "$VALUES"

if ! git diff --quiet -- "$VALUES"; then
  git add "$VALUES"
  git commit -m "chore: refresh myapp Workload Identity client-id for this session"
  git push
else
  echo ">>> No change (same Managed Identity as last session)."
fi

# ── Seed ACR with initial images ─────────────────────
echo ""
echo ">>> Building and pushing initial myapp + notifier images to ACR..."
cd ~/azure-devops-lab/terraform
ACR_NAME=$(terraform output -raw acr_login_server | cut -d'.' -f1)
ACR_LOGIN_SERVER=$(terraform output -raw acr_login_server)
CHART_TAG=$(grep 'tag:' ~/azure-devops-lab/helm-charts/myapp/values.yaml | awk '{print $2}' | tr -d '"')
az acr build \
  --registry "$ACR_NAME" \
  --image "myapp:latest" \
  --image "myapp:${CHART_TAG}" \
  ~/azure-devops-lab/app
az acr build \
  --registry "$ACR_NAME" \
  --image "notifier:latest" \
  ~/azure-devops-lab/app/notifier
echo ">>> Images pushed to ACR (myapp: latest, ${CHART_TAG}; notifier: latest)."

echo ""
echo ">>> Deploying notifier (Dapr pub/sub subscriber)..."
export ACR_LOGIN_SERVER
envsubst < ~/azure-devops-lab/k8s/dapr/notifier.yaml | kubectl apply -f -

# ── Trivy Operator ───────────────────────────────────
echo ""
echo ">>> Installing Trivy Operator..."
helm repo add aqua https://aquasecurity.github.io/helm-charts/
helm repo update
helm upgrade --install trivy-operator aqua/trivy-operator \
  --namespace trivy-system \
  --create-namespace \
  --set trivy.ignoreUnfixed=true \
  --wait \
  --timeout 5m

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
echo "myapp public URL:"
echo "  https://$APP_HOST  (self-signed cert — accept browser warning)"
echo ""
echo "Workload Identity Demo:"
echo "  kubectl logs -n workload-identity-demo kv-reader -f"
echo "  kubectl describe pod -n workload-identity-demo kv-reader"
echo ""
echo "Dapr — state, pub/sub, and Key Vault secrets, all through myapp's own sidecar:"
echo "  curl -X POST https://$APP_HOST/state -d '{\"key\":\"demo\",\"value\":\"hello\"}' -H 'Content-Type: application/json'"
echo "  curl https://$APP_HOST/state?key=demo"
echo "  curl -X POST https://$APP_HOST/publish -d '{\"message\":\"hi notifier\"}' -H 'Content-Type: application/json'"
echo "  kubectl logs -n default deployment/notifier -c notifier -f   # should show the published message"
echo "  curl https://$APP_HOST/secret/lab-demo-secret"
echo "  kubectl logs -n default deployment/myapp -c daprd            # sidecar's own logs"
echo ""