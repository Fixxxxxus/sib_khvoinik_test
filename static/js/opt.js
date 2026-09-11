/*
 * Корзина скрытого оптового каталога /opt/.
 *
 * Состав корзины живёт в localStorage: человек уходит из объявления на карточку,
 * возвращается в раздел и не теряет набранное. Скидка за объём и минимальная
 * сумма заказа считаются по тому же конфигу, что и на сервере
 * (pages/wholesale_pricing.py): Django отдаёт его в <script id="opt-discount-config">.
 *
 * Цена в localStorage нужна только для показа. При отправке уходят слаг раздела,
 * слаг позиции, id варианта и количество: суммы, скидку, минимальную сумму и
 * остатки сервер проверяет сам по БД.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'opt_cart_v2';
  var ORDER_URL = '/api/opt/order/';

  var config = readConfig();

  /* Насколько «одинаково близкими» считаем ступени по разным осям.
     Та же константа, что в pages/wholesale_pricing.HINT_TOLERANCE. */
  var HINT_TOLERANCE = 0.1;

  function readConfig() {
    var node = document.getElementById('opt-discount-config');
    var fallback = {
      basis: 'hybrid',
      tiers: [],
      approved: false,
      disclaimer: '',
      entry_percent: 0,
      individual_text: '',
      individual_price_text: '',
      min_order: 0
    };
    if (!node) return fallback;
    try {
      var parsed = JSON.parse(node.textContent || '{}');
      parsed.tiers = Array.isArray(parsed.tiers) ? parsed.tiers.slice() : [];
      /* Порядок ступеней: проценты по возрастанию, индивидуальная - последней. */
      parsed.tiers.sort(function (a, b) {
        var ra = [a.individual ? 1 : 0, a.percent || 0];
        var rb = [b.individual ? 1 : 0, b.percent || 0];
        return ra[0] - rb[0] || ra[1] - rb[1];
      });
      parsed.min_order = Number(parsed.min_order || 0);
      parsed.entry_percent = Number(parsed.entry_percent || 0);
      return parsed;
    } catch (e) {
      return fallback;
    }
  }

  function readCart() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function writeCart(lines) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
    } catch (e) {
      /* приватный режим или переполнение: корзина живёт до перезагрузки */
    }
  }

  /* Ключ строки: варианты одной позиции - разные строки корзины. */
  function lineKey(line) {
    return [line.section || '', line.slug || '', line.variant == null ? '' : line.variant].join('|');
  }

  function amount(value) {
    var rounded = Math.round(value * 100) / 100;
    var whole = Math.round(rounded);
    var text = (Math.abs(rounded - whole) < 0.005 ? whole : rounded.toFixed(2)).toString();
    return text.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  function money(value) {
    return amount(value) + ' ₽';
  }

  /* Остаток словами: по штукам или по рублям, смотря какая ось ступени. */
  function formatAxis(axis, value) {
    return axis === 'quantity' ? amount(value) + ' шт' : money(value);
  }

  /* Оси ступени: количество, чек или обе. */
  function tierAxes(tier) {
    var axes = [];
    if (tier.min_quantity) axes.push({ axis: 'quantity', threshold: Number(tier.min_quantity) });
    if (tier.min_amount) axes.push({ axis: 'amount', threshold: Number(tier.min_amount) });
    return axes;
  }

  /* Ступень взята, если выполнена ЛЮБАЯ из её осей. */
  function tierReached(tier, subtotal, quantity) {
    return tierAxes(tier).some(function (ax) {
      var value = ax.axis === 'quantity' ? quantity : subtotal;
      return value >= ax.threshold;
    });
  }

  /* Ближайшая ось ступени: по какой из них добрать меньше в долях порога. */
  function tierGap(tier, subtotal, quantity) {
    var best = null;
    tierAxes(tier).forEach(function (ax) {
      var value = ax.axis === 'quantity' ? quantity : subtotal;
      var remaining = Math.max(0, ax.threshold - value);
      var relative = ax.threshold ? remaining / ax.threshold : 0;
      if (!best || relative < best.relative) {
        best = {
          axis: ax.axis,
          threshold: ax.threshold,
          remaining: remaining,
          remainingText: formatAxis(ax.axis, remaining),
          relative: relative
        };
      }
    });
    return best;
  }

  function totals(lines) {
    var subtotal = 0;
    var quantity = 0;
    lines.forEach(function (line) {
      subtotal += Number(line.price) * Number(line.qty);
      quantity += Number(line.qty);
    });

    var percent = 0;
    var individual = false;
    var tierKey = 'retail';
    var state = [];
    config.tiers.forEach(function (tier) {
      var reached = tierReached(tier, subtotal, quantity);
      var gap = tierGap(tier, subtotal, quantity);
      state.push({
        key: tier.key,
        reached: reached,
        fill: reached ? 100 : gap ? Math.max(0, Math.min(100, (1 - gap.relative) * 100)) : 0
      });
      if (!reached) return;
      tierKey = tier.key;
      if (tier.individual) {
        individual = true;
      } else {
        percent = Math.max(percent, Number(tier.percent || 0));
      }
    });

    /* Ближайшая невзятая ступень по обеим осям, а не следующая по списку.
       Если оси примерно одинаково далеко, ведём к нижней ступени лестницы:
       та же логика, что в pages/wholesale_pricing.next_tier_for. */
    var candidates = [];
    config.tiers.forEach(function (tier, index) {
      if (tierReached(tier, subtotal, quantity)) return;
      if (tier.individual ? individual : Number(tier.percent || 0) <= percent) return;
      var gap = tierGap(tier, subtotal, quantity);
      if (!gap) return;
      candidates.push({
        key: tier.key,
        label: tier.label,
        percent: tier.percent,
        individual: !!tier.individual,
        axis: gap.axis,
        remaining: gap.remaining,
        remainingText: gap.remainingText,
        relative: gap.relative,
        rank: index
      });
    });
    var next = null;
    if (candidates.length) {
      var closest = Math.min.apply(null, candidates.map(function (c) { return c.relative; }));
      candidates.forEach(function (c) {
        if (c.relative > closest + HINT_TOLERANCE) return;
        if (!next || c.rank < next.rank) next = c;
      });
    }

    var discount = Math.round(subtotal * percent) / 100;
    return {
      subtotal: subtotal,
      quantity: quantity,
      percent: percent,
      individual: individual,
      tierKey: tierKey,
      tierState: state,
      discount: discount,
      total: subtotal - discount,
      next: next,
      minOrderLeft: Math.max(0, config.min_order - subtotal),
      minOrderOk: subtotal >= config.min_order
    };
  }

  /* Подсказка под полосой: те же формулировки, что и на сервере. */
  function progressHint(sums) {
    if (!config.tiers.length) return '';
    if (sums.individual) return config.individual_text;
    if (sums.quantity <= 0 && sums.subtotal <= 0) {
      return 'Оптовая скидка ' + config.entry_percent + '% включается с первой штуки';
    }
    if (!sums.next) return 'Максимальная скидка ' + sums.percent + '%';
    if (sums.next.individual) {
      return 'До индивидуальных условий осталось ' + sums.next.remainingText;
    }
    return 'До скидки ' + sums.next.percent + '% осталось ' + sums.next.remainingText;
  }

  function addQty(data, delta) {
    var lines = readCart();
    var key = lineKey(data);
    var found = null;
    lines.forEach(function (line) {
      if (lineKey(line) === key) found = line;
    });
    var next = (found ? Number(found.qty) : 0) + delta;
    setQtyForKey(lines, key, data, next);
  }

  function setQtyForKey(lines, key, data, qty) {
    var stock = data && data.stock != null ? Number(data.stock) : null;
    if (stock != null && stock >= 0 && qty > stock) qty = stock;
    if (!(qty > 0)) qty = 0;

    var index = -1;
    lines.forEach(function (line, i) {
      if (lineKey(line) === key) index = i;
    });
    if (qty === 0) {
      if (index >= 0) lines.splice(index, 1);
    } else if (index >= 0) {
      lines[index].qty = qty;
      if (data) {
        lines[index].price = data.price;
        lines[index].title = data.title;
        lines[index].variantTitle = data.variantTitle || '';
        lines[index].size = data.size;
        lines[index].unit = data.unit;
        if (data.stock != null) lines[index].stock = Number(data.stock);
      }
    } else if (data) {
      lines.push({
        slug: data.slug,
        section: data.section,
        variant: data.variant == null ? null : Number(data.variant),
        variantTitle: data.variantTitle || '',
        title: data.title,
        size: data.size,
        unit: data.unit,
        price: Number(data.price),
        stock: data.stock == null ? null : Number(data.stock),
        qty: qty
      });
    }
    writeCart(lines);
    render();
  }

  function setQtyByIndex(index, qty) {
    var lines = readCart();
    var line = lines[index];
    if (!line) return;
    setQtyForKey(lines, lineKey(line), null, line.stock != null && qty > line.stock ? line.stock : qty);
  }

  function stepperData(node) {
    return {
      slug: node.getAttribute('data-slug'),
      section: node.getAttribute('data-section'),
      variant: node.getAttribute('data-variant') || null,
      variantTitle: node.getAttribute('data-variant-title') || '',
      title: node.getAttribute('data-title'),
      size: node.getAttribute('data-size') || '',
      unit: node.getAttribute('data-unit') || 'шт',
      price: Number(node.getAttribute('data-price') || 0),
      stock: node.hasAttribute('data-stock') ? Number(node.getAttribute('data-stock')) : null
    };
  }

  /* Степперы на карточке показывают то, что уже лежит в корзине. */
  function syncSteppers(lines) {
    document.querySelectorAll('[data-opt-stepper]').forEach(function (node) {
      var data = stepperData(node);
      var key = lineKey(data);
      var qty = 0;
      lines.forEach(function (line) {
        if (lineKey(line) === key) qty = Number(line.qty);
      });
      var input = node.querySelector('[data-opt-step-input]');
      if (input && document.activeElement !== input) input.value = String(qty);
      var dec = node.querySelector('[data-opt-step-dec]');
      if (dec) dec.disabled = qty <= 0;
      var inc = node.querySelector('[data-opt-step-inc]');
      if (inc) inc.disabled = data.stock != null && qty >= data.stock;
    });
  }

  /* Полоса прогресса: у каждой ступени своё деление, заливка - по её лучшей оси. */
  function renderProgress(sums) {
    document.querySelectorAll('[data-opt-progress-percent]').forEach(function (node) {
      node.textContent = sums.individual ? config.individual_price_text : 'Скидка ' + sums.percent + '%';
    });
    document.querySelectorAll('[data-opt-progress-hint]').forEach(function (node) {
      node.textContent = progressHint(sums);
    });

    var fills = {};
    sums.tierState.forEach(function (row) { fills[row.key] = row.fill; });
    document.querySelectorAll('[data-opt-progress-seg]').forEach(function (node) {
      var key = node.getAttribute('data-opt-progress-seg');
      node.style.width = (fills[key] || 0) + '%';
    });

    var warning = document.querySelector('[data-opt-min-order-warning]');
    if (warning) {
      var show = sums.quantity > 0 && !sums.minOrderOk;
      warning.textContent = show
        ? 'Минимальный заказ от ' + money(config.min_order) + '. Добавьте товаров ещё на ' + money(sums.minOrderLeft) + '.'
        : '';
      warning.hidden = !show;
    }
    var submit = document.querySelector('[data-opt-submit]');
    if (submit) submit.disabled = !sums.minOrderOk;
  }

  /* Активная ступень лестницы цен на карточке. */
  function renderLadder(sums) {
    document.querySelectorAll('[data-opt-tier-step]').forEach(function (node) {
      var active = node.getAttribute('data-tier') === sums.tierKey;
      node.classList.toggle('bg-brand/10', active);
      node.classList.toggle('ring-1', active);
      node.classList.toggle('ring-brand', active);
      var price = node.querySelector('p');
      if (price) {
        price.classList.toggle('text-brand', active);
        price.classList.toggle('text-slate-900', !active);
      }
    });
  }

  /* Лента чипов «ступени скидки» на витрине: подсвечиваем взятую ступень. */
  function renderTierChips(sums) {
    document.querySelectorAll('[data-opt-tier-chip]').forEach(function (node) {
      var active = node.getAttribute('data-opt-tier-chip') === sums.tierKey;
      node.classList.toggle('bg-slate-100', !active);
      node.classList.toggle('bg-brand/10', active);
      node.classList.toggle('ring-1', active);
    });
  }

  /* Липкая полоса заказа внизу мобильного экрана: живёт, пока в корзине есть позиции. */
  function renderMobileBar(sums) {
    var bar = document.querySelector('[data-opt-mobile-bar]');
    if (!bar) return;
    bar.hidden = sums.quantity <= 0;
    var totalNode = bar.querySelector('[data-opt-mobile-total]');
    if (totalNode) totalNode.textContent = money(sums.total);
  }

  function render() {
    var lines = readCart();
    var sums = totals(lines);

    document.querySelectorAll('[data-opt-cart-count]').forEach(function (node) {
      node.textContent = String(sums.quantity);
    });

    renderProgress(sums);
    renderLadder(sums);
    renderTierChips(sums);
    renderMobileBar(sums);
    syncSteppers(lines);

    var list = document.querySelector('[data-opt-cart-lines]');
    if (!list) return;
    list.innerHTML = '';
    lines.forEach(function (line, index) {
      var li = document.createElement('li');
      li.className = 'rounded-lg border border-slate-200 p-3';
      var variant = line.variantTitle
        ? '<p class="text-xs text-slate-600">' + escapeHtml(line.variantTitle) + '</p>'
        : '';
      var size = line.size ? '<p class="text-xs text-slate-500">' + escapeHtml(line.size) + '</p>' : '';
      var maxAttr = line.stock != null ? ' max="' + Number(line.stock) + '"' : '';
      li.innerHTML =
        '<div class="flex items-start justify-between gap-3">' +
        '<div><p class="text-sm font-medium text-slate-900">' + escapeHtml(line.title) + '</p>' + variant + size +
        '<p class="text-xs text-slate-500">' + money(line.price) + ' за ' + escapeHtml(line.unit || 'шт') + '</p></div>' +
        '<button type="button" data-opt-remove="' + index + '" class="text-xs text-slate-400 hover:text-red-600">убрать</button>' +
        '</div>' +
        '<div class="mt-2 flex items-center justify-between gap-3">' +
        '<div class="flex items-center rounded-lg border border-slate-300">' +
        '<button type="button" data-opt-dec="' + index + '" aria-label="Меньше" class="h-9 w-9 text-lg text-slate-500 hover:text-brand">-</button>' +
        '<input type="number" inputmode="numeric" min="0"' + maxAttr + ' value="' + Number(line.qty) + '" data-opt-line-qty="' + index + '" aria-label="Количество" class="h-9 w-14 border-x border-slate-300 text-center text-sm outline-none" />' +
        '<button type="button" data-opt-inc="' + index + '" aria-label="Больше" class="h-9 w-9 text-lg text-slate-500 hover:text-brand">+</button>' +
        '</div>' +
        '<span class="text-sm font-semibold text-slate-900">' + money(Number(line.price) * Number(line.qty)) + '</span>' +
        '</div>';
      list.appendChild(li);
    });

    toggle(document.querySelector('[data-opt-cart-empty]'), lines.length === 0);
    toggle(document.querySelector('[data-opt-cart-totals]'), lines.length > 0);
    toggle(document.querySelector('[data-opt-form]'), lines.length > 0);

    setText('[data-opt-total-qty]', String(sums.quantity));
    setText('[data-opt-subtotal]', money(sums.subtotal));
    setText('[data-opt-discount]', sums.percent ? '-' + money(sums.discount) + ' (' + sums.percent + '%)' : 'пока нет');
    setText('[data-opt-total]', money(sums.total));
    var note = document.querySelector('[data-opt-individual-note]');
    if (note) {
      note.textContent = sums.individual ? config.individual_text : '';
      note.hidden = !sums.individual;
    }
    /* На индивидуальной ступени подсказку не дублируем: ниже стоит та же строка. */
    setText('[data-opt-next-tier]', sums.individual ? '' : progressHint(sums));
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function setText(selector, text) {
    var node = document.querySelector(selector);
    if (node) node.textContent = text;
  }

  function toggle(node, visible) {
    if (!node) return;
    node.hidden = !visible;
    if (node.style) node.style.display = visible ? '' : 'none';
  }

  function openCart(open) {
    var cart = document.querySelector('[data-opt-cart]');
    if (!cart) return;
    cart.hidden = !open;
    if (open) render();
  }

  function utmFromLocation() {
    var params = new URLSearchParams(window.location.search);
    var utm = {};
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'yclid'].forEach(function (key) {
      var value = params.get(key);
      if (value) utm[key] = value;
    });
    return utm;
  }

  function submitOrder(form) {
    var lines = readCart();
    if (!lines.length) return;
    var sums = totals(lines);
    var errorNode = form.querySelector('[data-opt-form-error]');
    if (errorNode) errorNode.hidden = true;
    if (!sums.minOrderOk) {
      if (errorNode) {
        errorNode.textContent =
          'Минимальный заказ от ' + money(config.min_order) + '. Добавьте товаров ещё на ' + money(sums.minOrderLeft) + '.';
        errorNode.hidden = false;
      }
      return;
    }
    var button = form.querySelector('[data-opt-submit]');
    if (button) button.disabled = true;

    var payload = {
      name: (form.elements.name.value || '').trim(),
      phone: (form.elements.phone.value || '').trim(),
      email: (form.elements.email.value || '').trim(),
      comment: (form.elements.comment.value || '').trim(),
      company_site: (form.elements.company_site.value || '').trim(),
      source: 'opt_catalog',
      page_path: window.location.pathname,
      referrer: document.referrer || '',
      utm: utmFromLocation(),
      items: lines.map(function (line) {
        return {
          slug: line.slug,
          section: line.section,
          variant: line.variant == null ? null : Number(line.variant),
          qty: Number(line.qty)
        };
      })
    };

    fetch(ORDER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) { return res.json().catch(function () { return { ok: false }; }); })
      .then(function (data) {
        if (button) button.disabled = false;
        if (!data || !data.ok) {
          if (errorNode) {
            errorNode.textContent = (data && data.error) || 'Не получилось отправить заказ. Позвоните нам.';
            errorNode.hidden = false;
          }
          return;
        }
        writeCart([]);
        render();
        toggle(document.querySelector('[data-opt-success]'), true);
        toggle(form, false);
        toggle(document.querySelector('[data-opt-cart-empty]'), false);
      })
      .catch(function () {
        if (button) button.disabled = false;
        if (errorNode) {
          errorNode.textContent = 'Сеть недоступна. Попробуйте ещё раз или позвоните нам.';
          errorNode.hidden = false;
        }
      });
  }

  document.addEventListener('click', function (event) {
    var stepInc = event.target.closest('[data-opt-step-inc]');
    if (stepInc) {
      addQty(stepperData(stepInc.closest('[data-opt-stepper]')), 1);
      return;
    }
    var stepDec = event.target.closest('[data-opt-step-dec]');
    if (stepDec) {
      addQty(stepperData(stepDec.closest('[data-opt-stepper]')), -1);
      return;
    }
    var add = event.target.closest('[data-opt-add]');
    if (add) {
      addQty(
        {
          slug: add.getAttribute('data-slug'),
          section: add.getAttribute('data-section'),
          variant: null,
          title: add.getAttribute('data-title'),
          size: add.getAttribute('data-size') || '',
          unit: add.getAttribute('data-unit') || 'шт',
          price: Number(add.getAttribute('data-price') || 0),
          stock: null
        },
        1
      );
      openCart(true);
      return;
    }
    if (event.target.closest('[data-opt-cart-open]')) {
      openCart(true);
      return;
    }
    if (event.target.closest('[data-opt-cart-close]')) {
      openCart(false);
      return;
    }
    var remove = event.target.closest('[data-opt-remove]');
    if (remove) {
      setQtyByIndex(parseInt(remove.getAttribute('data-opt-remove'), 10), 0);
      return;
    }
    var inc = event.target.closest('[data-opt-inc]');
    if (inc) {
      var incIndex = parseInt(inc.getAttribute('data-opt-inc'), 10);
      setQtyByIndex(incIndex, Number(readCart()[incIndex].qty) + 1);
      return;
    }
    var dec = event.target.closest('[data-opt-dec]');
    if (dec) {
      var decIndex = parseInt(dec.getAttribute('data-opt-dec'), 10);
      setQtyByIndex(decIndex, Number(readCart()[decIndex].qty) - 1);
    }
  });

  /* Количество можно набрать и с клавиатуры: и в карточке, и в корзине. */
  document.addEventListener('change', function (event) {
    var stepInput = event.target.closest('[data-opt-step-input]');
    if (stepInput) {
      var node = stepInput.closest('[data-opt-stepper]');
      var data = stepperData(node);
      var typed = parseInt(stepInput.value, 10);
      setQtyForKey(readCart(), lineKey(data), data, isNaN(typed) ? 0 : typed);
      return;
    }
    var input = event.target.closest('[data-opt-line-qty]');
    if (!input) return;
    var index = parseInt(input.getAttribute('data-opt-line-qty'), 10);
    var qty = parseInt(input.value, 10);
    setQtyByIndex(index, isNaN(qty) ? 0 : qty);
  });

  document.addEventListener('submit', function (event) {
    var form = event.target.closest('[data-opt-form]');
    if (!form) return;
    event.preventDefault();
    submitOrder(form);
  });

  /* ------------------------------------------------------------------
     Галерея карточки позиции: крупный кадр и лента миниатюр.
     Без сторонних библиотек, без зума и без модалок - заказчик просил такое
     убрать. Переключение: клик по миниатюре, стрелки влево-вправо, свайп.
     ------------------------------------------------------------------ */

  var SWIPE_MIN = 40; /* короче - это тап или дрожание руки, не свайп */

  function galleryNode() {
    return document.querySelector('[data-opt-gallery]');
  }

  function gallerySlides(root) {
    return Array.prototype.slice.call(root.querySelectorAll('[data-opt-gallery-slide]'));
  }

  function showSlide(root, index) {
    var slides = gallerySlides(root);
    if (slides.length < 2) return;
    var next = (index + slides.length) % slides.length;
    slides.forEach(function (slide, i) {
      slide.classList.toggle('hidden', i !== next);
    });
    var thumbs = root.querySelectorAll('[data-opt-gallery-thumb]');
    Array.prototype.forEach.call(thumbs, function (thumb, i) {
      var active = i === next;
      thumb.classList.toggle('border-brand', active);
      thumb.classList.toggle('border-transparent', !active);
      if (active) {
        thumb.setAttribute('aria-current', 'true');
      } else {
        thumb.removeAttribute('aria-current');
      }
    });
    var counter = root.querySelector('[data-opt-gallery-current]');
    if (counter) counter.textContent = String(next + 1);
    root.setAttribute('data-opt-gallery-index', String(next));
  }

  function currentSlide(root) {
    var index = parseInt(root.getAttribute('data-opt-gallery-index'), 10);
    return isNaN(index) ? 0 : index;
  }

  document.addEventListener('click', function (event) {
    var thumb = event.target.closest('[data-opt-gallery-thumb]');
    if (!thumb) return;
    var root = thumb.closest('[data-opt-gallery]');
    if (!root) return;
    showSlide(root, parseInt(thumb.getAttribute('data-index'), 10) || 0);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    /* В полях ввода стрелки двигают курсор и количество - галерею не трогаем. */
    var active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT')) return;
    var root = galleryNode();
    if (!root || gallerySlides(root).length < 2) return;
    showSlide(root, currentSlide(root) + (event.key === 'ArrowRight' ? 1 : -1));
    event.preventDefault();
  });

  var swipeStartX = 0;
  var swipeStartY = 0;

  document.addEventListener('touchstart', function (event) {
    var frame = event.target.closest('[data-opt-gallery-frame]');
    if (!frame || !event.touches.length) return;
    swipeStartX = event.touches[0].clientX;
    swipeStartY = event.touches[0].clientY;
  }, { passive: true });

  document.addEventListener('touchend', function (event) {
    var frame = event.target.closest('[data-opt-gallery-frame]');
    if (!frame || !event.changedTouches.length) return;
    var root = frame.closest('[data-opt-gallery]');
    if (!root || gallerySlides(root).length < 2) return;
    var dx = event.changedTouches[0].clientX - swipeStartX;
    var dy = event.changedTouches[0].clientY - swipeStartY;
    /* Вертикальный жест - это скролл страницы, а не листание. */
    if (Math.abs(dx) < SWIPE_MIN || Math.abs(dx) < Math.abs(dy)) return;
    showSlide(root, currentSlide(root) + (dx < 0 ? 1 : -1));
  }, { passive: true });

  document.addEventListener('DOMContentLoaded', render);
})();
