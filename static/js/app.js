// Base path: read from <meta name="base-path"> set in HTML.
// On GitHub Pages the meta has "/sib_khvoinik_test"; Timeweb deploy
// sed-replaces it to "/"; localhost template leaves it empty.
var BASE_PATH = (function () {
  var el = document.querySelector('meta[name="base-path"]');
  if (el) {
    var p = el.getAttribute('content');
    return (!p || p === '/') ? '' : p.replace(/\/+$/, '');
  }
  return '';
})();

function initYear() {
  const el = document.getElementById('year');
  if (!el) return;
  const d = new Date();
  el.textContent = String(d.getFullYear());
}

// ── 152-ФЗ: Consent checkbox injection ──
function initConsentCheckboxes() {
  document.querySelectorAll('form[data-ui-form]').forEach((form) => {
    if (form.querySelector('[name="consent"]')) return;
    const submitBtn = form.querySelector('button[type="submit"], button:not([type])');
    if (!submitBtn) return;

    const wrapper = document.createElement('label');
    wrapper.className = 'flex items-start gap-2 text-xs text-slate-500 cursor-pointer';
    wrapper.innerHTML =
      '<input type="checkbox" name="consent" required class="mt-0.5 accent-brand shrink-0" />' +
      '<span>Даю <a href="' + BASE_PATH + '/consent/" class="text-brand underline hover:text-brand2" target="_blank">согласие на обработку персональных данных</a>' +
      ' в соответствии с <a href="' + BASE_PATH + '/privacy/" class="text-brand underline hover:text-brand2" target="_blank">Политикой конфиденциальности</a></span>';

    const checkbox = wrapper.querySelector('input');
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-50');
    checkbox.addEventListener('change', () => {
      submitBtn.disabled = !checkbox.checked;
      submitBtn.classList.toggle('opacity-50', !checkbox.checked);
    });

    submitBtn.parentNode.insertBefore(wrapper, submitBtn);
  });
}

// ── 152-ФЗ: Cookie banner ──
function initCookieBanner() {
  const banner = document.getElementById('cookieBanner');
  const acceptAll = document.getElementById('cookieAcceptAll');
  const necessaryOnly = document.getElementById('cookieNecessaryOnly');
  const settingsBtn = document.getElementById('cookieSettingsBtn');
  if (!banner || !acceptAll || !necessaryOnly) return;

  const consent = localStorage.getItem('cookie_consent');
  if (!consent) {
    banner.classList.remove('hidden');
  } else if (consent === 'all') {
    initYandexMetrika();
  }

  const setConsent = (value) => {
    localStorage.setItem('cookie_consent', value);
    banner.classList.add('hidden');
    if (value === 'all') initYandexMetrika();
  };

  acceptAll.addEventListener('click', () => setConsent('all'));
  necessaryOnly.addEventListener('click', () => setConsent('necessary'));

  if (settingsBtn) {
    settingsBtn.addEventListener('click', () => {
      localStorage.removeItem('cookie_consent');
      banner.classList.remove('hidden');
    });
  }
}

