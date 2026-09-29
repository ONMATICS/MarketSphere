/* =========================================================================
   MARKETSPHERE ADMIN — SETTINGS (settings.js)
   Interaction layer for admin_panel/templates/admin_settings.html.
   Vanilla JS, IIFE-scoped. Saves through the admin settings endpoint.
   NEVER generates settings markup — every section, card, field and table
   row already exists in the Django template. This file only enhances
   interaction: section switching, dirty-state tracking, toggles, modals,
   previews and toasts.

   Sections:
     1. Initialization / DOM Cache
     2. Navigation (section switching)
     3. Form State (dirty tracking per section)
     4. Dirty State (header bar + save/discard)
     5. Toggles (switch confirmation gating)
     6. Modals
     7. Confirmation (reset section / reset all / discard nav)
     8. Image Preview (logo / favicon upload)
     9. SEO Preview
    10. Theme Preview (appearance colors)
    11. Toasts
    12. Loading States (save button)
    13. Accessibility (dropdown, escape key)
    14. Responsive Behavior (mobile nav select, audit filters, ripple)
   ========================================================================= */

(function () {
    "use strict";

    var root = document.getElementById("setPage");
    if (!root) return;

    function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function qsa(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

    /* ================= 1. STATE ================= */
    var dirtySections = new Set();
    var pendingNavSection = null;
    var pendingToggle = null; // { input, modalId }

    /* =====================================================================
       2. NAVIGATION
       ===================================================================== */
    var navLinks = qsa(".set-nav-link", root);
    var panels = qsa(".set-panel", root);
    var mobileSelect = qs("#setMobileNavSelect");

    function activateSection(name, opts) {
        opts = opts || {};

        if (!opts.force && dirtySections.has(activeSectionName()) && name !== activeSectionName()) {
            pendingNavSection = name;
            openModal("setDiscardChangesModal");
            return;
        }

        navLinks.forEach(function (link) {
            var match = link.getAttribute("data-set-section") === name;
            link.classList.toggle("is-active", match);
            if (match) link.setAttribute("aria-current", "page");
            else link.removeAttribute("aria-current");
        });

        panels.forEach(function (panel) {
            panel.classList.toggle("is-active", panel.getAttribute("data-set-panel") === name);
        });

        if (mobileSelect) mobileSelect.value = name;

        root.setAttribute("data-active-section", name);
        window.scrollTo({ top: root.offsetTop - 90, behavior: "smooth" });
    }

    function activeSectionName() {
        return root.getAttribute("data-active-section") || "overview";
    }

    navLinks.forEach(function (link) {
        link.addEventListener("click", function () {
            activateSection(link.getAttribute("data-set-section"));
        });
    });

    qsa("[data-set-goto-section]").forEach(function (el) {
        el.addEventListener("click", function () {
            activateSection(el.getAttribute("data-set-goto-section"));
        });
    });

    if (mobileSelect) {
        mobileSelect.addEventListener("change", function () {
            activateSection(mobileSelect.value);
        });
    }

    /* =====================================================================
       3 & 4. FORM STATE / DIRTY STATE
       ===================================================================== */
    var unsavedBar = qs("#setUnsavedBar");
    var headerSaveBtn = qs("#setSaveChangesBtn");

    function markDirty(sectionName) {
        dirtySections.add(sectionName);
        updateUnsavedUI();
    }

    function clearDirty(sectionName) {
        dirtySections.delete(sectionName);
        updateUnsavedUI();
    }

    function updateUnsavedUI() {
        var isDirty = dirtySections.has(activeSectionName());
        if (unsavedBar) unsavedBar.classList.toggle("set-hidden", !isDirty);
        if (headerSaveBtn) headerSaveBtn.disabled = dirtySections.size === 0;
    }

    qsa("[data-set-form]").forEach(function (form) {
        var panel = form.closest(".set-panel");
        var sectionName = panel ? panel.getAttribute("data-set-panel") : null;
        if (!sectionName) return;

        qsa("[data-set-track]", form).forEach(function (field) {
            var evt = (field.tagName === "SELECT" || field.type === "checkbox" || field.type === "color") ? "change" : "input";
            field.addEventListener(evt, function () {
                markDirty(sectionName);
            });
        });
    });

    /* =====================================================================
       12. SAVE / RESET
       ===================================================================== */
    function csrfToken() {
        var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function applyBackendValues() {
        var dataNode = qs("#setBackendData");
        if (!dataNode) return;
        var data;
        try { data = JSON.parse(dataNode.textContent || "{}"); } catch (e) { return; }
        qsa("[data-set-form]").forEach(function (form) {
            var panel = form.closest(".set-panel");
            var section = panel && panel.getAttribute("data-set-panel");
            var values = data[section] || {};
            if (section === "notifications") {
                ["BUYER", "SELLER", "ADMIN"].forEach(function (audience) {
                    var field = audience.toLowerCase() + "_notifications";
                    var matrix = values[field] || {};
                    qsa("[data-notification-audience='" + audience + "']", form).forEach(function (row) {
                        var event = row.getAttribute("data-notification-event");
                        var channels = matrix[event] || matrix["*"] || { email: true, in_app: true, push: false };
                        qsa("[data-notification-channel]", row).forEach(function (input) {
                            var channel = input.getAttribute("data-notification-channel");
                            var value = channels[channel];
                            input.checked = value === true || value === "true" || value === 1 || value === "1" || (value === undefined && channel !== "push");
                        });
                    });
                });
            }
            qsa("[data-set-track][name]", form).forEach(function (field) {
                if (!Object.prototype.hasOwnProperty.call(values, field.name)) return;
                var value = values[field.name];
                if (field.type === "checkbox") field.checked = value === true || value === "true" || value === 1 || value === "1";
                else if (field.type !== "file") field.value = value == null ? "" : value;
            });
        });
    }

    function formPayload(form, sectionName) {
        var payload = new FormData(form);
        var booleanFields = [];
        qsa('input[type="checkbox"][data-set-track][name]', form).forEach(function (field) {
            payload.delete(field.name);
            payload.append(field.name, field.checked ? "true" : "false");
            booleanFields.push(field.name);
        });
        if (sectionName === "notifications") {
            ["BUYER", "SELLER", "ADMIN"].forEach(function (audience) {
                var matrix = {};
                qsa("[data-notification-audience='" + audience + "']", form).forEach(function (row) {
                    var channels = {};
                    qsa("[data-notification-channel]", row).forEach(function (input) {
                        channels[input.getAttribute("data-notification-channel")] = input.checked;
                    });
                    matrix[row.getAttribute("data-notification-event")] = channels;
                });
                payload.append(audience.toLowerCase() + "_notifications", JSON.stringify(matrix));
            });
        }
        payload.append("__section", sectionName);
        payload.append("__boolean_fields", JSON.stringify(booleanFields));
        return payload;
    }

    function runSave(button, sectionName) {
        if (!button || button.classList.contains("is-loading")) return;

        var panel = button.closest(".set-panel");
        var form = panel ? qs("[data-set-form]", panel) : null;
        if (!form || !sectionName) return;

        var originalHTML = button.innerHTML;
        button.classList.add("is-loading");
        button.disabled = true;
        button.innerHTML = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-3.5-7.1"></path></svg> Saving\u2026';

        fetch(window.location.href, {
            method: "POST",
            body: formPayload(form, sectionName),
            headers: { "X-CSRFToken": csrfToken(), "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin"
        }).then(function (response) {
            return response.json().then(function (body) {
                if (!response.ok || !body.ok) throw new Error(body.error || "Unable to save settings.");
                return body;
            });
        }).then(function () {
            clearDirty(sectionName);
            button.classList.remove("is-loading");
            button.disabled = false;
            button.innerHTML = originalHTML;
            showToast("Settings saved successfully.", "success");
        }).catch(function (error) {
            button.classList.remove("is-loading");
            button.disabled = false;
            button.innerHTML = originalHTML;
            showToast(error.message || "Unable to save settings.", "error");
        });
    }

    qsa("[data-set-save-section]").forEach(function (btn) {
        if (btn.disabled) return;
        btn.addEventListener("click", function () {
            var panel = btn.closest(".set-panel");
            var sectionName = panel ? panel.getAttribute("data-set-panel") : null;
            runSave(btn, sectionName);
        });
    });

    if (headerSaveBtn) {
        headerSaveBtn.addEventListener("click", function () {
            var sections = Array.from(dirtySections);
            sections.forEach(function (sectionName) {
                var panel = qs('.set-panel[data-set-panel="' + sectionName + '"]');
                var saveBtn = panel ? qs("[data-set-save-section]", panel) : null;
                if (saveBtn) runSave(saveBtn, sectionName);
            });
        });
    }

    var resetChangesBtn = qs("#setResetChangesBtn");
    if (resetChangesBtn) {
        resetChangesBtn.addEventListener("click", function () {
            var panel = qs('.set-panel[data-set-panel="' + activeSectionName() + '"]');
            var form = panel ? qs("[data-set-form]", panel) : null;
            if (form) form.reset();
            clearDirty(activeSectionName());
            showToast("Changes discarded.", "info");
        });
    }

    var sectionResetTrigger = null;
    qsa("[data-set-reset-section]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            sectionResetTrigger = btn;
            openModal("setResetSectionModal");
        });
    });

    var confirmResetSectionBtn = qs("#setConfirmResetSectionBtn");
    if (confirmResetSectionBtn) {
        confirmResetSectionBtn.addEventListener("click", function () {
            if (sectionResetTrigger) {
                var panel = sectionResetTrigger.closest(".set-panel");
                var form = panel ? qs("[data-set-form]", panel) : null;
                if (form) form.reset();
                var sectionName = panel ? panel.getAttribute("data-set-panel") : null;
                if (sectionName) clearDirty(sectionName);
            }
            closeModal(qs("#setResetSectionModal"));
            showToast("Section reset to defaults.", "success");
        });
    }

    var confirmResetAllBtn = qs("#setConfirmResetAllBtn");
    if (confirmResetAllBtn) {
        confirmResetAllBtn.addEventListener("click", function () {
            qsa("[data-set-form]").forEach(function (form) { form.reset(); });
            dirtySections.clear();
            updateUnsavedUI();
            closeModal(qs("#setResetAllModal"));
            showToast("All settings have been reset to their defaults.", "success");
        });
    }

    var unsavedSaveBtn = qs("#setUnsavedSaveBtn");
    if (unsavedSaveBtn) {
        unsavedSaveBtn.addEventListener("click", function () {
            var panel = qs('.set-panel[data-set-panel="' + activeSectionName() + '"]');
            var saveBtn = panel ? qs("[data-set-save-section]", panel) : null;
            if (saveBtn) saveBtn.click();
        });
    }

    var discardBtn = qs("#setDiscardBtn");
    if (discardBtn) {
        discardBtn.addEventListener("click", function () {
            var panel = qs('.set-panel[data-set-panel="' + activeSectionName() + '"]');
            var form = panel ? qs("[data-set-form]", panel) : null;
            if (form) form.reset();
            clearDirty(activeSectionName());
            showToast("Changes discarded.", "info");
        });
    }

    applyBackendValues();

    /* =====================================================================
       7. DISCARD-ON-NAVIGATE CONFIRMATION
       ===================================================================== */
    var confirmDiscardNavBtn = qs("#setConfirmDiscardNavBtn");
    if (confirmDiscardNavBtn) {
        confirmDiscardNavBtn.addEventListener("click", function () {
            var leaving = activeSectionName();
            clearDirty(leaving);
            closeModal(qs("#setDiscardChangesModal"));
            if (pendingNavSection) {
                activateSection(pendingNavSection, { force: true });
                pendingNavSection = null;
            }
        });
    }

    /* =====================================================================
       5. TOGGLES REQUIRING CONFIRMATION
       ===================================================================== */
    qsa("[data-set-confirm-off]").forEach(function (input) {
        input.addEventListener("click", function (e) {
            if (!input.checked) {
                // about to turn OFF -> requires confirmation
                e.preventDefault();
                pendingToggle = { input: input, checkedAfter: false };
                openModal(input.getAttribute("data-set-confirm-off"));
            }
        });
    });

    qsa("[data-set-confirm-on]").forEach(function (input) {
        input.addEventListener("click", function (e) {
            if (input.checked) {
                // about to turn ON -> requires confirmation
                e.preventDefault();
                pendingToggle = { input: input, checkedAfter: true };
                openModal(input.getAttribute("data-set-confirm-on"));
            }
        });
    });

    qsa("[data-set-confirm-toggle]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            if (pendingToggle) {
                pendingToggle.input.checked = pendingToggle.checkedAfter;
                pendingToggle.input.dispatchEvent(new Event("change", { bubbles: true }));
                pendingToggle = null;
            }
            closeModal(btn.closest(".set-modal-overlay"));
            showToast("Setting updated.", "warning");
        });
    });

    qsa("[data-set-cancel-toggle]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            pendingToggle = null;
        });
    });

    /* =====================================================================
       6. MODALS
       ===================================================================== */
    var lastFocusedEl = null;

    function openModal(id) {
        var modal = typeof id === "string" ? document.getElementById(id) : id;
        if (!modal) return;
        lastFocusedEl = document.activeElement;
        modal.classList.remove("is-hidden");
        document.body.style.overflow = "hidden";
        var closeBtn = qs(".set-modal-close", modal);
        if (closeBtn) closeBtn.focus();
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.classList.add("is-hidden");
        document.body.style.overflow = "";
        if (lastFocusedEl && typeof lastFocusedEl.focus === "function") lastFocusedEl.focus();
    }

    function closeAllModals() {
        qsa(".set-modal-overlay").forEach(function (m) {
            if (!m.classList.contains("is-hidden")) closeModal(m);
        });
    }

    qsa("[data-set-open-modal]").forEach(function (trigger) {
        trigger.addEventListener("click", function () {
            openModal(trigger.getAttribute("data-set-open-modal"));
        });
    });

    qsa("[data-set-close-modal]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            closeModal(btn.closest(".set-modal-overlay"));
        });
    });

    qsa(".set-modal-overlay").forEach(function (overlay) {
        overlay.addEventListener("click", function (e) {
            if (e.target === overlay) closeModal(overlay);
        });
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeAllModals();
    });

    /* Test email */
    var confirmTestEmailBtn = qs("#setConfirmTestEmailBtn");
    if (confirmTestEmailBtn) {
        confirmTestEmailBtn.addEventListener("click", function () {
            closeModal(qs("#setTestEmailModal"));
            showToast("Test email prepared \u2014 no message was actually sent.", "info");
        });
    }

    /* Diagnostic action modals (clear cache / rebuild index / diagnostics) */
    qsa("[data-set-run-diagnostic]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var message = btn.getAttribute("data-set-run-diagnostic");
            closeModal(btn.closest(".set-modal-overlay"));
            showToast(message, "success");
        });
    });

    /* =====================================================================
       8. IMAGE PREVIEW (logo / favicon upload)
       ===================================================================== */
    qsa(".set-file-input").forEach(function (input) {
        input.addEventListener("change", function () {
            var file = input.files && input.files[0];
            if (!file) return;

            var imgTarget = document.getElementById(input.getAttribute("data-set-preview-target"));
            var placeholderTarget = document.getElementById(input.getAttribute("data-set-placeholder-target"));
            var reader = new FileReader();

            reader.onload = function (e) {
                if (imgTarget) {
                    imgTarget.src = e.target.result;
                    imgTarget.style.display = "";
                }
                if (placeholderTarget) placeholderTarget.style.display = "none";
            };
            reader.readAsDataURL(file);

            var panel = input.closest(".set-panel");
            if (panel) markDirty(panel.getAttribute("data-set-panel"));
            showToast("Image updated \u2014 remember to save your changes.", "info");
        });
    });

    qsa("[data-set-remove-preview]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var imgTarget = document.getElementById(btn.getAttribute("data-set-remove-preview"));
            var placeholderTarget = document.getElementById(btn.getAttribute("data-set-placeholder-target"));
            if (imgTarget) {
                imgTarget.removeAttribute("src");
                imgTarget.style.display = "none";
            }
            if (placeholderTarget) placeholderTarget.style.display = "";

            var panel = btn.closest(".set-panel");
            if (panel) markDirty(panel.getAttribute("data-set-panel"));
        });
    });

    /* =====================================================================
       PASSWORD VISIBILITY
       ===================================================================== */
    qsa("[data-set-toggle-password]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var input = document.getElementById(btn.getAttribute("data-set-toggle-password"));
            if (!input) return;
            var isHidden = input.type === "password";
            input.type = isHidden ? "text" : "password";
            btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
        });
    });

    /* =====================================================================
       9. SEO PREVIEW
       ===================================================================== */
    var serpTitle = qs("#setSerpTitle");
    var serpDesc = qs("#setSerpDesc");

    qsa('[data-set-seo-preview="title"]').forEach(function (input) {
        input.addEventListener("input", function () {
            if (serpTitle) serpTitle.textContent = input.value || "Untitled Page";
        });
    });
    qsa('[data-set-seo-preview="description"]').forEach(function (textarea) {
        textarea.addEventListener("input", function () {
            if (serpDesc) serpDesc.textContent = textarea.value || "";
        });
    });

    /* =====================================================================
       10. THEME PREVIEW (appearance colors)
       ===================================================================== */
    var themePreview = qs("#setThemePreview");

    qsa("[data-set-preview-color]").forEach(function (input) {
        var valueLabel = input.closest(".set-color-field") ? qs(".set-color-value", input.closest(".set-color-field")) : null;

        input.addEventListener("input", function () {
            if (valueLabel) valueLabel.textContent = input.value;
            if (!themePreview) return;

            var role = input.getAttribute("data-set-preview-color");
            if (role === "primary") {
                var header = qs(".set-preview-header", themePreview);
                var btn = qs(".set-preview-btn", themePreview);
                if (header) header.style.backgroundColor = input.value;
                if (btn) btn.style.backgroundColor = input.value;
            } else if (role === "secondary") {
                var priceEl = qs(".set-preview-card-price", themePreview);
                if (priceEl) priceEl.style.color = input.value;
            }
        });
    });

    /* =====================================================================
       11. TOASTS
       ===================================================================== */
    var toastContainer = qs("#setToastContainer");
    var TOAST_ICONS = {
        success: '<path d="M20 6 9 17l-5-5"></path>',
        info: '<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line>',
        warning: '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>',
        error: '<circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line>'
    };

    function showToast(message, type) {
        if (!toastContainer) return;
        type = type || "info";

        var toast = document.createElement("div");
        toast.className = "set-toast set-toast-" + type;
        toast.setAttribute("role", "status");
        toast.innerHTML =
            '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2">' +
            (TOAST_ICONS[type] || TOAST_ICONS.info) + "</svg>" +
            '<span class="set-toast-text"></span>';
        toast.querySelector(".set-toast-text").textContent = message;

        toastContainer.appendChild(toast);

        window.setTimeout(function () {
            toast.classList.add("is-leaving");
            window.setTimeout(function () { toast.remove(); }, 220);
        }, 4200);
    }

    qsa("[data-set-toast]").forEach(function (el) {
        el.addEventListener("click", function () {
            var type = el.getAttribute("data-set-toast") || "info";
            var message = el.getAttribute("data-set-toast-msg") || "Done.";
            showToast(message, type);
        });
    });

    window.MarketSphereSettingsToast = showToast;

    /* =====================================================================
       13. ACCESSIBILITY — MORE DROPDOWN
       ===================================================================== */
    var moreDropdown = qs("#setMoreDropdown");
    var moreTrigger = qs("#setMoreTrigger");

    if (moreDropdown && moreTrigger) {
        moreTrigger.addEventListener("click", function (e) {
            e.stopPropagation();
            var isOpen = moreDropdown.classList.toggle("is-open");
            moreTrigger.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });

        document.addEventListener("click", function (e) {
            if (!moreDropdown.contains(e.target)) {
                moreDropdown.classList.remove("is-open");
                moreTrigger.setAttribute("aria-expanded", "false");
            }
        });
    }

    /* =====================================================================
       14. RESPONSIVE / MISC — AUDIT FILTERS
       ===================================================================== */
    var auditFilters = qs("#setAuditFilters");
    var auditRows = qsa('[data-set-audit-category]');
    var auditEmpty = qs("#setAuditEmpty");

    if (auditFilters) {
        auditFilters.addEventListener("click", function (e) {
            var pill = e.target.closest(".set-pill");
            if (!pill) return;

            qsa(".set-pill", auditFilters).forEach(function (p) { p.classList.toggle("is-active", p === pill); });

            var filter = pill.getAttribute("data-set-audit-filter");
            var visibleCount = 0;

            auditRows.forEach(function (row) {
                var matches = filter === "all" || row.getAttribute("data-set-audit-category") === filter;
                row.classList.toggle("set-row-hidden", !matches);
                if (matches) visibleCount += 1;
            });

            if (auditEmpty) auditEmpty.classList.toggle("is-visible", visibleCount === 0);
        });
    }

    /* Ripple feedback on primary/danger buttons */
    function bindRipple(el) {
        el.addEventListener("click", function (e) {
            var rect = el.getBoundingClientRect();
            var ripple = document.createElement("span");
            var size = Math.max(rect.width, rect.height);

            ripple.style.position = "absolute";
            ripple.style.width = ripple.style.height = size + "px";
            ripple.style.left = (e.clientX - rect.left - size / 2) + "px";
            ripple.style.top = (e.clientY - rect.top - size / 2) + "px";
            ripple.style.borderRadius = "50%";
            ripple.style.background = "rgba(255,255,255,0.35)";
            ripple.style.pointerEvents = "none";
            ripple.style.transform = "scale(0)";
            ripple.style.transition = "transform 0.5s ease, opacity 0.6s ease";

            el.style.position = el.style.position || "relative";
            el.style.overflow = "hidden";
            el.appendChild(ripple);

            window.requestAnimationFrame(function () {
                ripple.style.transform = "scale(2.2)";
                ripple.style.opacity = "0";
            });

            window.setTimeout(function () { ripple.remove(); }, 600);
        });
    }
    qsa(".set-btn-primary, .set-btn-danger").forEach(bindRipple);

    /* Beforeunload guard for unsaved changes */
    window.addEventListener("beforeunload", function (e) {
        if (dirtySections.size === 0) return;
        e.preventDefault();
        e.returnValue = "";
    });

    /* =====================================================================
       INIT
       ===================================================================== */
    updateUnsavedUI();
})();
