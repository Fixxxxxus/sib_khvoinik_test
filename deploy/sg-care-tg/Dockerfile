FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Krasnoyarsk

# cron нужен только digest-cron сервису, но образ общий - ставим в обоих случаях
RUN apt-get update \
    && apt-get install -y --no-install-recommends cron tini ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir requests==2.32.3

COPY telegram_poll.py /app/telegram_poll.py
COPY telegram_digest.py /app/telegram_digest.py
COPY promo_invite.py /app/promo_invite.py
COPY run_digest.sh /app/run_digest.sh
COPY run_promo_invite.sh /app/run_promo_invite.sh
COPY crontab /etc/cron.d/sg-care-digest

RUN chmod 0644 /etc/cron.d/sg-care-digest \
    && chmod +x /app/run_digest.sh \
    && chmod +x /app/run_promo_invite.sh \
    && touch /var/log/sg-care-digest.log

# default CMD overridden by docker-compose service.command
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "/app/telegram_poll.py"]
