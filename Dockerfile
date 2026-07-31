FROM python:3.11-slim-bookworm

WORKDIR /app

# ffmpeg — опционально для PC audio / bell_rupor (admin «Звук ПК»)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py run_server.py change_log_seed.json ./
COPY guardschool ./guardschool
COPY static ./static
COPY widgets ./widgets

ENV GUARDSCHOOL_DEPLOYMENT_MODE=local
ENV GUARDSCHOOL_DATA_DIR=/data

EXPOSE 8000

# Один worker — см. docs/deploy.md (local_audio_worker)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
