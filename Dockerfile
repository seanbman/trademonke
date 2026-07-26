FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=UTC
COPY pyproject.toml requirements.lock ./
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
RUN pip install --no-cache-dir -c requirements.lock .
USER 65532:65532
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
