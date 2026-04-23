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
  const sizeWrap = host.firstElementChild;
  const modalCard = sizeWrap && sizeWrap.firstElementChild;
  let activeNoOverlay = false;
  let titleFxStyleReady = false;

  const templateMap = {
    'mini_brief': 'modal-template-mini_brief',
    'home_private_choice': 'modal-template-home_private_choice',
    'home_b2b_choice': 'modal-template-home_b2b_choice',
    'home_private_buy': 'modal-template-home_private_buy',
    'home_b2b_buy': 'modal-template-home_b2b_buy',
    'home_b2b_project': 'modal-template-home_b2b_project',
    'contact_zaboty': 'modal-template-contact_zaboty',
    'contact_zaboty_calendar': 'modal-template-contact_zaboty_calendar',
    'zaboty_expert_visit': 'modal-template-zaboty_expert_visit',
    'contact_consult': 'modal-template-contact_consult',
    'catalog_actual_stock': 'modal-template-catalog_actual_stock',
    'catalog_electronic_catalog': 'modal-template-catalog_electronic_catalog',
    'b2b_cpo': 'modal-template-b2b_cpo',
    'b2b_price_stock': 'modal-template-b2b_price_stock',
    'b2b_project_calc': 'modal-template-b2b_project_calc',
    'b2b_care_reglement': 'modal-template-b2b_care_reglement',
    'gazon_price_list': 'modal-template-gazon_price_list',
    'gazon_factory_open_day': 'modal-template-pitomnik_open_day_signup',
    'gazon_cpo': 'modal-template-gazon_cpo',
    'gazon_checklist': 'modal-template-gazon_checklist',
    'gazon_open_day': 'modal-template-gazon_open_day',
    'home_gazon_excursion': 'modal-template-home_gazon_excursion',
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
    'pitomnik_open_day_signup': 'modal-template-pitomnik_open_day_signup',
    'sadovye_digital_card': 'modal-template-sadovye_digital_card',
    'sadovye_novinki_notify': 'modal-template-sadovye_novinki_notify',
    'sadovye_novinka_1': 'modal-template-sadovye_novinka_1',
    'sadovye_novinka_2': 'modal-template-sadovye_novinka_2',
    'sadovye_novinka_3': 'modal-template-sadovye_novinka_3',
    'sadovye_novinka_4': 'modal-template-sadovye_novinka_4',
  };

  const initConsentGate = (root) => {
    const forms = Array.from(root.querySelectorAll('form'));
    forms.forEach((form) => {
      const checkbox = form.querySelector('[data-consent-checkbox]');
      const submitBtn = form.querySelector('[data-consent-submit]');
      if (!checkbox || !submitBtn) return;
      if (form.dataset.consentBound === '1') return;
      form.dataset.consentBound = '1';

      const syncState = () => {
        submitBtn.disabled = !checkbox.checked;
      };

      checkbox.addEventListener('change', syncState);
      syncState();
    });
  };

  const ensureModalTitleFx = () => {
    if (titleFxStyleReady || document.getElementById('sg-modal-title-fx')) return;
    const st = document.createElement('style');
    st.id = 'sg-modal-title-fx';
    st.textContent =
      '.sg-modal-title-arrow{display:inline-block;animation:sg-modal-arrow-bob 1.2s ease-in-out infinite;}' +
      '@keyframes sg-modal-arrow-bob{0%,100%{transform:translateX(0)}50%{transform:translateX(3px)}}';
    document.head.appendChild(st);
    titleFxStyleReady = true;
  };

  const escapeTitleHtml = (text) =>
    String(text || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');

  const setModalTitle = (title) => {
    const t = String(title || '');
    if (!t.includes('→')) {
      modalTitle.textContent = t;
      return;
    }
    ensureModalTitleFx();
    const i = t.indexOf('→');
    const left = escapeTitleHtml(t.slice(0, i));
    const right = escapeTitleHtml(t.slice(i + 1));
    modalTitle.innerHTML = `${left}<span class="sg-modal-title-arrow" aria-hidden="true">→</span>${right}`;
  };

  const renderSelectionModalPreview = (root, names) => {
    if (!root || !Array.isArray(names) || !names.length) return;
    const wrap = document.createElement('div');
    wrap.className = 'mb-4 rounded-2xl border border-brand/20 bg-brand/5 p-3';
    const title = document.createElement('div');
    title.className = 'text-xs font-semibold uppercase tracking-wide text-brand';
    title.textContent = 'Вы выбрали:';
    const chips = document.createElement('div');
    chips.className = 'mt-2 flex max-h-28 flex-wrap gap-2 overflow-y-auto pr-1';
    names.forEach((n) => {
      const chip = document.createElement('span');
      chip.className = 'inline-flex items-center rounded-full border border-brand/25 bg-white px-2.5 py-1 text-xs font-medium text-slate-700';
      chip.textContent = n;
      chips.appendChild(chip);
    });
    wrap.appendChild(title);
    wrap.appendChild(chips);
    root.insertBefore(wrap, root.firstChild);
  };

  const openModal = (targetKey, title, options) => {
    const opts = options || {};
    const tplId = templateMap[targetKey];
    if (!tplId) {
      console.warn('[SG modal] Неизвестный data-open-modal:', targetKey);
      return;
    }
    const tpl = document.getElementById(tplId);
    if (!tpl) {
      console.warn('[SG modal] Нет элемента #', tplId);
      return;
    }

    if (sizeWrap) {
      sizeWrap.classList.remove('max-w-lg', 'max-w-2xl');
      const wide =
        targetKey === 'ozelenenie_mini_project' ||
        targetKey === 'gazon_calc' ||
        targetKey === 'b2b_project_calc' ||
        targetKey === 'catalog_actual_stock' ||
        targetKey === 'pitomnik_open_day_signup' ||
        targetKey === 'gazon_factory_open_day' ||
        targetKey === 'sadovye_novinka_1' ||
        targetKey === 'sadovye_novinka_2' ||
        targetKey === 'sadovye_novinka_3' ||
        targetKey === 'sadovye_novinka_4';
      sizeWrap.classList.add(wide ? 'max-w-2xl' : 'max-w-lg');
    }

    if (host) {
      host.classList.toggle('backdrop-blur-[2px]', Boolean(opts.noOverlay));
      host.classList.toggle('bg-white/20', Boolean(opts.noOverlay));
    }
    if (modalCard) {
      modalCard.classList.toggle('border-brand/35', Boolean(opts.noOverlay));
      modalCard.classList.toggle('bg-white/95', Boolean(opts.noOverlay));
      modalCard.classList.toggle('shadow-[0_30px_80px_-30px_rgba(15,23,42,0.65)]', Boolean(opts.noOverlay));
    }

    setModalTitle(title || '');
    modalBody.innerHTML = '';
    modalBody.appendChild(tpl.content.cloneNode(true));
    bindOpenModalButtons(modalBody);
    renderSelectionModalPreview(modalBody, opts.selectionNames);
    if (window.lucide) window.lucide.createIcons();

    // Inject modal title as hidden field so it reaches B24 lead COMMENTS
    const modalContext = opts.contextTitle || title;
    if (modalContext) {
      const mForm = modalBody.querySelector('form[data-ui-form]');
      if (mForm) {
        const h = document.createElement('input');
        h.type = 'hidden';
        h.name = 'modalContext';
        h.value = modalContext;
        mForm.appendChild(h);
      }
    }

    initConsentGate(modalBody);

    // Inject consent checkbox into freshly cloned modal form
    const modalForm = modalBody.querySelector('form[data-ui-form]');
    if (modalForm && !modalForm.querySelector('[name="consent"]')) {
      initConsentCheckboxes();
    }

    activeNoOverlay = Boolean(opts.noOverlay);
    if (activeNoOverlay) {
      overlay.classList.add('hidden');
    } else {
      overlay.classList.remove('hidden');
    }
    host.classList.remove('hidden');
    host.classList.add('modal-enter');
    document.body.style.overflow = activeNoOverlay ? '' : 'hidden';
  };

  // Make it accessible for auto-open based on URL params.
  window.SGOpenModal = openModal;

  const closeModal = () => {
    overlay.classList.add('hidden');
    host.classList.add('hidden');
    host.classList.remove('modal-enter');
    activeNoOverlay = false;
    host.classList.remove('backdrop-blur-[2px]', 'bg-white/20');
    if (modalCard) {
      modalCard.classList.remove('border-brand/35', 'bg-white/95', 'shadow-[0_30px_80px_-30px_rgba(15,23,42,0.65)]');
    }
    document.body.style.overflow = '';
  };

  closeTop.addEventListener('click', closeModal);
  overlay.addEventListener('click', closeModal);
  document.addEventListener('click', (e) => {
    const closeBtn = e.target && e.target.closest('[data-close-modal]');
    if (closeBtn) closeModal();
  });

  const handleOpenModalButton = (btn, e) => {
    const key = btn.getAttribute('data-open-modal');
    if (!key) return;
    if (e) e.preventDefault();
    const title = btn.getAttribute('data-modal-title') || '';
    const noOverlay = btn.getAttribute('data-modal-no-overlay') === '1';
    const contextTitle = btn.getAttribute('data-modal-context') || title;
    let selectionNames = [];
    try {
      const rawNames = btn.getAttribute('data-modal-selection-names');
      const parsed = rawNames ? JSON.parse(rawNames) : [];
      selectionNames = Array.isArray(parsed) ? parsed.map((x) => String(x || '').trim()).filter(Boolean) : [];
    } catch (err) {
      selectionNames = [];
    }
    openModal(key, title, { noOverlay, contextTitle, selectionNames });
  };

  const bindOpenModalButtons = (root) => {
    const scope = root || document;
    scope.querySelectorAll('[data-open-modal]').forEach((btn) => {
      if (btn.dataset.modalBound === '1') return;
      btn.dataset.modalBound = '1';
      btn.addEventListener('click', (e) => {
        handleOpenModalButton(btn, e);
      });
    });
  };

  bindOpenModalButtons(document);

  // Fallback delegation for any late-inserted elements.
  document.addEventListener('click', (e) => {
    const btn = e.target && e.target.closest('[data-open-modal]');
    if (!btn) return;
    handleOpenModalButton(btn, e);
  });

  // Fallback binding for stubborn overlap/click issues on care page CTA.
  const zabotyCalendarCta = document.getElementById('zabotyCalendarCta');
  if (zabotyCalendarCta && zabotyCalendarCta.dataset.boundDirectModal !== '1') {
    zabotyCalendarCta.dataset.boundDirectModal = '1';
    zabotyCalendarCta.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openModal('contact_zaboty_calendar', 'Получать календарь сезонных работ');
    });
  }

  // ── Bitrix24 lead capture ──
  const B24_WEBHOOK = 'https://sgpichugi.bitrix24.ru/rest/1339/6y8mhtwuvyc4du94';

  // Human-readable form titles for Bitrix24 TITLE field
  const FORM_TITLES = {
    'request': 'Обращение с сайта',
    'mini-brief': 'Мини-бриф',
    'sluzhba-zaboty': 'Служба заботы',
    'sluzhba-zaboty-calendar': 'Календарь сезонных работ',
    'zaboty-expert-vyezd': 'Выезд специалиста (экспертная помощь)',
    'consultation': 'Консультация',
    'sadovye-novinki-notify': 'Уведомление о новинках',
    'contract-request': 'Запрос КП (B2B)',
    'project-calc': 'Расчёт проекта (B2B)',
    'price-stock': 'Прайс и наличие (B2B)',
    'reglement-uhoda': 'Регламент ухода (B2B)',
    'gazon-price-list': 'Прайс-лист газон',
    'gazon-cpo': 'КП на газон',
    'gazon-checklist': 'Чек-лист газон',
    'gazon-open-day': 'День открытых дверей',
    'gazon-logistics': 'Логистика газон',
    'gazon-presentation': 'Презентация газон',
    'gazon-calc': 'Калькулятор газона',
    'home-gazon-excursion': 'Экскурсия на рулонный газон',
    'home-private-buy': 'Покупка продукции (частные лица)',
    'home-b2b-buy': 'Покупка продукции (B2B)',
    'home-project-calc': 'Просчет проекта (B2B)',
    'ozelenenie-ready-project': 'Готовый проект озеленения',
    'mini-project': 'Мини-проект озеленения',
    'ozelenenie-audit-plan': 'Аудит участка',
    'ozelenenie-assess-upload': 'Оценка участка (фото)',
    'ozelenenie-send-project': 'Проверка проекта',
    'ozelenenie-materials-scheme': 'Подбор материалов и схема',
    'pitomnik-presentation': 'Презентация питомника',
    'pitomnik-open-day-signup': 'Запись на день открытых дверей (Питомник)',
    'digital-card': 'Цифровая карта',
    'assortment-interest': 'Запрос по ассортименту (каталог)',
  };

  // Labels for COMMENTS fields
  const FIELD_LABELS = {
    objectType: 'Тип объекта',
    area: 'Площадь, м²',
    region: 'Регион',
    topic: 'Тема',
    openDayVisitDate: 'Дата посещения',
    guestsCount: 'Количество участников',
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
    productType: 'Выбор продукции',
    address: 'Адрес',
    residentialComplex: 'Название ЖК',
    projectFile: 'Файл проекта',
    interest_vegetable_seedlings: 'Овощная рассада',
    interest_annual_seedlings: 'Однолетняя рассада',
    interest_perennials: 'Многолетние цветы',
    interest_shrubs: 'Кустарники',
    interest_trees: 'Деревья',
    modalContext: 'Запрос',
    open_day_greenhouse: '15 мая (тепличный комбинат)',
    open_day_kirza: '10 июня (питомник "Кирза")',
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
    private_person: 'Частное лицо',
    landscape_designer: 'Ландшафтный дизайнер',
    developer_company: 'Застройщик / компания',
    '15_may_2026_greenhouse': '15 мая 2026 - Тепличный комбинат (Новопичугово)',
    '10_june_2026_gazon_kirza': '10 июня 2026 - Рулонный газон (Новопичугово) + Питомник (Кирза)',
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

    var leadTitle = FORM_TITLES[formName] || formName;
    if (payload.modalContext) leadTitle += ' — ' + payload.modalContext;

    const fields = {
      TITLE: `Сайт: ${leadTitle}`,
      SOURCE_ID: '9',
      ASSIGNED_BY_ID: 1317,
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
      if (v instanceof File) {
        if (!v.name) continue;
        payload[k] = v.name;
        continue;
      }
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
    if (activeNoOverlay) {
      overlay.classList.add('hidden');
      host.classList.add('backdrop-blur-[2px]', 'bg-white/20');
      if (modalCard) {
        modalCard.classList.add('border-brand/35', 'bg-white/95', 'shadow-[0_30px_80px_-30px_rgba(15,23,42,0.65)]');
      }
    } else {
      overlay.classList.remove('hidden');
      host.classList.remove('backdrop-blur-[2px]', 'bg-white/20');
      if (modalCard) {
        modalCard.classList.remove('border-brand/35', 'bg-white/95', 'shadow-[0_30px_80px_-30px_rgba(15,23,42,0.65)]');
      }
    }
    host.classList.remove('hidden');
    document.body.style.overflow = activeNoOverlay ? '' : 'hidden';
  };

  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.hasAttribute('data-ui-form')) return;
    e.preventDefault();
    handleUiSubmit(form);
  });
}

