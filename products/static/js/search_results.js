/* =========================================================================
   MARKETSPHERE — SEARCH RESULTS PAGE
   AJAX filtering / sorting / pagination controller.

   This file replaces the old frontend-only filter engine (which filtered
   DOM nodes that already existed on the page) with a server-driven
   controller: every filter, sort, or page change sends a request to the
   backend and swaps in whatever it returns, while keeping the original
   fade/slide/reflow animation language from the previous implementation.

   Sections:
     1. Configuration
     2. DOM Cache
     3. State
     4. Utilities
     5. Loading / Error UI
     6. Animation
     7. Response Parsing (JSON or HTML — isolated so either can be swapped)
     8. Rendering
     9. AJAX Core
    10. Pagination
    11. Filters
    12. Sorting
    13. Search (header search bar)
    14. Cart / Misc delegated interactions
    15. History (URL <-> state)
    16. Initialization
   ========================================================================= */

(function () {
    'use strict';

    /* =====================================================================
       1. CONFIGURATION
       Every endpoint and tunable constant lives here. When the real
       filtering endpoint exists, only ENDPOINTS.search needs to change
       (or a dedicated endpoint can be added alongside it).
       ===================================================================== */
    const CONFIG = {
        ENDPOINTS: {
            // The search results page itself already accepts `q` as a GET
            // param and re-renders this exact template, so it doubles as
            // the AJAX filtering endpoint today. Point this at a dedicated
            // endpoint later without touching anything else in this file.
            search: window.location.pathname
        },

        DEBOUNCE_MS: {
            search: 400,
            price: 300,
            filterBatch: 120
        },

        REQUEST_TIMEOUT_MS: 15000,

        ANIMATION_MS: {
            leave: 280,
            enter: 420,
            move: 550,
            grid: 350,
            stagger: 45
        },

        EASING: 'cubic-bezier(0.2, 0.85, 0.2, 1)',

        TOAST_DURATION_MS: 5000
    };

    /* =====================================================================
       2. DOM CACHE
       ===================================================================== */
    const dom = {};

    function cacheDom() {
        dom.grid = document.getElementById('searchResultsGrid');
        dom.noResultsSection = document.getElementById('noResultsSection');
        dom.resultsCountEl = document.querySelector('.results-count strong');
        dom.queryLabelEl = document.querySelector('.results-count .fs-6');
        dom.breadcrumbQueryEl = document.querySelector('.pd-breadcrumb-wrap .breadcrumb-item.active');
        dom.categoryFilters = document.getElementById('category-filters');
        dom.mobileCategoryFilters = document.getElementById('mobile-category-filters');
        dom.brandFilters = document.getElementById('brand-filters');
        dom.mobileBrandFilters = document.getElementById('mobile-brand-filters');
        dom.sortSelect = document.getElementById('sortBy');
        dom.priceSliderDesktop = document.getElementById('priceRange');
        dom.priceSliderMobile = document.getElementById('priceRangeMobile');
        dom.priceMaxLabel = document.getElementById('priceMaxLabel');
        dom.priceMaxLabelMobile = document.getElementById('priceMaxLabelMobile');
        dom.clearFiltersDesktop = document.getElementById('clearFiltersDesktop');
        dom.clearFiltersMobile = document.getElementById('clearFiltersMobile');
        dom.paginationList = document.querySelector('.search-pagination-wrap .pagination');
        dom.paginationWrap = document.querySelector('.search-pagination-wrap');
        dom.backToTopBtn = document.getElementById('backToTopBtn');
        dom.headerSearchInput = document.querySelector('.site-header input[name="q"]');
        dom.headerSearchForm = dom.headerSearchInput ? dom.headerSearchInput.closest('form') : null;
        dom.resultsAnchor = document.querySelector('.sorting-row');
    }

    function getAllFilterInputs() {
        // Intentionally matches BOTH the desktop sidebar and the mobile
        // offcanvas checkboxes (both use the `.filter-card` wrapper), so
        // the two stay mirrored regardless of which one the user touches.
        return Array.from(document.querySelectorAll('.filter-card .form-check-input[type="checkbox"]'));
    }

    /* =====================================================================
       3. STATE
       Single source of truth for the current filter/sort/page selection.
       Everything else (checkboxes, sliders, URL) is a reflection of this.
       ===================================================================== */
    const state = {
        q: '',
        categories: [],   // slugs
        brands: [],       // slugs
        maxPrice: null,
        stockStates: [],  // 'in_stock' | 'out_of_stock'
        ratingMin: null,
        discountOnly: false,
        sort: 'newest',
        page: 1
    };

    /* =====================================================================
       4. UTILITIES
       ===================================================================== */
    function normalizeText(value) {
        return (value || '').replace(/\s+/g, ' ').trim().toLowerCase();
    }

    function formatPrice(value) {
        return 'Rs. ' + Number(value || 0).toLocaleString('en-IN');
    }

    function parsePrice(value) {
        const cleaned = String(value || '').replace(/[^\d]/g, '');
        return cleaned ? parseInt(cleaned, 10) : 0;
    }

    function escapeHtml(value) {
        const div = document.createElement('div');
        div.textContent = value == null ? '' : String(value);
        return div.innerHTML;
    }

    function debounce(fn, delay) {
        let timer = null;
        return function debounced() {
            const args = arguments;
            window.clearTimeout(timer);
            timer = window.setTimeout(function () {
                fn.apply(null, args);
            }, delay);
        };
    }

    function getCsrfToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function getSectionTitle(input) {
        const card = input.closest('.filter-card');
        const title = card ? card.querySelector('.card-header h6') : null;
        return normalizeText(title ? title.textContent : '');
    }

    function getLabelText(input) {
        const formCheck = input.closest('.form-check');
        const label = formCheck ? formCheck.querySelector('.form-check-label') : null;
        return normalizeText(label ? label.textContent : '');
    }

    function extractSlugFromId(id, prefixes) {
        let value = id;
        prefixes.forEach(function (prefix) {
            if (value.indexOf(prefix) === 0) {
                value = value.slice(prefix.length);
            }
        });
        return value;
    }

    // Keeps the desktop and mobile-offcanvas copies of a filter in sync,
    // matched by section + label text since they render independently.
    function syncFilterPair(source) {
        const section = getSectionTitle(source);
        const label = getLabelText(source);

        getAllFilterInputs().forEach(function (input) {
            if (input === source) return;
            if (getSectionTitle(input) !== section) return;
            if (getLabelText(input) !== label) return;
            input.checked = source.checked;
        });
    }

    /* =====================================================================
       5. LOADING / ERROR UI
       ===================================================================== */
    function ensureLoadingOverlay() {
        let overlay = document.getElementById('srLoadingOverlay');
        if (overlay) return overlay;

        if (!document.getElementById('srLoadingStyles')) {
            const style = document.createElement('style');
            style.id = 'srLoadingStyles';
            style.textContent =
                '.sr-loading-overlay{position:absolute;inset:0;display:flex;' +
                'align-items:center;justify-content:center;background:rgba(247,241,222,0.65);' +
                'z-index:5;opacity:0;pointer-events:none;transition:opacity .2s ease;border-radius:12px;}' +
                '.sr-loading-overlay.is-active{opacity:1;pointer-events:all;}' +
                '.sr-loading-spinner{width:42px;height:42px;border-radius:50%;' +
                'border:3px solid rgba(157,102,56,0.25);border-top-color:#9D6638;' +
                'animation:srSpin .7s linear infinite;}' +
                '@keyframes srSpin{to{transform:rotate(360deg);}}';
            document.head.appendChild(style);
        }

        overlay = document.createElement('div');
        overlay.id = 'srLoadingOverlay';
        overlay.className = 'sr-loading-overlay';
        overlay.innerHTML = '<div class="sr-loading-spinner" aria-hidden="true"></div>';

        const wrap = dom.grid.parentElement;
        if (wrap && getComputedStyle(wrap).position === 'static') {
            wrap.style.position = 'relative';
        }
        if (wrap) wrap.appendChild(overlay);

        return overlay;
    }

    function setFiltersDisabled(disabled) {
        getAllFilterInputs().forEach(function (input) { input.disabled = disabled; });
        [dom.sortSelect, dom.priceSliderDesktop, dom.priceSliderMobile,
        dom.clearFiltersDesktop, dom.clearFiltersMobile].forEach(function (el) {
            if (el) el.disabled = disabled;
        });
        if (dom.paginationList) {
            dom.paginationList.classList.toggle('is-loading', disabled);
        }
    }

    function showLoading() {
        ensureLoadingOverlay().classList.add('is-active');
        if (dom.grid) dom.grid.classList.add('is-updating');
        setFiltersDisabled(true);
    }

    function hideLoading() {
        const overlay = document.getElementById('srLoadingOverlay');
        if (overlay) overlay.classList.remove('is-active');
        setFiltersDisabled(false);
        // grid's is-updating class is cleared by the enter animation itself
    }


    function handleRequestError(err) {
        if (err && err.name === 'AbortError') return; // superseded by a newer request, not a real failure

        console.error('[MarketSphere Search] request failed:', err);

        let message = 'Something went wrong while updating results. Please try again.';
        if (err instanceof TypeError) {
            message = 'Network error — please check your connection and try again.';
        } else if (err && typeof err.message === 'string' && /^server:5/.test(err.message)) {
            message = 'The search service is temporarily unavailable. Please try again shortly.';
        } else if (err && typeof err.message === 'string' && err.message === 'server:404') {
            message = 'The search service could not be reached.';
        } else if (err && err.message === 'timeout') {
            message = 'The request timed out. Please try again.';
        }

        showToast(message, "error");
    }

    /* =====================================================================
       6. ANIMATION
       Because every filter/sort/page change now round-trips to the server,
       the DOM nodes are wholesale replaced rather than reordered in place —
       true FLIP (matching old node -> new node) isn't possible across a
       network request. The same visual language is preserved instead by:
         - fading/scaling the current cards out (staggered, "leave")
         - swapping the grid's HTML
         - fading/scaling the new cards in (staggered, "enter")
       which reproduces fade-out, fade-in, grid reflow and product
       movement without depending on node identity surviving the request.
       ===================================================================== */
    function animateLeaveAll(items, onDone) {
        if (!items.length) {
            onDone();
            return;
        }

        items.forEach(function (item, index) {
            item.style.transition =
                'transform ' + CONFIG.ANIMATION_MS.leave + 'ms ease, opacity ' + CONFIG.ANIMATION_MS.leave + 'ms ease';
            item.style.transitionDelay = Math.min(index * 15, 150) + 'ms';
            item.style.transform = 'scale(0.96) translateY(6px)';
            item.style.opacity = '0';
        });

        window.setTimeout(onDone, CONFIG.ANIMATION_MS.leave + 170);
    }

    function animateEnter(items) {
        if (!items.length) return;

        items.forEach(function (item) {
            item.classList.add('search-result-item', 'is-entering');
            item.style.transition = 'none';
            item.style.opacity = '0';
            item.style.transform = 'translate3d(0, 14px, 0) scale(0.98)';
        });

        // Force a reflow so the browser commits the "before" state before animating.
        void dom.grid.offsetHeight;

        items.forEach(function (item, index) {
            const delay = Math.min(index * CONFIG.ANIMATION_MS.stagger, 260);

            window.setTimeout(function () {
                item.style.transition =
                    'transform ' + CONFIG.ANIMATION_MS.move + 'ms ' + CONFIG.EASING +
                    ', opacity ' + CONFIG.ANIMATION_MS.enter + 'ms ease';
                item.style.opacity = '1';
                item.style.transform = 'translate3d(0, 0, 0) scale(1)';

                window.setTimeout(function () {
                    item.classList.remove('is-entering');
                    item.style.transition = '';
                    item.style.transform = '';
                    item.style.opacity = '';
                }, CONFIG.ANIMATION_MS.move);
            }, delay);
        });

        window.setTimeout(function () {
            dom.grid.classList.remove('is-updating');
        }, CONFIG.ANIMATION_MS.grid);
    }

    function scrollToResultsTop() {
        const target = dom.resultsAnchor || dom.grid;
        if (!target) return;
        const top = target.getBoundingClientRect().top + window.scrollY - 110;
        window.scrollTo({ top: Math.max(top, 0), behavior: 'smooth' });
    }

    /* =====================================================================
       7. RESPONSE PARSING
       Normalizes either a JSON API response or an HTML partial/full-page
       response into one shared shape so the rest of the code never has to
       care which one the backend is currently returning.
       ===================================================================== */
    async function parseResponse(response) {
        const contentType = response.headers.get('content-type') || '';

        if (contentType.indexOf('application/json') !== -1) {
            return normalizeJsonPayload(await response.json());
        }

        return normalizeHtmlPayload(await response.text());
    }

    function normalizeJsonPayload(data) {
        // Supports either pre-rendered fragments or raw product objects.
        const productsHTML = data.products_html
            || (Array.isArray(data.products) ? data.products.map(renderProductCard).join('') : '');

        return {
            productsHTML: productsHTML,
            count: typeof data.count === 'number'
                ? data.count
                : (Array.isArray(data.products) ? data.products.length : null),
            paginationHTML: data.pagination_html || null,
            categoryHTML: data.category_html || null,
            mobileCategoryHTML: data.mobile_category_html || null,
            brandHTML: data.brand_html || null,
            mobileBrandHTML: data.mobile_brand_html || null,
            currentPage: data.page || state.page,
            totalPages: data.num_pages || null,
            hasResults: productsHTML.trim().length > 0
        };
    }

    function normalizeHtmlPayload(html) {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const newGrid = doc.getElementById('searchResultsGrid');
        const newCountEl = doc.querySelector('.results-count strong');
        const newPaginationList = doc.querySelector('.search-pagination-wrap .pagination');
        const newPaginationWrap = doc.querySelector('.search-pagination-wrap');
        const newCategoryFilters = doc.getElementById('category-filters');
        const newMobileCategoryFilters = doc.getElementById('mobile-category-filters');
        const newBrandFilters = doc.getElementById('brand-filters');
        const newMobileBrandFilters = doc.getElementById('mobile-brand-filters');

        return {
            productsHTML: newGrid ? newGrid.innerHTML : '',
            count: newCountEl ? (parseInt(newCountEl.textContent, 10) || 0) : null,
            paginationHTML: newPaginationList ? newPaginationList.innerHTML : null,
            categoryHTML: newCategoryFilters ? newCategoryFilters.innerHTML : null,
            mobileCategoryHTML: newMobileCategoryFilters ? newMobileCategoryFilters.innerHTML : null,
            brandHTML: newBrandFilters ? newBrandFilters.innerHTML : null,
            mobileBrandHTML: newMobileBrandFilters ? newMobileBrandFilters.innerHTML : null,
            hasPagination: !!newPaginationWrap && !newPaginationWrap.classList.contains('d-none'),
            currentPage: state.page,
            totalPages: null,
            hasResults: !!(newGrid && newGrid.children.length > 0)
        };
    }

    // Client-side product card renderer used only when the backend sends
    // raw product objects (JSON path) instead of pre-rendered HTML.
    function renderProductCard(product) {
        const price = product.price;
        const discount = product.discount_price;
        const hasDiscount = discount != null && Number(discount) < Number(price);
        const discountPercent = hasDiscount
            ? Math.round(100 - (Number(discount) / Number(price)) * 100)
            : 0;
        const imageUrl = product.image_url
            || (product.images && product.images[0] && product.images[0].url)
            || '';
        const wishlisted = Boolean(product.is_wishlisted);
        const stock = Number(product.stock_quantity || 0);
        const productUrl = product.url || '#';

        let stockBadge = '<span class="stock-badge in-stock">In Stock</span>';
        if (stock <= 0) {
            stockBadge = '<span class="stock-badge out-of-stock">Out of Stock</span>';
        } else if (stock <= 80) {
            stockBadge = '<span class="stock-badge low-stock">Only ' + stock + ' left</span>';
        }

        return (
            '<div class="col-lg-3 col-md-6 col-6" data-search-item-id="' + escapeHtml(product.id) + '">' +
            '<div class="product-card">' +
            '<div class="product-card-media">' +
            (hasDiscount ? '<span class="badge-discount">-' + discountPercent + '%</span>' : '') +
            '<button class="wishlist-btn' + (wishlisted ? ' active' : '') + '" type="button" ' +
            'data-product-slug="' + escapeHtml(product.slug) + '" ' +
            'aria-label="' + (wishlisted ? 'Remove from wishlist' : 'Add to wishlist') + '">' +
            '<i class="bi ' + (wishlisted ? 'bi-heart-fill' : 'bi-heart') + '"></i>' +
            '</button>' +
            (product.category_name
                ? '<span class="product-category-badge">' + escapeHtml(product.category_name) + '</span>'
                : '') +
            '<a href="' + escapeHtml(productUrl) + '" class="product-image-placeholder">' +
            (imageUrl
                ? '<img src="' + escapeHtml(imageUrl) + '" alt="' + escapeHtml(product.name) + '">'
                : '<i class="bi bi-image"></i>') +
            '</a>' +
            '</div>' +
            '<div class="product-card-body">' +
            '<span class="product-brand">' +
            (product.brand_name ? escapeHtml(product.brand_name) : 'No Brand') +
            '</span>' +
            '<h6 class="product-name"><a href="' + escapeHtml(productUrl) + '">' +
            escapeHtml(product.name) + '</a></h6>' +
            '<div class="product-rating">' +
            '<i class="bi bi-star-fill"></i><i class="bi bi-star-fill"></i>' +
            '<i class="bi bi-star-fill"></i><i class="bi bi-star-fill"></i>' +
            '<i class="bi bi-star-half"></i>' +
            '<span>(' + (product.review_count || 0) + ')</span>' +
            '</div>' +
            '<div class="product-price">' +
            (hasDiscount
                ? '<span class="price-current">Rs. ' + discount + '</span>' +
                '<span class="price-original">Rs. ' + price + '</span>'
                : '<span class="price-current">Rs. ' + price + '</span>') +
            '</div>' +
            stockBadge +
            '<button class="btn add-to-cart-btn w-100" ' + (stock <= 0 ? 'disabled' : '') +
            ' data-add-url="' + escapeHtml(product.add_to_cart_url || '') + '">' +
            '<i class="bi bi-cart4"></i> Add to Cart' +
            '</button>' +
            '</div>' +
            '</div>' +
            '</div>'
        );
    }

    /* =====================================================================
       8. RENDERING
       ===================================================================== */
    function toggleNoResults(show) {
        if (dom.noResultsSection) dom.noResultsSection.classList.toggle('d-none', !show);
        if (dom.grid) dom.grid.classList.toggle('d-none', show);
    }

    function updateCounts(payload) {
        if (dom.resultsCountEl && typeof payload.count === 'number') {
            dom.resultsCountEl.textContent = String(payload.count);
        }
        if (dom.queryLabelEl) {
            dom.queryLabelEl.textContent = '"' + (state.q || '') + '"';
        }
        if (dom.breadcrumbQueryEl) {
            dom.breadcrumbQueryEl.textContent = state.q || 'Search results';
        }
    }

    function updateProducts(payload) {
        const oldItems = dom.grid ? Array.from(dom.grid.children) : [];

        const applySwap = function () {
            if (!dom.grid) return;
            dom.grid.innerHTML = payload.productsHTML || '';
            const newItems = Array.from(dom.grid.children);
            const hasResults = payload.hasResults != null ? payload.hasResults : newItems.length > 0;

            toggleNoResults(!hasResults);
            animateEnter(newItems);
        };

        if (!dom.grid) return;
        animateLeaveAll(oldItems, applySwap);
    }

    function updateDynamicFilters(payload) {
        [
            [dom.categoryFilters, payload.categoryHTML],
            [dom.mobileCategoryFilters, payload.mobileCategoryHTML],
            [dom.brandFilters, payload.brandHTML],
            [dom.mobileBrandFilters, payload.mobileBrandHTML]
        ].forEach(function (entry) {
            if (entry[0] && entry[1] != null) entry[0].innerHTML = entry[1];
        });

        // Re-apply active selections to the newly-rendered checkbox elements.
        applyStateToUI();
    }

    /* =====================================================================
       9. AJAX CORE
       ===================================================================== */
    let activeController = null;

    function buildQueryParams(s) {
        const params = new URLSearchParams();
        if (s.q) params.set('q', s.q);
        s.categories.forEach(function (slug) { params.append('category', slug); });
        s.brands.forEach(function (slug) { params.append('brand', slug); });
        if (s.maxPrice) params.set('max_price', String(s.maxPrice));
        s.stockStates.forEach(function (st) { params.append('availability', st); });
        if (s.ratingMin) params.set('rating_min', String(s.ratingMin));
        if (s.discountOnly) params.set('discount', '1');
        if (s.sort && s.sort !== 'newest') params.set('sort', s.sort);
        if (s.page && s.page > 1) params.set('page', String(s.page));
        return params;
    }

    async function loadProducts(options) {
        const opts = options || {};
        const pushHistory = opts.pushHistory !== false;
        const scroll = !!opts.scroll;

        if (activeController) {
            activeController.abort();
        }
        const controller = new AbortController();
        activeController = controller;

        showLoading();

        const params = buildQueryParams(state);
        const url = CONFIG.ENDPOINTS.search + (params.toString() ? '?' + params.toString() : '');

        const timeoutId = window.setTimeout(function () {
            controller.abort();
        }, CONFIG.REQUEST_TIMEOUT_MS);

        try {
            const response = await fetch(url, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json, text/html;q=0.9'
                },
                signal: controller.signal
            });

            window.clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error('server:' + response.status);
            }

            const payload = await parseResponse(response);

            updateProducts(payload);
            updateDynamicFilters(payload);
            updateCounts(payload);
            updatePagination(payload);

            if (pushHistory) updateUrl(params);
            if (scroll) scrollToResultsTop();
        } catch (err) {
            window.clearTimeout(timeoutId);
            handleRequestError(err);
        } finally {
            if (controller === activeController) {
                hideLoading();
                activeController = null;
            }
        }
    }

    const debouncedLoad = debounce(function () {
        loadProducts({ pushHistory: true, scroll: false });
    }, CONFIG.DEBOUNCE_MS.filterBatch);

    /* =====================================================================
       10. PAGINATION
       ===================================================================== */
    function paginationItemMarkup(page, disabled, active, htmlLabel) {
        const classes = ['page-item'];
        if (disabled) classes.push('disabled');
        if (active) classes.push('active');
        const attrs = disabled ? 'tabindex="-1" aria-disabled="true"' : '';
        return '<li class="' + classes.join(' ') + '"><a class="page-link" href="#" data-page="' +
            page + '" ' + attrs + '>' + htmlLabel + '</a></li>';
    }

    function buildPaginationMarkup(current, total) {
        const items = [];
        items.push(paginationItemMarkup(
            Math.max(current - 1, 1), current <= 1, false,
            '<i class="bi bi-chevron-left"></i> Previous'
        ));

        const start = Math.max(1, current - 2);
        const end = Math.min(total, current + 2);
        for (let page = start; page <= end; page++) {
            items.push(paginationItemMarkup(page, false, page === current, String(page)));
        }

        items.push(paginationItemMarkup(
            Math.min(current + 1, total), current >= total, false,
            'Next <i class="bi bi-chevron-right"></i>'
        ));

        return items.join('');
    }

    function updatePagination(payload) {
        if (!dom.paginationList) return;

        if (payload.paginationHTML != null) {
            dom.paginationList.innerHTML = payload.paginationHTML;
            if (dom.paginationWrap) {
                dom.paginationWrap.classList.toggle('d-none', payload.hasPagination === false);
            }
            return;
        }

        if (payload.totalPages) {
            dom.paginationList.innerHTML = buildPaginationMarkup(payload.currentPage || state.page, payload.totalPages);
            if (dom.paginationWrap) dom.paginationWrap.classList.remove('d-none');
        } else {
            dom.paginationList.innerHTML = '';
            if (dom.paginationWrap) dom.paginationWrap.classList.add('d-none');
        }
    }

    function goToPage(page) {
        if (!Number.isFinite(page) || page < 1 || page === state.page) return;
        state.page = page;
        loadProducts({ pushHistory: true, scroll: true });
    }

    function bindPaginationEvents() {
        if (!dom.paginationList) return;

        // Event delegation: works for both the initial server-rendered
        // pagination markup and anything swapped in afterwards.
        dom.paginationList.addEventListener('click', function (e) {
            const link = e.target.closest('.page-link');
            if (!link) return;
            e.preventDefault();

            const item = link.closest('.page-item');
            if (item && (item.classList.contains('disabled') || item.classList.contains('active'))) return;

            const page = parseInt(link.dataset.page, 10);
            goToPage(page);
        });
    }

    /* =====================================================================
       11. FILTERS
       ===================================================================== */
    function readFiltersFromDOM() {
        const categories = [];
        const brands = [];
        const stockStates = new Set();
        const ratingThresholds = [];
        let discountOnly = false;

        getAllFilterInputs().forEach(function (input) {
            if (!input.checked) return;

            const section = getSectionTitle(input);

            if (section === 'categories') {
                categories.push(extractSlugFromId(input.id, ['m-cat-', 'cat-']));
            } else if (section === 'brand') {
                brands.push(extractSlugFromId(input.id, ['m-brand-', 'brand-']));
            } else if (section === 'availability') {
                const label = getLabelText(input);
                if (label === 'in stock') stockStates.add('in_stock');
                else if (label === 'out of stock') stockStates.add('out_of_stock');
            } else if (section === 'rating') {
                const rating = parseInt(input.id.split('-').pop(), 10);
                if (!Number.isNaN(rating)) ratingThresholds.push(rating);
            } else if (section === 'discount') {
                discountOnly = true;
            }
        });

        return {
            categories: Array.from(new Set(categories)),
            brands: Array.from(new Set(brands)),
            stockStates: Array.from(stockStates),
            // Extracts the highest selected rating (e.g., 4) from the cascaded selection
            ratingMin: ratingThresholds.length ? Math.max.apply(null, ratingThresholds) : null,
            discountOnly: discountOnly
        };
    }

    function bindFilterCheckboxEvents() {
        // Delegated on the document so both the desktop sidebar and the
        // mobile offcanvas are covered with a single listener.
        document.addEventListener('change', function (e) {
            const input = e.target.closest('.filter-card .form-check-input[type="checkbox"]');
            if (!input) return;

            const section = getSectionTitle(input);

            if (section === 'rating') {
                const clickedRating = parseInt(input.id.split('-').pop(), 10);
                const isChecked = input.checked;

                // Cascade: Check all ratings below/equal to clicked, or uncheck all
                getAllFilterInputs().forEach(function (otherInput) {
                    if (getSectionTitle(otherInput) === 'rating') {
                        const otherRating = parseInt(otherInput.id.split('-').pop(), 10);
                        if (isChecked) {
                            otherInput.checked = (otherRating <= clickedRating);
                        } else {
                            otherInput.checked = false;
                        }
                    }
                });
            } else {
                syncFilterPair(input);
            }

            Object.assign(state, readFiltersFromDOM());
            state.page = 1;
            debouncedLoad();
        });
    }
    function getCurrentMaxPrice() {
        const slider = dom.priceSliderDesktop || dom.priceSliderMobile;
        return slider ? parsePrice(slider.value) : null;
    }

    function syncPriceSliders(source) {
        if (source === dom.priceSliderDesktop && dom.priceSliderMobile) {
            dom.priceSliderMobile.value = source.value;
            if (dom.priceMaxLabelMobile) dom.priceMaxLabelMobile.textContent = formatPrice(source.value);
        } else if (source === dom.priceSliderMobile && dom.priceSliderDesktop) {
            dom.priceSliderDesktop.value = source.value;
            if (dom.priceMaxLabel) dom.priceMaxLabel.textContent = formatPrice(source.value);
        }
    }

    const debouncedPriceLoad = debounce(function () {
        state.maxPrice = getCurrentMaxPrice();
        state.page = 1;
        loadProducts({ pushHistory: true, scroll: false });
    }, CONFIG.DEBOUNCE_MS.price);

    function bindPriceSlider(slider, label) {
        if (!slider) return;

        const updateLabel = function () {
            if (label) label.textContent = formatPrice(slider.value);
        };
        updateLabel();

        slider.addEventListener('input', function () {
            updateLabel();
            syncPriceSliders(slider);
            debouncedPriceLoad();
        });
    }

    function clearFilters() {
        getAllFilterInputs().forEach(function (input) { input.checked = false; });

        [dom.priceSliderDesktop, dom.priceSliderMobile].forEach(function (slider) {
            if (!slider) return;
            slider.value = slider.getAttribute('value') || slider.max;
        });
        if (dom.priceMaxLabel && dom.priceSliderDesktop) {
            dom.priceMaxLabel.textContent = formatPrice(dom.priceSliderDesktop.value);
        }
        if (dom.priceMaxLabelMobile && dom.priceSliderMobile) {
            dom.priceMaxLabelMobile.textContent = formatPrice(dom.priceSliderMobile.value);
        }
        if (dom.sortSelect) dom.sortSelect.value = 'newest';
        if (dom.headerSearchInput) dom.headerSearchInput.value = '';

        state.q = '';
        state.categories = [];
        state.brands = [];
        state.stockStates = [];
        state.ratingMin = null;
        state.maxPrice = null;
        state.discountOnly = false;
        state.sort = 'newest';
        state.page = 1;

        loadProducts({ pushHistory: true, scroll: false });
    }

    function bindClearFiltersEvents() {
        [dom.clearFiltersDesktop, dom.clearFiltersMobile].forEach(function (btn) {
            if (btn) btn.addEventListener('click', clearFilters);
        });
    }

    /* =====================================================================
       12. SORTING
       ===================================================================== */
    function bindSortEvents() {
        if (!dom.sortSelect) return;

        dom.sortSelect.addEventListener('change', function () {
            state.sort = dom.sortSelect.value;
            state.page = 1;
            loadProducts({ pushHistory: true, scroll: false });
        });
    }

    /* =====================================================================
       13. SEARCH (header search bar)
       The header search form (in base.html) normally submits a full GET
       navigation. It's hijacked here — only on this page — into the same
       AJAX pipeline so searching never triggers a reload either.
       ===================================================================== */
    function bindHeaderSearch() {
        if (!dom.headerSearchForm || !dom.headerSearchInput) return;

        if (state.q) dom.headerSearchInput.value = state.q;

        dom.headerSearchForm.addEventListener('submit', function (e) {
            e.preventDefault();
            state.q = dom.headerSearchInput.value.trim();
            state.categories = [];
            state.brands = [];
            state.page = 1;
            loadProducts({ pushHistory: true, scroll: false });
        });

        dom.headerSearchInput.addEventListener('input', debounce(function () {
            state.q = dom.headerSearchInput.value.trim();
            state.categories = [];
            state.brands = [];
            state.page = 1;
            loadProducts({ pushHistory: true, scroll: false });
        }, CONFIG.DEBOUNCE_MS.search));
    }

    /* =====================================================================
       14. CART / MISC DELEGATED INTERACTIONS
       Delegated on the grid container so it keeps working for every batch
       of AJAX-loaded product cards without rebinding listeners per card
       (avoids duplicate listeners / memory leaks on repeated filtering).
       Wishlist buttons are intentionally NOT handled here — they're
       already covered globally by the document-level delegation in
       static/js/scripts.js, which applies to dynamically inserted buttons
       automatically.
       ===================================================================== */
    async function handleAddToCart(btn) {
        const url = btn.dataset.addUrl;
        if (!url || btn.classList.contains('is-loading')) return;

        const originalHTML = btn.innerHTML;
        btn.disabled = true;
        btn.classList.add('is-loading');

        try {
            const response = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) throw new Error('add-to-cart:' + response.status);

            const data = await response.json();
            btn.innerHTML = '<i class="bi bi-check2"></i> Added';

            const cartBadge = document.getElementById('cartCounter');
            if (cartBadge && typeof data.cart_count !== 'undefined') {
                cartBadge.textContent = data.cart_count;
            }
        } catch (err) {
            console.error('[MarketSphere Search] add to cart failed:', err);
            showToast('Could not add this item to your cart. Please try again.', "error");
        } finally {
            window.setTimeout(function () {
                btn.innerHTML = originalHTML;
                btn.disabled = false;
                btn.classList.remove('is-loading');
            }, 1500);
        }
    }

    function bindGridDelegatedEvents() {
        if (!dom.grid) return;

        dom.grid.addEventListener('click', function (e) {
            const addToCartBtn = e.target.closest('.add-to-cart-btn:not([disabled])');
            if (addToCartBtn) {
                handleAddToCart(addToCartBtn);
            }
        });
    }

    function bindBackToTop() {
        if (!dom.backToTopBtn) return;

        const toggle = function () {
            dom.backToTopBtn.classList.toggle('visible', window.scrollY > 400);
        };

        window.addEventListener('scroll', toggle);
        toggle();

        dom.backToTopBtn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    /* =====================================================================
       15. HISTORY (URL <-> STATE)
       ===================================================================== */
    function updateUrl(params) {
        const query = params.toString();
        const url = window.location.pathname + (query ? '?' + query : '');
        window.history.pushState({ srFilters: true }, '', url);
    }

    function readStateFromUrl() {
        const params = new URLSearchParams(window.location.search);

        state.q = params.get('q') || '';
        state.categories = params.getAll('category');
        state.brands = params.getAll('brand');
        state.maxPrice = params.get('max_price') ? parseInt(params.get('max_price'), 10) : null;
        state.stockStates = params.getAll('availability');
        state.ratingMin = params.get('rating_min') ? parseInt(params.get('rating_min'), 10) : null;
        state.discountOnly = params.get('discount') === '1';
        state.sort = params.get('sort') || 'newest';
        state.page = params.get('page') ? (parseInt(params.get('page'), 10) || 1) : 1;
    }

    function applyStateToUI() {
        getAllFilterInputs().forEach(function (input) {
            const section = getSectionTitle(input);

            if (section === 'categories') {
                const slug = extractSlugFromId(input.id, ['m-cat-', 'cat-']);
                input.checked = state.categories.indexOf(slug) !== -1;
            } else if (section === 'brand') {
                const slug = extractSlugFromId(input.id, ['m-brand-', 'brand-']);
                input.checked = state.brands.indexOf(slug) !== -1;
            } else if (section === 'availability') {
                const label = getLabelText(input);
                input.checked =
                    (label === 'in stock' && state.stockStates.indexOf('in_stock') !== -1) ||
                    (label === 'out of stock' && state.stockStates.indexOf('out_of_stock') !== -1);
            } else if (section === 'rating') {
                const rating = parseInt(input.id.split('-').pop(), 10);
                // Changed from '===' to '<=' to maintain the cascade on page load
                input.checked = state.ratingMin != null && rating <= state.ratingMin;
            }
        });

        if (dom.sortSelect) dom.sortSelect.value = state.sort;

        if (state.maxPrice) {
            [dom.priceSliderDesktop, dom.priceSliderMobile].forEach(function (slider) {
                if (slider) slider.value = state.maxPrice;
            });
        }
        if (dom.priceMaxLabel && dom.priceSliderDesktop) {
            dom.priceMaxLabel.textContent = formatPrice(dom.priceSliderDesktop.value);
        }
        if (dom.priceMaxLabelMobile && dom.priceSliderMobile) {
            dom.priceMaxLabelMobile.textContent = formatPrice(dom.priceSliderMobile.value);
        }

        if (dom.headerSearchInput && state.q) {
            dom.headerSearchInput.value = state.q;
        }
    }

    function handlePopState() {
        readStateFromUrl();
        applyStateToUI();
        loadProducts({ pushHistory: false, scroll: false });
    }

    /* =====================================================================
       16. INITIALIZATION
       Reads state from the URL and syncs the UI to it WITHOUT firing a
       network request — the products already on the page (server-rendered)
       are treated as "page 1" of the current filter set.
       ===================================================================== */
    function init() {
        cacheDom();

        if (!dom.grid) return; // nothing to control on this page

        readStateFromUrl();
        applyStateToUI();

        bindFilterCheckboxEvents();
        bindPriceSlider(dom.priceSliderDesktop, dom.priceMaxLabel);
        bindPriceSlider(dom.priceSliderMobile, dom.priceMaxLabelMobile);
        bindSortEvents();
        bindClearFiltersEvents();
        bindHeaderSearch();
        bindPaginationEvents();
        bindGridDelegatedEvents();
        bindBackToTop();

        window.addEventListener('popstate', handlePopState);

        // Sync empty-state visibility for the initial server-rendered
        // markup — purely a DOM check, no request involved.
        toggleNoResults(dom.grid.children.length === 0);

        // Exposed for debugging / future integration (e.g. "load more").
        window.MarketSphereSearchResults = {
            getState: function () { return Object.assign({}, state); },
            reload: function () { loadProducts({ pushHistory: true, scroll: false }); },
            goToPage: goToPage
        };
    }

    document.addEventListener('DOMContentLoaded', init);
})();
