"""HTML-шаблоны карточек Службы заботы (контентная + промо)."""
from __future__ import annotations

import html

from .assets import font_face_css, lucide_src
from .palettes import PALETTES, SEASON_EMBLEM

CHANNELS = [("mail", "Email"), ("send", "Telegram"), ("message-circle", "MAX")]
PROMO_HEADLINE = "Полный календарь ухода - на сайте"
PROMO_SUBTEXT = ("Подпишитесь на еженедельный дайджест Службы заботы. Что делать в саду "
                 "именно на этой неделе - в Email, Telegram или MAX.")
PROMO_URL = "gazony.ru/sluzhba-zaboty"
PROMO_BRAND = "Сибирские газоны"


def render_card_html(*, season: str, category_label: str, category_icon: str,
                     headline: str, bullets: list[str]) -> str:
    p = PALETTES[season]
    emblem = SEASON_EMBLEM[season]
    items = "\n".join(
        f'<div class="item"><div class="check"><i data-lucide="check"></i></div>'
        f'<div class="item-text">{html.escape(b)}</div></div>'
        for b in bullets
    )
    edge_icons = ["leaf", emblem, "leaf", "droplet", "leaf", emblem, "leaf"]
    edge = "".join(f'<i data-lucide="{ic}"></i>' for ic in edge_icons)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{font_face_css()}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ background:#888; }}
  .card {{
    --bg:{p['bg']}; --bg-accent:{p['bg_accent']}; --accent:{p['accent']};
    --accent-ink:{p['accent_ink']}; --ink:{p['ink']}; --surface:{p['surface']};
    --body-on-dark:{p['body_on_dark']}; --muted:{p['muted']}; --on-dark:#fff;
    --kicker:{p['kicker']};
    width:1280px; height:1280px; overflow:hidden;
    display:flex; flex-direction:column; background:var(--surface);
    font-family:'Manrope',sans-serif; -webkit-font-smoothing:antialiased;
  }}
  .top {{ position:relative; padding:96px 80px 72px; display:flex; flex-direction:column;
    gap:30px; height:430px;
    background:
      radial-gradient(120% 150% at 82% 0%, color-mix(in srgb, var(--bg-accent) 60%, transparent), transparent 62%),
      var(--bg); }}
  .emblem {{ position:absolute; top:60px; left:1046px; width:158px; height:158px;
            color:var(--on-dark); opacity:.15; }}
  .emblem svg {{ width:158px; height:158px; }}
  .edge {{ position:absolute; left:64px; top:338px; width:1152px; display:flex;
          justify-content:space-between; align-items:center; opacity:.2; color:var(--on-dark); }}
  .edge svg {{ width:48px; height:48px; }}
  .eyebrow {{ display:flex; align-items:center; gap:14px; }}
  .tick {{ width:34px; height:3px; border-radius:2px; background:var(--kicker); }}
  .kicker {{ font-size:22px; font-weight:700; color:var(--kicker); letter-spacing:3px; }}
  .title-row {{ display:flex; align-items:center; gap:28px; }}
  .icon-tile {{ width:104px; height:104px; border-radius:26px; background:var(--bg-accent);
               display:flex; align-items:center; justify-content:center; color:var(--on-dark);
               flex-shrink:0; }}
  .icon-tile svg {{ width:58px; height:58px; }}
  .cat-title {{ font-size:84px; font-weight:800; color:var(--on-dark); line-height:1; }}
  .body {{ flex:1; display:flex; flex-direction:column; gap:42px;
          padding:60px 80px 40px; background:var(--surface); }}
  .headline {{ font-size:54px; font-weight:800; color:var(--ink); line-height:1.08; }}
  .checklist {{ display:flex; flex-direction:column; gap:30px; }}
  .item {{ display:flex; gap:22px; align-items:center; }}
  .check {{ width:46px; height:46px; border-radius:13px; background:var(--accent);
           display:flex; align-items:center; justify-content:center; flex-shrink:0;
           color:var(--accent-ink); }}
  .check svg {{ width:28px; height:28px; stroke-width:3; }}
  .item-text {{ font-size:31px; font-weight:500; color:var(--ink); line-height:1.22; }}
  .footer {{ display:flex; align-items:center; gap:12px; padding:24px 80px 44px;
            background:var(--surface); color:var(--muted); }}
  .footer svg {{ width:30px; height:30px; }}
  .footer span {{ font-size:27px; font-weight:600; }}
</style></head>
<body>
  <div class="card" id="card">
    <div class="top">
      <i class="emblem" data-lucide="{emblem}"></i>
      <div class="edge">{edge}</div>
      <div class="eyebrow"><span class="tick"></span><span class="kicker">СЛУЖБА ЗАБОТЫ</span></div>
      <div class="title-row">
        <div class="icon-tile"><i data-lucide="{html.escape(category_icon)}"></i></div>
        <div class="cat-title">{html.escape(category_label)}</div>
      </div>
    </div>
    <div class="body">
      <div class="headline">{html.escape(headline)}</div>
      <div class="checklist">{items}</div>
    </div>
    <div class="footer"><i data-lucide="sprout"></i><span>Служба заботы · gazony.ru</span></div>
  </div>
  <script>{lucide_src()}</script>
  <script>
    window.__ready = false;
    (async () => {{
      try {{ lucide.createIcons(); }} catch (e) {{ console.error('lucide', e); }}
      if (document.fonts && document.fonts.ready) {{ await document.fonts.ready; }}
      window.__ready = true;
    }})();
  </script>
