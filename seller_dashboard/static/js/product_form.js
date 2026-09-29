/* =========================================================
   MARKETSPHERE — ADD PRODUCT (SELLER DASHBOARD)
   Frontend-only enhancements for seller_dashboard/products/create.html.
   No fetch, no AJAX, no backend calls, no external libraries.
   All "Save Draft" / "Publish" actions only simulate loading
   states — nothing is persisted until the backend is wired up.

   Sections:
     1. Utilities
     2. Floating Labels
     3. Character Counters
     4. Slug Auto-Generation
     5. SEO Preview Sync
     6. Toggle Switches / Visibility Options
     7. Tags Input
     8. Image Upload (drag & drop + click)
     9. Completion Percentage + Checklist
    10. Accordion (mobile)
    11. Sticky Footer + Dirty State
    12. Button Loading States
    13. Discard Confirmation Modal
    14. Scroll Reveal
    15. Init
   ========================================================= */
let uploadedImages = [];
let deletedImageIds = [];
(function () {
    'use strict';

    /* =====================================================
       1. UTILITIES
       ===================================================== */
    function slugify(value) {
        return String(value || '')
            .toLowerCase()
            .trim()
            .replace(/['"()]/g, '')
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '');
    }

    function debounce(fn, delay) {
        var timer = null;
        return function debounced() {
            var args = arguments;
            window.clearTimeout(timer);
            timer = window.setTimeout(function () {
                fn.apply(null, args);
            }, delay);
        };
    }

    function $(selector, scope) {
        return (scope || document).querySelector(selector);
    }

    function $all(selector, scope) {
        return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
    }

    var form = document.getElementById('pfProductForm');
    var page = document.getElementById('pfPage');

    if (!form || !page) {
        return; // Not on the Add Product page
    }

    /* =====================================================
       2. FLOATING LABELS
       Adds/removes a class so labels stay "floated" for
       elements (like readonly slug, or pre-filled values)
       where :not(:placeholder-shown) alone isn't reliable.
       ===================================================== */
    function syncFloatingLabel(field) {
        var input = field.querySelector('.pf-input, .pf-textarea');
        if (!input) return;
        field.classList.toggle('pf-label-float', input.value.trim().length > 0);
    }

    function initFloatingLabels() {
        $all('.pf-field-floating').forEach(function (field) {
            var input = field.querySelector('.pf-input, .pf-textarea');
            if (!input) return;

            syncFloatingLabel(field);
            input.addEventListener('input', function () { syncFloatingLabel(field); });
            input.addEventListener('blur', function () { syncFloatingLabel(field); });
        });
    }

    /* =====================================================
       3. CHARACTER COUNTERS
       ===================================================== */
    function initCharacterCounters() {
        $all('[data-pf-counter]').forEach(function (el) {
            var counterEl = document.getElementById(el.getAttribute('data-pf-counter'));
            if (!counterEl) return;

            var update = function () {
                counterEl.textContent = String(el.value.length);
                var max = parseInt(el.getAttribute('maxlength'), 10);
                var counterWrap = counterEl.closest('.pf-char-counter');
                if (counterWrap && max) {
                    counterWrap.classList.toggle('is-near-limit', el.value.length >= max * 0.9);
                }
            };

            el.addEventListener('input', update);
            update();
        });
    }

    /* =====================================================
       4. SLUG AUTO-GENERATION
       Mirrors the product name into the slug field until the
       seller explicitly unlocks and edits the slug themselves.
       ===================================================== */
    function initSlugGeneration() {
        var nameInput = document.getElementById('pfName');
        var slugInput = document.getElementById('pfSlug');
        var slugPreview = document.getElementById('pfSlugPreview');
        var slugEditBtn = document.getElementById('pfSlugEditBtn');
        var slugField = slugInput ? slugInput.closest('.pf-field') : null;

        if (!nameInput || !slugInput) return;

        var slugLocked = true; // auto-follows the name until the seller edits it manually

        function updateSlug() {
            var slug = slugify(nameInput.value) || 'your-product-slug';
            if (slugLocked) {
                slugInput.value = slug === 'your-product-slug' ? '' : slug;
            }
            if (slugPreview) {
                slugPreview.textContent = '/product/' + slug;
            }
            if (slugField) syncFloatingLabel(slugField);
            syncSeoUrl(slug);
        }

        nameInput.addEventListener('input', updateSlug);

        if (slugEditBtn) {
            slugEditBtn.addEventListener('click', function () {
                slugLocked = !slugLocked;
                slugInput.readOnly = slugLocked;
                slugInput.classList.toggle('pf-input-mono', true);
                slugEditBtn.setAttribute('aria-pressed', slugLocked ? 'false' : 'true');
                if (!slugLocked) {
                    slugInput.focus();
                }
            });
        }

        slugInput.addEventListener('input', function () {
            if (!slugLocked) {
                slugInput.value = slugify(slugInput.value);
                syncSeoUrl(slugInput.value || 'your-product-slug');
            }
        });

        updateSlug();
    }

    /* =====================================================
       5. SEO PREVIEW SYNC
       ===================================================== */
    function syncSeoUrl(slug) {
        var urlSlugEl = document.getElementById('pfSeoUrlSlug');
        if (urlSlugEl) urlSlugEl.textContent = slug || 'your-product-slug';
    }

    function initSeoPreview() {
        var nameInput = document.getElementById('pfName');
        var shortDesc = document.getElementById('pfShortDescription');
        var metaTitle = document.getElementById('pfMetaTitle');
        var metaDesc = document.getElementById('pfMetaDescription');

        var previewTitle = document.getElementById('pfSeoPreviewTitle');
        var previewDesc = document.getElementById('pfSeoPreviewDesc');

        function updatePreview() {
            var titleSource = (metaTitle && metaTitle.value.trim()) || (nameInput && nameInput.value.trim());
            var descSource = (metaDesc && metaDesc.value.trim()) || (shortDesc && shortDesc.value.trim());

            if (previewTitle) {
                previewTitle.textContent = (titleSource || 'Your Product Name') + ' — MarketSphere';
            }
            if (previewDesc) {
                previewDesc.textContent = descSource ||
                    'Your short description will appear here, giving shoppers a preview of what this product offers before they click through.';
            }
        }

        [nameInput, shortDesc, metaTitle, metaDesc].forEach(function (el) {
            if (el) el.addEventListener('input', updatePreview);
        });

        updatePreview();
    }

    /* =====================================================
       6. TOGGLE SWITCHES / VISIBILITY OPTIONS
       ===================================================== */
    function initSwitches() {
        $all('.pf-switch input[type="checkbox"]').forEach(function (input) {
            input.addEventListener('change', function () {
                markDirty();
            });
        });
    }

    function initVisibilityOptions() {
        var options = $all('.pf-visibility-option');
        var scheduleField = document.getElementById('pfScheduleField');

        function applySelection() {
            var selected = null;
            options.forEach(function (option) {
                var input = option.querySelector('input');
                var isChecked = input && input.checked;
                option.classList.toggle('is-selected', !!isChecked);
                if (isChecked) selected = input.value;
            });

            if (scheduleField) {
                scheduleField.style.opacity = selected === 'draft' ? '0.5' : '1';
            }
        }

        options.forEach(function (option) {
            option.addEventListener('click', function () {
                var input = option.querySelector('input');
                if (input) input.checked = true;
                applySelection();
                markDirty();
            });
        });

        applySelection();
    }

    /* =====================================================
       7. TAGS INPUT
       ===================================================== */
    function initTagsInput() {
        var wrap = document.getElementById('pfTagsInput');
        var field = document.getElementById('pfTagInputField');
        if (!wrap || !field) return;

        function removeChip(chip) {
            chip.remove();
            markDirty();
        }

        function addTag(value) {
            var text = value.trim().replace(/,+$/, '');
            if (!text) return;

            var chip = document.createElement('span');
            chip.className = 'pf-tag-chip';
            chip.textContent = text + ' ';

            var removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'pf-tag-remove';
            removeBtn.setAttribute('aria-label', 'Remove tag ' + text);
            removeBtn.innerHTML = '&times;';
            removeBtn.addEventListener('click', function () { removeChip(chip); });

            chip.appendChild(removeBtn);
            wrap.insertBefore(chip, field);
            markDirty();
        }

        wrap.addEventListener('click', function (e) {
            if (e.target === wrap) field.focus();

            var removeBtn = e.target.closest('.pf-tag-remove');
            if (removeBtn) {
                removeChip(removeBtn.closest('.pf-tag-chip'));
            }
        });

        field.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                addTag(field.value);
                field.value = '';
            } else if (e.key === 'Backspace' && !field.value) {
                var chips = wrap.querySelectorAll('.pf-tag-chip');
                var last = chips[chips.length - 1];
                if (last) removeChip(last);
            }
        });
    }

    /* =====================================================
       8. IMAGE UPLOAD (drag & drop + click)
       Frontend-only preview via object URLs — nothing is
       uploaded anywhere.
       ===================================================== */
    function initImageUpload() {
        var zone = document.getElementById('pfUploadZone');
        var input = document.getElementById('pfImageInput');
        var primarySlot = document.getElementById('pfPrimarySlot');
        var page = document.getElementById('pfPage');
        var grid = document.getElementById('pfImageGrid');
        var maxImages = Math.max(1, parseInt(page && page.dataset.maxImages, 10) || 8);
        var maxImageSize = (parseFloat(page && page.dataset.maxImageSizeMb) || 5) * 1024 * 1024;

        if (!zone || !input) return;

        // The server is authoritative, but keep the picker in sync with the
        // configured limit instead of leaving the old four-slot UI in place.
        if (grid) {
            var secondary = Array.from(grid.querySelectorAll('[data-image-slot]'));
            var filledSecondary = secondary.filter(function (slot) {
                return slot.classList.contains('pf-image-slot-filled');
            }).length;
            secondary.filter(function (slot) {
                return !slot.classList.contains('pf-image-slot-filled');
            }).forEach(function (slot) { slot.remove(); });
            var emptyCount = Math.max(0, maxImages - 1 - filledSecondary);
            for (var slotIndex = 0; slotIndex < emptyCount; slotIndex++) {
                var slot = document.createElement('div');
                slot.className = 'pf-image-slot';
                slot.setAttribute('data-image-slot', '');
                slot.innerHTML = '<div class="pf-image-slot-empty"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg></div>';
                grid.appendChild(slot);
            }
        }
        var extraSlots = $all('[data-image-slot]');
        document.querySelectorAll(".pf-image-remove-btn").forEach(function (btn) {

            btn.addEventListener("click", function (e) {

                e.stopPropagation();

                const slot = btn.closest("[data-image-slot]");
                const imageId = slot.dataset.imageId;

                if (imageId) {
                    deletedImageIds.push(imageId);
                }

                const img = slot.querySelector("img");
                if (img) img.remove();

                btn.remove();

                slot.classList.remove("pf-image-slot-filled");

                slot.innerHTML = `
            <div class="pf-image-slot-empty">
                <svg viewBox="0 0 24 24"
                     width="18"
                     height="18"
                     fill="none"
                     stroke="currentColor"
                     stroke-width="1.6"
                     stroke-linecap="round"
                     stroke-linejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
            </div>
        `;

                markDirty();
                updateCompletion();

            });

        });

        function findEmptySlot() {
            if (primarySlot && !primarySlot.classList.contains('pf-image-slot-filled')) {
                return primarySlot;
            }
            return extraSlots.find(function (slot) {
                return !slot.classList.contains('pf-image-slot-filled');
            });
        }

        function fillSlot(slot, file) {
            if (!slot || !file || !file.type || file.type.indexOf('image/') !== 0) return;

            var url = URL.createObjectURL(file);
            var img = document.createElement('img');
            img.src = url;
            img.alt = file.name;

            var isPrimary = slot === primarySlot;

            slot.classList.add('pf-image-slot-filled');
            var emptyState = slot.querySelector('.pf-image-slot-empty');
            if (emptyState) emptyState.style.display = 'none';

            var existingImg = slot.querySelector('img');
            if (existingImg) existingImg.remove();
            slot.insertBefore(img, slot.firstChild);

            if (!isPrimary) {
                var removeBtn = document.createElement('button');
                removeBtn.type = 'button';
                removeBtn.className = 'pf-image-remove-btn';
                removeBtn.setAttribute('aria-label', 'Remove image');
                removeBtn.innerHTML = '&times;';
                removeBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    img.remove();
                    removeBtn.remove();
                    slot.classList.remove('pf-image-slot-filled');
                    if (emptyState) emptyState.style.display = '';
                    updateCompletion();
                });
                slot.appendChild(removeBtn);

                removeBtn.addEventListener("click", function (e) {

                    e.stopPropagation();

                    uploadedImages = uploadedImages.filter(f => f !== file);

                    img.remove();
                    removeBtn.remove();

                    slot.classList.remove("pf-image-slot-filled");

                    if (emptyState)
                        emptyState.style.display = "";

                    updateCompletion();

                });
            }

            markDirty();
            updateCompletion();


        }

        function handleFiles(fileList) {

            const files = Array.from(fileList || []);

            files.forEach(function (file) {

                if (!file.type.startsWith("image/")) return;
                if (file.size > maxImageSize) {
                    if (typeof showToast === 'function') showToast('Each image must be within the configured size limit.', 'danger');
                    return;
                }

                const slot = findEmptySlot();

                if (!slot) return;

                uploadedImages.push(file);

                fillSlot(slot, file);
            });
        }
        zone.addEventListener('click', function () { input.click(); });
        zone.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                input.click();
            }
        });

        input.addEventListener('change', function () {
            handleFiles(input.files);
            input.value = '';
        });

        ['dragenter', 'dragover'].forEach(function (eventName) {
            zone.addEventListener(eventName, function (e) {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.add('is-dragover');
            });
        });

        ['dragleave', 'drop'].forEach(function (eventName) {
            zone.addEventListener(eventName, function (e) {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.remove('is-dragover');
            });
        });

        zone.addEventListener('drop', function (e) {
            if (e.dataTransfer && e.dataTransfer.files) {
                handleFiles(e.dataTransfer.files);
            }
        });
    }

    function hasAnyImage() {
        var primarySlot = document.getElementById('pfPrimarySlot');
        if (primarySlot && primarySlot.classList.contains('pf-image-slot-filled')) return true;
        return $all('[data-image-slot]').some(function (slot) {
            return slot.classList.contains('pf-image-slot-filled');
        });
    }

    /* =====================================================
       9. COMPLETION PERCENTAGE + CHECKLIST
       ===================================================== */
    var CHECKLIST_FIELDS = ['name', 'sku', 'short_description', 'description', 'price', 'category', 'stock_quantity'];

    function fieldHasValue(name) {
        var el = form.querySelector('[name="' + name + '"]');
        if (!el) return false;
        return String(el.value || '').trim().length > 0;
    }

    function updateCompletion() {
        var total = CHECKLIST_FIELDS.length + 1; // +1 for images
        var complete = 0;

        CHECKLIST_FIELDS.forEach(function (name) {
            var item = document.querySelector('.pf-checklist-item[data-checklist-for="' + name + '"]');
            var done = fieldHasValue(name);
            if (item) item.classList.toggle('is-complete', done);
            if (done) complete += 1;
        });

        var imagesItem = document.querySelector('.pf-checklist-item[data-checklist-for="images"]');
        var imagesDone = hasAnyImage();
        if (imagesItem) imagesItem.classList.toggle('is-complete', imagesDone);
        if (imagesDone) complete += 1;

        var percent = Math.round((complete / total) * 100);

        var percentEl = document.getElementById('pfCompletionPercent');
        var fillEl = document.getElementById('pfCompletionBarFill');
        var captionEl = document.getElementById('pfCompletionCaption');

        if (percentEl) percentEl.textContent = percent + '%';
        if (fillEl) fillEl.style.width = percent + '%';

        if (captionEl) {
            if (percent === 100) {
                captionEl.textContent = 'All set — this product is ready to publish.';
            } else if (percent >= 60) {
                captionEl.textContent = 'Almost there — a few more details to go.';
            } else {
                captionEl.textContent = 'Fill in the required fields to publish your product.';
            }
        }
    }

    function initCompletionTracking() {
        form.addEventListener('input', debounce(updateCompletion, 120));
        form.addEventListener('change', updateCompletion);
        updateCompletion();
    }

    /* =====================================================
       10. ACCORDION (mobile)
       Desktop keeps every card expanded; below the tablet
       breakpoint, cards collapse and the header becomes a
       toggle. The first card starts expanded either way.
       ===================================================== */
    function initAccordion() {
        var cards = $all('[data-pf-section]');

        cards.forEach(function (card, index) {
            if (index === 0) card.classList.add('is-expanded');

            var trigger = card.querySelector('.pf-accordion-trigger');
            if (!trigger) return;

            trigger.addEventListener('click', function () {
                if (window.innerWidth > 991) return; // accordion only applies below the tablet breakpoint
                card.classList.toggle('is-expanded');
            });
        });

        window.addEventListener('resize', debounce(function () {
            if (window.innerWidth > 991) {
                cards.forEach(function (card) { card.classList.add('is-expanded'); });
            }
        }, 200));
    }

    /* =====================================================
       11. STICKY FOOTER + DIRTY STATE
       ===================================================== */
    var isDirty = false;

    function markDirty() {
        isDirty = true;
        page.setAttribute('data-dirty', 'true');

        var status = document.getElementById('pfStickyStatus');
        if (status) {
            status.classList.remove('is-saved');
            status.innerHTML = '<span class="pf-status-dot"></span> Unsaved changes';
        }
    }

    function markSaved(label) {
        isDirty = false;
        page.setAttribute('data-dirty', 'false');

        var status = document.getElementById('pfStickyStatus');
        if (status) {
            status.classList.add('is-saved');
            status.innerHTML = '<span class="pf-status-dot"></span> ' + (label || 'All changes saved');
        }
    }

    function initDirtyTracking() {
        form.addEventListener('input', markDirty);
        form.addEventListener('change', markDirty);

        window.addEventListener('beforeunload', function (e) {
            if (!isDirty) return;
            e.preventDefault();
            e.returnValue = '';
            return '';
        });
    }

    /* =====================================================
       12. BUTTON LOADING STATES
       Simulates a save/publish request with a short delay —
       no network activity, purely a UI affordance until the
       backend endpoints exist.
       ===================================================== */
    function setButtonLoading(btn, isLoading) {
        if (!btn) return;

        var label = btn.querySelector('.pf-btn-label');
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

    function simulateSave(btn, savedLabel) {
        if (!btn || btn.classList.contains('is-loading')) return;

        setButtonLoading(btn, true);

        window.setTimeout(function () {
            setButtonLoading(btn, false);
            markSaved(savedLabel);
        }, 900);
    }

    function getFormData() {

        const data = {
            name: document.getElementById("pfName").value.trim(),
            slug: document.getElementById("pfSlug").value.trim(),
            sku: document.getElementById("pfSku").value.trim(),
            barcode: document.getElementById("pfBarcode").value.trim(),

            short_description: document.getElementById("pfShortDescription").value.trim(),
            description: document.getElementById("pfFullDescription").value.trim(),

            price: parseFloat(document.getElementById("pfRegularPrice").value) || 0,
            discount_price: parseFloat(document.getElementById("pfDiscountPrice").value) || null,

            stock_quantity: parseInt(document.getElementById("pfStockQty").value) || 0,
            min_stock_level: parseInt(document.getElementById("pfMinStock").value) || 0,

            is_available: document.getElementById("pfAvailableToggle").checked,
            is_featured: document.getElementById("pfFeaturedToggle").checked,

            category: document.getElementById("pfCategory").value || null,
            brand: document.getElementById("pfBrand").value || null,

            weight: parseFloat(document.getElementById("pfWeight").value) || null,

            meta_title: document.getElementById("pfMetaTitle").value.trim(),
            meta_description: document.getElementById("pfMetaDescription").value.trim(),

            visibility:
                document.querySelector('input[name="visibility"]:checked')?.value || "published",

            publish_at:
                document.getElementById("pfScheduleDate").value || null
        };


        // Promotions -> selected promotion IDs + promotion prices
        data.promotions = Array.from(
            document.querySelectorAll(".promo-checkbox:checked")
        ).map(checkbox => {
            const promotionId = checkbox.value;
            const priceInput = document.querySelector(
                `input[name="promotion_price_${promotionId}"]`
            );

            return {
                id: promotionId,
                price: priceInput ? priceInput.value : ""
            };
        });

        // Tags -> Array
        data.tags = Array.from(
            document.querySelectorAll("#pfTagsInput .pf-tag-chip")
        ).map(chip => {
            const clone = chip.cloneNode(true);
            clone.querySelector(".pf-tag-remove")?.remove();
            return clone.textContent.trim();
        });


        // Dimensions -> Object
        data.dimensions = {
            length: parseFloat(document.getElementById("pfLength").value) || null,
            width: parseFloat(document.getElementById("pfWidth").value) || null,
            height: parseFloat(document.getElementById("pfHeight").value) || null
        };


        // Images -> File[]
        data.images = uploadedImages;

        return data;
    }
    function getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
    function initActionButtons() {
        var saveButtons = [document.getElementById('pfSaveDraftTopBtn'), document.getElementById('pfSaveDraftBtn')];
        var publishButtons = [document.getElementById('pfPublishTopBtn'), document.getElementById('pfPublishBtn')];
        var updateButtons = [document.getElementById('pfUpdateTopBtn'), document.getElementById('pfUpdateBtn')];

        updateButtons.forEach(function (btn) {

            if (!btn) return;

            btn.addEventListener("click", async function () {

                const product = getFormData();
                if (!validatePromotionData(product.promotions)) return;
                const formData = new FormData();
                const productSlug = document.getElementById("pfSectionInfo").dataset.productSlug;
                if (product.visibility === "published") {

                    const percentEl = document.getElementById("pfCompletionPercent").textContent;

                    if (percentEl !== "100%") {
                        showToast("Please complete the product data first.");
                        return;
                    }
                }

                // Normal fields
                for (const key in product) {

                    if (
                        key === "tags" ||
                        key === "promotions" ||
                        key === "dimensions" ||
                        key === "images"
                    ) {
                        continue;
                    }

                    formData.append(key, product[key] ?? "");
                }

                // JSON fields
                formData.append("tags", JSON.stringify(product.tags));
                formData.append("promotions", JSON.stringify(product.promotions));
                formData.append("dimensions", JSON.stringify(product.dimensions));

                // Newly uploaded images
                product.images.forEach(function (image) {
                    formData.append("images", image);
                });

                // Existing images marked for deletion
                formData.append(
                    "deleted_images",
                    JSON.stringify(deletedImageIds)
                );

                try {

                    const response = await fetch(
                        `/seller/products/edit-product/${productSlug}`,
                        {
                            method: "POST",
                            headers: {
                                "X-CSRFToken": getCSRFToken()
                            },
                            body: formData
                        }
                    );

                    const result = await response.json();

                    if (response.ok && result.success) {

                        // Images were deleted successfully, clear the list
                        deletedImageIds = [];


                        window.location.reload();
                        simulateSave(btn, "Product updated");

                    } else {

                        console.error(result);
                        showToast(result.message || "Failed to update product.");

                    }

                } catch (error) {

                    console.error(error);
                    showToast("Something went wrong while updating the product.");

                }

            });

        });
        saveButtons.forEach(function (btn) {

            if (!btn) return;

            btn.addEventListener("click", async function () {

                const product = getFormData();
                if (!validatePromotionData(product.promotions)) return;
                const formData = new FormData();
                if (!product.name.trim()) {
                    showToast("Please enter a product name.");
                    return;
                }

                // Append normal fields
                for (const key in product) {

                    if (
                        key === "tags" ||
                        key === "promotions" ||
                        key === "dimensions" ||
                        key === "images"
                    ) {
                        continue;
                    }

                    formData.append(key, product[key]);
                }

                // Append arrays & object as JSON
                formData.append("tags", JSON.stringify(product.tags));
                formData.append("promotions", JSON.stringify(product.promotions));
                formData.append("dimensions", JSON.stringify(product.dimensions));

                // Append images
                product.images.forEach(image => {
                    formData.append("images", image);
                });

                try {

                    const response = await fetch("/seller/products/save-draft/", {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": getCSRFToken()
                        },
                        body: formData
                    });

                    const result = await response.json();

                    if (response.ok && result.success) {
                        console.log(result);
                        simulateSave(btn, "Draft saved");
                    } else {
                        console.error(result);
                        showToast(result.message || "Failed to save draft.");
                    }

                } catch (error) {
                    console.error(error);
                    showToast("Something went wrong while saving the draft.");
                }

            });

        });

        publishButtons.forEach(function (btn) {

            if (!btn) return;

            btn.addEventListener("click", async function () {

                var percentEl = document.getElementById('pfCompletionPercent').textContent;
                if (percentEl != "100%") {
                    showToast("Please Complete the product data first.", "error");
                    return;
                }

                const product = getFormData();
                if (!validatePromotionData(product.promotions)) return;

                const formData = new FormData();

                // Append normal fields
                for (const key in product) {

                    if (
                        key === "tags" ||
                        key === "promotions" ||
                        key === "dimensions" ||
                        key === "images"
                    ) {
                        continue;
                    }

                    formData.append(key, product[key]);
                }

                // Append arrays & object as JSON
                formData.append("tags", JSON.stringify(product.tags));
                formData.append("promotions", JSON.stringify(product.promotions));
                formData.append("dimensions", JSON.stringify(product.dimensions));

                // Append images
                product.images.forEach(image => {
                    formData.append("images", image);
                });
                try {

                    const response = await fetch("/seller/products/add-product/", {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": getCSRFToken()
                        },
                        body: formData
                    });

                    const result = await response.json();

                    if (response.ok && result.success) {
                        console.log(result);
                        showToast("Product has been sent successfully for admin approval.", "success");
                        simulateSave(btn, "Product published");
                    } else {
                        console.error(result);
                        showToast(result.message || "Failed to publish product.");
                    }

                } catch (error) {
                    console.error(error);
                    showToast("Something went wrong while publishing the product.");
                }

            });

        });
    }

    /* =====================================================
       13. DISCARD CONFIRMATION MODAL
       ===================================================== */
    function initDiscardModal() {
        var overlay = document.getElementById('pfDiscardModalOverlay');
        var cancelTopBtn = document.getElementById('pfCancelTopBtn');
        var cancelBtn = document.getElementById('pfCancelBtn');
        var keepEditingBtn = document.getElementById('pfDiscardCancelBtn');
        var confirmBtn = document.getElementById('pfDiscardConfirmBtn');

        if (!overlay) return;

        function openModal() {
            overlay.classList.remove('pf-hidden');
            document.body.style.overflow = 'hidden';
        }

        function closeModal() {
            overlay.classList.add('pf-hidden');
            document.body.style.overflow = '';
        }

        function handleCancelClick() {
            if (isDirty) {
                openModal();
            } else {
                window.location.href = "/seller/products/";
            }
        }

        [cancelTopBtn, cancelBtn].forEach(function (btn) {
            if (btn) btn.addEventListener('click', handleCancelClick);
        });

        if (keepEditingBtn) keepEditingBtn.addEventListener('click', closeModal);

        if (confirmBtn) {
            confirmBtn.addEventListener('click', function () {
                closeModal();
                markSaved('Changes discarded');
            });
        }

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) closeModal();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && !overlay.classList.contains('pf-hidden')) {
                closeModal();
            }
        });
    }

    /* =====================================================
       14. SCROLL REVEAL
       ===================================================== */
    function initScrollReveal() {
        var targets = $all('.pf-reveal');
        if (!targets.length) return;

        if (!('IntersectionObserver' in window)) {
            targets.forEach(function (el) { el.classList.add('is-visible'); });
            return;
        }

        var observer = new IntersectionObserver(function (entries, obs) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-visible');
                obs.unobserve(entry.target);
            });
        }, { threshold: 0.08 });

        targets.forEach(function (el) { observer.observe(el); });
    }

    /* =====================================================
       15. INIT
       ===================================================== */
    function init() {
        initFloatingLabels();
        initCharacterCounters();
        initSlugGeneration();
        initSeoPreview();
        initSwitches();
        initVisibilityOptions();
        initTagsInput();
        initImageUpload();
        initCompletionTracking();
        initAccordion();
        initDirtyTracking();
        initActionButtons();
        initDiscardModal();
        initScrollReveal();
    }

    document.addEventListener('DOMContentLoaded', init);
})();
document.addEventListener("DOMContentLoaded", () => {
    const cards = document.querySelectorAll(".pf-card");

    cards.forEach(card => {
        const trigger = card.querySelector(".pf-accordion-trigger");
        const body = card.querySelector(".pf-card-body");
        const caret = card.querySelector(".pf-accordion-caret");

        if (!trigger || !body || !caret) return;

        trigger.addEventListener("click", () => {
            const isCollapsed = card.classList.toggle("is-collapsed");

            body.style.display = isCollapsed ? "none" : "block";

            caret.style.transform = isCollapsed
                ? "rotate(-90deg)"
                : "rotate(0deg)";
        });
    });
});

