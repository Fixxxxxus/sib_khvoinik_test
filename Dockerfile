FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

ENV CARE_CHROMIUM_PATH=/usr/bin/chromium

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev \
        zlib1g-dev \
        curl \
        chromium \
        fonts-liberation \
        libnss3 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libasound2 \
        cron \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/staticfiles /app/media

COPY deploy/gazony-cron/crontab /etc/cron.d/gazony-digest
COPY deploy/gazony-cron/cron-entrypoint.sh /app/cron-entrypoint.sh
COPY deploy/gazony-cron/run_email_max_digest.sh /app/run_email_max_digest.sh
RUN chmod 0644 /etc/cron.d/gazony-digest \
    && chmod +x /app/cron-entrypoint.sh /app/run_email_max_digest.sh \
    && touch /var/log/gazony-digest.log

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
