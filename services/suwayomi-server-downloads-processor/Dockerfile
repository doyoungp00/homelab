FROM python:3.12-slim

RUN pip install --no-cache-dir watchdog

WORKDIR /app
COPY process_downloads.py /app/process_downloads.py

# Runs as a persistent service: watches --download for new folders and
# archives them into --archive. Adjust paths/flags to taste.
CMD ["python3", "/app/process_downloads.py", \
     "--download", "/data/download", \
     "--archive", "/data/archive", \
     "--db", "/data/state/processed_manga.db", \
     "--interval", "60", \
     "--settle-seconds", "30"]
