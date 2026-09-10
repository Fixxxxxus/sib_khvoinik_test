/*
 * Корзина скрытого оптового каталога /opt/.
 *
 * Состав корзины живёт в localStorage: человек уходит из объявления на карточку,
 * возвращается в раздел и не теряет набранное. Скидка за объём считается по тому
 * же конфигу, что и на сервере (pages/wholesale_pricing.py): Django отдаёт его
 * в <script id="opt-discount-config">.
 *
 * Цена в localStorage нужна только для показа. При отправке уходят слаг раздела,
 * слаг позиции и количество: суммы, скидку и итог сервер считает сам по БД.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'opt_cart_v1';
  var ORDER_URL = '/api/opt/order/';

  var config = readConfig();

  function readConfig() {
    var node = document.getElementById('opt-discount-config');
    var fallback = { basis: 'amount', tiers: [], approved: false, disclaimer: '' };
    if (!node) return fallback;
    try {
      var parsed = JSON.parse(node.textContent || '{}');
      parsed.tiers = Array.isArray(parsed.tiers) ? parsed.tiers.slice() : [];
      parsed.tiers.sort(function (a, b) { return a.threshold - b.threshold; });
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

  function money(value) {
    var rounded = Math.round(value * 100) / 100;
    var whole = Math.round(rounded);
    var text = (Math.abs(rounded - whole) < 0.005 ? whole : rounded.toFixed(2)).toString();
    return text.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' ₽';
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
        next = tier;
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
      base: base
    };
  }

  function addToCart(data, qty) {
    var lines = readCart();
    var found = null;
    lines.forEach(function (line) {
      if (line.slug === data.slug && line.section === data.section) found = line;
    });
    if (found) {
      found.qty = Number(found.qty) + qty;
      found.price = data.price;
      found.title = data.title;
      found.size = data.size;
      found.unit = data.unit;
    } else {
      lines.push({
        slug: data.slug,
        section: data.section,
        title: data.title,
        size: data.size,
        unit: data.unit,
        price: data.price,
        qty: qty
      });
    }
    writeCart(lines);
    render();
  }

  function setQty(index, qty) {
    var lines = readCart();
    if (!lines[index]) return;
    if (qty < 1) {
      lines.splice(index, 1);
    } else {
      lines[index].qty = qty;
    }
    writeCart(lines);
    render();
  }

  function nextTierText(sums) {
    if (!sums.next) return '';
    var left = sums.next.threshold - sums.base;
    if (left <= 0) return '';
    if (config.basis === 'quantity') {
      return 'До скидки ' + sums.next.percent + '% не хватает ' + left + ' шт.';
    }
    return 'До скидки ' + sums.next.percent + '% не хватает ' + money(left) + '.';
  }

  function render() {
    var lines = readCart();
    var sums = totals(lines);

    document.querySelectorAll('[data-opt-cart-count]').forEach(function (node) {
      node.textContent = String(sums.quantity);
    });

    var list = document.querySelector('[data-opt-cart-lines]');
    if (!list) return;
    list.innerHTML = '';
    lines.forEach(function (line, index) {
      var li = document.createElement('li');
      li.className = 'rounded-lg border border-slate-200 p-3';
      var size = line.size ? '<p class="text-xs text-slate-500">' + escapeHtml(line.size) + '</p>' : '';
      li.innerHTML =
        '<div class="flex items-start justify-between gap-3">' +
        '<div><p class="text-sm font-medium text-slate-900">' + escapeHtml(line.title) + '</p>' + size +
        '<p class="text-xs text-slate-500">' + money(line.price) + ' за ' + escapeHtml(line.unit || 'шт') + '</p></div>' +
        '<button type="button" data-opt-remove="' + index + '" class="text-xs text-slate-400 hover:text-red-600">убрать</button>' +
        '</div>' +
        '<div class="mt-2 flex items-center justify-between gap-3">' +
        '<div class="flex items-center gap-2">' +
        '<button type="button" data-opt-dec="' + index + '" class="h-8 w-8 rounded border border-slate-300 text-slate-700">-</button>' +
        '<input type="number" min="1" value="' + Number(line.qty) + '" data-opt-line-qty="' + index + '" class="h-8 w-20 rounded border border-slate-300 px-2 text-sm" />' +
        '<button type="button" data-opt-inc="' + index + '" class="h-8 w-8 rounded border border-slate-300 text-slate-700">+</button>' +
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
    setText('[data-opt-next-tier]', nextTierText(sums));
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
    var button = form.querySelector('[data-opt-submit]');
    var errorNode = form.querySelector('[data-opt-form-error]');
    if (errorNode) errorNode.hidden = true;
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
        return { slug: line.slug, section: line.section, qty: Number(line.qty) };
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
    var add = event.target.closest('[data-opt-add]');
    if (add) {
      var qtyInput = document.querySelector('[data-opt-qty-input]');
      var qty = qtyInput ? parseInt(qtyInput.value, 10) : 1;
      if (!qty || qty < 1) qty = 1;
      addToCart(
        {
          slug: add.getAttribute('data-slug'),
          section: add.getAttribute('data-section'),
          title: add.getAttribute('data-title'),
          size: add.getAttribute('data-size') || '',
          unit: add.getAttribute('data-unit') || 'шт',
          price: Number(add.getAttribute('data-price') || 0)
        },
        add.closest('[data-opt-cart]') ? 1 : qty
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
      setQty(parseInt(remove.getAttribute('data-opt-remove'), 10), 0);
      return;
    }
    var inc = event.target.closest('[data-opt-inc]');
    if (inc) {
      var incIndex = parseInt(inc.getAttribute('data-opt-inc'), 10);
      setQty(incIndex, Number(readCart()[incIndex].qty) + 1);
      return;
    }
    var dec = event.target.closest('[data-opt-dec]');
    if (dec) {
      var decIndex = parseInt(dec.getAttribute('data-opt-dec'), 10);
      setQty(decIndex, Number(readCart()[decIndex].qty) - 1);
    }
  });

  document.addEventListener('change', function (event) {
    var input = event.target.closest('[data-opt-line-qty]');
    if (!input) return;
    var index = parseInt(input.getAttribute('data-opt-line-qty'), 10);
    var qty = parseInt(input.value, 10);
    setQty(index, isNaN(qty) ? 0 : qty);
  });

  document.addEventListener('submit', function (event) {
    var form = event.target.closest('[data-opt-form]');
    if (!form) return;
    event.preventDefault();
    submitOrder(form);
  });

  document.addEventListener('DOMContentLoaded', render);
})();
