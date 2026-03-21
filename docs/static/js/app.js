function initYear() {
  const el = document.getElementById('year');
  if (!el) return;
  const d = new Date();
  el.textContent = String(d.getFullYear());
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

/** Герои на весь экран минус шапка (главная, газоны). Убирает щель снизу, если calc(100dvh − Xrem) не совпал с реальной высотой header. */
function initViewportHeroHeights() {
  const header = document.getElementById('site-header');
  const heroes = document.querySelectorAll('[data-home-hero], [data-gazon-hero]');
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
  };

  const openModal = (targetKey, title) => {
    const tplId = templateMap[targetKey] || 'modal-template-success';
    const tpl = document.getElementById(tplId);
    if (!tpl) return;

    modalTitle.textContent = title || '';
    modalBody.innerHTML = '';
    modalBody.appendChild(tpl.content.cloneNode(true));

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

  // Submit UI-only forms (save to localStorage)
  const handleUiSubmit = async (form) => {
    const tag = form.getAttribute('data-form-tag') || 'unknown';
    const uiAction = form.getAttribute('data-ui-action') || '';
    const formData = new FormData(form);
    const payload = {};
    for (const [k, v] of formData.entries()) payload[k] = v;

    const entry = { tag, payload, ts: new Date().toISOString() };
    const key = 'sg_leads';
    const existing = JSON.parse(localStorage.getItem(key) || '[]');
    existing.push(entry);
    localStorage.setItem(key, JSON.stringify(existing));

    // Swap to success template
    const successTpl = document.getElementById('modal-template-success');
    if (successTpl) {
      modalTitle.textContent = '';
      modalBody.innerHTML = '';
      modalBody.appendChild(successTpl.content.cloneNode(true));
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

  const base = 500; // placeholder, from ТЗ: "от 500 ₽/м²"
  const regionMult = {
    'Новосибирск': 1,
    'Красноярск': 1.05,
    'Томск': 1.02,
    'Иркутск': 1.1,
    'Кемерово': 1.03,
    'Норильск': 1.2,
    'Другое': 1.15,
  };
  const formatMult = {
    'Самовывоз': 1.0,
    'Доставка': 1.12,
    'Сборная поставка': 1.08,
  };

  const volumeMult = (a) => {
    // placeholder: larger volume -> slight discount
    if (a <= 50) return 1.0;
    const v = 1 - (a - 50) / 950 * 0.25; // ~down to 0.75 by 1000
    return Math.max(0.75, v);
  };

  const formatRu = (n) => new Intl.NumberFormat('ru-RU').format(Math.round(n));

  const calculate = (area, region, format, outTotal, outPer, outNote, onCalculated) => {
    const a = Number(area.value);
    if (!a || Number.isNaN(a) || a <= 0) return;
    const r = region.value;
    const f = format.value;

    const rm = regionMult[r] ?? regionMult['Другое'];
    const fm = formatMult[f] ?? formatMult['Доставка'];
    const vm = volumeMult(a);

    const per = base * rm * fm * vm;
    const total = per * a;

    outPer.textContent = `${formatRu(per)} ₽`;
    outTotal.textContent = `${formatRu(total)} ₽`;
    outNote.textContent =
      'Это расчет-заглушка для дизайна. Точная стоимость зависит от объема, региона и условий поставки.';

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

    const onCalc = () => calculate(area, region, format, outTotal, outPer, outNote);

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
    const cpWrap = modalForm.querySelector('#modalCalcCpWrap');
    const resultBlock = modalForm.querySelector('#modalCalcResultBlock');
    if (!area || !region || !format || !outTotal || !outPer || !outNote || !calcBtn || !cpWrap) return;

    const resetModalCalc = () => {
      outPer.textContent = '—';
      outTotal.textContent = '—';
      outNote.textContent = '';
      cpWrap.classList.add('hidden');
      if (resultBlock) resultBlock.classList.add('hidden');
    };

    resetModalCalc();

    const onCalc = () => {
      calculate(area, region, format, outTotal, outPer, outNote, () => {
        if (resultBlock) resultBlock.classList.remove('hidden');
        cpWrap.classList.remove('hidden');
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

document.addEventListener('DOMContentLoaded', () => {
  initYear();
  initViewportHeroHeights();
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
  initGazonCalculator();
});

