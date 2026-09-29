/* ==========================================================================
   MARKETSPHERE ADMIN — PRODUCT DETAIL / MODERATION CONSOLE (detail.js)
   Vanilla JS, IIFE-scoped. Page-scoped to admin_dashboard/catalog/products/detail.html.
   All interactions are frontend-only / simulated — no fetch()/AJAX calls.
   Backend wiring points are marked with // TODO(backend).
   ========================================================================== */

(function () {
    "use strict";

    var page = document.getElementById("apdPage");
    if (!page) return;

    /* ================= UTILITIES ================= */
    function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function qsa(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
    function on(el, evt, handler) { if (el) el.addEventListener(evt, handler); }
    function delegate(root, evt, selector, handler) {
        on(root, evt, function (e) {
            var target = e.target.closest(selector);
            if (target && root.contains(target)) handler(e, target);
        });
    }

    /* ================= SCROLL REVEAL ================= */
    (function initScrollReveal() {
        var items = qsa(".apd-reveal", page);
        if (!("IntersectionObserver" in window) || items.length === 0) {
            items.forEach(function (el) { el.classList.add("is-visible"); });
            return;
        }
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.08, rootMargin: "0px 0px -40px 0px" });
        items.forEach(function (el) { observer.observe(el); });
    })();

    /* ================= ANIMATED COUNTERS ================= */
    (function initCounters() {
        var counters = qsa("[data-count-to]", page);
        if (counters.length === 0) return;

        function animateCounter(el) {
            var target = parseFloat(el.getAttribute("data-count-to")) || 0;
            var decimals = parseInt(el.getAttribute("data-decimal"), 10) || 0;
            var prefix = el.getAttribute("data-prefix") || "";
            var suffix = el.textContent.trim().endsWith("%") ? "%" : "";
            var duration = 900;
            var start = null;

            function step(ts) {
                if (!start) start = ts;
                var progress = Math.min((ts - start) / duration, 1);
                var eased = 1 - Math.pow(1 - progress, 3);
                var value = target * eased;
                var formatted = decimals > 0 ? value.toFixed(decimals) : Math.round(value).toLocaleString("en-US");
                el.textContent = prefix + formatted + suffix;
                if (progress < 1) requestAnimationFrame(step);
                else el.textContent = prefix + (decimals > 0 ? target.toFixed(decimals) : target.toLocaleString("en-US")) + suffix;
            }
            requestAnimationFrame(step);
        }

        if (!("IntersectionObserver" in window)) {
            counters.forEach(animateCounter);
            return;
        }
        var counterObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    counterObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.4 });
        counters.forEach(function (el) { counterObserver.observe(el); });
    })();

    /* ================= TOASTS ================= */
    // var toastContainer = document.getElementById("apdToastContainer");
    // function showToast(message, type) {
    //     if (!toastContainer || !message) return;
    //     var toast = document.createElement("div");
    //     toast.className = "apd-toast" + (type ? " apd-toast-" + type : "");
    //     var iconPaths = {
    //         success: '<path d="M20 6 9 17l-5-5"></path>',
    //         danger: '<path d="M18 6 6 18M6 6l12 12"></path>',
    //         warning: '<path d="M12 9v4M12 17h.01"></path><circle cx="12" cy="12" r="10"></circle>',
    //         info: '<circle cx="12" cy="12" r="10"></circle><path d="M12 16v-4M12 8h.01"></path>'
    //     };
    //     var icon = iconPaths[type] || iconPaths.info;
    //     toast.innerHTML =
    //         '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' + icon + "</svg>" +
    //         '<span>' + message + "</span>";
    //     toastContainer.appendChild(toast);
    //     setTimeout(function () {
    //         toast.classList.add("is-leaving");
    //         setTimeout(function () { toast.remove(); }, 220);
    //     }, 3400);
    // }

    delegate(page, "click", "[data-apd-toast]", function (e, target) {
        var type = target.getAttribute("data-apd-toast");
        var msg = target.getAttribute("data-apd-toast-msg") || "Action completed";
        showToast(msg, type);
    });

    /* ================= BUTTON LOADING STATE ================= */
    function setButtonLoading(btn, isLoading) {
        if (!btn) return;
        if (isLoading) {
            btn.dataset.originalLabel = btn.querySelector(".apd-btn-label") ? btn.querySelector(".apd-btn-label").textContent : "";
            btn.classList.add("is-loading");
            btn.disabled = true;
        } else {
            btn.classList.remove("is-loading");
            btn.disabled = false;
        }
    }

    /* ================= BACK BUTTON ================= */
    on(document.getElementById("apdBackBtn"), "click", function () {
        // TODO(backend): navigate to admin_dashboard:catalog_products_list
        if (window.history.length > 1) window.history.back();
    });

    /* ================= MORE DROPDOWN (body-appended to avoid clipping) ================= */

    function getCookie(name) {
        var cookieValue = null;

        if (document.cookie && document.cookie !== "") {
            var cookies = document.cookie.split(";");

            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();

                if (cookie.substring(0, name.length + 1) === (name + "=")) {
                    cookieValue = decodeURIComponent(
                        cookie.substring(name.length + 1)
                    );
                    break;
                }
            }
        }

        return cookieValue;
    }


    /* ================= MORE DROPDOWN + ALL ACTIONS ================= */
    (function initMoreDropdown() {
        var wrap = document.getElementById("apdMoreDropdown");
        var trigger = document.getElementById("apdMoreTrigger");

        if (!wrap || !trigger) return;

        var menu = wrap.querySelector(".apd-dropdown-menu");

        if (!menu) return;

        /*
         * The menu is moved to body so it cannot be clipped
         * by cards, containers, tabs, or overflow:hidden.
         */
        document.body.appendChild(menu);

        function positionMenu() {
            var rect = trigger.getBoundingClientRect();

            menu.style.position = "fixed";
            menu.style.top = (rect.bottom + 8) + "px";
            menu.style.right = (window.innerWidth - rect.right) + "px";
            menu.style.left = "auto";
        }

        function openMenu() {
            positionMenu();

            wrap.classList.add("is-open");

            /*
             * Because the menu is now inside body, CSS selector
             * #apdMoreDropdown .apd-dropdown-menu no longer works.
             */
            menu.classList.add("is-open");

            trigger.setAttribute("aria-expanded", "true");
        }

        function closeMenu() {
            wrap.classList.remove("is-open");
            menu.classList.remove("is-open");
            trigger.setAttribute("aria-expanded", "false");
        }

        function getProductSlug() {
            var productData = document.getElementById("product-data");

            return productData
                ? productData.dataset.productSlug
                : "";
        }
        function getSellerId() {
            var productData = document.getElementById("product-data");

            return productData
                ? productData.dataset.sellerId
                : "";
        }

        function showActionToast(message, type) {
            if (typeof showToast === "function") {
                showToast(message, type || "info");
            }
        }

        /* ================= TOGGLE DROPDOWN ================= */

        trigger.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();

            if (wrap.classList.contains("is-open")) {
                closeMenu();
            } else {
                openMenu();
            }
        });

        /* ================= ALL DROPDOWN ACTIONS ================= */

        menu.addEventListener("click", function (e) {
            var actionButton = e.target.closest("[data-apd-action]");

            if (!actionButton) return;

            e.preventDefault();
            e.stopPropagation();

            var action = actionButton.getAttribute("data-apd-action");
            var productSlug = getProductSlug();

            closeMenu();

            if (!productSlug) {
                showActionToast("Product slug not found.", "danger");
                return;
            }

            switch (action) {

                /* ================= EDIT ================= */
                case "edit":

                    if (typeof window.apdActivateTab === "function") {
                        window.apdActivateTab("information", true);
                    } else {
                        showActionToast(
                            "Unable to open product information.",
                            "danger"
                        );
                    }

                    break;
                /* ================= PREVIEW ================= */

                case "preview":
                    showActionToast("Opening product preview…", "info");
                    break;


                /* ================= VIEW LIVE ================= */

                case "view-live":
                    showActionToast("Opening live product…", "info");
                    window.open("/product/" + productSlug, "_blank");
                    break;


                /* ================= VIEW SELLER ================= */

                case "view-seller":
                    showActionToast("Opening seller profile…", "info");
                    window.open("/admin-db/user/sellers/" + getSellerId(), "_blank");
                    break;


                /* ================= EMAIL SELLER ================= */

                // case "email-seller":
                //     var emailModal = document.getElementById("apdEmailModal");

                //     if (emailModal) {
                //         emailModal.classList.remove("is-hidden");
                //     } else {
                //         showActionToast("Email modal not found.", "danger");
                //     }

                //     break;


                /* ================= EXPORT PRODUCT ================= */

                case "export-product":
                    showActionToast("Preparing product export…", "info");
                    window.location.href = `/products/${productSlug}/export-pdf/`
                    break;


                /* ================= EXPORT ORDERS ================= */

                case "export-orders":
                    showActionToast("Preparing order export…", "info");
                    window.location.href = `/products/${productSlug}/export-orders/`
                    break;


                /* ================= DUPLICATE ================= */

                case "duplicate":
                    showActionToast("Product duplication will be connected next.", "info");
                    break;


                /* ================= ARCHIVE ================= */
                case "archive":
                    var archiveModal = document.getElementById("apdArchiveModal");

                    if (archiveModal) {
                        archiveModal.classList.remove("is-hidden");
                    } else {
                        showToast("Archive modal not found.", "danger");
                    }

                    break;


                case "delete":
                    var deleteModal = document.getElementById("apdDeleteModal");

                    if (deleteModal) {
                        deleteModal.classList.remove("is-hidden");
                    } else {
                        showToast("Delete modal not found.", "danger");
                    }

                    break;

                default:
                    console.warn("Unknown product action:", action);
                    break;
            }
        });


        /* ================= OUTSIDE CLICK ================= */

        document.addEventListener("click", function (e) {
            if (!wrap.contains(e.target) && !menu.contains(e.target)) {
                closeMenu();
            }
        });


        /* ================= ESCAPE ================= */

        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") {
                closeMenu();
            }
        });


        /* ================= RESIZE ================= */

        window.addEventListener("resize", function () {
            if (wrap.classList.contains("is-open")) {
                positionMenu();
            }
        });


        /* ================= SCROLL ================= */

        window.addEventListener(
            "scroll",
            function () {
                if (wrap.classList.contains("is-open")) {
                    closeMenu();
                }
            },
            true
        );

    })();

    /* ================= PRICING ================= */

    (function initPricing() {

        var productData =
            document.getElementById("product-data");

        var editPricingBtn =
            document.getElementById("apdEditPricingBtn");
        var editPricingBtn1 =
            document.getElementById("apdEditPricingBtn1");
        var editPricingBtns = [editPricingBtn, editPricingBtn1];
        var removeDiscountBtn =
            document.getElementById("apdRemoveDiscountBtn");

        var removeDiscountBtn1 =
            document.getElementById("apdRemoveDiscountBtn1");

        var removeDiscountBtns = [removeDiscountBtn, removeDiscountBtn1];

        var editPriceModal =
            document.getElementById("apdEditPriceModal");

        var currentPriceInput =
            document.getElementById("apdCurrentPrice");

        var discountPriceInput =
            document.getElementById("apdDiscountPrice");

        var savePriceBtn =
            document.getElementById("apdSavePriceBtn");

        if (!productData) return;

        var productSlug =
            productData.dataset.productSlug;


        /* ================= EDIT PRICING ================= */

        editPricingBtns.forEach(function (btn) {


            on(btn, "click", function () {

                if (!editPriceModal) {
                    showToast(
                        "Pricing modal not found.",
                        "danger"
                    );
                    return;
                }

                openModal("apdEditPriceModal");

                if (currentPriceInput) {
                    currentPriceInput.focus();
                }
            });
        });


        /* ================= SAVE PRICING ================= */

        if (savePriceBtn) {

            on(savePriceBtn, "click", async function () {

                var price =
                    currentPriceInput
                        ? currentPriceInput.value.trim()
                        : "";

                var discountPrice =
                    discountPriceInput
                        ? discountPriceInput.value.trim()
                        : "";

                if (!price) {
                    showToast(
                        "Current price is required.",
                        "danger"
                    );
                    return;
                }

                if (Number(price) < 0) {
                    showToast(
                        "Price cannot be negative.",
                        "danger"
                    );
                    return;
                }

                if (
                    discountPrice !== "" &&
                    Number(discountPrice) < 0
                ) {
                    showToast(
                        "Discount price cannot be negative.",
                        "danger"
                    );
                    return;
                }

                if (
                    discountPrice !== "" &&
                    Number(discountPrice) >= Number(price)
                ) {
                    showToast(
                        "Discount price must be lower than the current price.",
                        "danger"
                    );
                    return;
                }

                setButtonLoading(
                    savePriceBtn,
                    true
                );

                try {

                    var response = await fetch(
                        `/admin-db/catalog/product-management/${productSlug}/price/`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken"),
                                "X-Requested-With": "XMLHttpRequest"
                            },

                            body: JSON.stringify({
                                price: price,
                                discount_price:
                                    discountPrice === ""
                                        ? null
                                        : discountPrice
                            })
                        }
                    );

                    var data =
                        await response.json();

                    if (
                        !response.ok ||
                        !data.success
                    ) {
                        throw new Error(
                            data.message ||
                            "Unable to update pricing."
                        );
                    }

                    closeModal(editPriceModal);

                    showToast(
                        data.message ||
                        "Pricing updated successfully.",
                        "success"
                    );

                    setTimeout(function () {
                        window.location.reload();
                    }, 600);

                } catch (error) {

                    console.error(
                        "Pricing update error:",
                        error
                    );

                    showToast(
                        error.message ||
                        "Unable to update pricing.",
                        "danger"
                    );

                } finally {

                    setButtonLoading(
                        savePriceBtn,
                        false
                    );
                }
            });
        }


        /* ================= REMOVE DISCOUNT ================= */

        removeDiscountBtns.forEach(function (btn) {



            on(
                btn,
                "click",
                async function () {

                    if (!productSlug) {
                        showToast(
                            "Product slug not found.",
                            "danger"
                        );
                        return;
                    }

                    if (
                        !confirm(
                            "Are you sure you want to remove the discount?"
                        )
                    ) {
                        return;
                    }

                    btn.disabled = true;

                    try {

                        var response = await fetch(
                            `/admin-db/catalog/product-management/${productSlug}/price/remove-discount/`,
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type": "application/json",
                                    "X-CSRFToken": getCookie("csrftoken"),
                                    "X-Requested-With": "XMLHttpRequest"
                                }
                            }
                        );

                        var data =
                            await response.json();

                        if (
                            !response.ok ||
                            !data.success
                        ) {
                            throw new Error(
                                data.message ||
                                "Unable to remove discount."
                            );
                        }

                        showToast(
                            data.message ||
                            "Discount removed successfully.",
                            "success"
                        );

                        setTimeout(function () {
                            window.location.reload();
                        }, 600);

                    } catch (error) {

                        console.error(
                            "Remove discount error:",
                            error
                        );

                        showToast(
                            error.message ||
                            "Unable to remove discount.",
                            "danger"
                        );

                    } finally {

                        btn.disabled = false;
                    }
                }
            );
        });

    })();
    /* ================= TABS ================= */
    (function initTabs() {
        var tabsNav = document.getElementById("apdTabs");
        if (!tabsNav) return;

        var tabs = qsa(".apd-tab", tabsNav);
        var panels = qsa(".apd-tab-panel", page);

        function activateTab(name, scroll) {
            tabs.forEach(function (t) {
                var isActive = t.getAttribute("data-apd-tab") === name;

                t.classList.toggle("is-active", isActive);
                t.setAttribute(
                    "aria-selected",
                    isActive ? "true" : "false"
                );
            });

            panels.forEach(function (p) {
                p.classList.toggle(
                    "is-active",
                    p.getAttribute("data-apd-panel") === name
                );
            });

            if (scroll) {
                tabsNav.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }

            window.location.hash = "tab-" + name;
        }

        /* Make it available to other handlers */
        window.apdActivateTab = activateTab;

        delegate(tabsNav, "click", ".apd-tab", function (e, target) {
            activateTab(
                target.getAttribute("data-apd-tab"),
                false
            );
        });

        delegate(page, "click", "[data-apd-goto-tab]", function (e, target) {
            activateTab(
                target.getAttribute("data-apd-goto-tab"),
                true
            );
        });

        var initialHash = window.location.hash.replace("#tab-", "");

        if (
            initialHash &&
            qs(
                '.apd-tab[data-apd-tab="' + initialHash + '"]',
                tabsNav
            )
        ) {
            activateTab(initialHash, false);
        }
    })();

    /* ================= BACK TO MEDIA PREVIEW ================= */
    (function initBackToMedia() {
        var button = document.getElementById("apdBackToMediaBtn");
        var mediaSection = document.getElementById("apdMediaPreview");

        if (!button || !mediaSection) return;

        on(button, "click", function () {

            mediaSection.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

        });
    })();

    /* ================= MODALS ================= */
    var lastFocusedEl = null;
    function openModal(id) {
        var modal = document.getElementById(id);
        if (!modal) return;
        lastFocusedEl = document.activeElement;
        modal.classList.remove("is-hidden");
        document.body.style.overflow = "hidden";
        var focusable = modal.querySelector("button, input, select, textarea");
        if (focusable) focusable.focus();
    }
    function closeModal(modal) {
        if (!modal) return;
        modal.classList.add("is-hidden");
        document.body.style.overflow = "";
        if (lastFocusedEl) lastFocusedEl.focus();
    }

    delegate(page, "click", "[data-apd-open-modal]", function (e, target) {
        openModal(target.getAttribute("data-apd-open-modal"));
    });
    qsa("[data-apd-modal]").forEach(function (overlay) {
        delegate(overlay, "click", "[data-apd-close-modal]", function () { closeModal(overlay); });
        on(overlay, "click", function (e) { if (e.target === overlay) closeModal(overlay); });
    });
    on(document, "keydown", function (e) {
        if (e.key === "Escape") {
            qsa('[data-apd-modal]:not(.is-hidden)').forEach(function (m) { closeModal(m); });
        }
    });

    // Confirm-action buttons inside modals: run loading state, toast, close.
    // Confirm-action buttons inside modals
    /* ================= UNHIDE PRODUCT ================= */

    (function initUnhideProduct() {
        var button = document.getElementById("apdunHideBtn");
        var hideButton = document.getElementById("apdHideBtn");
        var productData = document.getElementById("product-data");

        if (!button || !productData) return;

        on(button, "click", async function () {

            if (button.dataset.submitting === "true") {
                return;
            }

            var productSlug = productData.dataset.productSlug;

            if (!productSlug) {
                showToast("error", "Product information is missing.");
                return;
            }

            button.dataset.submitting = "true";
            setButtonLoading(button, true);

            try {
                var response = await fetch(
                    `/admin-db/catalog/product-management/${productSlug}/unhide/`,
                    {
                        method: "POST",

                        headers: {
                            "X-CSRFToken": getCookie("csrftoken"),
                            "X-Requested-With": "XMLHttpRequest"
                        }
                    }
                );

                var data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(
                        data.message ||
                        "Unable to unhide product."
                    );
                }

                /* Update buttons only after successful backend response */

                button.classList.add("is-hidden");

                if (hideButton) {
                    hideButton.classList.remove("is-hidden");
                }

                /* Update any status UI using your existing function */
                if (typeof applyStatusChange === "function") {
                    applyStatusChange("published");
                }

                showToast(
                    data.message || "Product unhidden successfully.", "success"
                );

            } catch (error) {

                console.error("Unhide product failed:", error);

                showToast(
                    "error",
                    error.message ||
                    "Unable to unhide product."
                );

            } finally {

                setButtonLoading(button, false);
                button.dataset.submitting = "false";
            }
        });
    })();

    /* ================= TOGGLE PRODUCT FEATURED ================= */

    (function initFeaturedButton() {

        var button = document.getElementById("apdFeatureBtn");
        var button1 = document.getElementById("apdFeatureBtnDown");
        var productData = document.getElementById("product-data");
        var buttons = [button, button1];
        if (!buttons || !productData) return;
        buttons.forEach(function (btn) {


            on(btn, "click", async function () {

                if (button.dataset.submitting === "true") {
                    return;
                }

                var productSlug = productData.dataset.productSlug;

                if (!productSlug) {
                    if (typeof showToast === "function") {
                        showToast("Product slug is missing.", "danger");
                    }
                    return;
                }

                var isFeatured = button.dataset.featured === "true";

                /*
                 * If data-featured does not exist yet, determine the
                 * initial state from the Django-rendered button.
                 */
                if (!button.dataset.featured) {
                    isFeatured = !!button.querySelector(".bi-star-fill");
                }

                var action = isFeatured
                    ? "unfeature"
                    : "feature";

                button.dataset.submitting = "true";
                button.disabled = true;

                try {

                    var response = await fetch(
                        `/admin-db/catalog/product-management/${productSlug}/toggle-featured/`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken"),
                                "X-Requested-With": "XMLHttpRequest"
                            },

                            body: JSON.stringify({
                                action: action
                            })
                        }
                    );

                    var data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to update featured status."
                        );
                    }

                    /*
                     * Store the new state so the next click knows
                     * whether to feature or unfeature.
                     */
                    button.dataset.featured = data.featured
                        ? "true"
                        : "false";

                    /*
                     * Update the star icon.
                     */
                    if (data.featured) {

                        button.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg"
                         width="16"
                         height="16"
                         fill="currentColor"
                         class="bi bi-star-fill"
                         viewBox="0 0 16 16">
                        <path d="M3.612 15.443c-.386.198-.824-.149-.746-.592l.83-4.73L.173 6.765c-.329-.314-.158-.888.283-.95l4.898-.696L7.538.792c.197-.39.73-.39.927 0l2.184 4.327 4.898.696c.441.062.612.636.282.95l-3.522 3.356.83 4.73c.078.443-.36.79-.746.592L8 13.187l-4.389 2.256z"/>
                    </svg>
                `;

                    } else {

                        button.innerHTML = `
                    <svg viewBox="0 0 24 24"
                         width="16"
                         height="16"
                         fill="none"
                         stroke="currentColor"
                         stroke-width="2">
                        <path d="m12 2 2.9 6.26L22 9.27l-5 4.87L18.2 21 12 17.6 5.8 21 7 14.14 2 9.27l7.1-1.01L12 2Z"></path>
                    </svg>
                `;

                    }

                    button.setAttribute(
                        "aria-label",
                        data.featured
                            ? "Remove from featured"
                            : "Add to featured"
                    );

                    if (typeof showToast === "function") {
                        showToast(
                            data.message ||
                            (
                                data.featured
                                    ? "Product featured successfully."
                                    : "Product removed from featured."
                            ),
                            "success"
                        );
                    }

                } catch (error) {

                    console.error(
                        "Featured product error:",
                        error
                    );

                    if (typeof showToast === "function") {
                        showToast(
                            error.message ||
                            "Unable to update featured status.",
                            "danger"
                        );
                    }

                } finally {

                    button.disabled = false;
                    button.dataset.submitting = "false";

                }

            });
        });

    })();
    delegate(
        document,
        "click",
        "[data-apd-confirm-action]",
        async function (e, target) {

            var overlay = target.closest("[data-apd-modal]");

            if (!overlay) return;

            var action = target.getAttribute("data-apd-confirm-action");

            if (target.dataset.submitting === "true") {
                return;
            }

            target.dataset.submitting = "true";
            setButtonLoading(target, true);

            try {

                /* ================= APPROVE PRODUCT ================= */

                if (action === "approve-product") {

                    var notifyCheckbox = overlay.querySelector(
                        'input[type="checkbox"]'
                    );

                    var publishToggle = overlay.querySelector(
                        '.apd-switch input[type="checkbox"]'
                    );

                    var productSlug = document.getElementById("product-data").dataset.productSlug;

                    var payload = {
                        notify_seller: notifyCheckbox
                            ? notifyCheckbox.checked
                            : false,
                        publish_immediately: publishToggle
                            ? publishToggle.checked
                            : false
                    };

                    var response = await fetch(
                        `/admin-db/catalog/product-management/${productSlug}/approve/`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken"),
                                "X-Requested-With": "XMLHttpRequest"
                            },

                            body: JSON.stringify(payload)
                        }
                    );

                    var data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to approve product."
                        );
                    }

                    /* ================= SUCCESS ================= */

                    setButtonLoading(target, false);
                    target.dataset.submitting = "false";

                    var newStatus = target.getAttribute(
                        "data-apd-set-status"
                    );

                    document.getElementById("apdApproveBtn").classList.add("is-hidden");
                    if (newStatus) {
                        applyStatusChange(newStatus);
                    }

                    closeModal(overlay);

                    if (typeof showToast === "function") {
                        showToast(
                            data.message || "Product approved successfully", "success"
                        );
                    }

                    return;
                }

                /* ================= HIDE PRODUCT ================= */

                if (action === "hide-product") {

                    var reasonSelect = overlay.querySelector("#apdHideReason");

                    var notifyCheckbox = overlay.querySelector(
                        'label.apd-checkbox input[type="checkbox"]'
                    );

                    var productSlug = document.getElementById("product-data").dataset.productSlug;
                    var payload = {
                        reason: reasonSelect
                            ? reasonSelect.value
                            : "",
                        notify_seller: notifyCheckbox
                            ? notifyCheckbox.checked
                            : false
                    };

                    var response = await fetch(
                        `/admin-db/catalog/product-management/${productSlug}/hide/`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken"),
                                "X-Requested-With": "XMLHttpRequest"
                            },

                            body: JSON.stringify(payload)
                        }
                    );

                    var data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to hide product."
                        );
                    }

                    setButtonLoading(target, false);
                    target.dataset.submitting = "false";

                    var newStatus = target.getAttribute(
                        "data-apd-set-status"
                    );

                    if (newStatus) {
                        applyStatusChange(newStatus);
                    }

                    closeModal(overlay);

                    if (typeof showToast === "function") {
                        showToast(
                            data.message ||
                            "Product hidden from storefront", "warning"
                        );
                    }

                    return;
                }
                // that do not have a backend endpoint yet.

                /* ================= REJECT PRODUCT ================= */

                if (action === "reject-product") {

                    var reasonSelect = overlay.querySelector("#apdRejectReason");
                    var noteField = overlay.querySelector("#apdRejectNote");

                    var resubmitCheckbox = overlay.querySelector(
                        'input[type="checkbox"]'
                    );

                    var productData = document.getElementById("product-data");

                    if (!productData) {
                        throw new Error("Product information is missing.");
                    }

                    var productSlug = productData.dataset.productSlug;

                    if (!productSlug) {
                        throw new Error("Product slug is missing.");
                    }

                    var payload = {
                        reason: reasonSelect
                            ? reasonSelect.value
                            : "",

                        admin_note: noteField
                            ? noteField.value.trim()
                            : "",

                        allow_resubmit: resubmitCheckbox
                            ? resubmitCheckbox.checked
                            : false
                    };

                    var response = await fetch(
                        `/admin-db/catalog/product-management/${productSlug}/reject/`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken"),
                                "X-Requested-With": "XMLHttpRequest"
                            },

                            body: JSON.stringify(payload)
                        }
                    );

                    var data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to reject product."
                        );
                    }

                    setButtonLoading(target, false);
                    target.dataset.submitting = "false";

                    var newStatus = target.getAttribute(
                        "data-apd-set-status"
                    );

                    if (newStatus) {
                        applyStatusChange(newStatus);
                    }
                    document.getElementById("apdApproveBtn").classList.remove("is-hidden");
                    // documents.getElementById("apdRejectBtn").classList.add("is-hidden");

                    closeModal(overlay);

                    if (typeof showToast === "function") {
                        showToast(
                            data.message || "Product rejected",
                            "danger"
                        );
                    }

                    return;
                }

                if (action === "publish-product") {

                    var publishImmediately = overlay.querySelector(
                        '.apd-switch input[type="checkbox"]'
                    );

                    var featureHomepage = overlay.querySelectorAll(
                        '.apd-switch input[type="checkbox"]'
                    );

                    var productSlug = document
                        .getElementById("product-data")
                        .dataset.productSlug;

                    var payload = {
                        publish_immediately: publishImmediately
                            ? publishImmediately.checked
                            : true,

                        feature_homepage: featureHomepage.length > 1
                            ? featureHomepage[1].checked
                            : false
                    };

                    var response = await fetch(
                        `/admin-db/catalog/product-management/${productSlug}/publish/`,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken"),
                                "X-Requested-With": "XMLHttpRequest"
                            },

                            body: JSON.stringify(payload)
                        }
                    );

                    var data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to publish product."
                        );
                    }

                    setButtonLoading(target, false);
                    target.dataset.submitting = "false";

                    var newStatus = target.getAttribute(
                        "data-apd-set-status"
                    );

                    if (newStatus) {
                        applyStatusChange(newStatus);
                    }

                    closeModal(overlay);

                    if (typeof showToast === "function") {
                        showToast(
                            data.message ||
                            "Product published successfully.",
                            "success"
                        );
                    }

                    return;
                }
                setTimeout(function () {

                    setButtonLoading(target, false);
                    target.dataset.submitting = "false";

                    var newStatus = target.getAttribute(
                        "data-apd-set-status"
                    );

                    if (newStatus) {
                        applyStatusChange(newStatus);
                    }

                    if (overlay) {
                        closeModal(overlay);
                    }

                }, 650);

            } catch (error) {

                console.error(
                    "Product action failed:",
                    error
                );

                setButtonLoading(target, false);
                target.dataset.submitting = "false";

                if (typeof showToast === "function") {
                    showToast(
                        "error",
                        error.message ||
                        "Something went wrong. Please try again."
                    );
                }
            }
        }
    );
    /* ================= STATUS PILLS / STRIP SYNC (frontend-only simulation) ================= */
    function applyStatusChange(status) {
        var approvalPill = document.getElementById("apdApprovalPill");
        var publicationPill = document.getElementById("apdPublicationPill");
        // TODO(backend): reflect Product.approval_status / Product.is_published from server response
        var map = {
            approved: { approval: ["c-success", "Approved"] },
            rejected: { approval: ["c-danger", "Rejected"] },
            published: { publication: ["c-accent", "Published"] },
            hidden: { publication: ["c-muted", "Hidden"] },
            archived: { publication: ["c-muted", "Archived"] }
        };
        var change = map[status];
        if (!change) return;
        if (change.approval && approvalPill) {
            approvalPill.className = "apd-badge-pill " + change.approval[0];
            approvalPill.querySelector("svg") && (approvalPill.lastChild.textContent = " " + change.approval[1]);
        }
        if (change.publication && publicationPill) {
            publicationPill.className = "apd-badge-pill " + change.publication[0];
            publicationPill.lastChild.textContent = " " + change.publication[1];
        }
    }

    /* ================= FEATURE TOGGLE ================= */
    function toggleFeatured() {
        var pill = document.getElementById("apdFeaturedPill");
        if (!pill) return;
        var nowHidden = pill.classList.toggle("apd-hidden");
        showToast(nowHidden ? "Removed from featured products" : "Product marked as featured", nowHidden ? "info" : "success");
        // TODO(backend): PATCH Product.is_featured
    }
    on(document.getElementById("apdFeatureBtn"), "click", toggleFeatured);
    on(document.getElementById("apdFeatureBtnDown"), "click", toggleFeatured);

    /* ================= DELETE CONFIRMATION GATING ================= */
    (function initDeleteGate() {
        var nameInput = document.getElementById("apdDeleteConfirmName");
        var wordInput = document.getElementById("apdDeleteConfirmInput");
        var confirmBtn = document.getElementById("apdDeleteConfirmBtn");

        if (!nameInput || !wordInput || !confirmBtn) return;

        var expectedName = "Hammad Ashraf"; // TODO(backend): product.name

        function check() {
            var ok =
                nameInput.value.trim() === expectedName &&
                wordInput.value.trim().toUpperCase() === "DELETE";

            confirmBtn.disabled = !ok;
        }

        on(nameInput, "input", check);
        on(wordInput, "input", check);

        on(confirmBtn, "click", function () {

            var productData = document.getElementById("product-data");

            if (!productData) {
                showToast(
                    "Product data not found.",
                    "danger"
                );
                return;
            }

            var productSlug = productData.dataset.productSlug;

            if (!productSlug) {
                showToast(
                    "Product slug not found.",
                    "danger"
                );
                return;
            }

            setButtonLoading(confirmBtn, true);

            fetch("/seller/products/toggle-archive/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({
                    productSlug: productSlug,
                    action: "archive"
                })
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return {
                            ok: response.ok,
                            data: data
                        };
                    });
                })
                .then(function (result) {
                    var data = result.data;

                    if (!result.ok || data.status !== "success") {
                        throw new Error(
                            data.message ||
                            "Unable to archive product."
                        );
                    }

                    closeModal(
                        document.getElementById("apdDeleteModal")
                    );

                    showToast(
                        data.message || "Product archived successfully.",
                        "warning"
                    );

                    setTimeout(function () {
                        window.location.reload();
                    }, 700);
                })
                .catch(function (error) {
                    console.error(
                        "Product archive error:",
                        error
                    );

                    showToast(
                        error.message ||
                        "Something went wrong while archiving the product.",
                        "danger"
                    );
                })
                .finally(function () {
                    setButtonLoading(
                        confirmBtn,
                        false
                    );
                });
        });
    })();

    /* ================= ARCHIVE CONFIRMATION ================= */

    (function initArchiveConfirm() {
        var archiveConfirmBtn = document.querySelector(
            '[data-apd-confirm-action="hide-product"]'
        );

        if (!archiveConfirmBtn) return;

        on(archiveConfirmBtn, "click", function () {

            var pathParts = window.location.pathname
                .split("/")
                .filter(Boolean);

            var productSlug = null;
            var productsIndex = pathParts.indexOf("products");

            if (
                productsIndex !== -1 &&
                pathParts[productsIndex + 1]
            ) {
                productSlug = pathParts[productsIndex + 1];
            }

            if (!productSlug) {
                console.error(
                    "Product slug could not be determined:",
                    window.location.pathname
                );

                showToast(
                    "Product slug not found.",
                    "danger"
                );

                return;
            }

            setButtonLoading(
                archiveConfirmBtn,
                true
            );

            var label = archiveConfirmBtn.querySelector(
                ".apd-btn-label"
            );

            if (label) {
                label.textContent = "Archiving...";
            }

            fetch("/seller/products/toggle-archive/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({
                    product_slug: productSlug
                })
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return {
                            ok: response.ok,
                            data: data
                        };
                    });
                })
                .then(function (result) {
                    var data = result.data;

                    if (!result.ok || !data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to archive product."
                        );
                    }

                    closeModal(
                        document.getElementById("apdArchiveModal")
                    );

                    showToast(
                        "Product archived successfully.",
                        "warning"
                    );

                    setTimeout(function () {
                        window.location.reload();
                    }, 700);
                })
                .catch(function (error) {
                    console.error(
                        "Archive product error:",
                        error
                    );

                    showToast(
                        error.message ||
                        "Something went wrong while archiving the product.",
                        "danger"
                    );
                })
                .finally(function () {
                    setButtonLoading(
                        archiveConfirmBtn,
                        false
                    );

                    if (label) {
                        label.textContent = "Hide Product";
                    }
                });
        });
    })();
    /* ================= INLINE EDIT MODE (Information tab) ================= */
    (function initInlineEdit() {

        var editBtn = document.getElementById("apdEditInfoBtn");
        var cancelBtn = document.getElementById("apdCancelEditBtn");
        var saveBtn = document.getElementById("apdSaveEditBtn");

        if (!editBtn || !cancelBtn || !saveBtn) return;


        /* ================= FIELDS ================= */

        var nameInput = document.getElementById("apdProductName");
        var slugInput = document.getElementById("apdProductSlug");
        var skuInput = document.getElementById("apdProductSku");
        var barcodeInput = document.getElementById("apdProductBarcode");

        var shortDescriptionInput = document.getElementById(
            "apdProductShortDescription"
        );

        var descriptionInput = document.getElementById(
            "apdProductDescription"
        );

        var categorySelect = document.getElementById(
            "apdProductCategory"
        );

        var subcategorySelect = document.getElementById(
            "apdProductSubcategory"
        );

        var brandSelect = document.getElementById(
            "apdProductBrand"
        );


        /* ================= PRODUCT SLUG ================= */

        var productData = document.getElementById("product-data");

        var currentProductSlug = productData
            ? productData.dataset.productSlug
            : null;


        /* ================= CATEGORY ================= */

        function syncCategoryFields() {

            if (!categorySelect || !subcategorySelect) {
                return;
            }

            var categoryId = categorySelect.value;

            var options = subcategorySelect.querySelectorAll("option");

            options.forEach(function (option) {

                if (!option.value) {
                    option.hidden = false;
                    return;
                }

                var parentId = option.getAttribute(
                    "data-parent-id"
                );

                option.hidden = parentId !== categoryId;
            });


            /*
             * If the currently selected subcategory does not
             * belong to the selected parent category, clear it.
             */

            var selected = subcategorySelect.options[
                subcategorySelect.selectedIndex
            ];

            if (
                selected &&
                selected.value &&
                selected.hidden
            ) {
                subcategorySelect.value = "";
            }
        }


        if (categorySelect) {
            on(
                categorySelect,
                "change",
                syncCategoryFields
            );
        }


        /* ================= EDIT MODE ================= */

        function enterEdit() {

            page.classList.add("is-editing");

            editBtn.classList.add("apd-hidden");

            cancelBtn.classList.remove("apd-hidden");

            saveBtn.classList.remove("apd-hidden");

            syncCategoryFields();
        }


        /* ================= CANCEL ================= */

        function exitEdit() {

            page.classList.remove("is-editing");

            editBtn.classList.remove("apd-hidden");

            cancelBtn.classList.add("apd-hidden");

            saveBtn.classList.add("apd-hidden");
        }


        on(editBtn, "click", enterEdit);

        on(cancelBtn, "click", exitEdit);


        /* ================= SAVE ================= */

        on(saveBtn, "click", function () {

            if (saveBtn.dataset.submitting === "true") {
                return;
            }

            if (!currentProductSlug) {

                showToast(
                    "Product slug not found.",
                    "danger"
                );

                return;
            }


            /* ================= VALIDATION ================= */

            if (!nameInput || !nameInput.value.trim()) {

                showToast(
                    "Product name is required.",
                    "danger"
                );

                return;
            }

            if (!slugInput || !slugInput.value.trim()) {

                showToast(
                    "Product slug is required.",
                    "danger"
                );

                return;
            }


            saveBtn.dataset.submitting = "true";

            setButtonLoading(
                saveBtn,
                true
            );


            /* ================= CATEGORY ================= */

            var categoryId = categorySelect
                ? categorySelect.value
                : "";


            /*
             * If a subcategory is selected, that category is
             * the actual Product.category.
             */

            if (
                subcategorySelect &&
                subcategorySelect.value
            ) {
                categoryId = subcategorySelect.value;
            }


            /* ================= PAYLOAD ================= */

            var payload = {

                name: nameInput
                    ? nameInput.value.trim()
                    : "",

                slug: slugInput
                    ? slugInput.value.trim()
                    : "",

                sku: skuInput
                    ? skuInput.value.trim()
                    : "",

                barcode: barcodeInput
                    ? barcodeInput.value.trim()
                    : "",

                short_description: shortDescriptionInput
                    ? shortDescriptionInput.value
                    : "",

                description: descriptionInput
                    ? descriptionInput.value
                    : "",

                category_id: categoryId,

                brand_id: brandSelect
                    ? brandSelect.value
                    : ""
            };


            /* ================= REQUEST ================= */

            fetch(
                "/admin-db/catalog/product-management/" +
                encodeURIComponent(currentProductSlug) +
                "/update/",
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",

                        "X-CSRFToken":
                            getCookie("csrftoken"),

                        "X-Requested-With":
                            "XMLHttpRequest"
                    },

                    body: JSON.stringify(payload)
                }
            )

                .then(function (response) {

                    return response.json()
                        .then(function (data) {

                            return {
                                ok: response.ok,
                                data: data
                            };

                        });

                })

                .then(function (result) {

                    var data = result.data;

                    if (
                        !result.ok ||
                        !data.success
                    ) {

                        throw new Error(
                            data.message ||
                            "Unable to update product."
                        );
                    }


                    showToast(
                        data.message ||
                        "Product information updated.",
                        "success"
                    );


                    /*
                     * If slug was changed, move to the new
                     * product URL.
                     */

                    if (
                        data.product &&
                        data.product.slug &&
                        data.product.slug !== currentProductSlug
                    ) {

                        setTimeout(function () {

                            window.location.href =
                                "/admin-db/catalog/product-management/" +
                                encodeURIComponent(
                                    data.product.slug
                                ) +
                                "/";

                        }, 700);

                        return;
                    }


                    /*
                     * Otherwise reload the current page so all
                     * displayed information is refreshed.
                     */

                    setTimeout(function () {

                        window.location.reload();

                    }, 700);

                })

                .catch(function (error) {

                    console.error(
                        "Product update error:",
                        error
                    );

                    showToast(
                        error.message ||
                        "Something went wrong while updating the product.",
                        "danger"
                    );

                })

                .finally(function () {

                    setButtonLoading(
                        saveBtn,
                        false
                    );

                    saveBtn.dataset.submitting = "false";

                });

        });

    })();
    /* ================= PRICE HISTORY TOGGLE ================= */
    (function initPriceHistory() {
        var btn = document.getElementById("apdShowPriceHistoryBtn");
        var panel = document.getElementById("apdPriceHistory");
        if (!btn || !panel) return;
        panel.style.display = "flex";
        on(btn, "click", function () {
            var isHidden = panel.style.display === "none";
            panel.style.display = isHidden ? "flex" : "none";
            btn.setAttribute("aria-expanded", isHidden ? "true" : "false");
        });
    })();

    /* ================= MEDIA GALLERY ================= */

    (function initGallery() {
        var mainWrap = document.getElementById("apdGalleryMain");
        var mainImg = document.getElementById("apdMainImage");
        var counter = document.getElementById("apdImageCounter");
        var thumbs = qsa(".apd-thumb-item", page);
        var zoomBtn = document.getElementById("apdZoomBtn");
        var zoomModalImg = document.getElementById("apdZoomImage");
        var thumbTrigger = document.getElementById("apdThumbTrigger");
        var strip = document.getElementById("apdThumbStrip");
        var addBtn = document.getElementById("apdThumbAddBtn");
        var addBtn2 = document.getElementById("apdAddMediaBtn");
        var addBtn3 = document.getElementById("apdAddMediaBtn2");
        var mediaPanel = document.querySelector('[data-apd-panel="media-gallery"]');
        var maxImages = Math.max(1, parseInt(mediaPanel && mediaPanel.dataset.maxImages, 10) || 8);
        var maxImageSize = (parseFloat(mediaPanel && mediaPanel.dataset.maxImageSizeMb) || 5) * 1024 * 1024;
        if (thumbs.length === 0 && !strip) return;


        /* ================= PRODUCT ================= */

        var productData = document.getElementById("product-data");

        var productSlug = productData
            ? productData.dataset.productSlug
            : null;


        /* ================= API ================= */

        var galleryBaseUrl =
            "/admin-db/catalog/product-management/" +
            productSlug +
            "/images/";


        /* ================= SELECT IMAGE ================= */

        function selectThumb(thumb) {
            if (!thumb) return;

            thumbs.forEach(function (t) {
                t.classList.remove("is-active");
            });

            thumb.classList.add("is-active");

            var index = parseInt(
                thumb.getAttribute("data-index"),
                10
            ) || 0;

            var isPrimary = thumb.getAttribute("data-is-primary") === "true";
            var primaryTag = document.getElementById("is-primary");

            if (primaryTag) {
                primaryTag.style.display = isPrimary ? "" : "none";
            }
            var imageUrl = thumb.getAttribute("data-image");

            if (counter) {
                counter.textContent =
                    (index + 1) + " / " + thumbs.length;
            }

            if (!imageUrl || !mainImg) return;

            if (mainWrap) {
                mainWrap.classList.add("pd-fade");
            }

            setTimeout(function () {
                mainImg.src = imageUrl;

                if (mainWrap) {
                    mainWrap.classList.remove("pd-fade");
                }
            }, 160);
        }


        /* ================= THUMBNAIL CLICK ================= */

        delegate(
            strip,
            "click",
            ".apd-thumb-item",
            function (e, target) {

                if (e.target.closest(".apd-thumb-mini-btn")) {
                    return;
                }

                selectThumb(target);
            }
        );


        /* ================= ZOOM ================= */

        function openZoom() {
            if (!zoomModalImg) return;

            zoomModalImg.src = mainImg
                ? mainImg.src
                : "";

            openModal("apdZoomModal");
        }

        on(zoomBtn, "click", openZoom);
        on(thumbTrigger, "click", openZoom);

        on(
            thumbTrigger,
            "keydown",
            function (e) {
                if (
                    e.key === "Enter" ||
                    e.key === " "
                ) {
                    e.preventDefault();
                    openZoom();
                }
            }
        );

        if (mainWrap) {
            on(
                mainWrap,
                "click",
                function (e) {
                    if (
                        !e.target.closest(
                            ".apd-gallery-zoom-btn"
                        )
                    ) {
                        openZoom();
                    }
                }
            );
        }


        /* ================= ADD IMAGE ================= */

        var fileInput = document.getElementById(
            "apdGalleryFileInput"
        );

        if (!fileInput) {
            fileInput = document.createElement("input");

            fileInput.type = "file";
            fileInput.id = "apdGalleryFileInput";
            fileInput.accept =
                "image/jpeg,image/png,image/webp";
            fileInput.multiple = true;
            fileInput.style.display = "none";

            document.body.appendChild(fileInput);
        }


        on(
            addBtn,
            "click",
            function () {
                fileInput.click();
            }
        );


        on(
            addBtn,
            "keydown",
            function (e) {
                if (
                    e.key === "Enter" ||
                    e.key === " "
                ) {
                    e.preventDefault();
                    fileInput.click();
                }
            }
        );


        on(
            addBtn2,
            "click",
            function () {
                fileInput.click();
            }
        );

        on(
            addBtn3,
            "click",
            function () {
                fileInput.click();
            }
        );


        on(
            fileInput,
            "change",
            async function () {

                var files = Array.from(
                    fileInput.files || []
                );

                if (!files.length) return;

                if (!productSlug) {
                    showToast(
                        "Product slug not found.",
                        "danger"
                    );
                    return;
                }

                var remaining = Math.max(0, maxImages - thumbs.length);
                if (files.length > remaining) {
                    showToast("You can upload up to " + maxImages + " images for this product.", "danger");
                    files = files.slice(0, remaining);
                }
                files = files.filter(function (file) {
                    if (!file.type || file.type.indexOf("image/") !== 0) {
                        showToast("Only image files can be uploaded.", "danger");
                        return false;
                    }
                    if (file.size > maxImageSize) {
                        showToast("Each image must be within the configured size limit.", "danger");
                        return false;
                    }
                    return true;
                });
                if (!files.length) return;

                try {
                    for (var i = 0; i < files.length; i++) {

                        var file = files[i];

                        var formData = new FormData();

                        formData.append(
                            "image",
                            file
                        );

                        var response = await fetch(
                            galleryBaseUrl + "upload/",
                            {
                                method: "POST",

                                headers: {
                                    "X-CSRFToken":
                                        getCookie("csrftoken"),
                                    "X-Requested-With":
                                        "XMLHttpRequest"
                                },

                                body: formData
                            }
                        );

                        var data =
                            await response.json();

                        if (
                            !response.ok ||
                            !data.success
                        ) {
                            throw new Error(
                                data.message ||
                                "Unable to upload image."
                            );
                        }
                    }

                    showToast(
                        "Product image added successfully.",
                        "success"
                    );

                    setTimeout(function () {
                        window.location.reload();
                    }, 500);

                } catch (error) {

                    console.error(
                        "Image upload error:",
                        error
                    );

                    showToast(
                        error.message ||
                        "Unable to upload image.",
                        "danger"
                    );

                } finally {
                    fileInput.value = "";
                }
            }
        );


        /* ================= DELETE IMAGE ================= */
        delegate(
            strip,
            "click",
            ".apd-thumb-mini-btn.is-danger",
            async function (e, target) {

                e.preventDefault();
                e.stopPropagation();

                var thumb = target.closest(
                    ".apd-thumb-item"
                );

                if (!thumb) return;

                var imageId = thumb.getAttribute(
                    "data-image-id"
                );

                if (!imageId) {
                    showToast(
                        "Image ID not found.",
                        "danger"
                    );
                    return;
                }

                if (!confirm("Delete this product image?")) {
                    return;
                }

                try {
                    var response = await fetch(
                        galleryBaseUrl +
                        imageId +
                        "/delete/",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken"),
                                "X-Requested-With": "XMLHttpRequest"
                            },

                            body: JSON.stringify({
                                image_id: imageId
                            })
                        }
                    );

                    var data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to delete image."
                        );
                    }

                    showToast(
                        data.message ||
                        "Product image deleted.",
                        "success"
                    );

                    setTimeout(function () {
                        window.location.reload();
                    }, 500);

                } catch (error) {

                    console.error(
                        "Image delete error:",
                        error
                    );

                    showToast(
                        error.message ||
                        "Unable to delete image.",
                        "danger"
                    );
                }
            }
        );

        /* ================= SET PRIMARY IMAGE ================= */

        delegate(
            strip,
            "click",
            ".apd-thumb-mini-btn:not(.is-danger)",
            async function (e, target) {

                e.preventDefault();
                e.stopPropagation();

                var thumb = target.closest(
                    ".apd-thumb-item"
                );

                if (!thumb) return;

                var imageId = thumb.getAttribute(
                    "data-image-id"
                );

                if (!imageId) {
                    showToast(
                        "Image ID not found.",
                        "danger"
                    );
                    return;
                }

                if (
                    thumb.classList.contains("is-active") &&
                    target.classList.contains("is-active")
                ) {
                    showToast(
                        "This image is already the primary image.",
                        "info"
                    );
                    return;
                }

                target.disabled = true;

                try {

                    var response = await fetch(
                        galleryBaseUrl +
                        imageId +
                        "/set-primary/",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type": "application/json",
                                "X-CSRFToken": getCookie("csrftoken"),
                                "X-Requested-With": "XMLHttpRequest"
                            }
                        }
                    );

                    var data = await response.json();

                    if (!response.ok || !data.success) {
                        throw new Error(
                            data.message ||
                            "Unable to set primary image."
                        );
                    }

                    /*
                     * Remove primary state from every image.
                     */
                    qsa(
                        ".apd-thumb-mini-btn:not(.is-danger)",
                        strip
                    ).forEach(function (button) {
                        button.classList.remove("is-active");
                    });

                    qsa(
                        ".apd-thumb-item",
                        strip
                    ).forEach(function (item) {
                        item.classList.remove(
                            "is-primary"
                        );
                    });

                    /*
                     * Mark selected image as primary.
                     */
                    target.classList.add(
                        "is-active"
                    );

                    thumb.classList.add(
                        "is-primary"
                    );

                    showToast(
                        data.message ||
                        "Primary image updated successfully.",
                        "success"
                    );

                } catch (error) {

                    console.error(
                        "Set primary image error:",
                        error
                    );

                    showToast(
                        error.message ||
                        "Unable to set primary image.",
                        "danger"
                    );

                } finally {

                    target.disabled = false;
                }
            }
        );

        /* ================= DRAG & DROP ================= */

        var dragSrc = null;

        delegate(
            strip,
            "dragstart",
            ".apd-thumb-item",
            function (e, target) {

                dragSrc = target;

                e.dataTransfer.effectAllowed =
                    "move";

                target.classList.add(
                    "is-dragging"
                );
            }
        );


        delegate(
            strip,
            "dragend",
            ".apd-thumb-item",
            function (e, target) {

                target.classList.remove(
                    "is-dragging"
                );
            }
        );


        delegate(
            strip,
            "dragover",
            ".apd-thumb-item",
            function (e, target) {

                e.preventDefault();

                e.dataTransfer.dropEffect =
                    "move";
            }
        );


        delegate(
            strip,
            "drop",
            ".apd-thumb-item",
            async function (e, target) {

                e.preventDefault();

                if (
                    !dragSrc ||
                    dragSrc === target
                ) {
                    return;
                }

                var items = qsa(
                    ".apd-thumb-item",
                    strip
                );

                var srcIdx =
                    items.indexOf(dragSrc);

                var tgtIdx =
                    items.indexOf(target);

                if (srcIdx < tgtIdx) {
                    target.after(dragSrc);
                } else {
                    target.before(dragSrc);
                }

                var orderedIds = qsa(
                    ".apd-thumb-item",
                    strip
                ).map(function (item) {
                    return item.getAttribute(
                        "data-image-id"
                    );
                });

                try {

                    var response = await fetch(
                        galleryBaseUrl +
                        "reorder/",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",
                                "X-CSRFToken":
                                    getCookie(
                                        "csrftoken"
                                    ),
                                "X-Requested-With":
                                    "XMLHttpRequest"
                            },

                            body: JSON.stringify({
                                image_ids:
                                    orderedIds
                            })
                        }
                    );

                    var data =
                        await response.json();

                    if (
                        !response.ok ||
                        !data.success
                    ) {
                        throw new Error(
                            data.message ||
                            "Unable to update image order."
                        );
                    }

                    showToast(
                        data.message ||
                        "Media order updated.",
                        "success"
                    );

                    qsa(
                        ".apd-thumb-item",
                        strip
                    ).forEach(function (
                        item,
                        index
                    ) {
                        item.setAttribute(
                            "data-index",
                            index
                        );
                    });

                } catch (error) {

                    console.error(
                        "Image reorder error:",
                        error
                    );

                    showToast(
                        error.message ||
                        "Unable to update image order.",
                        "danger"
                    );

                    window.location.reload();
                }

                dragSrc = null;
            }
        );

    })();
    /* ================= STOCK RING / DONUT / BAR CHART / LINE CHART ANIMATIONS ================= */
    (function initVisualAnimations() {
        var animateTargets = qsa(".apd-stock-ring, .apd-donut, .apd-line-chart-wrap, .apd-bar-mini-chart", page);
        if (animateTargets.length === 0) return;
        if (!("IntersectionObserver" in window)) {
            animateTargets.forEach(function (el) { el.classList.add("is-animated"); });
            return;
        }
        var vizObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-animated");
                    vizObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.35 });
        animateTargets.forEach(function (el) { vizObserver.observe(el); });
    })();

    function initStatusDonut() {
        var donut = document.getElementById("apdStatusDonut");
        var ring = document.getElementById("apdStatusDonutRing");

        if (!donut || !ring) return;

        var delivered = Number(donut.dataset.delivered) || 0;

        var radius = 60;
        var circumference = 2 * Math.PI * radius;

        ring.style.strokeDasharray = circumference;
        ring.style.strokeDashoffset =
            circumference - (delivered / 100) * circumference;

        ring.style.transformOrigin = "70px 70px";
        ring.style.transform = "rotate(-0deg)";
    }
    document.addEventListener(
        "DOMContentLoaded",
        initStatusDonut
    );
    /* ================= LINE CHART TOOLTIP ================= */
    (function initChartTooltip() {
        var wrap = document.getElementById("apdRevenueLineChart");
        var tooltip = document.getElementById("apdChartTooltip");
        if (!wrap || !tooltip) return;
        delegate(wrap, "mouseenter", ".apd-line-chart-dot", function (e, dot) {
            var value = dot.getAttribute("data-value");
            var rect = wrap.getBoundingClientRect();
            var dotRect = dot.getBoundingClientRect();
            tooltip.textContent = value;
            tooltip.style.left = (dotRect.left - rect.left + dotRect.width / 2) + "px";
            tooltip.style.top = (dotRect.top - rect.top) + "px";
            tooltip.classList.add("is-visible");
        });
        delegate(wrap, "mouseleave", ".apd-line-chart-dot", function () {
            tooltip.classList.remove("is-visible");
        });
    })();

    /* ================= PRODUCT REVENUE LINE CHART ================= */

    (function initProductRevenueChart() {
        var wrap = document.getElementById("apdRevenueLineChart");

        if (!wrap) return;

        var path = document.getElementById("apdRevenuePath");
        var area = document.getElementById("apdRevenueArea");
        var dots = document.getElementById("apdRevenueDots");

        if (!path || !area || !dots) return;

        var rawData = wrap.getAttribute("data-revenue-trend");

        if (!rawData) return;

        var data;

        try {
            data = JSON.parse(rawData);
        } catch (error) {
            console.error("Revenue chart data is invalid:", error);
            return;
        }

        if (!Array.isArray(data) || !data.length) return;

        var width = 560;
        var height = 200;

        var paddingTop = 20;
        var paddingBottom = 10;

        var chartHeight = height - paddingTop - paddingBottom;

        var values = data.map(function (item) {
            return Number(item.revenue) || 0;
        });

        var maxValue = Math.max.apply(null, values);

        if (maxValue <= 0) {
            maxValue = 1;
        }

        var points = [];

        data.forEach(function (item, index) {

            var x;

            if (data.length === 1) {
                x = width / 2;
            } else {
                x = (index / (data.length - 1)) * width;
            }

            var value = Number(item.revenue) || 0;

            var y =
                paddingTop +
                chartHeight -
                ((value / maxValue) * chartHeight);

            points.push({
                x: x,
                y: y,
                value: value,
                label: item.label
            });
        });

        /* ================= LINE ================= */

        var pathData = "";

        points.forEach(function (point, index) {
            if (index === 0) {
                pathData += "M" + point.x + "," + point.y;
            } else {
                pathData += " L" + point.x + "," + point.y;
            }
        });

        path.setAttribute("d", pathData);

        /* ================= AREA ================= */

        var areaData =
            pathData +
            " L" + width + "," + height +
            " L0," + height +
            " Z";

        area.setAttribute("d", areaData);

        /* ================= DOTS ================= */

        dots.innerHTML = "";

        points.forEach(function (point) {

            var circle = document.createElementNS(
                "http://www.w3.org/2000/svg",
                "circle"
            );

            circle.setAttribute(
                "class",
                "apd-line-chart-dot"
            );

            circle.setAttribute("cx", point.x);
            circle.setAttribute("cy", point.y);
            circle.setAttribute("r", "4");

            circle.setAttribute(
                "data-value",
                point.label + ": Rs. " +
                point.value.toLocaleString("en-PK")
            );

            dots.appendChild(circle);
        });
    })();

    /* ================= ORDERS TABLE: SEARCH + FILTER ================= */
    (function initOrdersTable() {
        var searchInput = document.getElementById("apdOrdersSearch");
        var statusFilter = document.getElementById("apdOrdersStatusFilter");
        var rows = qsa("#apdOrdersTableBody .apd-row");
        var emptyState = document.getElementById("apdOrdersEmpty");
        if (!searchInput || rows.length === 0) return;

        function applyFilters() {
            var term = searchInput.value.trim().toLowerCase();
            var status = statusFilter ? statusFilter.value : "";
            var visibleCount = 0;
            rows.forEach(function (row) {
                var matchesSearch = !term || (row.getAttribute("data-search") || "").indexOf(term) !== -1;
                var matchesStatus = !status || row.getAttribute("data-status") === status;
                var show = matchesSearch && matchesStatus;
                row.classList.toggle("apd-row-hidden", !show);
                if (show) visibleCount++;
            });
            if (emptyState) emptyState.classList.toggle("is-visible", visibleCount === 0);
        }
        on(searchInput, "input", applyFilters);
        on(statusFilter, "change", applyFilters);
    })();

    /* ================= REVIEWS: SEARCH + FILTER ================= */
    (function initReviews() {
        var searchInput = document.getElementById("apdReviewsSearch");
        var ratingFilter = document.getElementById("apdReviewsRatingFilter");
        var cards = qsa("#apdReviewsList .apd-review-card");
        var emptyState = document.getElementById("apdReviewsEmpty");
        if (!searchInput || cards.length === 0) return;

        function applyFilters() {
            var term = searchInput.value.trim().toLowerCase();
            var rating = ratingFilter ? ratingFilter.value : "";
            var visibleCount = 0;
            cards.forEach(function (card) {
                var matchesSearch = !term || (card.getAttribute("data-search") || "").indexOf(term) !== -1;
                var matchesRating = !rating || card.getAttribute("data-rating") === rating;
                var show = matchesSearch && matchesRating;
                card.style.display = show ? "" : "none";
                if (show) visibleCount++;
            });
            if (emptyState) emptyState.classList.toggle("is-visible", visibleCount === 0);
        }
        on(searchInput, "input", applyFilters);
        on(ratingFilter, "change", applyFilters);
    })();

    /* ================= ACTIVITY TIMELINE FILTER PILLS ================= */
    (function initTimelineFilters() {
        var pillsWrap = document.getElementById("apdTimelineFilters");
        var items = qsa("#apdTimeline .apd-timeline-item");
        if (!pillsWrap || items.length === 0) return;

        delegate(pillsWrap, "click", ".apd-pill", function (e, pill) {
            qsa(".apd-pill", pillsWrap).forEach(function (p) { p.classList.remove("is-active"); });
            pill.classList.add("is-active");
            var filter = pill.getAttribute("data-apd-filter");
            items.forEach(function (item) {
                var show = filter === "all" || item.getAttribute("data-type") === filter;
                item.classList.toggle("apd-timeline-hidden", !show);
            });
        });
    })();

    /* ================= MODERATION CHECKLIST TOGGLE ================= */
    delegate(document.getElementById("apdModChecklist"), "click", "[data-apd-check]", function (e, item) {
        // Visual toggle only; final states are typically system-derived.
        if (item.classList.contains("is-warning")) return;
        item.classList.toggle("is-complete");
    });

    // /* ================= STOCK ADJUSTMENT PREVIEW ================= */
    // (function initStockAdjustPreview() {
    //     var typeSelect = document.getElementById("apdAdjustType");
    //     var qtyInput = document.getElementById("apdAdjustQty");
    //     var preview = document.getElementById("apdStockPreview");
    //     var currentStock = document.getElementById("product-id").dataset.stock; // TODO(backend): SellerOrder-aware stock read from Product model
    //     if (!typeSelect || !qtyInput || !preview) return;

    //     function updatePreview() {
    //         var qty = parseInt(qtyInput.value, 10) || 0;
    //         var type = typeSelect.value;
    //         var result = currentStock;
    //         if (type === "increase") result = currentStock + qty;
    //         else if (type === "decrease") result = Math.max(0, currentStock - qty);
    //         else if (type === "set") result = qty;
    //         preview.textContent = result.toLocaleString("en-US") + " units";
    //     }
    //     on(typeSelect, "change", updatePreview);
    //     on(qtyInput, "input", updatePreview);
    //     updatePreview();
    // })();

    /* ================= STOCK MANAGEMENT ================= */

    (function initStockManagement() {

        var productData =
            document.getElementById("product-data");

        if (!productData) return;

        var productSlug =
            productData.dataset.productSlug;

        var typeSelect =
            document.getElementById("apdAdjustType");

        var qtyInput =
            document.getElementById("apdAdjustQty");

        var reasonSelect =
            document.getElementById("apdAdjustReason");

        var noteInput =
            document.getElementById("apdAdjustNote");

        var preview =
            document.getElementById("apdStockPreview");

        var currentStockLabel =
            document.getElementById("apdCurrentStockLabel");

        var stockModal =
            document.getElementById("apdStockModal");

        var confirmBtn =
            stockModal
                ? stockModal.querySelector(
                    '[data-apd-confirm-action]'
                )
                : null;

        var currentStock =
            parseInt(
                productData.dataset.stock,
                10
            ) || 0;


        /* ================= STOCK PREVIEW ================= */

        function updatePreview() {

            var qty =
                parseInt(
                    qtyInput ? qtyInput.value : 0,
                    10
                ) || 0;

            var type =
                typeSelect
                    ? typeSelect.value
                    : "increase";

            var result = currentStock;

            if (type === "increase") {
                result = currentStock + qty;
            }

            else if (type === "decrease") {
                result = Math.max(
                    0,
                    currentStock - qty
                );
            }

            else if (type === "set") {
                result = qty;
            }

            if (preview) {
                preview.textContent =
                    result.toLocaleString("en-US") +
                    " units";
            }
        }


        on(
            typeSelect,
            "change",
            updatePreview
        );

        on(
            qtyInput,
            "input",
            updatePreview
        );


        /* ================= OPEN STOCK MODAL ================= */

        var openStockBtn =
            document.querySelector(
                '[data-apd-open-modal="apdStockModal"]'
            );

        if (openStockBtn) {

            on(
                openStockBtn,
                "click",
                function () {

                    if (qtyInput) {
                        qtyInput.value =
                            typeSelect &&
                                typeSelect.value === "set"
                                ? currentStock
                                : 1;
                    }

                    if (currentStockLabel) {
                        currentStockLabel.textContent =
                            currentStock.toLocaleString(
                                "en-US"
                            ) + " units";
                    }

                    updatePreview();

                    openModal(
                        "apdStockModal"
                    );
                }
            );
        }


        /* ================= CONFIRM ADJUSTMENT ================= */

        if (confirmBtn) {

            on(
                confirmBtn,
                "click",
                async function () {

                    var type =
                        typeSelect
                            ? typeSelect.value
                            : "";

                    var quantity =
                        parseInt(
                            qtyInput
                                ? qtyInput.value
                                : 0,
                            10
                        );

                    var reason =
                        reasonSelect
                            ? reasonSelect.value
                            : "";

                    var note =
                        noteInput
                            ? noteInput.value.trim()
                            : "";

                    if (!productSlug) {
                        showToast(
                            "Product slug not found.",
                            "danger"
                        );
                        return;
                    }

                    if (
                        isNaN(quantity) ||
                        quantity < 0
                    ) {
                        showToast(
                            "Enter a valid quantity.",
                            "danger"
                        );
                        return;
                    }

                    if (
                        type === "decrease" &&
                        quantity > currentStock
                    ) {
                        showToast(
                            "Stock cannot be reduced below zero.",
                            "danger"
                        );
                        return;
                    }

                    setButtonLoading(
                        confirmBtn,
                        true
                    );

                    try {

                        var response =
                            await fetch(
                                `/admin-db/catalog/product-management/${productSlug}/stock/adjust/`,
                                {
                                    method: "POST",

                                    headers: {
                                        "Content-Type":
                                            "application/json",

                                        "X-CSRFToken":
                                            getCookie(
                                                "csrftoken"
                                            ),

                                        "X-Requested-With":
                                            "XMLHttpRequest"
                                    },

                                    body: JSON.stringify({
                                        adjustment_type: type,
                                        quantity: quantity,
                                        reason: reason,
                                        note: note
                                    })
                                }
                            );

                        var data =
                            await response.json();

                        if (
                            !response.ok ||
                            !data.success
                        ) {
                            throw new Error(
                                data.message ||
                                "Unable to adjust stock."
                            );
                        }

                        closeModal(
                            stockModal
                        );

                        showToast(
                            data.message ||
                            "Stock adjustment applied.",
                            "success"
                        );

                        setTimeout(
                            function () {
                                window.location.reload();
                            },
                            600
                        );

                    } catch (error) {

                        console.error(
                            "Stock adjustment error:",
                            error
                        );

                        showToast(
                            error.message ||
                            "Unable to adjust stock.",
                            "danger"
                        );

                    } finally {

                        setButtonLoading(
                            confirmBtn,
                            false
                        );
                    }
                }
            );
        }


        /* ================= MARK OUT OF STOCK ================= */

        var outOfStockBtn =
            document.querySelectorAll(
                '[data-apd-stock-action="out-of-stock"]'
            );

        outOfStockBtn.forEach(function (btn) {

            on(
                btn,
                "click",
                async function () {

                    if (
                        !confirm(
                            "Mark this product as out of stock?"
                        )
                    ) {
                        return;
                    }

                    btn.disabled = true;

                    try {

                        var response =
                            await fetch(
                                `/admin-db/catalog/product-management/${productSlug}/stock/out-of-stock/`,
                                {
                                    method: "POST",

                                    headers: {
                                        "X-CSRFToken":
                                            getCookie(
                                                "csrftoken"
                                            ),

                                        "X-Requested-With":
                                            "XMLHttpRequest"
                                    }
                                }
                            );

                        var data =
                            await response.json();

                        if (
                            !response.ok ||
                            !data.success
                        ) {
                            throw new Error(
                                data.message ||
                                "Unable to mark product out of stock."
                            );
                        }

                        showToast(
                            data.message ||
                            "Product marked as out of stock.",
                            "warning"
                        );

                        setTimeout(
                            function () {
                                window.location.reload();
                            },
                            600
                        );

                    } catch (error) {

                        console.error(
                            "Out of stock error:",
                            error
                        );

                        showToast(
                            error.message ||
                            "Unable to update stock status.",
                            "danger"
                        );

                    } finally {

                        btn.disabled =
                            false;
                    }
                }
            );
        });


        /* ================= RESTORE STOCK ================= */

        var restoreStockBtn =
            document.querySelectorAll(
                '[data-apd-stock-action="restore"]'
            );

        restoreStockBtn.forEach(function (btn) {


            on(
                btn,
                "click",
                async function () {

                    if (
                        !confirm(
                            "Restore this product to an available stock status?"
                        )
                    ) {
                        return;
                    }

                    btn.disabled =
                        true;

                    try {

                        var response =
                            await fetch(
                                `/admin-db/catalog/product-management/${productSlug}/stock/restore/`,
                                {
                                    method: "POST",

                                    headers: {
                                        "X-CSRFToken":
                                            getCookie(
                                                "csrftoken"
                                            ),

                                        "X-Requested-With":
                                            "XMLHttpRequest"
                                    }
                                }
                            );

                        var data =
                            await response.json();

                        if (
                            !response.ok ||
                            !data.success
                        ) {
                            throw new Error(
                                data.message ||
                                "Unable to restore stock."
                            );
                        }

                        showToast(
                            data.message ||
                            "Stock restored.",
                            "success"
                        );

                        setTimeout(
                            function () {
                                window.location.reload();
                            },
                            600
                        );

                    } catch (error) {

                        console.error(
                            "Restore stock error:",
                            error
                        );

                        showToast(
                            error.message ||
                            "Unable to restore stock.",
                            "danger"
                        );

                    } finally {

                        btn.disabled =
                            false;
                    }
                }
            );
        });


        /* ================= INITIAL PREVIEW ================= */

        updatePreview();

    })();

    /* ================= ADD ADMIN NOTE ================= */
    (function initAddNote() {
        var saveBtn = document.getElementById("apdSaveNoteBtn");
        var textInput = document.getElementById("apdNoteText");
        var prioritySelect = document.getElementById("apdNotePriority");
        var categorySelect = document.getElementById("apdNoteCategory");
        var pinCheckbox = document.getElementById("apdNotePin");
        var notesList = document.getElementById("apdNotesList");
        if (!saveBtn || !notesList) return;

        var priorityBadgeMap = { low: "c-muted", normal: "c-info", high: "c-warning" };
        var priorityLabelMap = { low: "Low", normal: "Normal", high: "High" };

        on(saveBtn, "click", function () {
            var text = textInput.value.trim();
            if (!text) { showToast("Write a note before saving", "warning"); return; }
            var priority = prioritySelect.value;
            var category = categorySelect.value;
            var pinned = pinCheckbox.checked;

            var card = document.createElement("div");
            card.className = "apd-note-card" + (pinned ? " is-pinned" : "");
            card.innerHTML =
                '<div class="apd-note-head">' +
                '<span class="apd-note-avatar">A</span>' +
                '<div class="apd-note-meta"><strong>You (Admin)</strong><span>Just now &middot; ' + category + '</span></div>' +
                '<span class="apd-badge ' + priorityBadgeMap[priority] + '">' + priorityLabelMap[priority] + '</span>' +
                '</div>' +
                '<p class="apd-note-content"></p>' +
                '<div class="apd-note-actions">' +
                '<button type="button" class="apd-btn apd-btn-ghost apd-btn-sm" data-apd-toast="info" data-apd-toast-msg="Editing notes isn&#8217;t available yet.">Edit</button>' +
                '<button type="button" class="apd-btn apd-btn-ghost apd-btn-sm" data-apd-toast="info" data-apd-toast-msg="Note pin updated.">' + (pinned ? "Unpin" : "Pin") + '</button>' +
                '<button type="button" class="apd-btn apd-btn-ghost apd-btn-sm c-danger" data-apd-toast="danger" data-apd-toast-msg="Note removed.">Delete</button>' +
                '</div>';
            card.querySelector(".apd-note-content").textContent = text;
            notesList.insertBefore(card, notesList.firstChild);

            // TODO(backend): POST admin note to AdminProductNote model
            textInput.value = "";
            pinCheckbox.checked = false;
            closeModal(document.getElementById("apdNoteModal"));
            showToast("Admin note saved", "success");
        });
    })();

    /* ================= DELEGATED DELETE FOR DYNAMICALLY ADDED NOTE/ROW ACTIONS ================= */
    delegate(document, "click", ".apd-note-card [data-apd-toast='danger']", function (e, target) {
        var card = target.closest(".apd-note-card");
        if (card) {
            setTimeout(function () { card.remove(); }, 250);
        }
    });

})();
