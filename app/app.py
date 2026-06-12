from flask import Flask
app = Flask(__name__)

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
    app.run(host='0.0.0.0', port=5000)# v1.0.1
# v1.0.2
