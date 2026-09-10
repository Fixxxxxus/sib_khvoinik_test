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

  function readConfig() {
    var node = document.getElementById('opt-discount-config');
    var fallback = { basis: 'amount', tiers: [], approved: false, disclaimer: '', min_order: 0 };
    if (!node) return fallback;
    try {
      var parsed = JSON.parse(node.textContent || '{}');
      parsed.tiers = Array.isArray(parsed.tiers) ? parsed.tiers.slice() : [];
      parsed.tiers.sort(function (a, b) { return a.threshold - b.threshold; });
      parsed.min_order = Number(parsed.min_order || 0);
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

  /* База скидки словами: рубли или штуки, смотря что стоит в конфиге. */
  function formatBase(value) {
    return config.basis === 'quantity' ? amount(value) + ' шт' : money(value);
  }

  function totals(lines) {
    var subtotal = 0;
    var quantity = 0;
    lines.forEach(function (line) {
      subtotal += Number(line.price) * Number(line.qty);
      quantity += Number(line.qty);
    });
    var base = config.basis === 'quantity' ? quantity : subtotal;
    var percent = 0;
    var next = null;
    config.tiers.forEach(function (tier) {
      if (base >= tier.threshold) {
        percent = tier.percent;
      } else if (next === null) {
        next = { threshold: tier.threshold, percent: tier.percent, remaining: tier.threshold - base };
      }
    });
    var discount = Math.round(subtotal * percent) / 100;
    return {
      subtotal: subtotal,
      quantity: quantity,
      percent: percent,
      discount: discount,
      total: subtotal - discount,
      next: next,
      base: base,
      minOrderLeft: Math.max(0, config.min_order - subtotal),
      minOrderOk: subtotal >= config.min_order
    };
  }

  /* Подсказка под полосой: те же формулировки, что и на сервере. */
  function progressHint(sums) {
    if (!config.tiers.length) return '';
    if (!sums.next) return 'Максимальная скидка ' + sums.percent + '%';
    if (sums.percent === 0) {
      return 'Добавьте товаров на ' + formatBase(sums.next.remaining) + ', чтобы получить первую скидку';
    }
    return 'До скидки ' + sums.next.percent + '% осталось ' + formatBase(sums.next.remaining);
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

  /* Полоса прогресса: сегмент между соседними порогами заливается пропорционально. */
  function renderProgress(sums) {
    document.querySelectorAll('[data-opt-progress-percent]').forEach(function (node) {
      node.textContent = 'Скидка ' + sums.percent + '%';
    });
    document.querySelectorAll('[data-opt-progress-hint]').forEach(function (node) {
      node.textContent = progressHint(sums);
    });

    var marks = [0].concat(config.tiers.map(function (tier) { return tier.threshold; }));
    document.querySelectorAll('[data-opt-progress-seg]').forEach(function (node) {
      var index = parseInt(node.getAttribute('data-opt-progress-seg'), 10);
      var from = marks[index - 1];
      var to = marks[index];
      var width = 0;
      if (to > from) {
        width = Math.min(1, Math.max(0, (sums.base - from) / (to - from))) * 100;
      }
      node.style.width = width + '%';
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
      var percent = Number(node.getAttribute('data-percent'));
      var active = percent === sums.percent;
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

  function render() {
    var lines = readCart();
    var sums = totals(lines);

    document.querySelectorAll('[data-opt-cart-count]').forEach(function (node) {
      node.textContent = String(sums.quantity);
    });

    renderProgress(sums);
    renderLadder(sums);
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
    setText('[data-opt-next-tier]', progressHint(sums));
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

  document.addEventListener('DOMContentLoaded', render);
})();
