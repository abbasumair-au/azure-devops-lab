import os
from flask import Flask
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

# ── OTel setup ────────────────────────────────────────────────────────────────
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector-opentelemetry-collector.monitoring.svc.cluster.local:4317")

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True))
)
trace.set_tracer_provider(provider)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
