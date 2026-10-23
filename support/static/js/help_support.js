/* =========================================================
   MARKETSPHERE — HELP & SUPPORT PAGE SCRIPT
   Vanilla JS, IIFE pattern, no fetch()/AJAX — matches the
   frontend-only pattern used elsewhere in the project
   (see accounts/static/seller_account.js). This file only
   enhances already-rendered HTML/Django markup: it never
   generates the page's primary content.

   Relies on the global showToast(message, type) helper
   defined in static/js/scripts.js (already loaded on every
   page via base.html), so no duplicate toast system is
   introduced here.
   ========================================================= */

(function () {
    'use strict';

    document.addEventListener('DOMContentLoaded', function () {
        initFaqAccordion();
        initQuickHelpAnchors();
        initHelpDeepLink();
        initHelpSearch();
        initCharCounters();
        initAttachmentDropzone();
        initReportForm();
        initContactForm();
        initRequestDetailsModal();
        initRequestDeepLink();
        initScrollReveal();
    });

    /* =========================================================
       FAQ ACCORDION
       ========================================================= */
    function initFaqAccordion() {
        const items = document.querySelectorAll('.hs-accordion-item');

        items.forEach(function (item) {
            const trigger = item.querySelector('.hs-accordion-trigger');
            const panel = item.querySelector('.hs-accordion-panel');

            if (!trigger || !panel) return;

            trigger.addEventListener('click', function () {
                const isOpen = item.classList.contains('is-open');

                // Close any other open items (single-open accordion)
                items.forEach(function (other) {
                    if (other === item) return;
                    other.classList.remove('is-open');
                    const otherTrigger = other.querySelector('.hs-accordion-trigger');
                    const otherPanel = other.querySelector('.hs-accordion-panel');
                    if (otherTrigger) otherTrigger.setAttribute('aria-expanded', 'false');
                    if (otherPanel) otherPanel.style.maxHeight = null;
                });

                if (isOpen) {
                    item.classList.remove('is-open');
                    trigger.setAttribute('aria-expanded', 'false');
                    panel.style.maxHeight = null;
                } else {
                    item.classList.add('is-open');
                    trigger.setAttribute('aria-expanded', 'true');
                    panel.style.maxHeight = panel.scrollHeight + 24 + 'px';
                }
            });
        });
    }

    /* =========================================================
       PROFILE HELP LINKS / DEEP LINKS
       ========================================================= */
    function initHelpDeepLink() {
        const targetId = window.location.hash.slice(1);
        if (!targetId) return;

        const target = document.getElementById(targetId);
        if (!target) return;

        if (target.classList.contains('modal') && window.bootstrap) {
            window.bootstrap.Modal.getOrCreateInstance(target).show();
            return;
        }

        const rootStyles = window.getComputedStyle(document.documentElement);
        const stickyHeaderHeight = parseFloat(
            rootStyles.getPropertyValue('--sticky-header-height')
        ) || 96;
        const targetTop = target.getBoundingClientRect().top + window.pageYOffset;

        window.setTimeout(function () {
            window.scrollTo({
                top: Math.max(targetTop - stickyHeaderHeight - 16, 0),
                behavior: 'smooth'
            });
        }, 0);
    }

    /* =========================================================
       QUICK HELP ANCHORS
       ========================================================= */
    function initQuickHelpAnchors() {
        let highlightTimer = null;

        document.querySelectorAll('.hs-quick-card[href^="#"]').forEach(function (card) {
            card.addEventListener('click', function (event) {
                const targetId = card.getAttribute('href').slice(1);
                const target = document.getElementById(targetId);

                if (!target) return;

                event.preventDefault();

                const rootStyles = window.getComputedStyle(document.documentElement);
                const stickyHeaderHeight = parseFloat(
                    rootStyles.getPropertyValue('--sticky-header-height')
                ) || 96;
                const targetTop = target.getBoundingClientRect().top + window.pageYOffset;

                window.scrollTo({
                    top: Math.max(targetTop - stickyHeaderHeight - 16, 0),
                    behavior: 'smooth'
                });

                window.clearTimeout(highlightTimer);
                highlightTimer = window.setTimeout(function () {
                    target.classList.remove('hs-topic-highlight');
                    // Force a reflow so repeated clicks replay the short highlight.
                    void target.offsetWidth;
                    target.classList.add('hs-topic-highlight');
                }, 350);
                window.setTimeout(function () {
                    target.classList.remove('hs-topic-highlight');
                }, 1550);
            });
        });
    }

    /* =========================================================
       HELP SEARCH (filters already-rendered content only)
       ========================================================= */
    function initHelpSearch() {
        const searchInput = document.getElementById('hsSearchInput');
        const clearBtn = document.getElementById('hsSearchClear');
        const mainContent = document.getElementById('hsMainContent');
        const resultsSection = document.getElementById('hsSearchResultsSection');
        const resultsList = document.getElementById('hsSearchResultsList');
        const noResultsState = document.getElementById('hsNoResultsState');
        const queryLabel = document.getElementById('hsSearchQueryLabel');

        if (!searchInput) return;

        const searchableSelectors = [
            { selector: '.hs-topic-card', groupLabel: 'Help Topics', titleSelector: '.hs-topic-name', descSelector: '.hs-topic-desc', iconSelector: '.hs-topic-icon' },
            { selector: '.hs-article-row', groupLabel: 'Popular Help', titleSelector: '.hs-article-title', descSelector: '.hs-article-desc', iconSelector: '.hs-article-icon' },
            { selector: '.hs-accordion-item', groupLabel: 'FAQ', titleSelector: '.hs-accordion-trigger span', descSelector: '.hs-accordion-panel p', iconSelector: null }
        ];

        function normalize(text) {
            return (text || '').toLowerCase().trim();
        }

        function runSearch(rawQuery) {
            const query = normalize(rawQuery);

            if (!query) {
                resultsSection.classList.add('d-none');
                mainContent.classList.remove('d-none');
                clearBtn.classList.add('d-none');
                return;
            }

            clearBtn.classList.remove('d-none');
            mainContent.classList.add('d-none');
            resultsSection.classList.remove('d-none');

            if (queryLabel) queryLabel.textContent = rawQuery;

            resultsList.innerHTML = '';
            let totalMatches = 0;

            searchableSelectors.forEach(function (group) {
                const nodes = document.querySelectorAll(group.selector);
                const matches = [];

                nodes.forEach(function (node) {
                    const haystack = normalize(
                        (node.dataset.hsSearchText || '') + ' ' + node.textContent
                    );

                    if (haystack.indexOf(query) !== -1) {
                        matches.push(node);
                    }
                });

                if (!matches.length) return;

                totalMatches += matches.length;

                const groupLabelEl = document.createElement('div');
                groupLabelEl.className = 'hs-search-result-group-label';
                groupLabelEl.textContent = group.groupLabel;
                resultsList.appendChild(groupLabelEl);

                matches.forEach(function (node) {
                    const titleEl = group.titleSelector ? node.querySelector(group.titleSelector) : null;
                    const descEl = group.descSelector ? node.querySelector(group.descSelector) : null;

                    const title = titleEl ? titleEl.textContent.trim() : node.textContent.trim().slice(0, 80);
                    const desc = descEl ? descEl.textContent.trim() : '';

                    const row = document.createElement('a');
                    row.href = node.getAttribute('href') || '#';
                    row.className = 'hs-article-row';

                    row.innerHTML =
                        '<span class="hs-article-icon"><i class="bi bi-search"></i></span>' +
                        '<span class="hs-article-body">' +
                        '<span class="hs-article-title"></span>' +
                        '<span class="hs-article-desc"></span>' +
                        '</span>' +
                        '<i class="bi bi-chevron-right hs-article-arrow"></i>';

                    row.querySelector('.hs-article-title').textContent = title;
                    row.querySelector('.hs-article-desc').textContent = desc;

                    resultsList.appendChild(row);
                });
            });

            if (totalMatches === 0) {
                noResultsState.classList.remove('d-none');
            } else {
                noResultsState.classList.add('d-none');
            }
        }

        let debounceTimer = null;
        searchInput.addEventListener('input', function () {
            window.clearTimeout(debounceTimer);
            const value = searchInput.value;

            debounceTimer = window.setTimeout(function () {
                runSearch(value);
            }, 150);
        });

        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                searchInput.value = '';
                searchInput.focus();
                runSearch('');
            });
        }

        // Quick tag buttons prefill and trigger the search
        document.querySelectorAll('[data-hs-quick-search]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                const term = btn.dataset.hsQuickSearch || '';
                searchInput.value = term;
                searchInput.focus();
                runSearch(term);
                window.scrollTo({ top: searchInput.getBoundingClientRect().top + window.scrollY - 120, behavior: 'smooth' });
            });
        });
    }

    /* =========================================================
       CHARACTER COUNTERS (Report Problem + Contact Support)
       ========================================================= */
    function initCharCounters() {
        bindCounter('hsReportDescription', 'hsReportCharCounter');
        bindCounter('hsContactMessage', 'hsContactCharCounter');

        function bindCounter(textareaId, counterId) {
            const textarea = document.getElementById(textareaId);
            const counter = document.getElementById(counterId);

            if (!textarea || !counter) return;

            const max = parseInt(textarea.getAttribute('maxlength'), 10) || 0;

            function update() {
                const length = textarea.value.length;
                counter.textContent = length + ' / ' + max;
                counter.classList.toggle('is-near-limit', max > 0 && length >= max * 0.9);
            }

            textarea.addEventListener('input', update);
            update();
        }
    }

    /* =========================================================
       ATTACHMENT DROPZONE (Report Problem modal)
       ========================================================= */
    function initAttachmentDropzone() {
        const dropzone = document.getElementById('hsReportDropzone');
        const input = document.getElementById('hsReportAttachmentInput');
        const preview = document.getElementById('hsReportAttachmentPreview');
        const fileNameEl = document.getElementById('hsReportAttachmentName');
        const removeBtn = document.getElementById('hsReportAttachmentRemove');

        if (!dropzone || !input) return;

        function showFile(file) {
            if (!file) return;

            const maxSize = 10 * 1024 * 1024; // 10 MB
            const allowedExt = /\.(jpg|jpeg|png|webp|pdf)$/i;

            if (!allowedExt.test(file.name)) {
                if (window.showToast) window.showToast('Only JPG, PNG, WEBP and PDF files are allowed.', 'error');
                return;
            }

            if (file.size > maxSize) {
                if (window.showToast) window.showToast('Maximum file size is 10 MB.', 'error');
                return;
            }

            fileNameEl.textContent = file.name;
            preview.classList.remove('d-none');
            dropzone.classList.add('d-none');
        }

        function resetAttachment() {
            input.value = '';
            preview.classList.add('d-none');
            dropzone.classList.remove('d-none');
        }

        input.addEventListener('change', function () {
            if (input.files && input.files[0]) {
                showFile(input.files[0]);
            }
        });

        dropzone.addEventListener('dragover', function (e) {
            e.preventDefault();
            dropzone.classList.add('is-dragover');
        });

        dropzone.addEventListener('dragleave', function () {
            dropzone.classList.remove('is-dragover');
        });

        dropzone.addEventListener('drop', function (e) {
            e.preventDefault();
            dropzone.classList.remove('is-dragover');

            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                input.files = e.dataTransfer.files;
                showFile(e.dataTransfer.files[0]);
            }
        });

        if (removeBtn) {
            removeBtn.addEventListener('click', resetAttachment);
        }

        // Reset attachment state whenever the modal is closed
        const modalEl = document.getElementById('hsReportModal');
        if (modalEl) {
            modalEl.addEventListener('hidden.bs.modal', resetAttachment);
        }
    }


    /* =========================================================
       REPORT A PROBLEM — BACKEND SUBMIT
       ========================================================= */

    function initReportForm() {
        const submitBtn = document.getElementById('hsReportSubmitBtn');
        const form = document.getElementById('hsReportForm');
        const modalEl = document.getElementById('hsReportModal');

        if (!submitBtn || !form) return;

        submitBtn.addEventListener('click', async function () {
            const category = document.getElementById('hsReportCategory');
            const order = document.getElementById('hsReportOrder');
            const product = document.getElementById('hsReportProduct');
            const subject = document.getElementById('hsReportSubject');
            const description = document.getElementById('hsReportDescription');
            const attachment = document.getElementById('hsReportAttachmentInput');

            const fields = [category, subject, description];
            let hasError = false;

            fields.forEach(function (field) {
                if (!field) return;
                const value = field.value.trim();
                const isEmpty = !value;

                field.classList.toggle('is-invalid-field', isEmpty);
                if (isEmpty) {
                    hasError = true;
                }
            });

            if (hasError) {
                if (window.showToast) {
                    window.showToast('Please fill in all required fields.', 'error');
                }
                return;
            }

            const formData = new FormData();

            formData.append('request_type', 'problem');
            formData.append('category', category.value);
            formData.append('subject', subject.value.trim());
            formData.append('message', description.value.trim());

            if (order && order.value) {
                formData.append('related_order', order.value);
            }

            if (product && product.value.trim()) {
                formData.append('related_product', product.value.trim());
            }

            if (attachment && attachment.files && attachment.files.length > 0) {
                formData.append('attachment', attachment.files[0]);
            }

            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

            submitBtn.disabled = true;
            const originalBtnContent = submitBtn.innerHTML;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Submitting...';

            try {
                const response = await fetch('/support/api/requests/create/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken || ''
                    },
                    body: formData
                });

                const data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(data.message || 'Unable to submit your report.');
                }

                const modalInstance = modalEl && window.bootstrap ? window.bootstrap.Modal.getInstance(modalEl) : null;
                if (modalInstance) {
                    modalInstance.hide();
                }

                form.reset();

                fields.forEach(function (field) {
                    if (field) field.classList.remove('is-invalid-field');
                });

                const counter = document.getElementById('hsReportCharCounter');
                if (counter) {
                    counter.textContent = '0 / 600';
                }

                const attachmentPreview = document.getElementById('hsReportAttachmentPreview');
                if (attachmentPreview) {
                    attachmentPreview.classList.add('d-none');
                }

                const attachmentName = document.getElementById('hsReportAttachmentName');
                if (attachmentName) {
                    attachmentName.textContent = '';
                }

                if (window.showToast) {
                    window.showToast(
                        data.message || 'Your problem report has been submitted. Our team will review it shortly.',
                        'success'
                    );
                }

                // loadSupportRequests();

            } catch (error) {
                console.error('Support request submission error:', error);
                if (window.showToast) {
                    window.showToast(
                        error.message || 'Something went wrong while submitting your report.',
                        'error'
                    );
                }
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnContent;
            }
        });
    }


    /* =========================================================
       CONTACT SUPPORT — BACKEND SUBMIT
       ========================================================= */

    function initContactForm() {
        const submitBtn = document.getElementById('hsContactSubmitBtn');
        const form = document.getElementById('hsContactForm');
        const modalEl = document.getElementById('hsContactModal');

        if (!submitBtn || !form) return;

        submitBtn.addEventListener('click', async function () {
            const category = document.getElementById('hsContactCategory');
            const order = document.getElementById('hsContactOrder');
            const subject = document.getElementById('hsContactSubject');
            const message = document.getElementById('hsContactMessage');

            const fields = [category, subject, message];
            let hasError = false;

            fields.forEach(function (field) {
                if (!field) return;
                const value = field.value.trim();
                const isEmpty = !value;

                field.classList.toggle('is-invalid-field', isEmpty);
                if (isEmpty) {
                    hasError = true;
                }
            });

            if (hasError) {
                if (window.showToast) {
                    window.showToast('Please fill in all required fields.', 'error');
                }
                return;
            }

            const contactMethod = document.querySelector('input[name="hsContactMethod"]:checked');
            const formData = new FormData();

            formData.append('request_type', 'contact');
            formData.append('category', category.value);
            formData.append('subject', subject.value.trim());
            formData.append('message', message.value.trim());

            if (order && order.value) {
                formData.append('related_order', order.value);
            }

            if (contactMethod) {
                formData.append('preferred_contact_method', contactMethod.value);
            }

            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

            submitBtn.disabled = true;
            const originalBtnContent = submitBtn.innerHTML;

            submitBtn.innerHTML = `
            <span class="spinner-border spinner-border-sm me-1"
                  role="status"
                  aria-hidden="true"></span>
            Sending...
        `;

            try {
                const response = await fetch('/support/api/requests/create/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken || ''
                    },
                    body: formData
                });

                const data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(data.message || 'Unable to send your message.');
                }

                const modalInstance = modalEl && window.bootstrap ? window.bootstrap.Modal.getInstance(modalEl) : null;
                if (modalInstance) {
                    modalInstance.hide();
                }

                form.reset();

                fields.forEach(function (field) {
                    if (field) field.classList.remove('is-invalid-field');
                });

                const counter = document.getElementById('hsContactCharCounter');
                if (counter) {
                    counter.textContent = '0 / 500';
                }

                if (window.showToast) {
                    window.showToast(
                        data.message || 'Your message has been sent to our support team.',
                        'success'
                    );
                }

                // loadSupportRequests();

            } catch (error) {
                console.error('Contact support submission error:', error);
                if (window.showToast) {
                    window.showToast(
                        error.message || 'Something went wrong while sending your message.',
                        'error'
                    );
                }
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnContent;
            }
        });
    }

    /* =========================================================
       REQUEST DETAILS MODAL (populated from data attributes)
       ========================================================= */
    function initRequestDetailsModal() {
        const rows = document.querySelectorAll('.hs-request-row');
        const modalEl = document.getElementById('hsRequestDetailsModal');

        if (!rows.length || !modalEl) return;

        const statusMeta = {
            open: { label: 'Open', badgeClass: 'hs-status-open', icon: 'bi-circle-fill' },
            'in-progress': { label: 'In Progress', badgeClass: 'hs-status-in-progress', icon: 'bi-arrow-repeat' },
            resolved: { label: 'Resolved', badgeClass: 'hs-status-resolved', icon: 'bi-check-circle-fill' },
            'waiting_for_user': { label: 'Waiting for You', badgeClass: 'hs-status-in-progress', icon: 'bi-hourglass-split' },
            closed: { label: 'Closed', badgeClass: 'hs-status-resolved', icon: 'bi-check-circle-fill' }
        };

        const subjectEl = document.getElementById('hsRequestDetailSubject');
        const statusEl = document.getElementById('hsRequestDetailStatus');
        const idEl = document.getElementById('hsRequestDetailId');
        const categoryEl = document.getElementById('hsRequestDetailCategory');
        const createdEl = document.getElementById('hsRequestDetailCreated');
        const updatedEl = document.getElementById('hsRequestDetailUpdated');
        const messageEl = document.getElementById('hsRequestDetailMessage');

        rows.forEach(function (row) {
            row.addEventListener('click', function () {
                const data = row.dataset;
                const meta = statusMeta[data.requestStatus] || statusMeta[data.requestStatus.replace(/_/g, '-')] || statusMeta.open;

                if (subjectEl) subjectEl.textContent = data.requestSubject || '—';
                if (idEl) idEl.textContent = data.requestId || '—';
                if (categoryEl) categoryEl.textContent = data.requestCategory || '—';
                if (createdEl) createdEl.textContent = data.requestCreated || '—';
                if (updatedEl) updatedEl.textContent = data.requestUpdated || '—';
                if (messageEl) messageEl.textContent = data.requestMessage || '—';

                if (statusEl) {
                    statusEl.className = 'hs-status-badge ' + meta.badgeClass;
                    statusEl.innerHTML = '<i class="bi ' + meta.icon + '"></i> ' + meta.label;
                }

                loadThread(data.requestPk);
            });
        });
    }

    function loadThread(pk) {
        const wrap = document.getElementById('hsRequestDetailThread');
        const list = document.getElementById('hsRequestDetailThreadList');
        if (!wrap || !list || !pk) return;
        wrap.hidden = true;
        list.textContent = '';
        fetch('/support/api/requests/' + pk + '/', { headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                const msgs = (data.request && data.request.messages) || [];
                if (!msgs.length) return;
                msgs.forEach(function (m) {
                    const item = document.createElement('div');
                    item.className = 'hs-thread-msg' + (m.sender_type === 'admin' ? ' is-admin' : '');
                    const head = document.createElement('strong');
                    head.textContent = m.sender_label + ' \u00b7 ' + m.created_label;
                    const body = document.createElement('p');
                    body.textContent = m.message;
                    item.appendChild(head);
                    item.appendChild(body);
                    list.appendChild(item);
                });
                wrap.hidden = false;
            })
            .catch(function (err) { console.error('Support thread error:', err); });
    }

    function initRequestDeepLink() {
        const pk = new URLSearchParams(window.location.search).get('request');
        if (!pk) return;
        const row = document.querySelector('.hs-request-row[data-request-pk="' + pk + '"]');
        if (row) row.click();
    }

    async function loadSupportRequests() {
        const list = document.getElementById('hsRequestsList');
        const emptyState = document.getElementById('hsNoRequestsState');
        if (!list) return;
        try {
            const response = await fetch('/support/api/requests/', { headers: { 'Accept': 'application/json' } });
            if (!response.ok) return;
            const data = await response.json();
            list.innerHTML = '';
            (data.requests || []).forEach(function (item) {
                const row = document.createElement('div');
                const status = statusMetaFor(item.status);
                row.className = 'hs-request-row';
                row.dataset.bsToggle = 'modal';
                row.dataset.bsTarget = '#hsRequestDetailsModal';
                row.dataset.requestId = item.display_id;
                row.dataset.requestSubject = item.subject;
                row.dataset.requestCategory = item.category_label;
                row.dataset.requestCreated = item.created_label;
                row.dataset.requestUpdated = item.updated_label;
                row.dataset.requestStatus = item.status.replace('_', '-');
                row.dataset.requestMessage = item.message;
                row.innerHTML = '<span class="hs-request-icon"><i class="bi bi-ticket-perforated"></i></span><span class="hs-request-body"><span class="hs-request-title"></span><span class="hs-request-meta"></span></span><span class="hs-status-badge ' + status.badgeClass + '"><i class="bi ' + status.icon + '"></i> ' + status.label + '</span><i class="bi bi-chevron-right hs-request-arrow"></i>';
                row.querySelector('.hs-request-title').textContent = item.subject;
                row.querySelector('.hs-request-meta').textContent = item.display_id + ' · ' + item.category_label + ' · Opened ' + item.created_label;
                list.appendChild(row);
            });
            if (emptyState) emptyState.classList.toggle('d-none', (data.requests || []).length > 0);
            initRequestDetailsModal();
        } catch (error) {
            console.error('Support request list error:', error);
        }
    }

    function statusMetaFor(status) {
        return {
            open: { label: 'Open', badgeClass: 'hs-status-open', icon: 'bi-circle-fill' },
            in_progress: { label: 'In Progress', badgeClass: 'hs-status-in-progress', icon: 'bi-arrow-repeat' },
            waiting_for_user: { label: 'Waiting for User', badgeClass: 'hs-status-in-progress', icon: 'bi-hourglass-split' },
            resolved: { label: 'Resolved', badgeClass: 'hs-status-resolved', icon: 'bi-check-circle-fill' },
            closed: { label: 'Closed', badgeClass: 'hs-status-resolved', icon: 'bi-check-circle-fill' }
        }[status] || { label: 'Open', badgeClass: 'hs-status-open', icon: 'bi-circle-fill' };
    }

    /* =========================================================
       SCROLL REVEAL (matches seller_account.js / home.js pattern)
       ========================================================= */
    function initScrollReveal() {
        const revealTargets = document.querySelectorAll(
            '.hs-quick-card, .hs-topic-card, .hs-article-row, .hs-support-card, .hs-card'
        );

        revealTargets.forEach(function (el) {
            el.classList.add('reveal-on-scroll');
        });

        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver(function (entries, obs) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        obs.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.1 });

            revealTargets.forEach(function (el) {
                observer.observe(el);
            });
        } else {
            revealTargets.forEach(function (el) {
                el.classList.add('is-visible');
            });
        }
    }
})();