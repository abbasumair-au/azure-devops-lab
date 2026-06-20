FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# TODO: remplacer cette ligne par la commande pour démarrer run.py
CMD ["echo", "TODO: add the correct CMD to start the app"]
