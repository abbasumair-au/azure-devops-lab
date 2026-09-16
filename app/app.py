import os

import requests
from flask import Flask, request
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

# ── OTel setup ────────────────────────────────────────────────────────────────
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "otel-collector-opentelemetry-collector.monitoring.svc.cluster.local:4317")

provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "myapp"}))
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True))
)
trace.set_tracer_provider(provider)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

# ── Dapr sidecar ──────────────────────────────────────────────────────────────
# Every Dapr call is just HTTP to the sidecar sitting in the same Pod —
# nothing here talks to Redis or Key Vault directly. Swap the component
# behind "statestore"/"pubsub"/"keyvault" (k8s/dapr/components/) and none
# of this code changes.
DAPR_HTTP_PORT = os.getenv("DAPR_HTTP_PORT", "3500")
DAPR_BASE = f"http://localhost:{DAPR_HTTP_PORT}/v1.0"

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return {"status": "ok", "service": "myapp", "version": "1.0.0"}

@app.route('/health')
def health():
    return {"health": "healthy"}

@app.route('/ready')
def ready():
    # Readiness checks dependencies (DB, cache, etc.) — here app is always ready
    return {"ready": "true"}

@app.route('/state', methods=['GET', 'POST'])
def state():
    # Dapr state building block, backed by k8s/dapr/components/statestore.yaml (Redis).
    if request.method == 'POST':
        body = request.get_json(silent=True) or {}
        key = body.get('key')
        if not key:
            return {"error": "key is required"}, 400
        resp = requests.post(f"{DAPR_BASE}/state/statestore", json=[{"key": key, "value": body.get('value')}])
        resp.raise_for_status()
        return {"key": key, "value": body.get('value')}, 201

    key = request.args.get('key', 'demo')
    resp = requests.get(f"{DAPR_BASE}/state/statestore/{key}")
    if resp.status_code == 204:
        return {"key": key, "value": None}
    resp.raise_for_status()
    return {"key": key, "value": resp.json()}

@app.route('/publish', methods=['POST'])
def publish():
    # Dapr pub/sub building block — published here, delivered to notifier's
    # /notifications route (app/notifier/app.py) by its own sidecar. myapp
    # never talks to notifier directly.
    body = request.get_json(silent=True) or {"message": "hello from myapp"}
    resp = requests.post(f"{DAPR_BASE}/publish/pubsub/notifications", json=body)
    resp.raise_for_status()
    return {"published": body}, 202

@app.route('/secret/<name>')
def secret(name):
    # Dapr secrets building block, backed by k8s/dapr/components/secretstore.yaml
    # (Azure Key Vault, via the SAME Workload Identity binding as
    # k8s/workload-identity/ — myapp's own ServiceAccount, not a separate demo
    # identity). Try /secret/lab-demo-secret.
    resp = requests.get(f"{DAPR_BASE}/secrets/keyvault/{name}")
    resp.raise_for_status()
    return resp.json()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
