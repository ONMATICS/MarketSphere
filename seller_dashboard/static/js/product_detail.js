(function () {
    'use strict';
    var page = document.getElementById('spdPage');
    if (!page) return;

    function qs(s, c) { return (c || document).querySelector(s); }
    function qsa(s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); }
    function toast(msg, type) { if (window.showToast) window.showToast(msg, type || 'info'); }

    function getCookie(name) {
        var m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
        return m ? decodeURIComponent(m[1]) : '';
    }

    function post(url, payload) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload || {})
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (d) {
                return { ok: r.ok, data: d };
            });
        });
    }

    // Runs a POST, toasts the result and reloads on success.
    function run(btn, url, payload, fallback) {
        if (btn) btn.disabled = true;
        return post(url, payload).then(function (res) {
            var d = res.data;
            var success = res.ok && (d.success === true || d.status === 'success');
            if (!success) throw new Error(d.message || fallback || 'Something went wrong.');
            toast(d.message || 'Done.', 'success');
            setTimeout(function () { window.location.reload(); }, 600);
        }).catch(function (err) {
            toast(err.message, 'error');
            if (btn) btn.disabled = false;
        });
    }

    /* ---------- tabs (kept in the URL hash) ---------- */
    var tabs = qsa('.spd-tab'), panels = qsa('.spd-panel');
    function activate(name, scroll) {
        if (!qs('.spd-panel[data-spd-panel="' + name + '"]')) return;
        tabs.forEach(function (t) {
            var on = t.dataset.spdTab === name;
            t.classList.toggle('is-active', on);
            t.setAttribute('aria-selected', on ? 'true' : 'false');
        });
        panels.forEach(function (p) { p.classList.toggle('is-active', p.dataset.spdPanel === name); });
        if (scroll) qs('#spdTabs').scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (name === 'analytics') renderChart(currentMetric);
        if (history.replaceState) history.replaceState(null, '', '#tab-' + name);
    }
    tabs.forEach(function (t) { t.addEventListener('click', function () { activate(t.dataset.spdTab, false); }); });
    qsa('[data-spd-goto]').forEach(function (b) { b.addEventListener('click', function () { activate(b.dataset.spdGoto, true); }); });

    /* ---------- modals ---------- */
    function openModal(id) {
        var m = document.getElementById(id);
        if (!m) return;
        m.classList.remove('spd-hidden');
        document.body.style.overflow = 'hidden';
        var f = qs('input, select, textarea', m);
        if (f) f.focus();
    }
    function closeModals() {
        qsa('.spd-modal-overlay').forEach(function (m) { m.classList.add('spd-hidden'); });
        document.body.style.overflow = '';
    }
    qsa('[data-spd-open]').forEach(function (b) {
        b.addEventListener('click', function () { closeMenu(); openModal(b.dataset.spdOpen); });
    });
    qsa('[data-spd-close]').forEach(function (b) { b.addEventListener('click', closeModals); });
    qsa('.spd-modal-overlay').forEach(function (o) {
        o.addEventListener('click', function (e) { if (e.target === o) closeModals(); });
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') { closeModals(); closeMenu(); } });

    /* ---------- more menu ---------- */
    var more = document.getElementById('spdMore'), trigger = document.getElementById('spdMoreTrigger');
    function closeMenu() { if (more) { more.classList.remove('is-open'); trigger.setAttribute('aria-expanded', 'false'); } }
    if (trigger) {
        trigger.addEventListener('click', function (e) {
            e.stopPropagation();
            var open = more.classList.toggle('is-open');
            trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        document.addEventListener('click', function (e) { if (!more.contains(e.target)) closeMenu(); });
    }

    /* ---------- gallery + zoom ---------- */
    var mainImg = document.getElementById('spdMainImage');
    var counter = document.getElementById('spdImageCounter');
    var primaryTag = document.getElementById('spdPrimaryTag');
    var thumbs = qsa('.spd-thumb-item');
    thumbs.forEach(function (t) {
        t.addEventListener('click', function () {
            thumbs.forEach(function (x) { x.classList.remove('is-active'); });
            t.classList.add('is-active');
            if (mainImg) mainImg.src = t.dataset.spdImage;
            if (counter) counter.textContent = t.dataset.index + ' / ' + thumbs.length;
            if (primaryTag) primaryTag.style.display = t.dataset.primary === '1' ? '' : 'none';
        });
    });
    qsa('[data-spd-zoom]').forEach(function (z) {
        z.addEventListener('click', function () {
            var img = qs('#spdZoomImage');
            img.src = mainImg ? mainImg.src : (qs('.spd-thumb img') || {}).src || '';
            openModal('spdZoomModal');
        });
    });

    /* ---------- pricing ---------- */
    var saveP = document.getElementById('spdSavePriceBtn');
    if (saveP) saveP.addEventListener('click', function () {
        var price = document.getElementById('spdPriceInput').value.trim();
        var disc = document.getElementById('spdDiscountInput').value.trim();
        if (!price) return toast('Current price is required.', 'error');
        if (Number(price) < 0) return toast('Price cannot be negative.', 'error');
        if (disc !== '' && (Number(disc) < 0 || Number(disc) >= Number(price))) {
            return toast('Discount price must be lower than the current price.', 'error');
        }
        run(saveP, page.dataset.urlPricing, { price: price, discount_price: disc === '' ? null : disc }, 'Unable to update pricing.');
    });
    var rmDisc = document.getElementById('spdRemoveDiscountBtn');
    if (rmDisc) rmDisc.addEventListener('click', function () {
        if (!confirm('Remove the discount from this product?')) return;
        run(rmDisc, page.dataset.urlRemoveDiscount, {}, 'Unable to remove discount.');
    });

    /* ---------- stock ---------- */
    var stock = parseInt(page.dataset.stock, 10) || 0;
    var typeSel = document.getElementById('spdAdjustType');
    var qtyIn = document.getElementById('spdAdjustQty');
    var preview = document.getElementById('spdStockPreview');
    function updatePreview() {
        var qty = parseInt(qtyIn.value, 10) || 0, r = stock;
        if (typeSel.value === 'increase') r = stock + qty;
        else if (typeSel.value === 'decrease') r = Math.max(0, stock - qty);
        else r = qty;
        preview.textContent = r.toLocaleString('en-US') + ' units';
    }
    if (typeSel && qtyIn) {
        typeSel.addEventListener('change', updatePreview);
        qtyIn.addEventListener('input', updatePreview);
        updatePreview();
    }
    var saveS = document.getElementById('spdSaveStockBtn');
    if (saveS) saveS.addEventListener('click', function () {
        var qty = parseInt(qtyIn.value, 10);
        if (isNaN(qty) || qty < 0) return toast('Enter a valid quantity.', 'error');
        if (typeSel.value === 'decrease' && qty > stock) return toast('Stock cannot go below zero.', 'error');
        run(saveS, page.dataset.urlStock, {
            adjustment_type: typeSel.value,
            quantity: qty,
            reason: document.getElementById('spdAdjustReason').value,
            note: document.getElementById('spdAdjustNote').value.trim()
        }, 'Unable to adjust stock.');
    });
    var oos = document.getElementById('spdOutOfStockBtn');
    if (oos) oos.addEventListener('click', function () {
        if (confirm('Mark this product as out of stock?')) run(oos, page.dataset.urlOutOfStock, {}, 'Unable to update stock status.');
    });
    var restore = document.getElementById('spdRestoreBtn');
    if (restore) restore.addEventListener('click', function () {
        if (confirm('Restore this product to an available stock status?')) run(restore, page.dataset.urlRestore, {}, 'Unable to restore stock.');
    });

    /* ---------- visibility + archive ---------- */
    qsa('[data-spd-visibility]').forEach(function (b) {
        b.addEventListener('click', function () {
            run(b, page.dataset.urlVisibility, { action: b.dataset.spdVisibility }, 'Unable to change visibility.');
        });
    });
    qsa('[data-spd-archive]').forEach(function (b) {
        b.addEventListener('click', function () {
            run(b, page.dataset.urlArchive, { productSlug: page.dataset.productSlug, action: b.dataset.spdArchive }, 'Unable to update archive state.');
        });
    });

    /* ---------- orders filter ---------- */
    var oSearch = document.getElementById('spdOrdersSearch');
    var oStatus = document.getElementById('spdOrdersStatus');
    var rows = qsa('#spdOrdersTable .spd-row');
    var oEmpty = document.getElementById('spdOrdersEmpty');
    function filterOrders() {
        var term = (oSearch.value || '').trim().toLowerCase(), st = oStatus.value, visible = 0;
        rows.forEach(function (row) {
            var ok = (!term || (row.dataset.search || '').toLowerCase().indexOf(term) !== -1) && (!st || row.dataset.status === st);
            row.hidden = !ok;
            if (ok) visible++;
        });
        if (oEmpty) oEmpty.hidden = visible !== 0;
    }
    if (oSearch && rows.length) { oSearch.addEventListener('input', filterOrders); oStatus.addEventListener('change', filterOrders); }

    /* ---------- line chart (data comes from Django via json_script) ---------- */
    var dataEl = document.getElementById('spdChartData');
    var DATA = dataEl ? JSON.parse(dataEl.textContent) : [];
    var currentMetric = 'units';

    function fmt(metric, v) {
        return metric === 'revenue' ? 'Rs. ' + Math.round(v).toLocaleString('en-US') : String(v);
    }
    function renderChart(metric) {
        var el = document.getElementById('spdLineChart');
        if (!el || !DATA.length) return;
        var W = 640, H = 230, PT = 22, PB = 26, PL = 10, PR = 10;
        var vals = DATA.map(function (d) { return Number(d[metric]) || 0; });
        var max = Math.max.apply(null, vals) || 1;
        var step = (W - PL - PR) / Math.max(DATA.length - 1, 1);
        var pts = vals.map(function (v, i) {
            return { x: PL + i * step, y: PT + (H - PT - PB) * (1 - v / max), v: v, label: DATA[i].label };
        });
        var line = pts.map(function (p, i) { return (i ? 'L' : 'M') + p.x.toFixed(1) + ',' + p.y.toFixed(1); }).join(' ');
        var base = H - PB;
        var area = line + ' L' + pts[pts.length - 1].x.toFixed(1) + ',' + base + ' L' + pts[0].x.toFixed(1) + ',' + base + ' Z';
        var grid = [0, 0.5, 1].map(function (f) {
            var y = PT + (H - PT - PB) * f;
            return '<line x1="' + PL + '" x2="' + (W - PR) + '" y1="' + y + '" y2="' + y + '" class="spd-grid"/>';
        }).join('');
        var r = DATA.length > 45 ? 2 : 3.5;
        var dots = pts.map(function (p) {
            return '<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="' + r + '" class="spd-dot"><title>' +
                p.label + ': ' + fmt(metric, p.v) + '</title></circle>';
        }).join('');
        var mid = pts[Math.floor(pts.length / 2)];
        el.innerHTML =
            '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" preserveAspectRatio="xMidYMid meet" aria-hidden="true">' +
            '<defs><linearGradient id="spdGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#9D6638" stop-opacity="0.3"/><stop offset="100%" stop-color="#9D6638" stop-opacity="0"/></linearGradient></defs>' +
            grid + '<path d="' + area + '" fill="url(#spdGrad)"/><path d="' + line + '" class="spd-line"/>' + dots +
            '<text x="' + PL + '" y="12" class="spd-axis">Peak: ' + fmt(metric, max) + '</text>' +
            '<text x="' + PL + '" y="' + (H - 6) + '" class="spd-axis">' + pts[0].label + '</text>' +
            '<text x="' + mid.x.toFixed(1) + '" y="' + (H - 6) + '" text-anchor="middle" class="spd-axis">' + mid.label + '</text>' +
            '<text x="' + (W - PR) + '" y="' + (H - 6) + '" text-anchor="end" class="spd-axis">' + pts[pts.length - 1].label + '</text>' +
            '</svg>';
    }
    qsa('[data-spd-metric]').forEach(function (b) {
        b.addEventListener('click', function () {
            currentMetric = b.dataset.spdMetric;
            qsa('[data-spd-metric]').forEach(function (x) { x.classList.toggle('is-active', x === b); });
            renderChart(currentMetric);
        });
    });

    /* ---------- init ---------- */
    var hash = (window.location.hash || '').replace('#tab-', '');
    if (hash) activate(hash, false);
    renderChart(currentMetric);
})();