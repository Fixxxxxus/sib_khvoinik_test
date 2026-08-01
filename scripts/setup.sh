#!/usr/bin/env bash
#
# Подготовка свежего checkout (в том числе git worktree) к работе.
# Неинтерактивный, идемпотентный, завершается сам. Долгоживущих процессов нет.
#
# Что делает:
#   1. Поднимает .venv на Python 3.13 (Django 4.2 не поддерживает системный 3.14).
#   2. Ставит зависимости из requirements.txt + тестовые (pytest, pytest-django).
#   3. Создаёт .env из .env.example, если .env не пришёл вместе с worktree.
#   4. Проверяет бинарь Tailwind CLI (.bin/tailwindcss, лежит в git).
#   5. Прогоняет migrate на sqlite и django check.
#
# Опционально: SETUP_PLAYWRIGHT=1 — доставить Chromium для render_care_cards.
#
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log()  { printf '[setup] %s\n' "$*"; }
warn() { printf '[setup][WARN] %s\n' "$*" >&2; }

VENV=".venv"
PY_VERSION="3.13"

# --- 1. Виртуальное окружение -------------------------------------------------

if [ ! -x "$VENV/bin/python" ]; then
  if command -v uv >/dev/null 2>&1; then
    log "создаю $VENV через uv (Python $PY_VERSION)"
    uv venv --python "$PY_VERSION" "$VENV"
  elif command -v "python$PY_VERSION" >/dev/null 2>&1; then
    log "создаю $VENV через python$PY_VERSION -m venv"
    "python$PY_VERSION" -m venv "$VENV"
  elif command -v python3 >/dev/null 2>&1; then
    warn "нет uv и python$PY_VERSION: беру python3 ($(python3 -V 2>&1)). Django 4.2 официально поддерживает Python до 3.13 включительно."
    python3 -m venv "$VENV"
  else
    warn "не найден ни uv, ни python3 - окружение не создано, дальше идти некуда"
    exit 1
  fi
else
  log "$VENV уже существует ($("$VENV/bin/python" -V 2>&1))"
fi

PY="$VENV/bin/python"

# --- 2. Зависимости -----------------------------------------------------------

pip_install() {
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PY" --quiet "$@"
  elif "$PY" -m pip --version >/dev/null 2>&1; then
    "$PY" -m pip install --quiet --disable-pip-version-check "$@"
  else
    warn "в $VENV нет pip и нет uv - зависимости не установлены"
    return 1
  fi
}

log "ставлю зависимости из requirements.txt"
pip_install -r requirements.txt

# pytest.ini и conftest.py в репозитории есть, а тестовые пакеты в requirements.txt
# не объявлены. Ставим их отдельно, чтобы в свежем worktree проходили тесты.
log "ставлю тестовые зависимости (pytest, pytest-django)"
pip_install pytest pytest-django

# MCP-сервер Битрикс24 лежит в gitignored-каталоге, в свежем worktree его нет.
if [ -f bitrix24-mcp/requirements.txt ]; then
  log "ставлю зависимости bitrix24-mcp"
  pip_install -r bitrix24-mcp/requirements.txt
else
  warn "bitrix24-mcp/ отсутствует (каталог в .gitignore) - MCP-сервер Битрикс24 работать не будет"
fi

# --- 3. Локальный .env --------------------------------------------------------

if [ -f .env ]; then
  log ".env на месте"
elif [ -f .env.example ]; then
  cp .env.example .env
  warn "создан .env из .env.example: YANDEX_MAPS_API_KEY пустой, карта на /kontakty/ не загрузится"
else
  warn "нет ни .env, ни .env.example"
fi

# --- 4. Tailwind CLI ----------------------------------------------------------

if [ -f .bin/tailwindcss ]; then
  chmod +x .bin/tailwindcss
  if ./.bin/tailwindcss --help >/dev/null 2>&1; then
    log "Tailwind CLI готов: ./.bin/tailwindcss"
  else
    warn ".bin/tailwindcss не запускается на этой платформе - пересборка CSS недоступна"
  fi
else
  warn ".bin/tailwindcss не найден - пересобрать static/css/tailwind.css не получится"
fi

# --- 5. База и проверка Django ------------------------------------------------

log "применяю миграции (sqlite)"
"$PY" manage.py migrate --noinput

log "django check"
"$PY" manage.py check

# --- 6. Опционально: браузер для playwright -----------------------------------

if [ "${SETUP_PLAYWRIGHT:-0}" = "1" ]; then
  log "доставляю Chromium для playwright"
  "$PY" -m playwright install chromium
else
  log "пропускаю playwright install (SETUP_PLAYWRIGHT=1 - доставить Chromium для render_care_cards)"
fi

log "готово. Дальше: $VENV/bin/python manage.py runserver"