const brandInput = document.getElementById("pfBrandSearch");
const brandHidden = document.getElementById("pfBrand");
const dropdown = document.getElementById("pfBrandDropdown");

let timer = null;

brandInput.addEventListener("input", function () {

    clearTimeout(timer);

    const query = this.value.trim();

    if (query.length < 2) {

        dropdown.style.display = "none";
        dropdown.innerHTML = "";
        return;

    }

    timer = setTimeout(() => {

        fetch(`/api/search-brands/?q=${encodeURIComponent(query)}`)

            .then(res => res.json())

            .then(data => {

                dropdown.innerHTML = "";

                if (data.brands.length === 0) {

                    dropdown.innerHTML =
                        "<div class='pf-search-item'>No brands found</div>";

                    dropdown.style.display = "block";

                    return;
                }

                data.brands.forEach(brand => {

                    const item = document.createElement("div");

                    item.className = "pf-search-item";

                    item.textContent = brand.name;

                    item.addEventListener("click", function () {

                        brandInput.value = brand.name;

                        brandHidden.value = brand.slug;

                        dropdown.style.display = "none";

                    });

                    dropdown.appendChild(item);

                });

                dropdown.style.display = "block";

            });

    }, 300);

});


document.addEventListener("click", function (e) {

    if (!e.target.closest(".pf-search-select")) {

        dropdown.style.display = "none";

    }

});

