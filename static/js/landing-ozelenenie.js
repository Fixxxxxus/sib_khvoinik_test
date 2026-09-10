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
 *  - ведёт табы и шторку «до/после» в блоке кейсов;
 *  - шлёт цели Метрики: lead_form_view, lead_cta_click, lead_submit, phone_click,
 *    case_tab_click, case_compare_interact.
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
  // Счётчик поднимается из app.js только после «Принять все» в cookie-баннере, а
  // человек успевает нажать CTA и отправить заявку раньше. Раньше в этот момент
  // цель просто терялась и Директ не видел конверсию (аудит маркетолога, п.2).
  // Теперь цели складываются в очередь и досылаются, как только появится window.ym.
  var goalQueue = [];
  var metrikaReady = false;
  var ymClientId = '';

  function sendGoal(goal, params) {
    try {
      if (params) window.ym(METRIKA_ID, 'reachGoal', goal, params);
      else window.ym(METRIKA_ID, 'reachGoal', goal);
    } catch (e) { /* noop */ }
  }

  function reachGoal(goal, params) {
    if (metrikaReady && window.ym) {
      sendGoal(goal, params);
      return;
    }
    // Очередь ограничена: если согласия так и не будет, память не растёт.
    if (goalQueue.length < 20) goalQueue.push([goal, params]);
  }

  function captureClientId() {
    try {
      window.ym(METRIKA_ID, 'getClientID', function (id) {
        if (id) ymClientId = String(id);
      });
    } catch (e) { /* noop */ }
  }

  function onMetrikaReady() {
    if (metrikaReady) return;
    metrikaReady = true;
    captureClientId();
    var queued = goalQueue.splice(0, goalQueue.length);
    queued.forEach(function (item) { sendGoal(item[0], item[1]); });
  }

  // Хука «Метрика загрузилась» в app.js нет, поэтому просто ждём появления ym.
  // Опрос дешёвый и сам останавливается: либо счётчик появился, либо человек
  // так и не дал согласия за отведённые 15 минут.
  (function waitForMetrika() {
    if (window.ym) {
      onMetrikaReady();
      return;
    }
    var attempts = 0;
    var timer = setInterval(function () {
      attempts += 1;
      if (window.ym) {
        clearInterval(timer);
        onMetrikaReady();
      } else if (attempts > 1800) {
        clearInterval(timer);
      }
    }, 500);
  })();

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
  var leadSent = false;

  function showSuccess() {
    leadSent = true;
    var sticky = document.getElementById('stickyCta');
    if (sticky) sticky.hidden = true;
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
      referrer: document.referrer || '',
      // ClientID Метрики: по нему бэкенд досылает цель через Measurement Protocol,
      // если клиентский счётчик так и не поднялся (отказ от cookie, блокировщик).
      // Пустая строка - счётчика на странице не было, серверная отправка пропускается.
      ym_client_id: ymClientId
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
      button.addEventListener('click', ctaClick);
    }
  });

  // lead_cta_click шлём один раз за визит: кнопок-CTA на странице теперь три
  // (две формы плюс липкая полоска), и без дедупликации в Метрике будет тройной счёт.
  var ctaClicked = false;
  function ctaClick() {
    if (ctaClicked) return;
    ctaClicked = true;
    reachGoal('lead_cta_click', { landing_id: LANDING_ID });
  }

  // ── Липкий CTA на мобиле ───────────────────────────────────────────────────
  // Показываем, когда hero-форма ушла из кадра, и прячем, когда она вернулась,
  // чтобы полоска не накрывала собственную кнопку отправки. После успешной
  // заявки полоска не нужна - её гасит showSuccess().
  var stickyCta = document.getElementById('stickyCta');
  if (stickyCta) {
    var heroCard = document.getElementById('lead-hero');
    var stickyLink = stickyCta.querySelector('[data-sticky-cta]');
    if (stickyLink) stickyLink.addEventListener('click', ctaClick);

    if (heroCard && window.IntersectionObserver) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          stickyCta.hidden = entry.isIntersecting || leadSent;
        });
      }, { threshold: [0] }).observe(heroCard);
    } else {
      stickyCta.hidden = false;
    }
  }

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

  // ── Кейсы: табы и сравнение «до/после» ─────────────────────────────────────
  // Без JS видна первая панель (у остальных hidden в шаблоне), поэтому здесь
  // только улучшение: переключение табов, клавиатура и интерактивная шторка.
  (function () {
    var tablist = document.querySelector('[data-cases-tablist]');
    if (!tablist) return;

    var tabs = Array.prototype.slice.call(tablist.querySelectorAll('[data-case-tab]'));
    if (!tabs.length) return;

    function panelFor(key) {
      return document.querySelector('[data-case-panel="' + key + '"]');
    }

    function activate(key, focusTab) {
      tabs.forEach(function (tab) {
        var isActive = tab.getAttribute('data-case-tab') === key;
        tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
        tab.tabIndex = isActive ? 0 : -1;
        var panel = panelFor(tab.getAttribute('data-case-tab'));
        if (panel) panel.hidden = !isActive;
        if (isActive && focusTab) tab.focus();
      });
    }

    tabs.forEach(function (tab, index) {
      var key = tab.getAttribute('data-case-tab');

      tab.addEventListener('click', function () {
        if (tab.getAttribute('aria-selected') === 'true') return;
        activate(key, false);
        reachGoal('case_tab_click', { landing_id: LANDING_ID, case: key });
      });

      tab.addEventListener('keydown', function (e) {
        var step = 0;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') step = 1;
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') step = -1;
        else if (e.key === 'Home') step = -index;
        else if (e.key === 'End') step = tabs.length - 1 - index;
        else return;
        e.preventDefault();
        var next = tabs[(index + step + tabs.length) % tabs.length];
        var nextKey = next.getAttribute('data-case-tab');
        activate(nextKey, true);
        reachGoal('case_tab_click', { landing_id: LANDING_ID, case: nextKey });
      });
    });

    // case_compare_interact шлём один раз на кейс за сессию: иначе каждое
    // движение шторкой уедет в Метрику отдельной конверсией.
    var comparedCases = {};
    function markCompared(key) {
      if (comparedCases[key]) return;
      comparedCases[key] = true;
      reachGoal('case_compare_interact', { landing_id: LANDING_ID, case: key });
    }

    function clamp(n) {
      return Math.min(100, Math.max(0, Number(n) || 0));
    }

    document.querySelectorAll('[data-case-compare]').forEach(function (root) {
      var key = root.getAttribute('data-case-compare');
      var overlay = root.querySelector('[data-case-compare-overlay]');
      var divider = root.querySelector('[data-case-compare-divider]');
      var handle = root.querySelector('[data-case-compare-handle]');
      var range = root.querySelector('[data-case-compare-range]');
      if (!overlay || !divider || !handle || !range) return;

      // Тот же приём, что и у слайдеров в app.js (initBeforeAfterSliders):
      // верхний слой обрезается clip-path, ползунок лежит поверх прозрачным.
      function update(value) {
        var pct = clamp(value);
        overlay.style.clipPath = 'inset(0 ' + (100 - pct) + '% 0 0)';
        divider.style.left = pct + '%';
        handle.style.left = pct + '%';
        range.value = String(pct);
      }

      update(root.getAttribute('data-before-after-start') || range.value || 50);
      range.addEventListener('input', function () {
        update(range.value);
        markCompared(key);
      });
      range.addEventListener('change', function () { update(range.value); });

      // Мобильный переключатель: шторки нет, слой «До» либо целиком, либо совсем.
      var toggle = document.querySelector('[data-case-compare-toggle="' + key + '"]');
      if (!toggle) return;
      var sideButtons = Array.prototype.slice.call(toggle.querySelectorAll('[data-case-compare-side]'));
      sideButtons.forEach(function (button) {
        button.addEventListener('click', function () {
          var side = button.getAttribute('data-case-compare-side');
          sideButtons.forEach(function (other) {
            other.setAttribute('aria-pressed', other === button ? 'true' : 'false');
          });
          update(side === 'before' ? 100 : 0);
          markCompared(key);
        });
      });
      // На мобиле стартуем с «До»: шторка на 50% там не видна как переключатель.
      if (window.matchMedia && window.matchMedia('(max-width: 639px)').matches) update(100);
    });

    // CTA-полоса под кейсами ведёт к нижней форме и дёргает общую цель CTA.
    var casesCta = document.querySelector('[data-cases-cta]');
    if (casesCta) casesCta.addEventListener('click', ctaClick);
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
