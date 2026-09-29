/* =========================================================
   MARKETSPHERE ADMIN — ALL PROMOTIONS PAGE JS
   Minimal, presentational only: row-action dropdowns and
   wiring for placeholder buttons (Create Promotion, Manage
   Promotion, Archive) to the global showToast() helper
   already defined in static/js/scripts.js. No data fetching,
   no primary-table rendering happens here.
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {
    /* ---------------- Row action dropdowns ---------------- */
    const dropdowns = document.querySelectorAll(".apr-dropdown");

    function closeAllDropdowns(except) {
        dropdowns.forEach(function (dropdown) {
            if (dropdown !== except) {
                dropdown.classList.remove("is-open");
                const trigger = dropdown.querySelector(".apr-dropdown-trigger");
                if (trigger) trigger.setAttribute("aria-expanded", "false");
            }
        });
    }

    dropdowns.forEach(function (dropdown) {
        const trigger = dropdown.querySelector(".apr-dropdown-trigger");
        if (!trigger) return;

        trigger.addEventListener("click", function (event) {
            event.stopPropagation();
            const isOpen = dropdown.classList.toggle("is-open");
            trigger.setAttribute("aria-expanded", isOpen ? "true" : "false");
            closeAllDropdowns(dropdown);
        });
    });

    document.addEventListener("click", function () {
        closeAllDropdowns(null);
    });

    /* ---------------- Placeholder action toasts ---------------- */
    document.querySelectorAll("[data-toast]").forEach(function (el) {
        el.addEventListener("click", function (event) {
            event.preventDefault();
            const message = el.getAttribute("data-toast");
            if (typeof window.showToast === "function") {
                window.showToast(message, "info");
            }
        });
    });
});





/* =========================================================
   CREATE PROMOTION — form-only behaviors
   Presentational enhancements only; Django/backend validation
   remains authoritative. No AJAX, no primary-form rendering.
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {
    initImageUpload("aprBannerInput", "aprBannerPreview", "aprBannerFileName", "aprBannerRemoveBtn");
    initImageUpload("aprThumbnailInput", "aprThumbnailPreview", "aprThumbnailFileName", "aprThumbnailRemoveBtn");
    initHomepagePriorityToggle();
    initCategorySearch();
    initDateValidation();
    initSubmitState();
    initUpdateState();
});

/* ---------------- Image upload preview ---------------- */
function initImageUpload(inputId, previewId, fileNameId, removeBtnId) {
    const input = document.getElementById(inputId);
    const preview = document.getElementById(previewId);
    const fileNameEl = document.getElementById(fileNameId);
    const removeBtn = document.getElementById(removeBtnId);

    if (!input || !preview) return;

    input.addEventListener("change", function () {
        const file = input.files && input.files[0];
        if (!file) return;

        if (fileNameEl) fileNameEl.textContent = file.name;

        const reader = new FileReader();
        reader.onload = function (e) {
            preview.src = e.target.result;
            preview.hidden = false;
            if (removeBtn) removeBtn.classList.remove("is-hidden");
        };
        reader.readAsDataURL(file);
    });

    if (removeBtn) {
        removeBtn.addEventListener("click", function () {
            input.value = "";
            preview.src = "";
            preview.hidden = true;
            if (fileNameEl) fileNameEl.textContent = "";
            removeBtn.classList.add("is-hidden");
        });
    }
}

/* ---------------- Homepage priority enable/disable ---------------- */
function initHomepagePriorityToggle() {
    const toggle = document.getElementById("aprHomepageToggle");
    const priorityField = document.getElementById("aprHomepagePriorityField");

    if (!toggle || !priorityField) return;

    function syncState() {
        priorityField.classList.toggle("is-disabled", !toggle.checked);
    }

    toggle.addEventListener("change", syncState);
    syncState();
}

/* ---------------- Category search filter ---------------- */
function initCategorySearch() {
    const searchInput = document.getElementById("aprCategorySearch");
    const grid = document.getElementById("aprCategoryGrid");
    const noResults = document.getElementById("aprCategoryNoResults");

    if (!searchInput || !grid) return;

    const items = Array.from(grid.querySelectorAll(".apr-category-checkbox"));

    searchInput.addEventListener("input", function () {
        const query = searchInput.value.trim().toLowerCase();
        let visibleCount = 0;

        items.forEach(function (item) {
            const matches = item.dataset.categoryName.indexOf(query) !== -1;
            item.classList.toggle("is-hidden", !matches);
            if (matches) visibleCount += 1;
        });

        if (noResults) {
            noResults.classList.toggle("is-hidden", visibleCount !== 0 || items.length === 0);
        }
    });
}

