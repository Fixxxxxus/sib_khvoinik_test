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

# Rebuild Tailwind CSS after editing classes in templates/ or static/js/app.js
# (standalone CLI v3.4.x, https://github.com/tailwindlabs/tailwindcss/releases)
tailwindcss -c tailwind.config.js -i tailwind.input.css -o static/css/tailwind.css --minify

# Export pages to docs/ for GitHub Pages deployment
python scripts/export_home_to_docs.py          # полный docs/index.html (включая модалки)
python scripts/export_pitomnik_to_docs.py
python scripts/export_b2b_to_docs.py
python scripts/export_gazon_page_to_docs.py
python scripts/export_catalog_to_docs.py
python scripts/export_stati_to_docs.py         # список статей + детальные страницы
python scripts/export_common.py                # ВСЕГДА после экспортов: noindex для зеркала

# Сгенерировать картинки-карточки Службы заботы за неделю (web-контейнер, нужен Chromium в образе)
python manage.py render_care_cards --week 2026-W27
```

There are no tests or linters configured. The only frontend build step is the Tailwind CSS rebuild above (commit the regenerated `static/css/tailwind.css` together with template changes, and copy it to `docs/static/css/`).

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

### Tailwind CSS — prebuilt static CSS

Tailwind is compiled to `static/css/tailwind.css` with the standalone CLI (no node/npm). Config lives in `tailwind.config.js` (colors `brand: '#2D6A4F'`, `brand2: '#40916C'`, `accent: '#E9C46A'`; shadows `soft`/`glow`), entry file `tailwind.input.css`. After ANY change to Tailwind classes in `templates/` or `static/js/app.js`, rebuild the CSS (see Commands) - otherwise new classes silently have no styles. `static/js/tailwind.browser.js` is the legacy runtime compiler, kept only for old non-re-exported `docs/` pages.

### SEO/GEO infrastructure (`pages/seo.py`)

`robots.txt`, `sitemap.xml`, `llms.txt`, IndexNow key file and JSON-LD builders (FAQ, Product, Breadcrumbs, Article) live in `pages/seo.py` and are wired via `pages/urls.py`. Global Organization/GardenStore/WebSite JSON-LD: `templates/partials/schema_org.html` (included in `base.html`). Per-page meta: each dict in `pages/data.py` carries `seo_title`, `meta_description`, `canonical_path` (and optional `noindex`); dynamic pages set them in views. 301 redirects from the old site structure (`/company/`, `/services/*`, `/advice/*`) are in `pages/urls.py`.

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
