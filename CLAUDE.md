# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Marketing website for «Сибирский Хвойник» / «Сибирские газоны» (Siberian landscaping/nursery company).

**Production lives on `https://gazony.ru/` (and `panel.gazony.ru/` for admin).** It is served by Django + gunicorn behind Caddy in Docker on a VDS at `72.56.8.107:/opt/gazony`. Auto-deploy from `main` via `.github/workflows/deploy-vds.yml`. The VDS uses `Caddyfile.full` (apex + panel + www → apex redirect); `Caddyfile` is the older panel-only config.

GitHub Pages from `docs/` is a **secondary mirror** at `https://fixxxxxus.github.io/sib_khvoinik_test/`, kept for fallback/preview only. Do **not** assume Pages is prod, do **not** rely on `docs/` paths when serving anything to gazony.ru — the VDS serves Django templates live, not `docs/`. SEO/site-verification files (Yandex, Дзен, Google) MUST be wired through Django (template `<meta>` in `base.html` or a `path()` in `pages/urls.py`), not just dropped into `docs/`.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
python manage.py runserver

# Export pages to docs/ for GitHub Pages deployment
python scripts/export_home_to_docs.py          # полный docs/index.html (включая модалки)
python scripts/export_pitomnik_to_docs.py
python scripts/export_b2b_to_docs.py
python scripts/export_gazon_page_to_docs.py
python scripts/export_catalog_to_docs.py
```

There are no tests, linters, or frontend build steps configured.

## Bitrix24 MCP Server

Custom MCP server in `bitrix24-mcp/` — connects Claude Code to Bitrix24 REST API via incoming webhook (stdio transport, FastMCP).

**29 tools:** CRM (leads, deals, contacts, companies), tasks + comments, CRM forms, event webhooks. All tools prefixed `b24_`.

```bash
# Install MCP server deps
pip install -r bitrix24-mcp/requirements.txt
```

Portal: `sgpichugi.bitrix24.ru`. Webhook scopes: `crm`, `task`. Events work without a dedicated scope.

Note: `sender.*` (email marketing) module is not available on this portal — mailing tools intentionally excluded.

## Deploy

- **VDS (prod, gazony.ru)**: push to `main` → `deploy-vds.yml` → SSH to `/opt/gazony` → `git reset --hard origin/main` → `docker compose build && up -d`. Migrations + collectstatic run inside the web container at startup. Caddy reverse-proxies to `web:8000`, serves `/static/*` and `/media/*` directly.
- **GitHub Pages (mirror)**: `deploy-pages.yml` publishes `docs/`. Re-run the relevant `scripts/export_*_to_docs.py` after template edits and commit the regenerated HTML.

## Architecture

### Data flow: Python dicts → Django templates → static HTML → GitHub Pages

1. **`pages/data.py`** — all page content lives here as Python dictionaries (no database models). Each page has its own dict: `HOME_PAGE`, `GAZON_PAGE`, `CATALOG_PAGE`, etc.
2. **`pages/views.py`** — function-based views that pass data dicts to templates via `render()`.
3. **`templates/`** — Django templates with Tailwind utility classes. `base.html` is the layout; `pages/` has per-page templates; `partials/` has navbar, footer, modals.
4. **`scripts/`** — export scripts render templates to static HTML, rewrite paths (`/static/` → `/sib_khvoinik_test/static/`), and save to `docs/`.
5. **`docs/`** — pre-rendered static site deployed via GitHub Actions (`deploy-pages.yml`). Changes here are committed to git.

### Tailwind CSS — browser-compiled, no build step

Tailwind runs in the browser via `static/js/tailwind.browser.js`. Config is inline in `base.html`:
- `brand: '#2D6A4F'`, `brand2: '#40916C'`, `accent: '#E9C46A'`

No `package.json`, `tailwind.config.js`, or PostCSS — all runtime.

### Client-side (`static/js/app.js`)

Single JS file handling: hero viewport sizing, mobile menu, modal system, accordions, scroll animations, animated counters, before/after sliders, carousels, gazon pricing calculator, localStorage-based form submissions, Lucide icons.

### Routing (`pages/urls.py`)

All routes are flat: `/gazon/`, `/pitomnik/`, `/sadovye-centry/`, `/catalog/`, `/catalog/<slug>/`, `/stati/`, `/kontakty/`, etc.

## Key Conventions

- All user-facing text is in Russian. Timezone: `Asia/Krasnoyarsk`.
- Content changes go in `pages/data.py`, not in templates.
- After template changes, re-run the relevant export script and commit both the template and the updated `docs/` files.
- Images go in `static/media/images/` (prefer WebP). Videos in `static/media/videos/`.
- `docs/static/` mirrors `static/` — both must be updated when adding media.
