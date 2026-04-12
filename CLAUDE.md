# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Marketing website for «Сибирский Хвойник» — Siberian landscaping/nursery company. Django is used **only for local template rendering**, not as a full web app. The site is deployed as **static HTML on GitHub Pages** from the `docs/` folder.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
python manage.py runserver

# Export pages to docs/ for GitHub Pages deployment
python scripts/export_home_to_docs.py
python scripts/export_gazon_page_to_docs.py
python scripts/export_katalog_to_docs.py
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

## Architecture

### Data flow: Python dicts → Django templates → static HTML → GitHub Pages

1. **`pages/data.py`** — all page content lives here as Python dictionaries (no database models). Each page has its own dict: `HOME_PAGE`, `GAZON_PAGE`, `KATALOG_PAGE`, etc.
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

All routes are flat: `/gazon/`, `/pitomnik/`, `/sadovye-centry/`, `/katalog/`, `/katalog/<slug>/`, `/stati/`, `/kontakty/`, etc.

## Key Conventions

- All user-facing text is in Russian. Timezone: `Asia/Krasnoyarsk`.
- Content changes go in `pages/data.py`, not in templates.
- After template changes, re-run the relevant export script and commit both the template and the updated `docs/` files.
- Images go in `static/media/images/` (prefer WebP). Videos in `static/media/videos/`.
- `docs/static/` mirrors `static/` — both must be updated when adding media.