/**
 * Страницы раздела каталога (шаблон с #catalog-category-main): на мобильных
 * после выбора раздела/подраздела плавно прокручиваем к карточкам.
 * На десктопе не вмешиваемся.
 */
function initCatalogCategoryMobileAutoScroll() {
  const main = document.getElementById('catalog-category-main');
  if (!main) return;

  const mqMobile = window.matchMedia('(max-width: 1023px)');
  const mqReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const STORAGE_KEY = 'sg_catalog_mobile_scroll_to_main_v1';

  const aside = main.previousElementSibling;
  if (!(aside instanceof HTMLElement)) return;
  const navCard = aside.querySelector('[data-catalog-nav-card]');
  if (!(navCard instanceof HTMLElement)) return;

  const scrollMainIntoView = () => {
    if (!mqMobile.matches) return;
    main.scrollIntoView({
      behavior: mqReduce.matches ? 'auto' : 'smooth',
      block: 'start',
    });
  };

  const normalize = (url) => `${url.pathname.replace(/\/+$/, '') || '/'}?${url.searchParams.toString()}`;
  const currentUrl = new URL(window.location.href);

  try {
    if (mqMobile.matches && window.sessionStorage.getItem(STORAGE_KEY) === '1') {
      window.sessionStorage.removeItem(STORAGE_KEY);
      window.requestAnimationFrame(() => {
        window.setTimeout(scrollMainIntoView, 120);
      });
    }
  } catch (e) {
    // ignore
  }

  navCard.addEventListener('click', (e) => {
    const link = e.target.closest('a[href]');
    if (!(link instanceof HTMLAnchorElement)) return;
    if (!mqMobile.matches) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    let targetUrl = null;
    try {
      targetUrl = new URL(link.href, window.location.href);
    } catch (err) {
      return;
    }
    if (targetUrl.origin !== window.location.origin) return;

    const isSamePage = normalize(targetUrl) === normalize(currentUrl);
    if (isSamePage) {
      e.preventDefault();
      scrollMainIntoView();
      return;
    }

    try {
      window.sessionStorage.setItem(STORAGE_KEY, '1');
    } catch (err) {
      // ignore
    }
  });

  // Кнопка "Подробнее" в карточках раздела: после перехода на карточку
  // прокрутить мобильный экран ниже блока навигации к контенту карточки.
  main.querySelectorAll('a[data-catalog-more][href]').forEach((link) => {
    link.addEventListener('click', (e) => {
      if (!mqMobile.matches) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      try {
        const targetUrl = new URL(link.href, window.location.href);
        if (targetUrl.origin !== window.location.origin) return;
        window.sessionStorage.setItem(STORAGE_KEY, '1');
      } catch (err) {
        // ignore
      }
    });
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

function initGazonCalculator() {
  const inlineForm = document.getElementById('gazonCalculator');
  if (!inlineForm) return;

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

/** Карточка товара: варианты высота + контейнер → цена и наличие (data-plant-variant-picker). */
function initPlantVariantPicker() {
  const root = document.querySelector('[data-plant-variant-picker]');
  if (!root) return;
  const jsonEl = document.getElementById('plant-variants-json');
  if (!jsonEl || !jsonEl.textContent) return;
  let variants;
  try {
    variants = JSON.parse(jsonEl.textContent);
  } catch (e) {
    return;
  }
  if (!Array.isArray(variants) || variants.length === 0) return;
  const normalizeHeightLabel = (v) => {
    const s = String(v || '').trim();
    return /^уточняйте$/i.test(s) ? 'фиксированная' : s;
  };
  const normalizeContainerLabel = (v) => {
    const s = String(v || '').trim();
    if (s === 'кассета 6 ячеек' || s === 'кассета из 6 ячеек') return s;
    if (s === 'кассета из 4 ячеек' || s === 'кассета 4 ячеек') return s;
    if (/^формат\s+уточняйте$/i.test(s) || /^уточняйте$/i.test(s)) return 'формат фиксированный';
    return s;
  };
  variants = variants.map((x) => ({
    ...x,
    height: normalizeHeightLabel(x && x.height),
    container: normalizeContainerLabel(x && x.container),
  }));

  const selH = root.querySelector('[data-pv-height]');
  const selC = root.querySelector('[data-pv-container]');
  const priceEl = root.querySelector('[data-pv-price]');
  const hintEl = root.querySelector('[data-pv-stock-hint]');
  const badgeEl = root.querySelector('[data-pv-stock-badge]');
  const productName = root.getAttribute('data-product-name') || '';

  if (!root.dataset.pvInquiryStockBound) {
    root.dataset.pvInquiryStockBound = '1';
    root.addEventListener('click', (e) => {
      const link = e.target && e.target.closest('[data-pv-inquiry-stock]');
      if (!link) return;
      e.preventDefault();
      const selBtn = root.querySelector('[data-pv-sync-selection-button="1"]');
      if (selBtn && typeof window.SGOpenPodborInquiryFromButton === 'function') {
        window.SGOpenPodborInquiryFromButton(selBtn);
      }
    });
  }

  if (!selH || !selC || !priceEl) return;

  const uniq = (arr) => [...new Set(arr)];

  function fillSel(sel, values) {
    sel.innerHTML = '';
    values.forEach((v) => {
      const o = document.createElement('option');
      o.value = v;
      o.textContent = v;
      sel.appendChild(o);
    });
  }

  function variantsForHeight(h) {
    return variants.filter((x) => x.height === h);
  }

  function findVariant(h, c) {
    return variants.find((x) => x.height === h && x.container === c);
  }

  function refreshContainerOptions() {
    const h = selH.value;
    const list = variantsForHeight(h);
    const conts = uniq(list.map((x) => x.container));
    const fallback = uniq(variants.map((x) => x.container));
    fillSel(selC, conts.length ? conts : fallback);
    if (conts.length && !conts.includes(selC.value)) {
      selC.value = conts[0];
    }
  }

  function applyVariant(v) {
    if (!v) return;
    priceEl.textContent = v.price;
    const stock = Boolean(v.in_stock);
    if (hintEl) {
      hintEl.textContent = stock
        ? 'В продаже (точное наличие — по запросу).'
        : 'Этого формата сейчас нет в наличии; спросите о поступлении.';
      hintEl.className = stock ? 'mt-2 text-sm text-slate-600' : 'mt-2 text-sm font-medium text-slate-500';
    }
    if (badgeEl) {
      if (stock) {
        badgeEl.innerHTML =
          'Наличие:&nbsp;<a href="#" class="underline decoration-brand/40 underline-offset-2 hover:text-brand2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand/35 rounded-sm" data-pv-inquiry-stock aria-label="Открыть форму уточнения наличия для выбранного варианта">уточнить</a>';
        badgeEl.className =
          'rounded-2xl border border-black/5 bg-brand/10 px-4 py-2 text-sm font-semibold text-brand min-h-[2.75rem] flex items-center';
      } else {
        badgeEl.textContent = 'Нет в наличии';
        badgeEl.className =
          'rounded-2xl border border-black/10 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-500 min-h-[2.75rem] flex items-center';
      }
    }

    const detail = `${v.height}, ${v.container}`;
    const selectionBtn = root.querySelector('[data-pv-sync-selection-button="1"]');
    if (selectionBtn) {
      selectionBtn.setAttribute('data-selection-variant', detail);
      selectionBtn.setAttribute('data-selection-price', v.price || '');
      selectionBtn.setAttribute('data-selection-id', `${selectionBtn.getAttribute('data-selection-id') || productName}-${detail}`);
    }
  }

  fillSel(selH, uniq(variants.map((x) => x.height)));
  if (!selH.options.length) return;
  if (!selH.value) selH.value = selH.options[0].value;
  refreshContainerOptions();

  selH.addEventListener('change', () => {
    refreshContainerOptions();
    const v = findVariant(selH.value, selC.value);
    if (v) applyVariant(v);
  });
  selC.addEventListener('change', () => {
    const v = findVariant(selH.value, selC.value);
    if (v) applyVariant(v);
  });

  applyVariant(findVariant(selH.value, selC.value) || variants[0]);
}

const SG_SELECTION_ADD_ANIM_MS = 800;
const SG_SELECTION_PULSE_MS = 200;

function ensureSelectionAddEffectStyles() {
  if (document.getElementById('sg-selection-add-fx')) return;
  const st = document.createElement('style');
  st.id = 'sg-selection-add-fx';
  st.textContent =
    '.sg-selection-pulse{animation:sg-selection-pulse-anim ' +
    SG_SELECTION_PULSE_MS +
    'ms ease-in-out}' +
    '@keyframes sg-selection-pulse-anim{0%{transform:scale(1)}50%{transform:scale(1.08)}100%{transform:scale(1)}}' +
    '.sg-selection-flash-layer{position:absolute;inset:0;border-radius:inherit;pointer-events:none;z-index:0;opacity:0;' +
    'background:linear-gradient(135deg,#fff 0%,#fef9c3 42%,#fde68a 100%)}' +
    '.sg-selection-flash-layer.sg-selection-flash-on{animation:sg-selection-flash-anim .24s ease-out forwards}' +
    '@keyframes sg-selection-flash-anim{0%{opacity:.88}55%{opacity:.45}100%{opacity:0}}' +
    '.sg-selection-petal{position:absolute;left:50%;top:50%;width:7px;height:11px;margin-left:-3.5px;margin-top:-5.5px;' +
    'border-radius:50% 50% 50% 50%/65% 65% 35% 35%;' +
    'background:radial-gradient(circle at 30% 25%,#fecdd3 0%,#e11d48 42%,#9f1239 88%);' +
    'box-shadow:0 0 2px rgba(190,18,60,.35);transform-origin:50% 85%;pointer-events:none;z-index:2;opacity:1;' +
    'animation:sg-selection-petal-burst .8s cubic-bezier(.22,1,.36,1) forwards}' +
    '@keyframes sg-selection-petal-burst{0%{transform:translate3d(0,0,0) rotate(var(--sg-p-r,0deg)) scale(1);opacity:1}' +
    '100%{transform:translate3d(var(--sg-tx,0),var(--sg-ty,0),0) rotate(calc(var(--sg-p-r,0deg) + 28deg)) scale(.15);opacity:0}}' +
    '@media (prefers-reduced-motion:reduce){.sg-selection-pulse{animation:none}' +
    '.sg-selection-petal{animation-duration:.01ms!important;opacity:0!important}' +
    '.sg-selection-flash-layer.sg-selection-flash-on{animation-duration:.01ms!important}}';
  document.head.appendChild(st);
}

function ensureSelectionButtonLabel(btn) {
  let label = btn.querySelector('[data-selection-label]');
  if (label) return label;
  const text = (btn.textContent || '').replace(/\s+/g, ' ').trim() || 'Добавить в подбор';
  btn.textContent = '';
  label = document.createElement('span');
  label.setAttribute('data-selection-label', '');
  label.className = 'relative z-[1] inline-block';
  label.textContent = text;
  btn.appendChild(label);
  return label;
}

function playSelectionAddedBurst(btn) {
  ensureSelectionAddEffectStyles();
  btn.classList.add('sg-selection-pulse');
  window.setTimeout(() => btn.classList.remove('sg-selection-pulse'), SG_SELECTION_PULSE_MS);

  const flash = document.createElement('span');
  flash.className = 'sg-selection-flash-layer';
  flash.setAttribute('aria-hidden', 'true');
  btn.insertBefore(flash, btn.firstChild);
  window.requestAnimationFrame(() => flash.classList.add('sg-selection-flash-on'));
  window.setTimeout(() => flash.remove(), 400);

  const reduce =
    typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const count = reduce ? 0 : 14;
  const petals = [];
  for (let i = 0; i < count; i += 1) {
    const petal = document.createElement('span');
    petal.className = 'sg-selection-petal';
    const spread = -1.12 + (i / Math.max(1, count - 1)) * 2.24;
    const angle = -Math.PI / 2 + spread * 0.58 + (Math.random() - 0.5) * 0.28;
    const dist = 50 + Math.random() * 52;
    const tx = Math.cos(angle) * dist;
    const ty = Math.sin(angle) * dist;
    const rot = ((i * 23 + Math.random() * 55) % 360) - 48;
    petal.style.setProperty('--sg-tx', `${tx.toFixed(1)}px`);
    petal.style.setProperty('--sg-ty', `${ty.toFixed(1)}px`);
    petal.style.setProperty('--sg-p-r', `${rot.toFixed(1)}deg`);
    btn.appendChild(petal);
    petals.push(petal);
  }
  window.setTimeout(() => {
    petals.forEach((p) => p.remove());
  }, 820);
}

/**
 * Название для блока «Подбор»: короче и без «ломаного» текста.
 * 1) Убираем латинские/английские сорта в ASCII/типографских кавычках "…" / "…"
 *    (русские названия в «ёлочках» не трогаем).
 * 2) Если есть кириллица — отрезаем хвост латинского рода/вида (Cineraria maritima …).
 * 3) Снимаем висячие кавычки после обрезки (баг «Роза … "»).
 */
function selectionDisplayNameForPodbor(name) {
  const raw = String(name || '').trim();
  let s = raw.replace(/\s+/g, ' ').trim();
  if (!s) return s;

  const countLat = (t) => (t.match(/[A-Za-z]/g) || []).length;
  const countCyr = (t) => (t.match(/[\u0400-\u04FF]/g) || []).length;

  const stripLatinInAsciiQuotes = (str) => {
    let out = str;
    let prev;
    do {
      prev = out;
      out = out.replace(/\s*["\u201c\u201d]([^"\u201c\u201d]*?)["\u201c\u201d]\s*/g, (full, inner) => {
        const t = inner.trim();
        if (!t) return ' ';
        const lat = countLat(t);
        const cyr = countCyr(t);
        if (lat === 0) return full;
        if (cyr > 0 && cyr >= lat) return full;
        if (lat >= 2 && lat >= cyr) return ' ';
        if (cyr === 0 && lat >= 1) return ' ';
        return full;
      });
      out = out.replace(/\s+/g, ' ').trim();
    } while (out !== prev);
    return out;
  };

  s = stripLatinInAsciiQuotes(s);
  if (!s) return raw;

  if (/[\u0400-\u04FF]/.test(s)) {
    // Не отрезать «…" Hosta (ML)» по первому латинскому слову — иначе теряется (ML) С2/3;
    // латиница сразу после закрывающей " / типографской кавычки не считаем хвостом бинома.
    const re = /\s+[A-Z][a-z]{2,}\b/g;
    let idx = -1;
    let match = null;
    while ((match = re.exec(s))) {
      const prevChar = s[match.index - 1] || '';
      if (!/[\u0022\u201c\u201d]/.test(prevChar)) {
        idx = match.index;
        break;
      }
    }
    if (idx !== -1) s = s.slice(0, idx).trim();
    // Дублирующее латинское имя рода перед скобкой: … "Frances" … Hosta (ML)
    s = s.replace(/\s+[A-Z][a-z]{2,}\b(?=\s*\()/g, ' ').replace(/\s+/g, ' ').trim();
  }

  s = s
    .replace(/^[\s"'„“‚‘\u201c\u201d\u201e]+/g, '')
    .replace(/[\s"'„“‚‘\u201c\u201d\u201e]+$/g, '')
    .trim();
  s = s.replace(/"+$/g, '').replace(/^"+/g, '').trim();
  s = s.replace(/\s+/g, ' ').trim();

  // Каталог в ASCII/«типографских» кавычках держит англ. сорт; «ёлочки» для RU не трогаем
  if (/[\u0400-\u04FF]/.test(s)) {
    s = s.replace(/[\u0022\u201c\u201d]/g, '').replace(/\s+/g, ' ').trim();
    // Остаток одного латинского слова (битые данные / незакрытая кавычка)
    s = s.replace(/\s+[A-Z][a-z]{2,}\s*$/g, '').trim();
  }

  return s || raw;
}

/** Сброс битых имён вроде «Роза английская (William» после старой логики / обрезки. */
function selectionRepairTruncatedRoseCardName(name) {
  const n = String(name || '').replace(/\s+/g, ' ').trim();
  if (!/^роза английская/i.test(n)) return n;
  const closed = /\(\s*([^)]*)\)\s*$/.exec(n);
  if (closed) {
    const inner = closed[1].trim();
    const lat = (inner.match(/[A-Za-z]/g) || []).length;
    const cyr = (inner.match(/[\u0400-\u04FF]/g) || []).length;
    if (inner && lat >= 3 && cyr === 0) return 'Роза английская';
    return n;
  }
  if (/\(\s*[A-Za-z]/.test(n) && !/\)\s*$/.test(n)) return 'Роза английская';
  return n;
}

function selectionSuffixFromDescription(description) {
  const d = String(description || '').replace(/\s+/g, ' ').trim();
  if (!d) return '';
  let m = d.match(/\(([А-ЯЁа-яё][^)]{1,48})\)/);
  if (m) return m[1].trim();
  m = d.match(/«([^»]{2,48})»/);
  if (m) return m[1].trim();
  if (/[Вв]ильям\s+[Шш]експир/.test(d)) return 'Вильям Шекспир';
  return '';
}

function selectionSuffixFromUrl(url) {
  const u = String(url || '').trim();
  if (!u) return '';
  const parts = u.split('/').filter(Boolean);
  const slug = parts[parts.length - 1] || '';
  if (!slug) return '';
  const rosePrefix = 'roza-angliyskaya-';
  if (!slug.startsWith(rosePrefix)) return '';
  let rest = slug.slice(rosePrefix.length);
  rest = rest.replace(/-(s|r|p)\d+(?:-\d+)?$/i, '');
  rest = rest.replace(/-kashpo-\d+(?:-\d+)?l?$/i, '');
  rest = rest
    .split('-')
    .filter(Boolean)
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ')
    .trim();
  if (!rest) return '';
  return `(${rest})`;
}

function selectionFixAmbiguousName(item) {
  const repaired = selectionRepairTruncatedRoseCardName(item && item.name);
  const base = selectionDisplayNameForPodbor(repaired);
  if (base.toLowerCase() !== 'роза английская') return base;
  const suffix = selectionSuffixFromDescription(item && item.description) || selectionSuffixFromUrl(item && item.url);
  if (!suffix) return base;
  return `${base} ${suffix}`;
}

function initCatalogSelection() {
  const STORAGE_KEY = 'sg_catalog_selection_v2';
  const LEGACY_STORAGE_KEY = 'sg_catalog_selection_v1';
  const addButtons = Array.from(document.querySelectorAll('[data-selection-add]'));
  const panels = Array.from(document.querySelectorAll('[data-selection-panel]'));
  if (!addButtons.length && !panels.length) return;
  addButtons.forEach((b) => ensureSelectionButtonLabel(b));
  let memorySelection = [];

  const parseSelection = () => {
    try {
      let raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) raw = localStorage.getItem(LEGACY_STORAGE_KEY);
      raw = raw || '[]';
      const parsed = JSON.parse(raw);
      const arr = Array.isArray(parsed) ? parsed : [];
      const migrated = arr.map((item) => {
        const rawStep = item && item.qtyStep;
        const qtyStep =
          typeof rawStep === 'number' && Number.isFinite(rawStep) && rawStep >= 2 ? Math.floor(rawStep) : 1;
        let qty = typeof item.qty === 'number' && item.qty >= 1 ? Math.floor(item.qty) : qtyStep >= 2 ? qtyStep : 1;
        if (qtyStep >= 2 && qty % qtyStep !== 0) {
          qty = Math.max(qtyStep, Math.ceil(qty / qtyStep) * qtyStep);
        }
        return {
          ...item,
          qty,
          qtyStep,
          name: selectionFixAmbiguousName(item),
        };
      });
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated));
        localStorage.removeItem(LEGACY_STORAGE_KEY);
      } catch (e2) {
        // ignore quota / privacy mode
      }
      return migrated;
    } catch (e) {
      return memorySelection;
    }
  };

  let selection = parseSelection();
  let noticeEl = null;

  const normalizeText = (value) => (value || '').replace(/\s+/g, ' ').trim();
  const fallbackId = (btn) => {
    const name = normalizeText(btn.getAttribute('data-selection-name')) || 'item';
    return `item-${name.toLowerCase().replace(/[^a-zа-я0-9]+/gi, '-')}`;
  };

  const readItem = (btn) => {
    const itemId = normalizeText(btn.getAttribute('data-selection-id')) || fallbackId(btn);
    const variant = normalizeText(btn.getAttribute('data-selection-variant'));
    const rawName = normalizeText(btn.getAttribute('data-selection-name'));
    const shortName = selectionFixAmbiguousName({
      name: rawName,
      description: normalizeText(btn.getAttribute('data-selection-description')),
      url: btn.getAttribute('data-selection-url') || '',
    }) || rawName || 'Позиция каталога';
    const rawStep = normalizeText(btn.getAttribute('data-selection-qty-step'));
    const parsedStep = parseInt(rawStep, 10);
    const qtyStep = Number.isFinite(parsedStep) && parsedStep >= 2 ? parsedStep : 1;
    const qty = qtyStep >= 2 ? qtyStep : 1;
    return {
      id: itemId,
      name: shortName,
      category: normalizeText(btn.getAttribute('data-selection-category')),
      description: normalizeText(btn.getAttribute('data-selection-description')),
      price: normalizeText(btn.getAttribute('data-selection-price')),
      image: btn.getAttribute('data-selection-image') || '',
      url: btn.getAttribute('data-selection-url') || '',
      variant,
      note: variant ? `Вариант: ${variant}` : '',
      qty,
      qtyStep,
    };
  };

  const save = () => {
    memorySelection = [...selection];
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(selection));
    } catch (e) {
      // localStorage can be unavailable in private mode or strict privacy settings.
    }
  };
  const hasItem = (id) => selection.some((x) => x.id === id);

  const closeNotice = () => {
    if (!noticeEl) return;
    noticeEl.remove();
    noticeEl = null;
  };

  const panelForAddButton = (btn) => {
    if (!panels.length) return null;
    if (panels.length === 1) return panels[0];
    const root = btn.closest('main') || document.body;
    const local = panels.filter((p) => root.contains(p));
    if (local.length === 1) return local[0];
    const after = local.filter((p) => btn.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING);
    return after[0] || local[local.length - 1] || panels[0];
  };

  const showAddedNotice = (fromButton) => {
    closeNotice();
    const panel = fromButton ? panelForAddButton(fromButton) : panels[0];
    noticeEl = document.createElement('div');
    noticeEl.className = 'fixed bottom-4 left-4 right-4 z-[80] md:left-auto md:right-6 md:w-[28rem]';
    noticeEl.innerHTML = `
      <div class="rounded-2xl border border-brand/20 bg-white p-4 shadow-[0_18px_40px_-22px_rgba(15,23,42,0.45)]">
        <div class="text-base font-semibold text-slate-900">Товар успешно добавлен в подбор!</div>
        <div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          <button type="button" data-selection-notice-go class="rounded-xl bg-gradient-to-r from-brand to-brand2 px-4 py-2.5 text-sm font-semibold text-white hover:brightness-105 transition">Перейти в подбор</button>
          <button type="button" data-selection-notice-close class="rounded-xl border border-black/10 px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-black/5 transition">Продолжить просмотр каталога</button>
        </div>
      </div>
    `;
    document.body.appendChild(noticeEl);

    const goBtn = noticeEl.querySelector('[data-selection-notice-go]');
    const closeBtn = noticeEl.querySelector('[data-selection-notice-close]');
    goBtn?.addEventListener('click', () => {
      if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start', inline: 'nearest' });
      closeNotice();
    });
    closeBtn?.addEventListener('click', closeNotice);
    window.setTimeout(() => {
      closeNotice();
    }, 6000);
  };

  const syncAddButtons = () => {
    addButtons.forEach((btn) => {
      const id = normalizeText(btn.getAttribute('data-selection-id')) || fallbackId(btn);
      const active = hasItem(id);
      if (btn.dataset.selectionAnimating === '1') {
        if (!active) delete btn.dataset.selectionAnimating;
        else return;
      }
      const label = ensureSelectionButtonLabel(btn);
      label.textContent = active ? 'В подборе!' : 'Добавить в подбор';
      btn.classList.toggle('whitespace-nowrap', active);
      btn.classList.toggle('text-sm', active);
      btn.classList.toggle('opacity-80', active);
    });
  };

  const selectionTotalUnits = () =>
    selection.reduce((acc, item) => acc + (typeof item.qty === 'number' && item.qty >= 1 ? item.qty : 1), 0);

  const composeModalTitle = () => {
    if (!selection.length) return 'Уточнить наличие';
    const u = selectionTotalUnits();
    if (u > selection.length) return `Позиций в подборе → ${selection.length} · ${u} шт.`;
    return `Позиций в подборе → ${selection.length}`;
  };

  const escapeHtml = (text) =>
    String(text || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');

  const renderPanels = () => {
    panels.forEach((panel) => {
      const countEl = panel.querySelector('[data-selection-count]');
      const emptyEl = panel.querySelector('[data-selection-empty]');
      const listEl = panel.querySelector('[data-selection-list]');
      const submitBtn = panel.querySelector('[data-selection-submit]');
      if (!listEl || !submitBtn) return;

      if (countEl) {
        const u = selectionTotalUnits();
        countEl.textContent = u > selection.length ? `${selection.length} · ${u} шт.` : String(selection.length);
      }
      submitBtn.disabled = selection.length === 0;
      submitBtn.setAttribute('data-modal-title', composeModalTitle());
      const namesForModal = selection.map((item) => {
        const n = (item.name || '').trim();
        const q = typeof item.qty === 'number' && item.qty > 1 ? item.qty : 0;
        const base = item.variant ? `${n} (${item.variant})` : n;
        return q ? `${base} ×${q}` : base;
      });
      const preview = namesForModal.slice(0, 6).join('; ');
      const more = namesForModal.length > 6 ? `; + ещё ${namesForModal.length - 6}` : '';
      submitBtn.setAttribute('data-modal-context', namesForModal.length ? `Подбор: ${preview}${more}` : 'Уточнить наличие');
      submitBtn.setAttribute('data-modal-selection-names', JSON.stringify(namesForModal.slice(0, 24)));
      if (emptyEl) emptyEl.classList.toggle('hidden', selection.length > 0);

      listEl.innerHTML = '';
      selection.forEach((item) => {
        const displayName = (item.name || '').trim();
        const qty = typeof item.qty === 'number' && item.qty >= 1 ? item.qty : 1;
        const card = document.createElement('article');
        card.className = 'rounded-2xl border border-black/10 bg-white p-4 h-full min-h-[20rem] flex flex-col';
        const imageHtml = item.image
          ? `<img src="${escapeHtml(item.image)}" alt="${escapeHtml(displayName)}" class="h-full w-full object-cover" loading="lazy" decoding="async" />`
          : '<div class="h-full w-full bg-slate-100"></div>';
        const categoryHtml = item.category
          ? `<div class="mt-2 text-xs text-slate-500">${escapeHtml(item.category)}</div>`
          : '<div class="mt-2 text-xs text-transparent select-none">.</div>';
        const noteHtml = item.note
          ? `<div class="mt-1 text-xs text-slate-500">${escapeHtml(item.note)}</div>`
          : '';
        const priceHtml = item.price
          ? `<div class="mt-2 text-sm font-semibold text-brand">${escapeHtml(item.price)}</div>`
          : '<div class="mt-2 text-sm text-transparent select-none">.</div>';
        const link = item.url
          ? `<a href="${escapeHtml(item.url)}" class="inline-flex items-center text-sm font-semibold text-brand hover:text-brand2">Подробнее</a>`
          : '<span></span>';
        const qtyHtml = `<div class="mt-3 flex items-center gap-2">
            <span class="text-xs text-slate-500">Кол-во</span>
            <button type="button" data-selection-qty-dec="${escapeHtml(item.id)}" class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-black/10 text-lg font-medium text-slate-700 hover:bg-black/5 transition" aria-label="Минус">−</button>
            <span data-selection-qty-label="${escapeHtml(item.id)}" class="min-w-[1.5rem] text-center text-sm font-semibold text-slate-900">${qty}</span>
            <button type="button" data-selection-qty-inc="${escapeHtml(item.id)}" class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-black/10 text-lg font-medium text-slate-700 hover:bg-black/5 transition" aria-label="Плюс">+</button>
          </div>`;
        card.innerHTML = `
          <div class="h-28 overflow-hidden rounded-xl bg-slate-100">${imageHtml}</div>
          <div class="mt-3 text-lg font-semibold min-h-[5.5rem]">${escapeHtml(displayName)}</div>
          <div class="min-h-[4.5rem]">
            ${categoryHtml}
            ${noteHtml}
            ${priceHtml}
            ${qtyHtml}
          </div>
          <div class="mt-auto pt-3 flex items-end justify-between gap-3">
            ${link}
            <button type="button" data-selection-remove="${escapeHtml(item.id)}" class="rounded-xl border border-black/10 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-black/5 transition">Удалить</button>
          </div>
        `;
        listEl.appendChild(card);
      });
    });
  };

  document.addEventListener('click', (e) => {
    const incBtn = e.target && e.target.closest('[data-selection-qty-inc]');
    const decBtn = e.target && e.target.closest('[data-selection-qty-dec]');
    if (incBtn || decBtn) {
      const id = incBtn ? incBtn.getAttribute('data-selection-qty-inc') : decBtn.getAttribute('data-selection-qty-dec');
      const idx = selection.findIndex((x) => x.id === id);
      if (idx < 0) return;
      const stepRaw = selection[idx].qtyStep;
      const step = typeof stepRaw === 'number' && Number.isFinite(stepRaw) && stepRaw >= 2 ? stepRaw : 1;
      const cur = typeof selection[idx].qty === 'number' && selection[idx].qty >= 1 ? selection[idx].qty : step;
      if (incBtn) {
        selection[idx] = { ...selection[idx], qty: cur + step };
      } else if (cur <= step) {
        selection = selection.filter((x) => x.id !== id);
      } else {
        selection[idx] = { ...selection[idx], qty: cur - step };
      }
      save();
      syncAddButtons();
      renderPanels();
      return;
    }
    const removeBtn = e.target && e.target.closest('[data-selection-remove]');
    if (!removeBtn) return;
    const id = removeBtn.getAttribute('data-selection-remove');
    selection = selection.filter((x) => x.id !== id);
    save();
    syncAddButtons();
    renderPanels();
  });

  /**
   * Добавить/обновить позицию в подборе по кнопке data-selection-add и открыть форму «Позиций в подборе»
   * (тот же поток, что и у «Уточнить наличие» после renderPanels).
   */
  window.SGOpenPodborInquiryFromButton = (btn) => {
    if (!btn || typeof btn.matches !== 'function' || !btn.matches('[data-selection-add]')) return;
    const item = readItem(btn);
    const idx = selection.findIndex((x) => x.id === item.id);
    if (idx < 0) {
      selection = [...selection, item];
    } else {
      selection[idx] = { ...selection[idx], ...item };
    }
    save();
    syncAddButtons();
    renderPanels();
    const panel = panelForAddButton(btn);
    const submitBtn = panel && panel.querySelector('[data-selection-submit]');
    if (!submitBtn || typeof window.SGOpenModal !== 'function') return;
    const key = submitBtn.getAttribute('data-open-modal');
    if (!key) return;
    const title = submitBtn.getAttribute('data-modal-title') || '';
    const noOverlay = submitBtn.getAttribute('data-modal-no-overlay') === '1';
    const contextTitle = submitBtn.getAttribute('data-modal-context') || title;
    let selectionNames = [];
    try {
      const rawNames = submitBtn.getAttribute('data-modal-selection-names');
      const parsed = rawNames ? JSON.parse(rawNames) : [];
      selectionNames = Array.isArray(parsed) ? parsed.map((x) => String(x || '').trim()).filter(Boolean) : [];
    } catch (e) {
      selectionNames = [];
    }
    window.SGOpenModal(key, title, { noOverlay, contextTitle, selectionNames });
  };

  addButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      if (btn.dataset.selectionAnimating === '1') return;
      const item = readItem(btn);
      const exists = hasItem(item.id);
      if (!exists) {
        btn.dataset.selectionAnimating = '1';
        selection = [...selection, item];
        save();
        const label = ensureSelectionButtonLabel(btn);
        label.textContent = 'В подборе!';
        btn.classList.add('whitespace-nowrap', 'text-sm', 'opacity-80');
        renderPanels();
        playSelectionAddedBurst(btn);
        showAddedNotice(btn);
        window.setTimeout(() => {
          delete btn.dataset.selectionAnimating;
          syncAddButtons();
        }, SG_SELECTION_ADD_ANIM_MS);
        return;
      }
      const idx = selection.findIndex((x) => x.id === item.id);
      if (idx >= 0) {
        const stepRaw = selection[idx].qtyStep;
        const step = typeof stepRaw === 'number' && Number.isFinite(stepRaw) && stepRaw >= 2 ? stepRaw : 1;
        const cur = typeof selection[idx].qty === 'number' && selection[idx].qty >= 1 ? selection[idx].qty : step;
        selection[idx] = { ...selection[idx], qty: cur + step };
        save();
        renderPanels();
        playSelectionAddedBurst(btn);
        showAddedNotice(btn);
      }
    });
  });

  syncAddButtons();
  renderPanels();
}

