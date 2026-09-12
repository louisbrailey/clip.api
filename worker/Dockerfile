FROM python:3.12-slim
RUN useradd --uid 10001 --create-home worker
WORKDIR /app
COPY worker/runtime.py /app/runtime.py
RUN mkdir /state && chown worker:worker /state
USER worker
ENV PYTHONUNBUFFERED=1 JOURNAL_DIR=/state
CMD ["python", "/app/runtime.py"]
