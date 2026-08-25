FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ ./frontend/

EXPOSE 5000

# Lance directement l'API : les données de démo sont codées en dur dans
# data.py, plus besoin d'étape d'initialisation (seed).
CMD ["python", "app.py"]
