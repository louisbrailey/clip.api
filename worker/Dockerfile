FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home worker
WORKDIR /app
COPY worker/runtime.py worker/render.py /app/
RUN mkdir /state && chown worker:worker /state
USER worker
ENV PYTHONUNBUFFERED=1 JOURNAL_DIR=/state
CMD ["python", "/app/runtime.py"]
