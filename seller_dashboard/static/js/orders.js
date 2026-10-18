/* =========================================================================
   MARKETSPHERE — SELLER DASHBOARD: ORDERS
   Frontend-only interactions for seller_dashboard/templates/orders/list.html.
   No fetch(), no AJAX, no backend calls, no external libraries. Every
   action here (search, filter, sort, bulk select, row actions, cancel
   confirmation) is a pure DOM / UI simulation until the seller-orders
   backend (views, URLs, models) exists — matching the pattern already
   used across the rest of the app (see seller_dashboard/static/js/products.js).

   Sections:
     1. DOM Cache
     2. Dropdown Management (row + bulk actions)
     3. Checkbox Selection / Bulk Bar
     4. Bulk Actions
     5. Individual Row Actions
     6. Cancel Confirmation Modal
     7. Client-Side Search / Filter / Sort
     8. Empty State
     9. Scroll Reveal
    10. Init
   ========================================================================= */

document.addEventListener('DOMContentLoaded', function () {

    /* ================= 1. DOM CACHE ================= */
    const table = document.getElementById('soOrdersTable');
    const tableBody = document.getElementById('soOrdersTableBody');
    const selectAllCheckbox = document.getElementById('soSelectAll');
    const bulkBar = document.getElementById('soBulkBar');
    const bulkCount = document.getElementById('soBulkCount');
    const clearSelectionBtn = document.getElementById('soClearSelectionBtn');
    const emptyState = document.getElementById('soEmptyState');

    const searchInput = document.getElementById('soSearchInput');
    const statusFilter = document.getElementById('soStatusFilter');
    const paymentFilter = document.getElementById('soPaymentFilter');
    const dateFromInput = document.getElementById('soDateFrom');
    const dateToInput = document.getElementById('soDateTo');
    const sortFilter = document.getElementById('soSortFilter');
    const resetFiltersBtn = document.getElementById('soResetFiltersBtn');
    const exportOrdersBtn = document.getElementById('soExportOrdersBtn');

    const cancelModalOverlay = document.getElementById('soCancelModalOverlay');
    const cancelModalTitle = document.getElementById('soCancelModalTitle');
    const cancelModalText = document.getElementById('soCancelModalText');
    const cancelModalConfirm = document.getElementById('soCancelModalConfirm');
    const cancelModalDismiss = document.getElementById('soCancelModalDismiss');

    if (!table || !tableBody) return; // nothing to control on this page

    let confirmCallback = null;

    function getRowCheckboxes() {
        return Array.from(tableBody.querySelectorAll('.so-row-checkbox'));
    }

    function getVisibleRows() {
        return Array.from(tableBody.querySelectorAll('.so-row')).filter(function (row) {
            return !row.classList.contains('so-hidden');
        });
    }

    /* ================= 2. DROPDOWN MANAGEMENT ================= */
    document.addEventListener('click', function (e) {
        const trigger = e.target.closest('.so-dropdown-trigger');

        if (trigger) {
            e.preventDefault();
            const dropdown = trigger.closest('.so-dropdown');
            const isActive = dropdown.classList.contains('so-active');

            closeAllDropdowns();

            if (!isActive) {
                dropdown.classList.add('so-active');
                trigger.setAttribute('aria-expanded', 'true');
            }
        } else if (!e.target.closest('.so-dropdown-menu')) {
            closeAllDropdowns();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeAllDropdowns();
            closeCancelModal();
        }
    });

    function closeAllDropdowns() {
        document.querySelectorAll('.so-dropdown.so-active').forEach(function (dropdown) {
            dropdown.classList.remove('so-active');
            const trigger = dropdown.querySelector('.so-dropdown-trigger');
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        });
    }

    /* ================= 3. CHECKBOX SELECTION / BULK BAR ================= */
    function toggleRowHighlight(row, highlight) {
        if (!row) return;
        row.classList.toggle('is-selected', highlight);
    }

    function updateBulkBarState() {
        const checkedRows = getRowCheckboxes().filter(function (cb) { return cb.checked; });
        const totalCount = checkedRows.length;

        if (bulkCount) bulkCount.textContent = String(totalCount);
        if (bulkBar) bulkBar.classList.toggle('so-hidden', totalCount === 0);

        if (selectAllCheckbox) {
            const visibleCheckboxes = getVisibleRows()
                .map(function (row) { return row.querySelector('.so-row-checkbox'); })
                .filter(Boolean);
            const visibleChecked = visibleCheckboxes.filter(function (cb) { return cb.checked; });

            if (visibleChecked.length === 0) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            } else if (visibleChecked.length === visibleCheckboxes.length) {
                selectAllCheckbox.checked = true;
                selectAllCheckbox.indeterminate = false;
            } else {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = true;
            }
        }
    }

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            const isChecked = selectAllCheckbox.checked;
            getVisibleRows().forEach(function (row) {
                const cb = row.querySelector('.so-row-checkbox');
                if (cb) {
                    cb.checked = isChecked;
                    toggleRowHighlight(row, isChecked);
                }
            });
            updateBulkBarState();
        });
    }

    tableBody.addEventListener('change', function (e) {
        if (e.target.classList.contains('so-row-checkbox')) {
            const row = e.target.closest('.so-row');
            toggleRowHighlight(row, e.target.checked);
            updateBulkBarState();
        }
    });

    if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener('click', function () {
            getRowCheckboxes().forEach(function (cb) {
                cb.checked = false;
                toggleRowHighlight(cb.closest('.so-row'), false);
            });
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            }
            updateBulkBarState();
        });
    }

    /* ================= 4. BULK ACTIONS ================= */
    document.querySelectorAll('[data-bulk-action]').forEach(function (button) {
        button.addEventListener('click', function (e) {
            const action = e.target.closest('[data-bulk-action]').dataset.bulkAction;
            const selectedRows = getRowCheckboxes()
                .filter(function (cb) { return cb.checked; })
                .map(function (cb) { return cb.closest('.so-row'); });

            if (!selectedRows.length) return;

            if (action === 'processing') {
                selectedRows.forEach(function (row) { setRowStatus(row, 'processing', 'Processing'); });
            }
            // 'export' and 'print' are frontend placeholders only — no
            // backend endpoint exists yet to generate real files.

            closeAllDropdowns();
        });
    });

    function setRowStatus(row, statusClass, statusLabel) {
        const badge = row.querySelector('[data-label="Status"] .so-badge');
        if (!badge) return;
        badge.className = 'so-badge so-badge-' + statusClass;
        badge.textContent = statusLabel;
    }

    /* ================= 5. INDIVIDUAL ROW ACTIONS ================= */
    let rowPendingCancel = null;

    tableBody.addEventListener('click', function (e) {
        const actionItem = e.target.closest('[data-row-action]');
        if (!actionItem) return;

        const action = actionItem.dataset.rowAction;
        const row = actionItem.closest('.so-row');
        let orderNumber = actionItem.dataset.orderNumber || (row ? row.dataset.orderNumber : '');
        // orderNumber = orderNumber.split('-')[1];
        if (action === 'view') {
            window.location.href = "/seller/orders/"+orderNumber;
        } else if (action === 'print') {
            window.open(`/order/${orderNumber}/invoice/`, "_blank");
        } else if (action === 'contact') {
            window.alert('Contacting the customer for #' + orderNumber + ' isn\u2019t available yet \u2014 check back soon.');
        } else if (action === 'cancel') {
            rowPendingCancel = row;
            openCancelModal(orderNumber);
        }

        closeAllDropdowns();
    });

    // Clicking the order number itself mirrors the "View Details" row action.
    tableBody.addEventListener('click', function (e) {
        const link = e.target.closest('[data-view-order]');
        if (!link) return;
        e.preventDefault();
        window.location.href = "/seller/orders/" + link.dataset.viewOrder;
    });

    /* ================= 6. CANCEL CONFIRMATION MODAL ================= */
    function openCancelModal(orderNumber) {
        if (!cancelModalOverlay) return;

        if (cancelModalTitle) cancelModalTitle.textContent = 'Cancel order #' + orderNumber + '?';
        if (cancelModalText) {
            cancelModalText.textContent = 'This action cannot be undone. The customer will be notified that order #' + orderNumber + ' was cancelled.';
        }

        confirmCallback = function () {
            if (rowPendingCancel) {
                setRowStatus(rowPendingCancel, 'cancelled', 'Cancelled');
            }
            rowPendingCancel = null;
        };

        cancelModalOverlay.classList.remove('so-hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeCancelModal() {
        if (!cancelModalOverlay || cancelModalOverlay.classList.contains('so-hidden')) return;

        cancelModalOverlay.classList.add('so-hidden');
        document.body.style.overflow = '';
        confirmCallback = null;
        rowPendingCancel = null;
    }

    if (cancelModalDismiss) cancelModalDismiss.addEventListener('click', closeCancelModal);

    if (cancelModalOverlay) {
        cancelModalOverlay.addEventListener('click', function (e) {
            if (e.target === cancelModalOverlay) closeCancelModal();
        });
    }

    if (cancelModalConfirm) {
        cancelModalConfirm.addEventListener('click', function () {
            if (confirmCallback) confirmCallback();
            closeCancelModal();
        });
    }

    /* ================= 7. CLIENT-SIDE SEARCH / FILTER / SORT ================= */
    function badgeStatusFromRow(row) {
        const badge = row.querySelector('[data-label="Status"] .so-badge');
        if (!badge) return '';
        const modifier = Array.from(badge.classList).find(function (cls) {
            return cls.indexOf('so-badge-') === 0;
        });
        return modifier ? modifier.replace('so-badge-', '') : '';
    }

    function badgePaymentFromRow(row) {
        const badge = row.querySelector('[data-label="Payment"] .so-badge');
        if (!badge) return '';
        const modifier = Array.from(badge.classList).find(function (cls) {
            return cls.indexOf('so-badge-') === 0;
        });
        return modifier ? modifier.replace('so-badge-', '') : '';
    }

    function performFiltering() {
        const searchVal = (searchInput ? searchInput.value : '').toLowerCase().trim();
        const statusVal = (statusFilter ? statusFilter.value : '').toLowerCase();
        const paymentVal = (paymentFilter ? paymentFilter.value : '').toLowerCase();

        Array.from(tableBody.querySelectorAll('.so-row')).forEach(function (row) {
            const orderNumber = (row.dataset.orderNumber || '').toLowerCase();
            const customerName = (row.dataset.customerName || '').toLowerCase();
            const rowStatus = badgeStatusFromRow(row);
            const rowPayment = badgePaymentFromRow(row);

            const matchesSearch = !searchVal || orderNumber.includes(searchVal) || customerName.includes(searchVal);
            const matchesStatus = !statusVal || rowStatus === statusVal;
            const matchesPayment = !paymentVal || rowPayment === paymentVal;

            if (matchesSearch && matchesStatus && matchesPayment) {
                row.classList.remove('so-hidden');
            } else {
                row.classList.add('so-hidden');
                const cb = row.querySelector('.so-row-checkbox');
                if (cb) cb.checked = false;
            }
        });

        performSorting();
        updateBulkBarState();
        checkAndShowEmptyState();
    }

    function parseTotal(row) {
        const totalEl = row.querySelector('.so-total');
        if (!totalEl) return 0;
        return parseFloat(totalEl.textContent.replace(/[^0-9.]/g, '')) || 0;
    }

    function performSorting() {
        const sortVal = sortFilter ? sortFilter.value : 'newest';
        const rows = getVisibleRows();

        rows.sort(function (rowA, rowB) {
            if (sortVal === 'total-high-low' || sortVal === 'total-low-high') {
                const totalA = parseTotal(rowA);
                const totalB = parseTotal(rowB);
                return sortVal === 'total-high-low' ? totalB - totalA : totalA - totalB;
            }

            // "newest" / "oldest" rely on the rows' current DOM order,
            // which is already newest-first from the (placeholder) markup —
            // reverse it for "oldest" and leave "newest" as-is.
            return 0;
        });

        if (sortVal === 'oldest') {
            rows.reverse();
        }

        rows.forEach(function (row) { tableBody.appendChild(row); });
    }

    if (searchInput) searchInput.addEventListener('input', performFiltering);
    if (statusFilter) statusFilter.addEventListener('change', performFiltering);
    if (paymentFilter) paymentFilter.addEventListener('change', performFiltering);
    if (sortFilter) sortFilter.addEventListener('change', performFiltering);
    if (dateFromInput) dateFromInput.addEventListener('change', performFiltering);
    if (dateToInput) dateToInput.addEventListener('change', performFiltering);

    if (resetFiltersBtn) {
        resetFiltersBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (statusFilter) statusFilter.value = '';
            if (paymentFilter) paymentFilter.value = '';
            if (dateFromInput) dateFromInput.value = '';
            if (dateToInput) dateToInput.value = '';
            if (sortFilter) sortFilter.value = 'newest';
            performFiltering();
        });
    }

    if (exportOrdersBtn) {
        exportOrdersBtn.addEventListener('click', function () {
            let sellerId = exportOrdersBtn.dataset.sellerId;
            window.location.href = `/admin-db/sellers/${sellerId}/export-orders/`;
        });
    }

    /* ================= 8. EMPTY STATE ================= */
    function checkAndShowEmptyState() {
        const visibleCount = getVisibleRows().length;

        if (!emptyState) return;

        const tableCard = table.closest('.so-table-wrap');

        if (visibleCount === 0) {
            if (tableCard) tableCard.style.display = 'none';
            emptyState.classList.remove('so-hidden');
        } else {
            if (tableCard) tableCard.style.display = '';
            emptyState.classList.add('so-hidden');
        }
    }

    /* ================= 9. SCROLL REVEAL ================= */
    const revealTargets = document.querySelectorAll('.so-reveal');

    if ('IntersectionObserver' in window && revealTargets.length) {
        const observer = new IntersectionObserver(function (entries, obs) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    obs.unobserve(entry.target);
                }
            });
        }, { threshold: 0.05 });

        revealTargets.forEach(function (el) {
            observer.observe(el);
        });
    }

    /* ================= 10. INIT ================= */
    updateBulkBarState();
});