/** Справочная таблица форматов тары: страницы категорий каталога (#sg-packaging-formats-dialog, data-packaging-formats-open). */
function initPackagingFormatsDialog() {
  const dlg = document.getElementById('sg-packaging-formats-dialog');
  if (!dlg || dlg.dataset.sgPackagingBound === '1') return;
  dlg.dataset.sgPackagingBound = '1';

  let suppressOpenerUntil = 0;

  const forceClose = () => {
    suppressOpenerUntil = performance.now() + 450;
    if (dlg.open) dlg.close();
  };

  const closeBtn = dlg.querySelector('[data-packaging-formats-close]');
  if (closeBtn) {
    closeBtn.addEventListener(
      'pointerdown',
      (e) => {
        e.stopPropagation();
      },
      true
    );
    closeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      forceClose();
    });
  }

  dlg.addEventListener('click', (e) => {
    if (e.target !== dlg) return;
    e.preventDefault();
    e.stopPropagation();
    forceClose();
  });

  /* capture: true — срабатывает до всплытия; на Pages не теряется из‑за чужих обработчиков */
  document.addEventListener(
    'click',
    (e) => {
      const opener = e.target.closest('[data-packaging-formats-open]');
      if (!opener) return;
      if (performance.now() < suppressOpenerUntil) {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (dlg.contains(opener)) return;
      e.preventDefault();
      e.stopPropagation();
      if (dlg.open) return;
      try {
        if (typeof dlg.showModal === 'function') dlg.showModal();
        else if (typeof dlg.show === 'function') dlg.show();
      } catch (err) {
        try {
          if (typeof dlg.show === 'function') dlg.show();
        } catch (e2) {
          console.warn('Packaging dialog open failed', e2);
        }
      }
    },
    true
  );
}