// ── Яндекс.Метрика (условная загрузка) ──
let metrikaLoaded = false;
function initYandexMetrika() {
  if (metrikaLoaded) return;
  metrikaLoaded = true;

  // Replace XXXXXXXX with actual counter ID
  const COUNTER_ID = 'XXXXXXXX';

  (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
  m[i].l=1*new Date();
  for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
  k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
  (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");

  ym(COUNTER_ID, "init", {
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    webvisor: true,
  });
}

// UI-only placeholder PDF generators
window.SGDownloadGazonChecklist = function () {
  const text =
    'Чек-лист подготовки участка под газон\\n\\n1) Подготовка основания\\n2) Планировка грунтов\\n3) Завоз грунтов\\n4) Вертикальная планировка\\n5) Готовый результат\\n\\nЭто заглушка для этапа 1.';
  const blob = new Blob([text], { type: 'application/pdf' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'checklist-gazon.pdf';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};

/** Герои на весь экран минус шапка. Убирает щель снизу на мобильных браузерах. */
function initViewportHeroHeights() {
  const header = document.getElementById('site-header');
  const heroes = document.querySelectorAll(
    '[data-home-hero], [data-gazon-hero], [data-ozelenenie-hero], [data-b2b-hero], [data-pitomnik-hero], [data-sadovye-centry-hero], [data-zaboty-hero]'
  );
  if (!header || heroes.length === 0) return;

  const apply = () => {
    const h = window.innerHeight - header.offsetHeight;
    // +1px: субпиксель / GitHub Pages / Safari — иначе снизу проступает белый body
    const px = `${Math.max(280, Math.ceil(h) + 1)}px`;
    heroes.forEach((el) => {
      el.style.minHeight = px;
    });
  };

  apply();
  let t = null;
  window.addEventListener('resize', () => {
    window.clearTimeout(t);
    t = window.setTimeout(apply, 100);
  });
  window.addEventListener('orientationchange', apply);
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => apply());
    ro.observe(header);
  }
}

/** Hero главной: как у «Газон» — без вспышки первого кадра MP4 до фактического playing */
function initHomeHeroVideo() {
  const v = document.querySelector('section[data-home-hero] video.hero-bg-video');
  if (!v) return;
  const reveal = () => v.classList.add('is-home-hero-ready');
  v.addEventListener('playing', reveal, { once: true });
  try {
    if (!v.paused && v.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) reveal();
  } catch (e) {
    /* ignore */
  }
}

/** Hero «Газон»: плавное появление видео после start воспроизведения — убирает кадр из кэша/рассинхрон с poster */
function initGazonHeroVideo() {
  const v = document.getElementById('gazon-hero-video');
  if (!v) return;
  const reveal = () => v.classList.add('is-gazon-hero-ready');
  v.addEventListener('playing', reveal, { once: true });
  try {
    if (!v.paused && v.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) reveal();
  } catch (e) {
    /* ignore */
  }
}

function initB2bHeroVideo() {
  const v = document.getElementById('b2b-hero-video');
  if (!v) return;
  const reveal = () => v.classList.add('is-b2b-hero-ready');
  v.addEventListener('playing', reveal, { once: true });
  try {
    if (!v.paused && v.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) reveal();
  } catch (e) {
    /* ignore */
  }
}

function initBurger() {
  const burgerBtn = document.getElementById('burgerBtn');
  const mobileMenu = document.getElementById('mobileMenu');
  if (!burgerBtn || !mobileMenu) return;
  burgerBtn.addEventListener('click', () => {
    mobileMenu.classList.toggle('hidden');
    const open = !mobileMenu.classList.contains('hidden');
    burgerBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (window.lucide) window.lucide.createIcons();
  });

  // Close menu when clicking a link
  mobileMenu.querySelectorAll('a').forEach((a) => {
    a.addEventListener('click', () => {
      mobileMenu.classList.add('hidden');
      burgerBtn.setAttribute('aria-expanded', 'false');
    });
  });
}

function initModal() {
  const overlay = document.getElementById('modalOverlay');
  const host = document.getElementById('modalHost');
  const closeTop = document.getElementById('modalCloseTop');
  const modalTitle = document.getElementById('modalTitle');
  const modalBody = document.getElementById('modalBody');
  if (!overlay || !host || !closeTop || !modalTitle || !modalBody) return;

  const templateMap = {
    'mini_brief': 'modal-template-mini_brief',
    'contact_zaboty': 'modal-template-contact_zaboty',
    'contact_consult': 'modal-template-contact_consult',
    'b2b_cpo': 'modal-template-b2b_cpo',
    'b2b_price_stock': 'modal-template-b2b_price_stock',
    'b2b_care_reglement': 'modal-template-b2b_care_reglement',
    'gazon_price_list': 'modal-template-gazon_price_list',
    'gazon_cpo': 'modal-template-gazon_cpo',
    'gazon_checklist': 'modal-template-gazon_checklist',
    'gazon_open_day': 'modal-template-gazon_open_day',
    'gazon_logistics': 'modal-template-gazon_logistics',
    'gazon_presentation': 'modal-template-gazon_presentation',
    'gazon_calc': 'modal-template-gazon_calc',
    'ozelenenie_ready_project': 'modal-template-ozelenenie-ready_project',
    'ozelenenie_mini_project': 'modal-template-ozelenenie-mini_project',
    'ozelenenie_audit_plan': 'modal-template-ozelenenie-audit_plan',
    'ozelenenie_assess_upload': 'modal-template-ozelenenie-assess_upload',
    'ozelenenie_send_project': 'modal-template-ozelenenie-send_project',
    'ozelenenie_materials_scheme': 'modal-template-ozelenenie-materials_scheme',
    'pitomnik_presentation': 'modal-template-pitomnik_presentation',
    'sadovye_digital_card': 'modal-template-sadovye_digital_card',
    'sadovye_novinki_notify': 'modal-template-sadovye_novinki_notify',
    'sadovye_novinka_1': 'modal-template-sadovye_novinka_1',
    'sadovye_novinka_2': 'modal-template-sadovye_novinka_2',
    'sadovye_novinka_3': 'modal-template-sadovye_novinka_3',
    'sadovye_novinka_4': 'modal-template-sadovye_novinka_4',
  };

  const initConsentGate = (root) => {
    const form = root.querySelector('form[data-consent-gated="1"]');
    if (!form) return;

    const checkbox = form.querySelector('[data-consent-checkbox]');
    const submitBtn = form.querySelector('[data-consent-submit]');
    if (!checkbox || !submitBtn) return;

    const syncState = () => {
      submitBtn.disabled = !checkbox.checked;
    };

    checkbox.addEventListener('change', syncState);
    syncState();
  };

  const openModal = (targetKey, title) => {
    const tplId = templateMap[targetKey] || 'modal-template-success';
    const tpl = document.getElementById(tplId);
    if (!tpl) return;

    const sizeWrap = host.firstElementChild;
    if (sizeWrap) {
      sizeWrap.classList.remove('max-w-lg', 'max-w-2xl');
      const wide =
        targetKey === 'contact_zaboty' ||
        targetKey === 'ozelenenie_mini_project' ||
        targetKey === 'gazon_calc' ||
        targetKey === 'sadovye_novinka_1' ||
        targetKey === 'sadovye_novinka_2' ||
        targetKey === 'sadovye_novinka_3' ||
        targetKey === 'sadovye_novinka_4';
      sizeWrap.classList.add(wide ? 'max-w-2xl' : 'max-w-lg');
    }

    modalTitle.textContent = title || '';
    modalBody.innerHTML = '';
    modalBody.appendChild(tpl.content.cloneNode(true));
    if (window.lucide) window.lucide.createIcons();
    initConsentGate(modalBody);

    // Inject consent checkbox into freshly cloned modal form
    const modalForm = modalBody.querySelector('form[data-ui-form]');
    if (modalForm && !modalForm.querySelector('[name="consent"]')) {
      initConsentCheckboxes();
    }

    // Калькулятор: передать форму из modalBody — иначе getElementById может попасть в <template> и повесить input на скрытые поля.
    if (targetKey === 'gazon_calc') {
      const calcForm = modalBody.querySelector('#gazonCalculatorModal');
      initGazonCalculator(calcForm);
    }

    overlay.classList.remove('hidden');
    host.classList.remove('hidden');
    host.classList.add('modal-enter');
    document.body.style.overflow = 'hidden';
  };

  // Make it accessible for auto-open based on URL params.
  window.SGOpenModal = openModal;

  const closeModal = () => {
    overlay.classList.add('hidden');
    host.classList.add('hidden');
    host.classList.remove('modal-enter');
    document.body.style.overflow = '';
  };

  closeTop.addEventListener('click', closeModal);
  overlay.addEventListener('click', closeModal);
  document.addEventListener('click', (e) => {
    const closeBtn = e.target && e.target.closest('[data-close-modal]');
    if (closeBtn) closeModal();
  });

  // Open by UI buttons
  document.querySelectorAll('[data-open-modal]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const key = btn.getAttribute('data-open-modal');
      const title = btn.getAttribute('data-modal-title') || '';
      openModal(key, title);
    });
  });

  // ── Bitrix24 lead capture ──
  const B24_WEBHOOK = 'https://sgpichugi.bitrix24.ru/rest/1/6phslfom1dj09wh3';

  // Human-readable form titles for Bitrix24 TITLE field
  const FORM_TITLES = {
    'request': 'Обращение с сайта',
    'mini-brief': 'Мини-бриф',
    'sluzhba-zaboty': 'Служба заботы',
    'consultation': 'Консультация',
    'sadovye-novinki-notify': 'Уведомление о новинках',
    'contract-request': 'Запрос КП (B2B)',
    'price-stock': 'Прайс и наличие (B2B)',
    'reglement-uhoda': 'Регламент ухода (B2B)',
    'gazon-price-list': 'Прайс-лист газон',
    'gazon-cpo': 'КП на газон',
    'gazon-checklist': 'Чек-лист газон',
    'gazon-open-day': 'День открытых дверей',
    'gazon-logistics': 'Логистика газон',
    'gazon-presentation': 'Презентация газон',
    'gazon-calc': 'Калькулятор газона',
    'ozelenenie-ready-project': 'Готовый проект озеленения',
    'mini-project': 'Мини-проект озеленения',
    'ozelenenie-audit-plan': 'Аудит участка',
    'ozelenenie-assess-upload': 'Оценка участка (фото)',
    'ozelenenie-send-project': 'Проверка проекта',
    'ozelenenie-materials-scheme': 'Подбор материалов и схема',
    'pitomnik-presentation': 'Презентация питомника',
    'digital-card': 'Цифровая карта',
  };

  // Labels for COMMENTS fields
  const FIELD_LABELS = {
    objectType: 'Тип объекта',
    area: 'Площадь, м²',
    region: 'Регион',
    topic: 'Тема',
    message: 'Сообщение',
    city: 'Город',
    budget: 'Бюджет',
    deadline: 'Сроки',
    quantity: 'Количество',
    comment: 'Комментарий',
    notes: 'Пожелания',
    collaborationFormat: 'Формат сотрудничества',
    clientType: 'Тип клиента',
    deliveryWhen: 'Сроки поставки',
    date: 'Дата',
    format: 'Формат поставки',
    stage: 'Стадия объекта',
    preferred_messenger: 'Мессенджер',
    link: 'Ссылка',
    service: 'Услуга',
    address: 'Адрес',
  };

  // Readable display values for select options
  const VALUE_LABELS = {
    ozelenenie: 'Озеленение', gazon: 'Газон',
    sadovye_centry: 'Садовые центры', b2b: 'B2B',
    roll: 'Поставка рулонного газона',
    combined: 'Комбинированное решение',
    plants: 'Контрактные поставки растений',
    turnkey: 'Реализация под ключ',
    partial: 'Частичная реализация',
    partner: 'Партнёрство с ландшафтными компаниями',
    uk: 'Сопровождение для УК',
    max: 'MAX', telegram: 'Telegram', email: 'Эл. почта',
  };

  // care_*/promo_* checkbox labels
  const CARE_LABELS = {
    care_gazon: 'Газон', care_conifer: 'Хвойные',
    care_deciduous_trees: 'Лиственные деревья',
    care_deciduous_shrubs: 'Лиственные кустарники',
    care_hydrangea: 'Гортензия', care_peony: 'Пионы',
    care_ornamental_apple: 'Яблони декоративные',
    care_perennials: 'Многолетние цветы', care_roses: 'Розы',
    promo_news: 'Новинки', promo_sales: 'Акции',
  };

  const sendLeadToB24 = (tag, payload) => {
    const [section, formName] = tag.includes('/') ? tag.split('/', 2) : ['other', tag];

    const fields = {
      TITLE: `Сайт: ${FORM_TITLES[formName] || formName}`,
      SOURCE_ID: 'WEB',
      UTM_SOURCE: 'website',
      UTM_MEDIUM: section,
      UTM_CONTENT: formName,
      UTM_TERM: window.location.pathname,
    };

    // ── Map contact info to CRM fields ──
    if (payload.name) fields.NAME = payload.name;
    if (payload.contactPerson) fields.NAME = payload.contactPerson;
    if (payload.phone) {
      fields.PHONE = [{ VALUE: payload.phone, VALUE_TYPE: 'WORK' }];
    }
    if (payload.email) {
      fields.EMAIL = [{ VALUE: payload.email, VALUE_TYPE: 'WORK' }];
    }
    // B2B forms use combined "contact" field for phone or email
    if (payload.contact) {
      var val = payload.contact.trim();
      if (val.includes('@')) {
        fields.EMAIL = [{ VALUE: val, VALUE_TYPE: 'WORK' }];
      } else {
        fields.PHONE = [{ VALUE: val, VALUE_TYPE: 'WORK' }];
      }
    }
    if (payload.company) fields.COMPANY_TITLE = payload.company;

    // ── Build COMMENTS from remaining fields ──
    var skipKeys = [
      'name', 'phone', 'email', 'company', 'formTag', 'consent',
      'contactPerson', 'contact', 'consent_messages',
    ];

    var lines = [];

    // Group care_*/promo_* checkboxes into one line
    var subs = Object.keys(payload)
      .filter(function (k) { return (k.startsWith('care_') || k.startsWith('promo_')) && payload[k]; })
      .map(function (k) { return CARE_LABELS[k] || k; });
    if (subs.length) lines.push('<b>Подписки:</b> ' + subs.join(', '));

    Object.entries(payload)
      .filter(function (e) {
        var k = e[0];
        return !skipKeys.includes(k) && !k.startsWith('care_') && !k.startsWith('promo_');
      })
      .forEach(function (e) {
        var k = e[0], v = e[1];
        if (!v || v === '1') return; // skip empty and bare checkbox "1"
        var label = FIELD_LABELS[k] || k;
        var display = VALUE_LABELS[v] || v;
        lines.push('<b>' + label + ':</b> ' + display);
      });

    if (lines.length) fields.COMMENTS = lines.join('<br>');

    fetch(`${B24_WEBHOOK}/crm.lead.add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields }),
    }).catch((err) => console.warn('[B24] lead send failed:', err));
  };

  // Submit UI-only forms (save to localStorage)
  const handleUiSubmit = async (form) => {
    const tag = form.getAttribute('data-form-tag') || 'unknown';
    const uiAction = form.getAttribute('data-ui-action') || '';
    const formData = new FormData(form);
    const payload = {};
    for (const [k, v] of formData.entries()) {
      if (Object.prototype.hasOwnProperty.call(payload, k)) {
        const cur = payload[k];
        payload[k] = Array.isArray(cur) ? [...cur, v] : [cur, v];
      } else {
        payload[k] = v;
      }
    }

    const entry = { tag, payload, ts: new Date().toISOString() };
    const key = 'sg_leads';
    const existing = JSON.parse(localStorage.getItem(key) || '[]');
    existing.push(entry);
    localStorage.setItem(key, JSON.stringify(existing));

    sendLeadToB24(tag, payload);

    // Swap to success template
    const successTpl = document.getElementById('modal-template-success');
    if (successTpl) {
      modalTitle.textContent = '';
      modalBody.innerHTML = '';
      modalBody.appendChild(successTpl.content.cloneNode(true));
      if (window.lucide) window.lucide.createIcons();
    }

    // Optional UI-only side effects
    if (uiAction === 'download_gazon_checklist') {
      window.SGDownloadGazonChecklist && window.SGDownloadGazonChecklist();
    }

    // Ensure success is visible even for non-modal forms
    overlay.classList.remove('hidden');
    host.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  };

  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.hasAttribute('data-ui-form')) return;
    e.preventDefault();
    handleUiSubmit(form);
  });
}

function initAccordion() {
  document.querySelectorAll('[data-accordion]').forEach((acc) => {
    const items = acc.querySelectorAll('[data-accordion-item]');
    items.forEach((item) => {
      const btn = item.querySelector('[data-accordion-toggle]');
      const panel = item.querySelector('[data-accordion-panel]');
      if (!btn || !panel) return;
      btn.addEventListener('click', () => {
        const expanded = btn.getAttribute('aria-expanded') === 'true';
        // toggle
        btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        panel.classList.toggle('hidden', expanded);
      });
      // default state
      btn.setAttribute('aria-expanded', btn.getAttribute('aria-expanded') || 'false');
    });
  });
}

function initAnimations() {
  const els = Array.from(document.querySelectorAll('[data-animate="fadeInUp"]'));
  if (!els.length) return;

  els.forEach((el) => {
    el.classList.add('opacity-0', 'translate-y-4');
  });

  const obs = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        el.classList.remove('opacity-0', 'translate-y-4');
        el.classList.add('opacity-100', 'translate-y-0');
        el.style.transition = 'opacity 600ms ease, transform 600ms ease';
        obs.unobserve(el);
      });
    },
    { threshold: 0.12 }
  );

  els.forEach((el) => obs.observe(el));
}

function initCounters() {
  const counters = Array.from(document.querySelectorAll('[data-counter-target]'));
  if (!counters.length) return;

  const animate = (el, target) => {
    const duration = 900;
    const start = performance.now();
    const from = 0;

    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const val = Math.round(from + (target - from) * (t * (2 - t)));
      el.textContent = String(val);
      if (t < 1) requestAnimationFrame(step);
    };

    requestAnimationFrame(step);
  };

  const obs = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        const target = Number(el.getAttribute('data-counter-target'));
        if (Number.isNaN(target)) return;
        animate(el, target);
        obs.unobserve(el);
      });
    },
    { threshold: 0.25 }
  );

  counters.forEach((el) => obs.observe(el));
}

/** Слайдер фото тепличного комбината на странице «Питомник». */
function initPitomnikGreenhouseSlider() {
  const root = document.querySelector('[data-pitomnik-greenhouse-slider]');
  if (!root) return;
  const track = root.querySelector('[data-pitomnik-greenhouse-track]');
  if (!track) return;
  const n = track.children.length;
  if (n === 0) return;

  let i = 0;
  const dots = Array.from(root.querySelectorAll('[data-pitomnik-greenhouse-dot]'));
  const prev = root.querySelector('[data-pitomnik-greenhouse-prev]');
  const next = root.querySelector('[data-pitomnik-greenhouse-next]');

  const apply = () => {
    track.style.transform = `translateX(-${i * 100}%)`;
    dots.forEach((btn, j) => {
      const on = j === i;
      btn.setAttribute('data-active', on ? 'true' : 'false');
      btn.setAttribute('aria-selected', on ? 'true' : 'false');
    });
  };

  prev?.addEventListener('click', () => {
    i = (i - 1 + n) % n;
    apply();
  });
  next?.addEventListener('click', () => {
    i = (i + 1) % n;
    apply();
  });
  dots.forEach((btn, j) => {
    btn.addEventListener('click', () => {
      i = j;
      apply();
    });
  });

  apply();
}

/** Мини-слайдеры в карточках ассортимента на странице «Садовые центры». */
function initSadovyeAssortmentSliders() {
  const roots = Array.from(document.querySelectorAll('[data-sadovye-assortment-slider]'));
  if (!roots.length) return;

  roots.forEach((root) => {
    const track = root.querySelector('[data-sadovye-assortment-track]');
    if (!track) return;
    const n = track.children.length;
    if (n === 0) return;

    let i = 0;
    const dots = Array.from(root.querySelectorAll('[data-sadovye-assortment-dot]'));
    const prev = root.querySelector('[data-sadovye-assortment-prev]');
    const next = root.querySelector('[data-sadovye-assortment-next]');

    const apply = () => {
      const slideWidth = root.clientWidth || 0;
      track.style.transform = `translateX(-${i * slideWidth}px)`;
      dots.forEach((btn, j) => {
        const on = j === i;
        btn.setAttribute('data-active', on ? 'true' : 'false');
        btn.setAttribute('aria-selected', on ? 'true' : 'false');
      });
    };

    prev?.addEventListener('click', () => {
      i = (i - 1 + n) % n;
      apply();
    });
    next?.addEventListener('click', () => {
      i = (i + 1) % n;
      apply();
    });
    dots.forEach((btn, j) => {
      btn.addEventListener('click', () => {
        i = j;
        apply();
      });
    });

    window.addEventListener('resize', apply);
    apply();
  });
}

/** Слайдер «Расширенная экспертная помощь» на странице «Служба заботы»: картинка + подпись слева синхронно. */
function initZabotyExpertSlider() {
  const roots = Array.from(document.querySelectorAll('[data-zaboty-expert-slider]'));
  if (!roots.length) return;

  roots.forEach((root) => {
    const viewport = root.querySelector('[data-zaboty-expert-slider-viewport]');
    const track = root.querySelector('[data-zaboty-expert-track]');
    const caption = root.querySelector('[data-zaboty-expert-caption]');
    if (!viewport || !track || !caption) return;

    const slides = Array.from(track.querySelectorAll('[data-zaboty-expert-slide]'));
    const n = slides.length;
    if (n === 0) return;

    let i = 0;
    const dots = Array.from(root.querySelectorAll('[data-zaboty-expert-dot]'));
    const prev = root.querySelector('[data-zaboty-expert-prev]');
    const next = root.querySelector('[data-zaboty-expert-next]');

    const setCaption = () => {
      const text = slides[i]?.getAttribute('data-caption') || '';
      caption.textContent = text;
    };

    const apply = () => {
      const slideWidth = viewport.clientWidth || 0;
      track.style.transform = `translateX(-${i * slideWidth}px)`;
      dots.forEach((btn, j) => {
        const on = j === i;
        btn.setAttribute('data-active', on ? 'true' : 'false');
        btn.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      setCaption();
    };

    prev?.addEventListener('click', () => {
      i = (i - 1 + n) % n;
      apply();
    });
    next?.addEventListener('click', () => {
      i = (i + 1) % n;
      apply();
    });
    dots.forEach((btn, j) => {
      btn.addEventListener('click', () => {
        i = j;
        apply();
      });
    });

    window.addEventListener('resize', apply);
    apply();
  });
}

function initBeforeAfterSliders() {
  const sliders = Array.from(document.querySelectorAll('[data-before-after]'));
  if (!sliders.length) return;

  const clamp = (n) => Math.min(100, Math.max(0, n));

  sliders.forEach((root) => {
    const range = root.querySelector('[data-before-after-range]');
    const overlay = root.querySelector('[data-before-after-overlay]');
    const divider = root.querySelector('[data-before-after-divider]');
    const handle = root.querySelector('[data-before-after-handle]');
    if (!range || !overlay || !divider || !handle) return;

    const update = (value) => {
      const pct = clamp(Number(value));
      overlay.style.clipPath = `inset(0 ${100 - pct}% 0 0)`;
      divider.style.left = `${pct}%`;
      handle.style.left = `${pct}%`;
      range.value = String(pct);
    };

    const start = Number(root.getAttribute('data-before-after-start') || range.value || 50);
    update(start);
    range.addEventListener('input', () => update(range.value));
    range.addEventListener('change', () => update(range.value));
  });
}

/** @param {HTMLFormElement | null | undefined} modalFormFromModal — форма из открытого окна (не из &lt;template&gt;) */
function initGazonCalculator(modalFormFromModal) {
  const inlineForm = document.getElementById('gazonCalculator');
  let modalForm = modalFormFromModal || null;
  if (!modalForm) {
    const m = document.getElementById('gazonCalculatorModal');
    // Не инициализировать копию внутри <template> (иначе слушатели input висят на скрытом DOM)
    if (m && !m.closest('template')) modalForm = m;
  }
  if (!inlineForm && !modalForm) return;

  /** Прайс-лист 2026 (с НДС 5%): только объём м²; регион и формат поставки на цену не влияют */
  const gazonPricePerM2 = (a) => {
    if (!a || Number.isNaN(a) || a <= 0) return null;
    if (a >= 2500) return 540;
    if (a > 1000) return 575;
    if (a > 500) return 585;
    return 590;
  };

  const CALC_DISCLAIMER =
    'Это ориентировочный расчет. Точная стоимость зависит от объема, региона и условий поставки.';

  const formatRu = (n) => new Intl.NumberFormat('ru-RU').format(Math.round(n));

  const calculate = (area, outTotal, outPer, outNote, onCalculated) => {
    const a = Number(area.value);
    const per = gazonPricePerM2(a);
    if (per == null) return;

    const total = per * a;

    outPer.textContent = `${formatRu(per)} ₽`;
    outTotal.textContent = `${formatRu(total)} ₽`;
    if (outNote) outNote.textContent = CALC_DISCLAIMER;

    if (onCalculated) onCalculated();
  };

  if (inlineForm) {
    const area = document.getElementById('calcArea');
    const region = document.getElementById('calcRegion');
    const format = document.getElementById('calcFormat');
    const outTotal = document.getElementById('calcTotal');
    const outPer = document.getElementById('calcPerM2');
    const outNote = document.getElementById('calcNote');
    if (!area || !region || !format || !outTotal || !outPer || !outNote) return;

    if (inlineForm.dataset.boundInline === '1') return;
    inlineForm.dataset.boundInline = '1';

    const onCalc = () => calculate(area, outTotal, outPer, outNote);

    ['input', 'change'].forEach((evt) => {
      area.addEventListener(evt, onCalc);
      region.addEventListener(evt, onCalc);
      format.addEventListener(evt, onCalc);
    });

    inlineForm.addEventListener('submit', (e) => {
      e.preventDefault();
      onCalc();
    });
  }

  if (modalForm) {
    const area = modalForm.querySelector('#modalCalcArea');
    const region = modalForm.querySelector('#modalCalcRegion');
    const format = modalForm.querySelector('#modalCalcFormat');
    const outTotal = modalForm.querySelector('#modalCalcTotal');
    const outPer = modalForm.querySelector('#modalCalcPerM2');
    const outNote = modalForm.querySelector('#modalCalcNote');
    const calcBtn = modalForm.querySelector('#modalCalcBtn');
    const resultBlock = modalForm.querySelector('#modalCalcResultBlock');
    if (!area || !region || !format || !outTotal || !outPer || !calcBtn) return;

    const resetModalCalc = () => {
      outPer.textContent = '—';
      outTotal.textContent = '—';
      if (outNote) outNote.textContent = '';
      if (resultBlock) resultBlock.classList.add('hidden');
    };

    resetModalCalc();

    const onCalc = () => {
      calculate(area, outTotal, outPer, outNote, () => {
        if (resultBlock) resultBlock.classList.remove('hidden');
      });
    };

    calcBtn.addEventListener('click', (e) => {
      e.preventDefault();
      onCalc();
    });

    modalForm.addEventListener('submit', (e) => {
      e.preventDefault();
      e.stopPropagation();
      onCalc();
    });
  }
}

/** Карта на странице «Контакты»: три метки (API 2.1). Координаты фиксированы (OSM), без геокодера —
 *  на GitHub Pages геокодер Яндекса часто даёт пустой ответ или «левые» точки при тех же запросах, что на localhost. */
function initContactsYandexMap() {
  const el = document.getElementById('contactsYandexMap');
  if (!el) return;
  if (el.dataset.sgContactsMap === '1') return;
  el.dataset.sgContactsMap = '1';

  const apiKey = (
    (typeof window.SG_YANDEX_MAPS_API_KEY === 'string' && window.SG_YANDEX_MAPS_API_KEY) ||
    el.getAttribute('data-yandex-maps-key') ||
    ''
  ).trim();

  // [широта, долгота] WGS84 — проверено по OpenStreetMap (здание / ТЦ / центр села)
  const places = [
    {
      title: 'Главный офис',
      address: 'г. Новосибирск, ул. Железнодорожная, 12/1, оф.501',
      coords: [55.0453816, 82.9017817],
    },
    {
      title: 'Садовый центр №1',
      address: 'г. Новосибирск, ул. Ватутина, 107, СЦ Мега',
      coords: [54.9642844, 82.9362306],
    },
    {
      title: 'Садовый центр №2',
      address: 'с. Новопичугово, ориентир ул. Сосновая, СЦ Новопичугово',
      coords: [54.61031, 82.34969],
    },
  ];

  const showFallback = () => {
    el.className =
      'flex h-56 min-h-[14rem] w-full items-center justify-center bg-slate-100 px-6 text-center text-sm text-slate-600 md:h-80';
    el.textContent = 'Карту не удалось загрузить. Адреса указаны в блоке слева.';
  };

  const loadYandexScript = () =>
    new Promise((resolve, reject) => {
      if (window.ymaps) {
        window.ymaps.ready(() => resolve());
        return;
      }
      const s = document.createElement('script');
      const keyPart = apiKey ? `&apikey=${encodeURIComponent(apiKey)}` : '';
      s.src = `https://api-maps.yandex.ru/2.1/?lang=ru_RU${keyPart}`;
      s.async = true;
      s.onload = () => {
        if (!window.ymaps) {
          reject(new Error('ymaps'));
          return;
        }
        window.ymaps.ready(() => resolve());
      };
      s.onerror = () => reject(new Error('load'));
      document.head.appendChild(s);
    });

  loadYandexScript()
    .then(() => {
      const { ymaps } = window;
      const map = new ymaps.Map(
        el,
        {
          center: [55.03, 82.95],
          zoom: 9,
          controls: ['zoomControl', 'typeSelector'],
        },
        { suppressMapOpenBlock: true }
      );

      const collection = new ymaps.GeoObjectCollection();
      places.forEach((p) => {
        collection.add(
          new ymaps.Placemark(
            p.coords,
            {
              balloonContentHeader: p.title,
              balloonContentBody: p.address,
            },
            { preset: 'islands#greenIcon' }
          )
        );
      });
      map.geoObjects.add(collection);
      const bounds = collection.getBounds();
      if (bounds) {
        map.setBounds(bounds, { checkZoomRange: true, zoomMargin: 48 });
      }
    })
    .catch(() => showFallback());
}

document.addEventListener('DOMContentLoaded', () => {
  initYear();
  initViewportHeroHeights();
  initHomeHeroVideo();
  initGazonHeroVideo();
  initB2bHeroVideo();
  initBurger();
  initModal();
  // Auto-open gazon calculator from URL: /gazon/?calc=1
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get('calc') === '1' && window.SGOpenModal) {
      window.SGOpenModal('gazon_calc', 'Рассчитать стоимость');
    }
  } catch (e) {
    // ignore
  }
  initAccordion();
  initAnimations();
  initCounters();
  initBeforeAfterSliders();
  initPitomnikGreenhouseSlider();
  initSadovyeAssortmentSliders();
  initZabotyExpertSlider();
  initGazonCalculator();
  initContactsYandexMap();
  initConsentCheckboxes();
  initCookieBanner();
});