/* ---------------- Client-side date sanity check ---------------- */
function initDateValidation() {
    const startInput = document.getElementById("aprStartAt");
    const endInput = document.getElementById("aprEndAt");
    const hint = document.getElementById("aprDateHint");

    if (!startInput || !endInput) return;

    function validate() {
        if (!startInput.value || !endInput.value) return;

        const isInvalid = new Date(endInput.value) <= new Date(startInput.value);
        endInput.classList.toggle("is-invalid", isInvalid);

        if (hint) {
            hint.textContent = isInvalid
                ? "End date must be after the start date."
                : "Must be after the start date and time.";
        }
    }

    startInput.addEventListener("change", validate);
    endInput.addEventListener("change", validate);
}

/* ---------------- Submit-state feedback ---------------- */
function initSubmitState() {
    const form = document.getElementById("aprCreateForm");
    const submitBtn = document.getElementById("aprSubmitBtn");

    if (!form || !submitBtn) return;

    form.addEventListener("submit", function () {
        if (submitBtn.disabled) return;
        submitBtn.disabled = true;
        submitBtn.innerHTML = "Creating\u2026";
    });
}

function initUpdateState() {
    const form = document.getElementById("aprUpdateForm");
    const submitBtn = document.getElementById("aprUpdateBtn");

    if (!form || !submitBtn) return;

    form.addEventListener("submit", function () {
        if (submitBtn.disabled) return;
        submitBtn.disabled = true;
        submitBtn.innerHTML = "Updating\u2026";
    });
}


/* =========================================================
   MANAGE PROMOTION PRODUCTS — row actions
   Real POST requests to the existing service-backed endpoints.
   No table rendering here — only reacting to server responses.
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {
    initEditPromoPriceModal();
    initFeatureToggle();
    initRemoveModal();
});

function getCsrfToken() {
    if (typeof window.getCookie === "function") {
        return window.getCookie("csrftoken");
    }
    const cookie = document.cookie.split("; ").find(function (row) {
        return row.startsWith("csrftoken=");
    });
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
}

/* ---------------- Edit Promotion Price ---------------- */
function initEditPromoPriceModal() {
    const modal = document.getElementById("aprEditPriceModal");
    if (!modal) return;

    const nameEl = document.getElementById("aprEditPriceProductName");
    const regularEl = document.getElementById("aprEditPriceRegular");
    const currentEl = document.getElementById("aprEditPriceCurrent");
    const input = document.getElementById("aprNewPromoPrice");
    const errorEl = document.getElementById("aprEditPriceError");
    const saveBtn = document.getElementById("aprEditPriceSaveBtn");

    let activeUrl = null;
    let activeRow = null;

    function openModal(btn) {
        activeUrl = btn.dataset.url;
        activeRow = document.getElementById("aprRow" + btn.dataset.promoItemId);

        if (nameEl) nameEl.textContent = btn.dataset.productName;
        if (regularEl) regularEl.textContent = "Rs. " + btn.dataset.regularPrice;
        if (currentEl) currentEl.textContent = "Rs. " + btn.dataset.currentPrice;
        if (input) input.value = btn.dataset.currentPrice;
        if (errorEl) {
            errorEl.classList.add("is-hidden");
            errorEl.textContent = "";
        }

        modal.classList.remove("is-hidden");
    }

    function closeModal() {
        modal.classList.add("is-hidden");
        activeUrl = null;
        activeRow = null;
    }

    document.querySelectorAll(".apr-edit-price-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            openModal(btn);
        });
    });

    const closeBtn = document.getElementById("aprEditPriceModalClose");
    const cancelBtn = document.getElementById("aprEditPriceCancelBtn");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", function (event) {
        if (event.target === modal) closeModal();
    });

    if (saveBtn) {
        saveBtn.addEventListener("click", function () {
            if (!activeUrl || !input) return;

            errorEl.classList.add("is-hidden");
            saveBtn.disabled = true;

            fetch(activeUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrfToken(),
                },
                body: JSON.stringify({ promotion_price: input.value }),
            })
                .then(function (response) {
                    return response.json().then(function (data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function (result) {
                    if (!result.ok || !result.data.success) {
                        errorEl.textContent = result.data.message || "Unable to update the promotion price.";
                        errorEl.classList.remove("is-hidden");
                        return;
                    }

                    if (activeRow) {
                        const priceEl = activeRow.querySelector(".apr-promo-price-value");
                        const discountEl = activeRow.querySelector(".apr-discount-value");
                        if (priceEl) priceEl.textContent = "Rs. " + Math.round(parseFloat(result.data.promotion_price));
                        if (discountEl) discountEl.textContent = Math.round(parseFloat(result.data.discount_percentage)) + "% OFF";
                    }

                    if (typeof window.showToast === "function") {
                        window.showToast(result.data.message, "success");
                    }

                    closeModal();
                })
                .catch(function () {
                    errorEl.textContent = "Something went wrong. Please try again.";
                    errorEl.classList.remove("is-hidden");
                })
                .finally(function () {
                    saveBtn.disabled = false;
                });
        });
    }
}