/**
 * Полоска дат календаря: sticky top должен совпадать с высотой #site-header.
 * Иначе шапка (z-50) визуально/по hit-test перекрывает ряд (z-40, top=4.5rem) — клики «пропадают».
 */
function syncCalendarTimelineHeaderOffset() {
  const header = document.getElementById('site-header');
  const bars = document.querySelectorAll('[data-sg-calendar-timeline]');
  if (!header || !bars.length) return;

  const apply = () => {
    const px = Math.max(56, Math.ceil(header.getBoundingClientRect().height));
    bars.forEach((bar) => {
      bar.style.top = `${px}px`;
    });
  };

  apply();
  let resizeT = null;
  window.addEventListener('resize', () => {
    window.clearTimeout(resizeT);
    resizeT = window.setTimeout(apply, 120);
  });
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => apply());
    ro.observe(header);
  }
}

/* ── Calendar timeline: auto-highlight current period ── */
function initTimeline() {
  syncCalendarTimelineHeaderOffset();

  const pills = document.querySelectorAll('.timeline-pill');
  if (!pills.length) return;

  const now = new Date();
  const monthNames = {
    'январ':0,'феврал':1,'март':2,'апрел':3,'ма':4,'май':4,
    'июн':5,'июл':6,'август':7,'сентябр':8,'октябр':9,'ноябр':10,'декабр':11
  };

  function parseDate(text) {
    const m = text.match(/(\d+)\s+(\S+?)\s*[–—-]\s*(\d+)\s+(\S+)/);
    if (!m) {
      const m2 = text.match(/(\d+)\s*[–—-]\s*(\d+)\s+(\S+)/);
      if (!m2) return null;
      const month = Object.entries(monthNames).find(([k]) => m2[3].toLowerCase().startsWith(k));
      if (!month) return null;
      return {
        start: new Date(now.getFullYear(), month[1], parseInt(m2[1])),
        end: new Date(now.getFullYear(), month[1], parseInt(m2[2]))
      };
    }
    const sm = Object.entries(monthNames).find(([k]) => m[2].toLowerCase().startsWith(k));
    const em = Object.entries(monthNames).find(([k]) => m[4].toLowerCase().startsWith(k));
    if (!sm || !em) return null;
    return {
      start: new Date(now.getFullYear(), sm[1], parseInt(m[1])),
      end: new Date(now.getFullYear(), em[1], parseInt(m[3]))
    };
  }

  let activePill = null;
  pills.forEach(pill => {
    const range = parseDate(pill.dataset.period || pill.textContent);
    if (range && now >= range.start && now <= range.end) {
      pill.classList.remove('bg-white', 'border-black/10');
      pill.classList.add('bg-brand', 'text-white', 'border-brand');
      activePill = pill;
    }
  });

  if (activePill) {
    activePill.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }

  // Smooth scroll for anchor pills (plant page)
  document.querySelectorAll('.timeline-pill[href^="#"]').forEach(pill => {
    pill.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.querySelector(pill.getAttribute('href'));
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // Period filter for button pills (main/category pages)
  const filterPills = document.querySelectorAll('.timeline-pill:not([href])');
  const plantCards = document.querySelectorAll('.plant-card');
  if (filterPills.length) {
    filterPills.forEach(pill => {
      pill.addEventListener('click', () => {
        const period = pill.dataset.period;
        const wasActive = pill.dataset.filterActive === 'true';

        // Reset all pills to default (preserve current-period highlight)
        filterPills.forEach(p => {
          p.dataset.filterActive = 'false';
          if (p.dataset.currentPeriod !== 'true') {
            p.classList.remove('bg-brand', 'text-white', 'border-brand');
            p.classList.add('bg-white', 'border-black/10');
          } else {
            p.classList.remove('ring-2', 'ring-brand/50');
          }
        });

        if (wasActive) {
          // Deselect — show all
          plantCards.forEach(c => { c.style.display = ''; });
        } else {
          // Activate this pill
          pill.dataset.filterActive = 'true';
          pill.classList.remove('bg-white', 'border-black/10');
          pill.classList.add('bg-brand', 'text-white', 'border-brand');
          if (pill.dataset.currentPeriod === 'true') {
            pill.classList.add('ring-2', 'ring-brand/50');
          }
          // Filter cards
          let visibleCount = 0;
          plantCards.forEach(c => {
            const periods = (c.dataset.periods || '').split('||');
            const match = periods.includes(period);
            c.style.display = match ? '' : 'none';
            if (match) visibleCount++;
          });
        }
      });
    });

    // Mark current-period pills for preserving highlight
    filterPills.forEach(pill => {
      if (pill.classList.contains('bg-brand')) {
        pill.dataset.currentPeriod = 'true';
      }
    });
  }
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
  initCatalogCategoryMobileAutoScroll();
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
  initPackagingFormatsDialog();
  initCatalogSelection();
  initPlantVariantPicker();
  initTimeline();
  initPlantGalleries();
  initPlantCardCoverGallerySwap();
});

// ── Plant image galleries ──
function initPlantGalleries() {
  document.querySelectorAll('[data-gallery]').forEach(function (gallery) {
    var mainWrap = gallery.querySelector('[data-gallery-main]');
    var mainImg = mainWrap ? mainWrap.querySelector('img') : null;
    var thumbs = gallery.querySelectorAll('[data-gallery-thumb]');
    var srcs = [];

    gallery.querySelectorAll('[data-gallery-src]').forEach(function (el) {
      srcs.push(el.textContent.trim());
    });

    if (!mainImg || srcs.length < 2) return;

    var current = 0;

    function show(idx) {
      if (idx === current) return;
      mainImg.style.opacity = '0';
      setTimeout(function () {
        mainImg.src = srcs[idx];
        mainImg.style.opacity = '1';
      }, 150);
      thumbs.forEach(function (t) {
        var i = parseInt(t.getAttribute('data-gallery-thumb'), 10);
        if (i === idx) {
          t.classList.remove('ring-transparent', 'hover:ring-brand/40');
          t.classList.add('ring-brand');
        } else {
          t.classList.remove('ring-brand');
          t.classList.add('ring-transparent', 'hover:ring-brand/40');
        }
      });
      current = idx;
    }

    thumbs.forEach(function (thumb) {
      thumb.addEventListener('click', function () {
        show(parseInt(thumb.getAttribute('data-gallery-thumb'), 10));
      });
    });

    // Click main image → next
    mainWrap.addEventListener('click', function () {
      show((current + 1) % srcs.length);
    });
  });
}

/** Карточка растения: клик по миниатюре галереи меняет местами src с главным фото (только просмотр). */
function initPlantCardCoverGallerySwap() {
  document.querySelectorAll('[data-plant-photo-swap]').forEach(function (root) {
    var main = root.querySelector('[data-plant-main-cover]');
    var thumbs = root.querySelectorAll('[data-plant-gallery-thumb]');
    if (!main || !thumbs.length) return;

    thumbs.forEach(function (thumb) {
      thumb.setAttribute('role', 'button');
      if (!thumb.hasAttribute('tabindex')) thumb.setAttribute('tabindex', '0');

      function swap() {
        var ms = main.getAttribute('src');
        var ts = thumb.getAttribute('src');
        if (!ms || !ts) return;
        main.setAttribute('src', ts);
        thumb.setAttribute('src', ms);
        var ma = main.getAttribute('alt') || '';
        var ta = thumb.getAttribute('alt') || '';
        main.setAttribute('alt', ta);
        thumb.setAttribute('alt', ma);
      }

      thumb.addEventListener('click', function (e) {
        e.preventDefault();
        swap();
      });
      thumb.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          swap();
        }
      });
    });
  });
}

