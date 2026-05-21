# sg-care-tg

Docker-стек для бота «Служба заботы» @sg_customer_care_bot.

Перенесён с GitHub Actions (`.github/workflows/telegram-polling.yml` и
`telegram-digest.yml`) на Contabo VPS `processorio` (62.171.164.115),
т.к. GitHub Actions раннеры не имеют стабильного доступа к
`api.telegram.org`.

## Состав

- `polling`: long-poll Telegram getUpdates 24/7 (`telegram_poll.py`).
  Обрабатывает `/start <token>`, `/help`, `/unsubscribe`,
  callback `unsub:<token>`. После `/api/care/tg/optin/`, если ответ
  содержит поле `welcome`, бот сразу отправляет welcome-сообщение и
  отчитывается через `/api/care/tg/mark-digest-sent/`.
- `digest-cron`: контейнер с системным cron, запускающий
  `telegram_digest.py` каждый четверг **05:00 UTC = 12:00 NSK**.

Оба сервиса собираются из одного `Dockerfile` (`sg-care-tg:latest`).

## Deploy

```bash
ssh processorio
cd /opt/sg-care-tg
# .env с реальными секретами должен быть на месте (не в git)
docker compose up -d --build
docker compose ps
```

Состав `.env` смотри в `.env.example`. Файл `.env` хранится только на VPS,
в репозиторий не коммитится.

## Логи

```bash
# long-poll
docker compose logs --tail 200 -f polling

# cron + digest
docker compose logs --tail 200 -f digest-cron

# непосредственно журнал digest (внутри контейнера)
docker compose exec digest-cron tail -n 200 -f /var/log/sg-care-digest.log
```

## Ручной запуск дайджеста

```bash
# текущая ISO-неделя
docker compose exec polling python /app/telegram_digest.py

# конкретная неделя
docker compose exec -e WEEK=2026-W21 polling python /app/telegram_digest.py
```

## Обновление кода

```bash
cd /opt/sg-care-tg
# обновить файлы через rsync с локальной машины:
#   rsync -avz --exclude .env deploy/sg-care-tg/ processorio:/opt/sg-care-tg/
docker compose up -d --build
```
