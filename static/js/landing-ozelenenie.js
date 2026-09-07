/*
 * Посадочная «Озеленение · финал сезона» (/ozelenenie-season-end/).
 *
 * Отдельный файл, а не кусок app.js: у лендинга свой эндпоинт POST /api/lead/,
 * свои цели Метрики и своя атрибуция (UTM + yclid), и он не должен ломаться
 * вместе с общей системой форм сайта.
 *
 * Что делает:
 *  - запоминает UTM и yclid из адресной строки в sessionStorage (человек может
 *    уйти на политику и вернуться уже без меток в URL);
 *  - валидирует и нормализует телефон на клиенте, показывает ошибки у полей;
 *  - шлёт заявку и показывает экран успеха;
 *  - шлёт цели Метрики: lead_form_view, lead_cta_click, lead_submit, phone_click.
 */
(function () {
  'use strict';

  var METRIKA_ID = 108722541; // счётчик сайта, инициализируется в app.js после согласия на cookie
  var STORAGE_KEY = 'sg_landing_attribution';
  var UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];
  var ATTR_KEYS = UTM_KEYS.concat(['yclid']);

  var root = document.getElementById('hero');
  if (!root) return;

  var meta = document.querySelector('meta[name="landing-id"]');
  var LANDING_ID = meta ? meta.getAttribute('content') : 'ozelenenie-season-end';
  var SERVICE_LABEL = 'Озеленение · получить предложение';
  var AREA_LABEL = 'от 100 м²';

  // ── Метрика ────────────────────────────────────────────────────────────────
  function reachGoal(goal, params) {
    if (!window.ym) return; // счётчик грузится только после согласия в cookie-баннере
    try {
      if (params) ym(METRIKA_ID, 'reachGoal', goal, params);
      else ym(METRIKA_ID, 'reachGoal', goal);
    } catch (e) { /* noop */ }
  }

  // ── Атрибуция ──────────────────────────────────────────────────────────────
  function readStored() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function captureAttribution() {
    var stored = readStored();
    var params = new URLSearchParams(location.search);
    var changed = false;
    ATTR_KEYS.forEach(function (key) {
      var value = params.get(key);
      if (value) {
        stored[key] = value;
        changed = true;
      }
    });
    if (changed) {
      try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(stored)); } catch (e) { /* noop */ }
    }
    return stored;
  }

  var attribution = captureAttribution();

  function utmPayload() {
    var utm = {};
    ATTR_KEYS.forEach(function (key) {
      if (attribution[key]) utm[key] = attribution[key];
    });
    return utm;
  }

  // ── Телефон ────────────────────────────────────────────────────────────────
  function digitsOf(value) {
    return String(value || '').replace(/\D/g, '');
  }

  // Приводим к 11 цифрам с 7 - тем же правилам, что и бэкенд (pages/landing_leads.py).
  function normalizePhone(value) {
    var digits = digitsOf(value);
    if (digits.length === 11 && (digits[0] === '7' || digits[0] === '8')) return '7' + digits.slice(1);
    if (digits.length === 10 && digits[0] === '9') return '7' + digits;
    return '';
  }

  function formatPhone(value) {
    var digits = digitsOf(value);
    if (!digits) return '';
    // Вставка «+7 913...» поверх подставленного «+7 » даёт две семёрки подряд:
    // срезаем префиксы 7/8, пока цифр больше десяти, остаток - сам номер.
    if (digits.length <= 10 && (digits[0] === '8' || digits[0] === '7')) digits = digits.slice(1);
    while (digits.length > 10 && (digits[0] === '8' || digits[0] === '7')) digits = digits.slice(1);
    if (digits.length > 10) digits = digits.slice(digits.length - 10);
    digits = digits.slice(0, 10);
    var out = '+7';
    if (digits.length) out += ' (' + digits.slice(0, 3);
    if (digits.length >= 3) out += ')';
    if (digits.length > 3) out += ' ' + digits.slice(3, 6);
    if (digits.length > 6) out += '-' + digits.slice(6, 8);
    if (digits.length > 8) out += '-' + digits.slice(8, 10);
    return out;
  }

  function bindPhoneMask(input) {
    function apply() {
      var caretAtEnd = input.selectionStart === input.value.length;
      var formatted = formatPhone(input.value);
      if (formatted !== input.value) {
        input.value = formatted;
        if (caretAtEnd) {
          try { input.setSelectionRange(formatted.length, formatted.length); } catch (e) { /* noop */ }
        }
      }
    }
    input.addEventListener('input', apply);
    input.addEventListener('focus', function () {
      if (!input.value) input.value = '+7 ';
    });
    input.addEventListener('blur', function () {
      if (digitsOf(input.value).length <= 1) input.value = '';
    });
  }

  // ── Ошибки ─────────────────────────────────────────────────────────────────
  function errorBox(form, field) {
    return form.querySelector('[data-error-for="' + field + '"]');
  }

  function clearErrors(form) {
    form.querySelectorAll('[data-error-for]').forEach(function (box) {
      box.textContent = '';
      box.classList.add('hidden');
    });
    form.querySelectorAll('.border-red-400').forEach(function (el) {
      el.classList.remove('border-red-400');
    });
  }

  function showError(form, field, message) {
    var box = errorBox(form, field);
    if (box) {
      box.textContent = message;
      box.classList.remove('hidden');
    }
    var input = form.querySelector('[name="' + field + '"]');
    if (input) {
      if (input.type !== 'checkbox') input.classList.add('border-red-400');
      try { input.focus({ preventScroll: false }); } catch (e) { input.focus(); }
    }
    return false;
  }

  // ── Отправка ───────────────────────────────────────────────────────────────
  function showSuccess() {
    // Форма есть в двух местах: после успеха меняем на экран успеха обе,
    // чтобы человек не отправил заявку второй раз со второго блока.
    document.querySelectorAll('[data-lead-form-wrap]').forEach(function (wrap) {
      wrap.hidden = true;
    });
    document.querySelectorAll('[data-lead-success]').forEach(function (box) {
      box.hidden = false;
    });
    if (window.lucide) {
      try { window.lucide.createIcons(); } catch (e) { /* noop */ }
    }
  }

  function submitForm(form) {
    clearErrors(form);

    var nameInput = form.querySelector('[name="name"]');
    var phoneInput = form.querySelector('[name="phone"]');
    var consentInput = form.querySelector('[name="consent"]');
    var commentInput = form.querySelector('[name="comment"]');
    var honeypot = form.querySelector('[name="company_site"]');
    var button = form.querySelector('[data-lead-submit]');

    var name = (nameInput ? nameInput.value : '').trim();
    var phone = normalizePhone(phoneInput ? phoneInput.value : '');

    if (name.length < 2) return showError(form, 'name', 'Укажите имя, минимум 2 символа.');
    if (!phone) return showError(form, 'phone', 'Проверьте номер: нужен российский номер из 11 цифр.');
    if (!consentInput || !consentInput.checked) {
      return showError(form, 'consent', 'Без согласия на обработку данных мы не сможем перезвонить.');
    }

    var payload = {
      name: name,
      phone: phone,
      consent: true,
      comment: commentInput ? commentInput.value.trim() : '',
      company_site: honeypot ? honeypot.value : '',
      landing_id: LANDING_ID,
      landing_url: location.href,
      page_path: location.pathname,
      source: 'yandex_direct',
      service_label: SERVICE_LABEL,
      area_label: AREA_LABEL,
      utm: utmPayload(),
      referrer: document.referrer || ''
    };

    if (button) {
      button.disabled = true;
      button.dataset.label = button.textContent;
      button.textContent = 'Отправляем...';
    }

    function restore() {
      if (!button) return;
      button.disabled = false;
      if (button.dataset.label) button.textContent = button.dataset.label;
    }

    fetch('/api/lead/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) { return res.json().catch(function () { return { ok: false }; }); })
      .then(function (data) {
        if (data && data.ok) {
          reachGoal('lead_submit', {
            landing_id: LANDING_ID,
            lead_id: data.lead_id || '',
            utm_campaign: attribution.utm_campaign || '',
            utm_content: attribution.utm_content || ''
          });
          showSuccess();
          return;
        }
        restore();
        var field = data && data.field ? data.field : 'form';
        showError(form, field, (data && data.error) || 'Не получилось отправить заявку. Позвоните нам, пожалуйста.');
      })
      .catch(function () {
        restore();
        showError(form, 'form', 'Связь с сервером пропала. Попробуйте ещё раз или позвоните нам.');
      });

    return false;
  }

  document.querySelectorAll('[data-landing-form]').forEach(function (form) {
    var phoneInput = form.querySelector('[name="phone"]');
    if (phoneInput) bindPhoneMask(phoneInput);

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      submitForm(form);
    });

    var button = form.querySelector('[data-lead-submit]');
    if (button) {
      button.addEventListener('click', function () { reachGoal('lead_cta_click'); });
    }
  });

  // ── lead_form_view: форма в hero показалась хотя бы наполовину ──────────────
  (function () {
    var heroForm = document.querySelector('#lead-hero [data-landing-form]');
    if (!heroForm || !window.IntersectionObserver) return;
    var sessionFlag = 'sg_landing_form_view';
    try {
      if (sessionStorage.getItem(sessionFlag)) return;
    } catch (e) { /* noop */ }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.intersectionRatio < 0.5) return;
        observer.disconnect();
        try { sessionStorage.setItem(sessionFlag, '1'); } catch (e) { /* noop */ }
        reachGoal('lead_form_view');
      });
    }, { threshold: [0.5] });
    observer.observe(heroForm);
  })();

  // ── Виджет чата Битрикс24 ──────────────────────────────────────────────────
  // app.js поднимает виджет на всех страницах, и на мобиле его кнопка садится
  // ровно на «Получить предложение». Своих стилей виджета не переспорить (они
  // приезжают позже и с !important), поэтому гасим инлайном, как только появится.
  (function () {
    function hideWidget() {
      var wrap = document.querySelector('.b24-widget-button-wrapper');
      if (!wrap) return false;
      wrap.style.setProperty('display', 'none', 'important');
      return true;
    }
    if (hideWidget()) return;
    if (!window.MutationObserver) return;
    var observer = new MutationObserver(function () {
      if (hideWidget()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    // Виджет может так и не подгрузиться (блокировщик, нет сети) - не наблюдаем вечно.
    setTimeout(function () { observer.disconnect(); }, 30000);
  })();

  // ── phone_click ────────────────────────────────────────────────────────────
  // На сайте цель phone_click уже шлёт общий обработчик из app.js (initAnalyticsClicks).
  // Дублировать его нельзя - в Метрике получится двойной счёт, поэтому вешаем свой
  // обработчик только если app.js на странице нет.
  if (!document.querySelector('script[src*="js/app.js"]')) {
    document.addEventListener('click', function (e) {
      var link = e.target && e.target.closest ? e.target.closest('a[href^="tel:"]') : null;
      if (link) reachGoal('phone_click');
    }, true);
  }
})();