(function initPromoPopup() {
  var STORAGE_KEY = 'sg_promo_popup_28apr_closed';
  var SHOW_DELAY_MS = 2000;

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn, { once: true });
    } else {
      fn();
    }
  }

  ready(function () {
    var popup = document.getElementById('promoPopup');
    if (!popup) return;

    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') return;
    } catch (e) { /* приватный режим — всё равно показываем */ }

    var closers = popup.querySelectorAll('[data-promo-close]');
    var mapLinks = popup.querySelectorAll('[data-promo-action]');
    var prevBodyOverflow = '';
    var isOpen = false;

    function open() {
      if (isOpen) return;
      isOpen = true;
      popup.classList.add('is-open');
      popup.setAttribute('aria-hidden', 'false');
      prevBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      document.addEventListener('keydown', onKeydown);
    }

    function close(persist) {
      if (!isOpen) return;
      isOpen = false;
      popup.classList.remove('is-open');
      popup.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = prevBodyOverflow;
      document.removeEventListener('keydown', onKeydown);
      if (persist !== false) {
        try { localStorage.setItem(STORAGE_KEY, '1'); } catch (e) { /* noop */ }
      }
    }

    function onKeydown(e) {
      if (e.key === 'Escape' || e.key === 'Esc') close(true);
    }

    closers.forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        close(true);
      });
    });

    // Клик по карте — закрываем и сохраняем, ссылка откроется в новой вкладке
    mapLinks.forEach(function (link) {
      link.addEventListener('click', function () {
        close(true);
      });
    });

    setTimeout(open, SHOW_DELAY_MS);
  });
})();