</body></html>"""


def render_promo_html(season: str) -> str:
    p = PALETTES[season]
    emblem = SEASON_EMBLEM[season]
    chips = "".join(
        f'<div class="chip"><i data-lucide="{ic}"></i><span>{name}</span></div>'
        for ic, name in CHANNELS
    )
    edge_icons = ["leaf", emblem, "flower-2", "droplet", "sprout", emblem, "leaf"]
    edge = "".join(f'<i data-lucide="{ic}"></i>' for ic in edge_icons)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{font_face_css()}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ background:#888; }}
  .card {{
    --bg:{p['bg']}; --bg-accent:{p['bg_accent']}; --accent:{p['accent']};
    --accent-ink:{p['accent_ink']}; --on-dark:#fff; --body-on-dark:{p['body_on_dark']};
    --kicker:{p['kicker']}; --cta-bg:{p['cta_bg']}; --cta-ink:{p['cta_ink']};
    width:1280px; height:1280px; overflow:hidden; position:relative;
    display:flex; flex-direction:column; padding:104px 88px 92px;
    background:
      radial-gradient(120% 130% at 85% 100%, color-mix(in srgb, var(--bg-accent) 55%, transparent), transparent 60%),
      var(--bg);
    font-family:'Manrope',sans-serif; -webkit-font-smoothing:antialiased; color:var(--on-dark);
  }}
  .edge {{ position:absolute; left:80px; right:80px; top:54px; display:flex;
          justify-content:space-between; align-items:center; opacity:.18; }}
  .edge svg {{ width:46px; height:46px; }}
  .watermark {{ position:absolute; right:-60px; bottom:-40px; width:520px; height:520px;
               color:var(--on-dark); opacity:.10; }}
  .watermark svg {{ width:520px; height:520px; }}
  .eyebrow {{ display:inline-flex; align-items:center; gap:12px; align-self:flex-start;
             border:2px solid color-mix(in srgb, var(--kicker) 80%, transparent);
             color:var(--kicker); padding:14px 26px; border-radius:999px;
             font-size:24px; font-weight:700; letter-spacing:2px; margin-top:60px; }}
  .eyebrow .dot {{ width:14px; height:14px; border-radius:50%; background:var(--kicker); }}
  .headline {{ font-size:88px; font-weight:800; line-height:1.04; margin-top:46px; max-width:1060px; }}
  .subtext {{ font-size:34px; font-weight:500; line-height:1.4; color:var(--body-on-dark);
             margin-top:40px; max-width:980px; }}
  .chips {{ display:flex; gap:24px; margin-top:54px; }}
  .chip {{ display:inline-flex; align-items:center; gap:14px;
          border:2px solid color-mix(in srgb, var(--on-dark) 35%, transparent);
          padding:20px 32px; border-radius:999px; font-size:30px; font-weight:600; }}
  .chip svg {{ width:34px; height:34px; }}
  .spacer {{ flex:1; }}
  .cta {{ display:flex; align-items:center; justify-content:center; gap:20px;
         background:var(--cta-bg); color:var(--cta-ink); border-radius:999px;
         padding:40px; font-size:42px; font-weight:800; }}
  .cta svg {{ width:46px; height:46px; }}
  .brand {{ display:flex; align-items:center; justify-content:center; gap:14px;
           margin-top:40px; opacity:.85; font-size:30px; font-weight:600; }}
  .brand svg {{ width:34px; height:34px; }}
</style></head>
<body>
  <div class="card" id="card">
    <div class="edge">{edge}</div>
    <i class="watermark" data-lucide="{emblem}"></i>
    <div class="eyebrow"><span class="dot"></span>СЛУЖБА ЗАБОТЫ</div>
    <div class="headline">{html.escape(PROMO_HEADLINE)}</div>
    <div class="subtext">{html.escape(PROMO_SUBTEXT)}</div>
    <div class="chips">{chips}</div>
    <div class="spacer"></div>
    <div class="cta"><i data-lucide="globe"></i><span>{PROMO_URL}</span></div>
    <div class="brand"><i data-lucide="sprout"></i><span>{PROMO_BRAND}</span></div>
  </div>
  <script>{lucide_src()}</script>
  <script>
    window.__ready = false;
    (async () => {{
      try {{ lucide.createIcons(); }} catch (e) {{ console.error(e); }}
      if (document.fonts && document.fonts.ready) {{ await document.fonts.ready; }}
      window.__ready = true;
    }})();
  </script>
</body></html>"""
