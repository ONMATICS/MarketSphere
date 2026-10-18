/* =========================================================
   MARKETSPHERE — ADMIN DASHBOARD HOME
   Frontend-only behavior for admin_panel/templates/admin_dashboard.html.
   No fetch, no AJAX, no backend calls, no external libraries.

   Responsibilities:
     1. Current date display
     2. Animated stat counters
     3. Scroll-reveal fade-in
     4. Admin sales overview — live database data
     5. Top category bar fill animation
     6. Quick action / task row ripple feedback
     7. Export report placeholder feedback
   ========================================================= */

(function () {
    'use strict';

    /* =====================================================
       1. CURRENT DATE
       ===================================================== */
    function initCurrentDate() {
        var dateEl = document.getElementById('adhCurrentDate');
        if (!dateEl) return;

        var now = new Date();
        dateEl.textContent = now.toLocaleDateString(undefined, {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
            year: 'numeric'
        });
    }

    /* =====================================================
       2. ANIMATED STAT COUNTERS
       ===================================================== */
    function animateCounter(el) {
        var target = parseFloat(el.getAttribute('data-count-to'));
        if (!isFinite(target)) return;

        var prefix = el.getAttribute('data-prefix') || '';
        var duration = 900;
        var startTime = null;

        function easeOutCubic(t) {
            return 1 - Math.pow(1 - t, 3);
        }

        function step(timestamp) {
            if (startTime === null) startTime = timestamp;
            var elapsed = timestamp - startTime;
            var progress = Math.min(elapsed / duration, 1);
            var eased = easeOutCubic(progress);
            var current = Math.round(target * eased);

            el.textContent = prefix + current.toLocaleString('en-IN');

            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                el.textContent = prefix + target.toLocaleString('en-IN');
            }
        }

        window.requestAnimationFrame(step);
    }

    function initCounters() {
        var counters = document.querySelectorAll('.adh-stat-value[data-count-to]');
        if (!counters.length) return;

        if (!('IntersectionObserver' in window)) {
            counters.forEach(animateCounter);
            return;
        }

        var observer = new IntersectionObserver(function (entries, obs) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.4 });

        counters.forEach(function (el) {
            observer.observe(el);
        });
    }

    /* =====================================================
       3. SCROLL REVEAL
       ===================================================== */
    function initScrollReveal() {
        var revealTargets = document.querySelectorAll('.adh-reveal');
        if (!revealTargets.length) return;

        if (!('IntersectionObserver' in window)) {
            revealTargets.forEach(function (el) { el.classList.add('is-visible'); });
            return;
        }

        var observer = new IntersectionObserver(function (entries, obs) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;

                var el = entry.target;
                var delay = Math.min(Array.prototype.indexOf.call(revealTargets, el) * 35, 210);

                window.setTimeout(function () {
                    el.classList.add('is-visible');
                }, delay);

                obs.unobserve(el);
            });
        }, { threshold: 0.08 });

        revealTargets.forEach(function (el) {
            observer.observe(el);
        });
    }

    /* =====================================================
       4. ADMIN SALES OVERVIEW — LIVE DATABASE DATA
       ===================================================== */
    function initAdminSalesChart() {
        const rangeSelect = document.getElementById("adhRangeSelect");
        const chartBars = document.getElementById("adhChartBars");
        const chartLabels = document.getElementById("adhChartLabels");
        const chartTotal = document.getElementById("adhChartTotal");
        const chartCaption = document.getElementById("adhChartCaption");
        const chartDataElement = document.getElementById("adhSalesChartData");

        if (
            !rangeSelect ||
            !chartBars ||
            !chartLabels ||
            !chartTotal ||
            !chartCaption ||
            !chartDataElement
        ) {
            return;
        }

        let chartData;

        try {
            chartData = JSON.parse(chartDataElement.textContent);
        } catch (error) {
            console.error("Unable to read admin sales chart data.", error);
            return;
        }

        const rangeCaptions = {
            today: "Revenue throughout today",
            "7d": "Revenue for the last 7 days",
            "30d": "Revenue for the last 30 days",
            "12m": "Revenue for the last 12 months",
        };

        const currencyFormatter = new Intl.NumberFormat("en-PK", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });

        function formatCurrency(value) {
            return `Rs. ${currencyFormatter.format(value)}`;
        }

        function renderChart(range) {
            const entries = chartData[range] || [];

            chartBars.replaceChildren();
            chartLabels.replaceChildren();

            if (!entries.length) {
                chartTotal.textContent = formatCurrency(0);
                chartCaption.textContent = "No chart data available.";
                return;
            }

            const totalRevenue = entries.reduce(
                (total, entry) => total + Number(entry.revenue || 0),
                0
            );

            const maxRevenue = Math.max(
                ...entries.map(entry => Number(entry.revenue || 0)),
                0
            );

            chartTotal.textContent = formatCurrency(totalRevenue);
            chartCaption.textContent = rangeCaptions[range] || "";

            entries.forEach((entry, index) => {
                const revenue = Number(entry.revenue || 0);

                /*
                 * Scale each bar relative to the highest revenue
                 * in the selected period.
                 *
                 * A zero-revenue bar remains visible through CSS.
                 */
                const height = maxRevenue > 0
                    ? (revenue / maxRevenue) * 100
                    : 0;

                const bar = document.createElement("span");

                bar.className = "adh-chart-bar";
                bar.style.setProperty("--adh-bar-h", `${height}%`);

                bar.title = `${entry.label}: ${formatCurrency(revenue)}`;

                bar.setAttribute(
                    "aria-label",
                    `${entry.label}: ${formatCurrency(revenue)}`
                );

                chartBars.appendChild(bar);

                const label = document.createElement("span");

                label.className = "adh-chart-label";
                label.textContent = entry.label;

                /*
                 * Prevent 30 daily labels from becoming crowded.
                 * The chart still contains every daily bar.
                 */
                if (range === "30d" && index % 5 !== 0 && index !== entries.length - 1) {
                    label.textContent = "";
                }

                if (range === "today" && index % 3 !== 0) {
                    label.textContent = "";
                }

                label.title = entry.label;

                chartLabels.appendChild(label);
            });
        }

        rangeSelect.addEventListener("change", function () {
            renderChart(this.value);
        });

        renderChart(rangeSelect.value);
    }

    /* =====================================================
       5. TOP CATEGORY BAR FILL
       ===================================================== */
    function initCategoryBars() {
        var fills = document.querySelectorAll('.adh-category-bar-fill');
        if (!fills.length) return;

        if (!('IntersectionObserver' in window)) {
            fills.forEach(function (el) { el.classList.add('is-filled'); });
            return;
        }

        var observer = new IntersectionObserver(function (entries, obs) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-filled');
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.3 });

        fills.forEach(function (el) {
            observer.observe(el);
        });
    }

    /* =====================================================
       6. RIPPLE FEEDBACK (quick actions + task rows)
       ===================================================== */
    function bindRipple(el) {
        el.addEventListener('click', function (e) {
            var rect = el.getBoundingClientRect();
            var ripple = document.createElement('span');
            var size = Math.max(rect.width, rect.height);

            ripple.className = 'adh-ripple';
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';

            el.style.position = el.style.position || 'relative';
            el.style.overflow = 'hidden';
            el.appendChild(ripple);

            window.requestAnimationFrame(function () {
                ripple.style.transition = 'transform 0.5s ease, opacity 0.6s ease';
                ripple.style.transform = 'scale(2.4)';
                ripple.style.opacity = '0';
            });

            window.setTimeout(function () {
                ripple.remove();
            }, 600);
        });
    }

    function initRipples() {
        document.querySelectorAll('.adh-action-card, .adh-task-btn').forEach(bindRipple);
    }

    /* =====================================================
       7. EXPORT REPORT PLACEHOLDER
       ===================================================== */
    function initExportButton() {
        var btn = document.getElementById('adhExportBtn');
        if (!btn) return;

        btn.addEventListener('click', function () {
            var original = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-3.5-7.1"></path></svg> Preparing…';

            window.setTimeout(function () {
                btn.disabled = false;
                btn.innerHTML = original;
                window.alert('Report export isn\u2019t available yet \u2014 check back soon.');
            }, 700);
        });
    }

    /* =====================================================
       INIT
       ===================================================== */
    document.addEventListener('DOMContentLoaded', function () {
        initCurrentDate();
        initCounters();
        initScrollReveal();
        initAdminSalesChart(); // Replaced the two old chart initialization calls
        initCategoryBars();
        initRipples();
        initExportButton();
    });
})();