/* =========================================================================
   MARKETSPHERE — SELLER DASHBOARD: SETTINGS
   Frontend-only interactions for seller_dashboard/templates/settings.html.
   No fetch(), no AJAX, no backend calls, no external libraries. Matches
   the pattern already used across the seller dashboard (see
   seller_dashboard/static/js/products.js, product_form.js).

   Sections:
     1. DOM Cache
     2. Toast Helper
     3. Scroll Reveal
     4. Settings Nav: Smooth Scroll + Scrollspy
     5. Mobile Nav Active Sync
     6. Character Counter
     7. Image Upload Preview (Logo / Banner, drag & drop)
     8. Dirty State Tracking
     9. Save / Cancel / Reset Button Behavior
    10. Leave-Page Confirmation
    11. Init
   ========================================================================= */
function getCookie(name) {
    let cookieValue = null;

    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");

        for (let cookie of cookies) {
            cookie = cookie.trim();

            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }

    return cookieValue;
}
document.addEventListener('DOMContentLoaded', function () {

    var page = document.getElementById('sePage');
    if (!page) return; // not on the settings page

    /* ================= 1. DOM CACHE ================= */
    var toastContainer = document.getElementById('seToastContainer');
    var navLinks = Array.prototype.slice.call(document.querySelectorAll('.se-nav-link'));
    var sections = Array.prototype.slice.call(document.querySelectorAll('[data-se-section]'));

    /* ================= 3. SCROLL REVEAL ================= */
    var revealTargets = Array.prototype.slice.call(document.querySelectorAll('.se-reveal'));

    if ('IntersectionObserver' in window && revealTargets.length) {
        var revealObserver = new IntersectionObserver(function (entries, obs) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-visible');
                obs.unobserve(entry.target);
            });
        }, { threshold: 0.08 });

        revealTargets.forEach(function (el) {
            revealObserver.observe(el);
        });
    } else {
        revealTargets.forEach(function (el) {
            el.classList.add('is-visible');
        });
    }

    /* ================= 4. SETTINGS NAV: SMOOTH SCROLL + SCROLLSPY ================= */
    function setActiveNav(id) {
        navLinks.forEach(function (link) {
            var isMatch = link.getAttribute('data-se-nav') === id;
            link.classList.toggle('is-active', isMatch);
            link.setAttribute('aria-selected', isMatch ? 'true' : 'false');
        });
    }

    navLinks.forEach(function (link) {
        link.addEventListener('click', function (e) {
            var targetId = link.getAttribute('data-se-nav');
            var target = document.getElementById(targetId);
            if (!target) return;

            e.preventDefault();
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            setActiveNav(targetId);

            if (window.history && window.history.replaceState) {
                window.history.replaceState(null, '', '#' + targetId);
            }
        });
    });

    if ('IntersectionObserver' in window && sections.length) {
        var spy = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    setActiveNav(entry.target.id);
                }
            });
        }, { rootMargin: '-40% 0px -50% 0px', threshold: 0 });

        sections.forEach(function (section) {
            spy.observe(section);
        });
    }

    /* ================= 6. CHARACTER COUNTER ================= */
    document.querySelectorAll('[data-se-counter]').forEach(function (el) {
        var counterEl = document.getElementById(el.getAttribute('data-se-counter'));
        if (!counterEl) return;

        var update = function () {
            counterEl.textContent = String(el.value.length);
        };

        el.addEventListener('input', update);
        update();
    });

    /* ================= 7. IMAGE UPLOAD PREVIEW ================= */
    function initImageUpload(zoneId, inputId, previewId, isRound) {
        var zone = document.getElementById(zoneId);
        var input = document.getElementById(inputId);
        var preview = document.getElementById(previewId);

        if (!zone || !input || !preview) return;

        function applyFile(file) {
            if (!file || !file.type || file.type.indexOf('image/') !== 0) return;

            var url = URL.createObjectURL(file);
            preview.innerHTML = '';

            var img = document.createElement('img');
            img.src = url;
            img.alt = isRound ? 'Store logo preview' : 'Store banner preview';
            preview.appendChild(img);

            markDirty();
        }

        zone.addEventListener('click', function () { input.click(); });
        zone.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                input.click();
            }
        });

        input.addEventListener('change', function () {
            if (input.files && input.files[0]) applyFile(input.files[0]);
            // input.value = '';
        });

        ['dragenter', 'dragover'].forEach(function (evt) {
            zone.addEventListener(evt, function (e) {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.add('is-dragover');
            });
        });

        ['dragleave', 'drop'].forEach(function (evt) {
            zone.addEventListener(evt, function (e) {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.remove('is-dragover');
            });
        });

        zone.addEventListener('drop', function (e) {
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
                applyFile(e.dataTransfer.files[0]);
            }
        });
    }

    initImageUpload('seLogoUploadZone', 'seLogoInput', 'seLogoPreview', true);
    initImageUpload('seBannerUploadZone', 'seBannerInput', 'seBannerPreview', false);

    var changeLogoBtn = document.getElementById('seChangeLogoBtn');
    var changeBannerBtn = document.getElementById('seChangeBannerBtn');
    var logoInput = document.getElementById('seLogoInput');
    var bannerInput = document.getElementById('seBannerInput');

    if (changeLogoBtn && logoInput) {
        changeLogoBtn.addEventListener('click', function () { logoInput.click(); });
    }
    if (changeBannerBtn && bannerInput) {
        changeBannerBtn.addEventListener('click', function () { bannerInput.click(); });
    }

    /* ================= 8. DIRTY STATE TRACKING ================= */
    var isDirty = false;

    function markDirty() {
        isDirty = true;
        page.setAttribute('data-dirty', 'true');
    }

    function markClean() {
        isDirty = false;
        page.setAttribute('data-dirty', 'false');
    }

    document.querySelectorAll('[data-se-track]').forEach(function (field) {
        var evt = (field.tagName === 'SELECT' || field.type === 'checkbox') ? 'change' : 'input';
        field.addEventListener(evt, markDirty);
    });

    /* ================= 9. SAVE / CANCEL / RESET BUTTONS ================= */
    function setButtonLoading(btn, isLoading) {
        var label = btn.querySelector('.se-btn-label');

        if (isLoading) {
            btn.classList.add('is-loading');
            btn.disabled = true;
            if (label) {
                btn.dataset.originalLabel = label.innerHTML;
                label.innerHTML = btn.getAttribute('data-loading-label') || 'Working&hellip;';
            }
        } else {
            btn.classList.remove('is-loading');
            btn.disabled = false;
            if (label && btn.dataset.originalLabel) {
                label.innerHTML = btn.dataset.originalLabel;
            }
        }
    }

    document.querySelectorAll("[data-se-save]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            if (btn.classList.contains("is-loading")) return;

            const section = btn.closest("[data-se-section]");
            // ================= BUSINESS ADDRESS =================
            if (section?.id === "businessAddress") {

                const fullName = document.getElementById("seBizName");
                const phone = document.getElementById("seBizPhone");
                const address1 = document.getElementById("seBizAddr1");
                const city = document.getElementById("seBizCity");
                const postalCode = document.getElementById("seBizPostal");

                if (!fullName.value.trim()) {
                    showToast("Please enter a business contact name.", "error");
                    fullName.focus();
                    return;
                }

                if (!address1.value.trim()) {
                    showToast("Please enter a business address.", "error");
                    address1.focus();
                    return;
                }

                setButtonLoading(btn, true);

                const formData = new FormData();
                formData.append("fullName", fullName.value.trim());
                formData.append("phone", phone.value.trim());
                formData.append("address", address1.value.trim());
                formData.append("city", city.value.trim());
                formData.append("postalCode", postalCode.value.trim());

                fetch("/accounts/update-seller-address/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    body: formData,
                })
                    .then(response => response.json())
                    .then(data => {
                        setButtonLoading(btn, false);

                        if (data.success) {
                            markClean();
                            showToast(data.message, "success");
                        } else {
                            showToast(
                                data.message || "Unable to update business address.",
                                "error"
                            );
                        }
                    })
                    .catch(error => {
                        console.error(error);

                        setButtonLoading(btn, false);

                        showToast(
                            "Something went wrong. Please try again.",
                            "error"
                        );
                    });

                return;
            }
            // ================= STORE INFORMATION =================
            if (section && section.id === "storeInformation") {

                const storeName = document.getElementById("seStoreName");
                const storeEmail = document.getElementById("seStoreEmail");
                const description = document.getElementById("seStoreDescription");
                const storeLogo = document.getElementById("seLogoInput");
                const storeBanner = document.getElementById("seBannerInput");

                if (!storeName.value.trim()) {
                    showToast("Please enter a store name before saving.", "error");
                    storeName.focus();
                    return;
                }

                setButtonLoading(btn, true);

                const formData = new FormData();

                formData.append("store_name", storeName.value.trim());
                formData.append("store_email", storeEmail.value.trim());
                formData.append("store_description", description.value.trim());

                if (storeLogo.files.length > 0) {
                    formData.append("store_logo", storeLogo.files[0]);
                }

                if (storeBanner.files.length > 0) {
                    formData.append("store_banner", storeBanner.files[0]);
                }

                fetch("/accounts/update-seller-info/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    body: formData,
                })
                    .then(response => response.json())
                    .then(data => {
                        setButtonLoading(btn, false);

                        if (data.success) {
                            markClean();
                            showToast(data.message, "success");
                        } else {
                            showToast(
                                data.message || "Unable to update store information.",
                                "error"
                            );
                        }
                    })
                    .catch(error => {
                        console.error(error);

                        setButtonLoading(btn, false);

                        showToast(
                            "Something went wrong. Please try again.",
                            "error"
                        );
                    });

                return;
            }
            // ================= SHIPPING PREFERENCES =================
            if (section && section.id === "shippingPreferences") {

                const defaultCourier = document.getElementById("seDefaultCourier");
                const handlingTime = document.getElementById("seHandlingTime");
                const returnAddress = document.getElementById("seReturnAddress");
                const shippingNotes = document.getElementById("seShippingNotes");
                const autoShipped = document.getElementById("seAutoShipped");
                const shippingFee = document.getElementById("seShippingFee");

                setButtonLoading(btn, true);

                const formData = new FormData();

                formData.append("default_courier", defaultCourier.value);
                formData.append("handling_time", handlingTime.value);
                formData.append("return_address", returnAddress.value.trim());
                formData.append("shipping_notes", shippingNotes.value.trim());
                formData.append("auto_mark_shipped", autoShipped.checked);
                formData.append("shipping_fee", shippingFee.value);

                fetch("/accounts/update-shipping-preferences/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    body: formData,
                })
                    .then(response => response.json())
                    .then(data => {

                        setButtonLoading(btn, false);

                        if (data.success) {
                            markClean();
                            showToast(data.message, "success");
                        } else {
                            showToast(data.message || "Unable to update shipping preferences.", "error");
                        }

                    })
                    .catch(error => {

                        console.error(error);

                        setButtonLoading(btn, false);

                        showToast("Something went wrong. Please try again.", "error");

                    });

                return;
            }
            // ================= NOTIFICATION PREFERENCES =================
            if (section && section.id === "notifications") {

                const emailNewOrder = document.getElementById("seEmailNewOrder");
                const emailCancelledOrder = document.getElementById("seEmailCancelledOrder");
                const emailDeliveredOrder = document.getElementById("seEmailDeliveredOrder");
                const emailLowStock = document.getElementById("seEmailLowStock");
                const weeklySalesSummary = document.getElementById("seWeeklySalesSummary");
                const monthlyStoreReport = document.getElementById("seMonthlyStoreReport");

                setButtonLoading(btn, true);

                const formData = new FormData();

                formData.append("email_new_order", emailNewOrder.checked);
                formData.append("email_cancelled_order", emailCancelledOrder.checked);
                formData.append("email_delivered_order", emailDeliveredOrder.checked);
                formData.append("email_low_stock", emailLowStock.checked);
                formData.append("weekly_sales_summary", weeklySalesSummary.checked);
                formData.append("monthly_store_report", monthlyStoreReport.checked);

                fetch("/accounts/update-notification-preferences/", {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                    },
                    body: formData,
                })
                    .then(response => response.json())
                    .then(data => {

                        setButtonLoading(btn, false);

                        if (data.success) {
                            markClean();
                            showToast(data.message, "success");
                        } else {
                            showToast(
                                data.message || "Unable to update notification preferences.",
                                "error"
                            );
                        }

                    })
                    .catch(error => {

                        console.error(error);

                        setButtonLoading(btn, false);

                        showToast(
                            "Something went wrong. Please try again.",
                            "error"
                        );

                    });

                return;
            } else if (section.id === "storeSettings") {
                // Save store settings
            }
            else if (section.id === "security") {
                // Save password
            }
        });
    });

    document.querySelectorAll('[data-se-cancel]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var card = btn.closest('.se-card');
            if (card) {
                card.querySelectorAll('input[type="text"], input[type="email"], textarea').forEach(function (field) {
                    field.value = '';
                });
                var counter = card.querySelector('[data-se-counter]');
                if (counter) counter.dispatchEvent(new Event('input'));
            }
            showToast('Changes discarded.', 'info');
        });
    });

    document.querySelectorAll('[data-se-reset]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var card = btn.closest('.se-card');
            if (!card) return;

            card.querySelectorAll('input, textarea').forEach(function (field) {
                if (field.type === 'checkbox') {
                    field.checked = false;
                } else {
                    field.value = '';
                }
            });
            card.querySelectorAll('select').forEach(function (select) {
                select.selectedIndex = 0;
            });

            showToast('Shipping preferences reset.', 'info');
        });
    });

    /* ================= 10. LEAVE-PAGE CONFIRMATION ================= */
    window.addEventListener('beforeunload', function (e) {
        if (!isDirty) return;
        e.preventDefault();
        e.returnValue = '';
        return '';
    });

    var leaveModalOverlay = document.getElementById('seLeaveModalOverlay');
    var leaveKeepBtn = document.getElementById('seLeaveKeepBtn');
    var leaveDiscardBtn = document.getElementById('seLeaveDiscardBtn');
    var pendingNavHref = null;

    function openLeaveModal(href) {
        if (!leaveModalOverlay) return;
        pendingNavHref = href;
        leaveModalOverlay.classList.remove('se-hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeLeaveModal() {
        if (!leaveModalOverlay) return;
        leaveModalOverlay.classList.add('se-hidden');
        document.body.style.overflow = '';
        pendingNavHref = null;
    }

    // Intercept in-app navigation (sidebar links, "Back to Store", etc.)
    // so unsaved changes on this page get a friendly confirmation instead
    // of the raw browser beforeunload prompt.
    document.addEventListener('click', function (e) {
        var link = e.target.closest('a[href]');
        if (!link) return;
        if (!isDirty) return;
        if (link.closest('.se-nav')) return; // in-page section links are fine
        if (link.target === '_blank') return;

        var href = link.getAttribute('href');
        if (!href || href.charAt(0) === '#') return;

        e.preventDefault();
        openLeaveModal(href);
    });

    if (leaveKeepBtn) {
        leaveKeepBtn.addEventListener('click', closeLeaveModal);
    }

    if (leaveDiscardBtn) {
        leaveDiscardBtn.addEventListener('click', function () {
            markClean();
            var href = pendingNavHref;
            closeLeaveModal();
            if (href) window.location.href = href;
        });
    }

    if (leaveModalOverlay) {
        leaveModalOverlay.addEventListener('click', function (e) {
            if (e.target === leaveModalOverlay) closeLeaveModal();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && leaveModalOverlay && !leaveModalOverlay.classList.contains('se-hidden')) {
            closeLeaveModal();
        }
    });

    /* ================= 11. INIT ================= */
    // Honor a deep-link hash (e.g. settings#security) on load.
    if (window.location.hash) {
        var initialId = window.location.hash.slice(1);
        var initialTarget = document.getElementById(initialId);
        if (initialTarget) {
            window.setTimeout(function () {
                initialTarget.scrollIntoView({ block: 'start' });
                setActiveNav(initialId);
            }, 50);
        }
    }
    const deactivateAccountBtn = document.getElementById("deactivateAccount");

    if (deactivateAccountBtn) {
        deactivateAccountBtn.addEventListener("click", function () {

            if (deactivateAccountBtn.classList.contains("is-loading")) return;

            const confirmed = confirm(
                "Are you sure you want to deactivate your seller account?\n\nYou won't be able to sell products until your account is reactivated."
            );

            if (!confirmed) return;

            setButtonLoading(deactivateAccountBtn, true);

            fetch("/accounts/deactivate-seller-account", {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
            })
                .then(response => response.json())
                .then(data => {

                    setButtonLoading(deactivateAccountBtn, false);

                    if (data.status === "success") {
                        showToast(
                            "Your seller account has been deactivated.",
                            "success"
                        );

                        setTimeout(() => {
                            window.location.href = "/";
                        }, 1500);
                    } else {
                        showToast(
                            data.message || "Unable to deactivate your account.",
                            "error"
                        );
                    }

                })
                .catch(error => {

                    console.error(error);

                    setButtonLoading(deactivateAccountBtn, false);

                    showToast(
                        "Something went wrong. Please try again.",
                        "error"
                    );

                });
        });
    }
});