const categoryInput = document.getElementById("pfCategorySearch");
const categoryHidden = document.getElementById("pfCategory");
const categoryDropdown = document.getElementById("pfCategoryDropdown");
const categoryLoader = document.getElementById("pfCategoryLoader");

let categoryTimer = null;

categoryInput.addEventListener("input", function () {

    clearTimeout(categoryTimer);

    const query = this.value.trim();
    // remove name from the visible input so only the hidden field is submitted
    categoryHidden.removeAttribute("name");
    categoryHidden.value = "";

    if (query.length < 2) {

        categoryDropdown.style.display = "none";
        categoryDropdown.innerHTML = "";

        return;
    }

    categoryTimer = setTimeout(() => {

        categoryLoader.style.display = "block";

        fetch(`/api/search-categories/?q=${encodeURIComponent(query)}`)

            .then(res => res.json())

            .then(data => {

                categoryLoader.style.display = "none";
                categoryDropdown.innerHTML = "";

                if (data.categories.length === 0) {

                    categoryDropdown.innerHTML =
                        "<div class='pf-search-item'>No categories found</div>";

                    categoryDropdown.style.display = "block";

                    return;
                }

                data.categories.forEach(category => {

                    const item = document.createElement("div");

                    item.className = "pf-search-item";

                    item.textContent = category.name;

                    item.addEventListener("click", function () {

                        categoryInput.value = category.name;
                        // Store slug
                        categoryHidden.value = category.slug;
                        categoryHidden.setAttribute("name", "category");
                        categoryHidden.dispatchEvent(new Event("change", { bubbles: true }));
                        categoryDropdown.style.display = "none";


                    });

                    categoryDropdown.appendChild(item);

                });

                categoryDropdown.style.display = "block";

            })

            .catch(error => {

                categoryLoader.style.display = "none";

                console.error(error);

            });

    }, 300);

});

