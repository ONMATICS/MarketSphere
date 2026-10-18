/* =========================================================================
   MARKETSPHERE — SELLER DASHBOARD: PRODUCTS
   Frontend-only interactions for seller_dashboard/templates/products/list.html.
   No fetch(), no AJAX, no backend calls, no external libraries. Every
   action here (search, filter, sort, bulk select, row actions, delete
   confirmation) is a pure DOM / UI simulation until the seller-products
   backend (views, URLs, models) exists — matching the pattern already
   used across the rest of the app (see products/static/js/cart.js,
   orders/static/js/checkout.js).

   Sections:
     1. DOM Cache
     2. Dropdown Management (row + bulk actions)
     3. Checkbox Selection / Bulk Bar
     4. Bulk Actions
     5. Individual Row Actions
     6. Delete Confirmation Modal
     7. Client-Side Search / Filter / Sort
     8. Empty State
     9. Init
   ========================================================================= */

document.addEventListener('DOMContentLoaded', function () {

    /* ================= 1. DOM CACHE ================= */
    const table = document.getElementById('pmProductsTable');
    const tableBody = document.getElementById('pmProductsTableBody');
    const selectAllCheckbox = document.getElementById('pmSelectAll');
    const bulkBar = document.getElementById('pmBulkBar');
    const bulkCount = document.getElementById('pmBulkCount');
    const clearSelectionBtn = document.getElementById('pmClearSelectionBtn');
    const emptyState = document.getElementById('pmEmptyState');

    const searchInput = document.getElementById('pmSearchInput');
    const categoryFilter = document.getElementById('pmCategoryFilter');
    const statusFilter = document.getElementById('pmStatusFilter');
    const sortFilter = document.getElementById('pmSortFilter');
    const applyFiltersBtn = document.getElementById('pmApplyFiltersBtn');
    const resetFiltersBtn = document.getElementById('pmResetFiltersBtn');

    const deleteModalOverlay = document.getElementById('pmDeleteModalOverlay');
    const deleteModalTitle = document.getElementById('pmDeleteModalTitle');
    const deleteModalText = document.getElementById('pmDeleteModalText');
    const deleteModalConfirm = document.getElementById('pmDeleteModalConfirm');
    const deleteModalCancel = document.getElementById('pmDeleteModalCancel');

    if (!table || !tableBody) return; // nothing to control on this page

    let confirmCallback = null;

    function getRowCheckboxes() {
        return Array.from(tableBody.querySelectorAll('.pm-row-checkbox'));
    }

    function getVisibleRows() {
        return Array.from(tableBody.querySelectorAll('.pm-row')).filter(function (row) {
            return !row.classList.contains('pm-hidden');
        });
    }

    function getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"], meta[name="csrf_token"]');
        if (meta && meta.content) return meta.content;

        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : null;
    }

    /* ================= 2. DROPDOWN MANAGEMENT ================= */
    document.addEventListener('click', function (e) {
        const trigger = e.target.closest('.pm-dropdown-trigger');

        if (trigger) {
            e.preventDefault();
            const dropdown = trigger.closest('.pm-dropdown');
            const isActive = dropdown.classList.contains('pm-active');

            closeAllDropdowns();

            if (!isActive) {
                dropdown.classList.add('pm-active');
                trigger.setAttribute('aria-expanded', 'true');
            }
        } else if (!e.target.closest('.pm-dropdown-menu')) {
            closeAllDropdowns();
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeAllDropdowns();
    });

    function closeAllDropdowns() {
        document.querySelectorAll('.pm-dropdown.pm-active').forEach(function (dropdown) {
            dropdown.classList.remove('pm-active');
            const trigger = dropdown.querySelector('.pm-dropdown-trigger');
            if (trigger) trigger.setAttribute('aria-expanded', 'false');
        });
    }

    /* ================= 3. CHECKBOX SELECTION / BULK BAR ================= */
    function toggleRowHighlight(row, highlight) {
        if (!row) return;
        row.classList.toggle('is-selected', highlight);
        row.style.backgroundColor = highlight ? 'rgba(157, 102, 56, 0.06)' : '';
    }

    function updateBulkBarState() {
        const checkedRows = getRowCheckboxes().filter(function (cb) { return cb.checked; });
        const totalCount = checkedRows.length;

        if (bulkCount) bulkCount.textContent = String(totalCount);
        if (bulkBar) bulkBar.classList.toggle('pm-hidden', totalCount === 0);

        if (selectAllCheckbox) {
            const visibleCheckboxes = getVisibleRows()
                .map(function (row) { return row.querySelector('.pm-row-checkbox'); })
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
                const cb = row.querySelector('.pm-row-checkbox');
                if (cb) {
                    cb.checked = isChecked;
                    toggleRowHighlight(row, isChecked);
                }
            });
            updateBulkBarState();
        });
    }

    tableBody.addEventListener('change', function (e) {
        if (e.target.classList.contains('pm-row-checkbox')) {
            const row = e.target.closest('.pm-row');
            toggleRowHighlight(row, e.target.checked);
            updateBulkBarState();
        }
    });

    if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener('click', function () {
            getRowCheckboxes().forEach(function (cb) {
                cb.checked = false;
                toggleRowHighlight(cb.closest('.pm-row'), false);
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
                .map(function (cb) { return cb.closest('.pm-row'); });

            if (!selectedRows.length) return;

            if (action === 'delete') {
                openDeleteModal(
                    'Delete ' + selectedRows.length + ' products?',
                    'Are you sure you want to delete these ' + selectedRows.length + ' selected products? This cannot be undone.',
                    function () {
                        selectedRows.forEach(function (row) { row.remove(); });
                        updateBulkBarState();
                        checkAndShowEmptyState();
                    }
                );
            } else if (action === 'publish') {
                selectedRows.forEach(function (row) { setRowStatus(row, 'published', 'Published'); });
                closeAllDropdowns();
            } else if (action === 'hide') {
                selectedRows.forEach(function (row) { setRowStatus(row, 'hidden', 'Hidden'); });
                closeAllDropdowns();
            }
        });
    });

    function setRowStatus(row, statusClass, statusLabel) {
        const badge = row.querySelector('.pm-badge');
        if (!badge) return;
        badge.className = 'pm-badge pm-badge-' + statusClass;
        badge.textContent = statusLabel;
    }

    /* ================= 5. INDIVIDUAL ROW ACTIONS ================= */
    let rowToDelete = null;
    let rowToHide = null;
    tableBody.addEventListener('click', function (e) {
        const actionItem = e.target.closest('[data-row-action]');
        if (!actionItem) return;
        const dropdonwn = e.target.closest('.pm-dropdown-menu');
        const productSlug = dropdonwn.dataset.productSlug;
        const action = actionItem.dataset.rowAction;
        const row = actionItem.closest('.pm-row');
        const productName = row.dataset.productName || row.querySelector('.pm-product-name').textContent;

        if (action === 'hide' || action === 'unhide') {
            rowToHide = row;
            openDeleteModal(
                `${action} product?`,
                'Are you sure you want to "' + action + " " + productName + '"? This action cannot be undone.',
                function () {
                    if (rowToHide) {
                        var csrfToken = getCSRFToken();
                        if (!csrfToken) {
                            showToast('Missing CSRF token. Please refresh the page and try again.');
                            return;
                        }

                        fetch(`/seller/products/${action}-product`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken,
                                'X-CSRF-Token': csrfToken
                            },
                            body: JSON.stringify({ productSlug: productSlug })
                        })
                            .then(function (res) { return res.json(); })
                            .then(function (response) {
                                if (response.status === 'success') {
                                    if (action === 'hide') {
                                        setRowStatus(row, 'hidden', 'Hidden');
                                    } else {
                                        setRowStatus(row, 'published', "Published");
                                    }
                                    showToast(response.message);
                                } else {
                                    showToast(response.message || `Unable to ${action} product.`);
                                }
                            })
                            .catch(function () {
                                showToast('An error occurred. Please try again.');
                            });
                    }
                }
            );
        } else if (action === 'live') {
            window.location.href = `/product/${productSlug}`;
        } else if (action === 'edit' || action === 'duplicate') {
            window.location.href = `/seller/products/edit-product/${productSlug}`;
            // Placeholder — no backend routing exists yet for editing/duplicating a product.
        } else if (action === 'delete') {
            let rowToDelete = row;

            openDeleteModal(
                'Delete product?',
                'Are you sure you want to delete "' + productName + '"?',
                function () {

                    if (!rowToDelete) return;

                    var csrfToken = getCSRFToken();

                    if (!csrfToken) {
                        showToast('Missing CSRF token. Please refresh the page and try again.');
                        return;
                    }

                    fetch('/seller/products/delete-product', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({
                            productSlug: productSlug
                        })
                    })
                        .then(function (res) {
                            return res.json().then(function (data) {
                                return {
                                    ok: res.ok,
                                    data: data
                                };
                            });
                        })
                        .then(function (result) {
                            if (!result.ok || result.data.status !== 'success') {
                                showToast(result.data.message || 'Unable to delete product.');
                                return;
                            }
                            console.log(rowToDelete);
                            rowToDelete.remove();
                            rowToDelete = null;
                            checkAndShowEmptyState();

                            showToast(result.data.message);
                        })
                        .catch(function (error) {
                            console.error(error);
                            showToast('An unexpected error occurred. Please try again.');
                        });

                }
            );
        }

        closeAllDropdowns();
    });

    /* ================= 6. DELETE CONFIRMATION MODAL ================= */
    function openDeleteModal(title, text, onConfirm) {
        if (!deleteModalOverlay) return;

        if (deleteModalTitle) deleteModalTitle.textContent = title;
        if (deleteModalText) deleteModalText.textContent = text;
        confirmCallback = onConfirm;

        deleteModalOverlay.classList.remove('pm-hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeDeleteModal() {
        if (!deleteModalOverlay) return;

        deleteModalOverlay.classList.add('pm-hidden');
        document.body.style.overflow = '';
        confirmCallback = null;
        rowToDelete = null;
    }

    if (deleteModalCancel) deleteModalCancel.addEventListener('click', closeDeleteModal);

    if (deleteModalOverlay) {
        deleteModalOverlay.addEventListener('click', function (e) {
            if (e.target === deleteModalOverlay) closeDeleteModal();
        });
    }

    if (deleteModalConfirm) {
        deleteModalConfirm.addEventListener('click', function () {
            if (confirmCallback) confirmCallback();
            closeDeleteModal();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && deleteModalOverlay && !deleteModalOverlay.classList.contains('pm-hidden')) {
            closeDeleteModal();
        }
    });

    /* ================= 7. CLIENT-SIDE SEARCH / FILTER / SORT ================= */
    function performFiltering() {
        const searchVal = (searchInput ? searchInput.value : '').toLowerCase().trim();
        const catVal = (categoryFilter ? categoryFilter.value : '').toLowerCase();
        const statusVal = (statusFilter ? statusFilter.value : '').toLowerCase();

        Array.from(tableBody.querySelectorAll('.pm-row')).forEach(function (row) {
            const nameEl = row.querySelector('.pm-product-name');
            const pName = row.dataset.productName || (nameEl ? nameEl.textContent.toLowerCase() : '');
            const skuEl = row.querySelector('.pm-product-sku');
            const pSku = skuEl ? skuEl.textContent.toLowerCase() : '';
            const catEl = row.querySelector('[data-label="Category"]');
            const pCategory = catEl ? catEl.textContent.toLowerCase().trim() : '';
            const statusBadge = row.querySelector('.pm-badge');

            let pStatus = '';
            if (statusBadge) {
                const statusModifier = Array.from(statusBadge.classList).find(function (cls) {
                    return cls.indexOf('pm-badge-') === 0;
                });
                pStatus = statusModifier ? statusModifier.replace('pm-badge-', '') : '';
            }

            const matchesSearch = !searchVal || pName.includes(searchVal) || pSku.includes(searchVal);
            const matchesCategory = !catVal || pCategory.replace(/&amp;/g, '&').includes(catVal.replace('-', ' '));
            const matchesStatus = !statusVal || pStatus === statusVal;

            if (matchesSearch && matchesCategory && matchesStatus) {
                row.classList.remove('pm-hidden');
            } else {
                row.classList.add('pm-hidden');
                const cb = row.querySelector('.pm-row-checkbox');
                if (cb) cb.checked = false;
            }
        });

        performSorting();
        updateBulkBarState();
        checkAndShowEmptyState();
    }

    function performSorting() {
        const sortVal = sortFilter ? sortFilter.value : 'newest';
        const rows = getVisibleRows();

        rows.sort(function (rowA, rowB) {
            if (sortVal === 'newest' || sortVal === 'oldest') {
                const dateA = new Date(rowA.querySelector('.pm-date').textContent);
                const dateB = new Date(rowB.querySelector('.pm-date').textContent);
                return sortVal === 'newest' ? dateB - dateA : dateA - dateB;
            }

            if (sortVal === 'price-low-high' || sortVal === 'price-high-low') {
                const priceA = parseFloat(rowA.querySelector('.pm-price').textContent.replace(/[^0-9]/g, ''));
                const priceB = parseFloat(rowB.querySelector('.pm-price').textContent.replace(/[^0-9]/g, ''));
                return sortVal === 'price-low-high' ? priceA - priceB : priceB - priceA;
            }

            if (sortVal === 'stock-low-high') {
                const stockA = parseInt(rowA.querySelector('.pm-stock').textContent, 10) || 0;
                const stockB = parseInt(rowB.querySelector('.pm-stock').textContent, 10) || 0;
                return stockA - stockB;
            }

            if (sortVal === 'name-a-z') {
                const nameA = rowA.querySelector('.pm-product-name').textContent.toLowerCase();
                const nameB = rowB.querySelector('.pm-product-name').textContent.toLowerCase();
                return nameA.localeCompare(nameB);
            }

            return 0;
        });

        rows.forEach(function (row) { tableBody.appendChild(row); });
    }

    if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', performFiltering);
    if (searchInput) searchInput.addEventListener('input', performFiltering);
    if (categoryFilter) categoryFilter.addEventListener('change', performFiltering);
    if (statusFilter) statusFilter.addEventListener('change', performFiltering);
    if (sortFilter) sortFilter.addEventListener('change', performFiltering);

    if (resetFiltersBtn) {
        resetFiltersBtn.addEventListener('click', function () {
            if (searchInput) searchInput.value = '';
            if (categoryFilter) categoryFilter.value = '';
            if (statusFilter) statusFilter.value = '';
            if (sortFilter) sortFilter.value = 'newest';
            performFiltering();
        });
    }

    /* ================= 8. EMPTY STATE ================= */
    function checkAndShowEmptyState() {
        const visibleCount = getVisibleRows().length;

        if (!emptyState) return;

        if (visibleCount === 0) {
            table.style.display = 'none';
            emptyState.classList.remove('pm-hidden');
        } else {
            table.style.display = '';
            emptyState.classList.add('pm-hidden');
        }
    }

    /* ================= 9. INIT ================= */
    updateBulkBarState();
});