/* ---------------- Feature / Unfeature ---------------- */
function initFeatureToggle() {
    document.querySelectorAll(".apr-toggle-featured-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const url = btn.dataset.url;
            const row = document.getElementById("aprRow" + btn.dataset.promoItemId);
            if (!url) return;

            fetch(url, {
                method: "POST",
                headers: { "X-CSRFToken": getCsrfToken() },
            })
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (!data.success) {
                        if (typeof window.showToast === "function") {
                            window.showToast(data.message || "Unable to update this product.", "error");
                        }
                        return;
                    }

                    if (row) {
                        const featuredBadge = row.querySelector(".apr-featured-badge");
                        const notFeaturedText = row.querySelector(".apr-not-featured-text");
                        if (featuredBadge) featuredBadge.classList.toggle("is-hidden", !data.is_featured);
                        if (notFeaturedText) notFeaturedText.classList.toggle("is-hidden", data.is_featured);
                    }

                    const label = btn.querySelector(".apr-toggle-featured-label");
                    if (label) label.textContent = data.is_featured ? "Unfeature" : "Feature";
                    btn.dataset.featured = data.is_featured ? "true" : "false";

                    if (typeof window.showToast === "function") {
                        window.showToast(data.message, "success");
                    }
                })
                .catch(function () {
                    if (typeof window.showToast === "function") {
                        window.showToast("Something went wrong. Please try again.", "error");
                    }
                });
        });
    });
}

/* ---------------- Remove from Promotion ---------------- */
function initRemoveModal() {
    const modal = document.getElementById("aprRemoveModal");
    if (!modal) return;

    const nameEl = document.getElementById("aprRemoveProductName");
    const confirmBtn = document.getElementById("aprRemoveConfirmBtn");

    let activeUrl = null;
    let activeRow = null;

    function openModal(btn) {
        activeUrl = btn.dataset.url;
        activeRow = document.getElementById("aprRow" + btn.dataset.promoItemId);
        if (nameEl) nameEl.textContent = btn.dataset.productName;
        modal.classList.remove("is-hidden");
    }

    function closeModal() {
        modal.classList.add("is-hidden");
        activeUrl = null;
        activeRow = null;
    }

    document.querySelectorAll(".apr-remove-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            openModal(btn);
        });
    });

    const closeBtn = document.getElementById("aprRemoveModalClose");
    const cancelBtn = document.getElementById("aprRemoveCancelBtn");
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", function (event) {
        if (event.target === modal) closeModal();
    });

    if (confirmBtn) {
        confirmBtn.addEventListener("click", function () {
            if (!activeUrl) return;

            confirmBtn.disabled = true;

            fetch(activeUrl, {
                method: "POST",
                headers: { "X-CSRFToken": getCsrfToken() },
            })
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (!data.success) {
                        if (typeof window.showToast === "function") {
                            window.showToast(data.message || "Unable to remove this product.", "error");
                        }
                        return;
                    }

                    if (activeRow) {
                        activeRow.remove();
                    }

                    if (typeof window.showToast === "function") {
                        window.showToast(data.message, "success");
                    }

                    closeModal();
                })
                .catch(function () {
                    if (typeof window.showToast === "function") {
                        window.showToast("Something went wrong. Please try again.", "error");
                    }
                })
                .finally(function () {
                    confirmBtn.disabled = false;
                });
        });
    }
}