document.addEventListener("click", function (e) {

    if (!e.target.closest(".pf-search-select")) {

        categoryDropdown.style.display = "none";

    }

});

document.addEventListener('DOMContentLoaded', function () {
    const removeDiscountBtn = document.getElementById('remove-discount');

    if (removeDiscountBtn) {
        removeDiscountBtn.addEventListener('click', function (e) {
            e.preventDefault(); // Prevent default button behavior

            // 1. Get the slug from the button's data attribute
            const productSlug = this.getAttribute('data-slug');
            if (!productSlug) {
                console.error("Product slug is missing.");
                return;
            }

            // 2. Construct the URL matching your urls.py
            const url = `/admin-db/catalog/product-management/${productSlug}/price/remove-discount/`;

            // 3. Get the CSRF token from the DOM (required by Django for POST requests)
            const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
            const csrfToken = csrfInput ? csrfInput.value : '';

            // Optional: Show loading state on button
            const originalText = this.innerText;
            this.innerText = 'Removing...';
            this.disabled = true;

            // 4. Make the fetch request
            fetch(url, {
                method: 'POST', // Assuming your view allows POST. Use 'GET' if specifically configured that way, but POST is safer for state-changing actions.
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest' // Tells Django this is an AJAX request
                }
            })
                .then(response => {
                    // Parse the JSON response
                    return response.json().then(data => ({ status: response.status, body: data }));
                })
                .then(({ status, body }) => {
                    if (status === 200 && body.success !== false) {
                        // Success handling
                        showToast('Discount removed successfully!', "success");

                        // You can update the UI here or simply reload the page to reflect changes
                        document.getElementById("pfDiscountPrice").value = " ";
                    } else {
                        // Handled error from your JsonResponse (e.g., status 404)
                        showToast(body.message || 'Failed to remove discount.', "error");
                    }
                })
                .catch(error => {
                    console.error('Fetch error:', error);
                    showToast('A network error occurred while removing the discount.', "error");
                })
                .finally(() => {
                    // Restore button state
                    this.innerText = originalText;
                    this.disabled = false;
                });
        });
    }
});

function togglePromoPrice(checkbox, promotionId) {
    const wrapper = document.getElementById(`price-wrapper-${promotionId}`);
    const input = document.querySelector(`input[name="promotion_price_${promotionId}"]`);
    if (!wrapper || !input) return;

    wrapper.style.display = checkbox.checked ? "block" : "none";
    input.disabled = !checkbox.checked;
    input.required = checkbox.checked;
    if (!checkbox.checked) input.value = "";
}

function validatePromotionData(promotions) {
    for (const promotion of promotions) {
        if (!promotion.id) {
            showToast("A selected promotion is invalid.", "error");
            return false;
        }
        const price = Number(promotion.price);
        if (!promotion.price || !Number.isFinite(price) || price <= 0) {
            showToast("Please enter a promotion price greater than zero.", "error");
            return false;
        }
    }
    return true;
}
