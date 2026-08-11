FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system bot && useradd --system --gid bot bot && chown -R bot:bot /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=bot:bot . .

USER bot

CMD ["python", "-m", "bms_tracker.cli"]