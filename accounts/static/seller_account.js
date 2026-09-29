document.addEventListener('DOMContentLoaded', function () {

    /* =========================================================
       NOTE: This file handles the Seller Account frontend interactions.
       Ensure backend endpoints match the fetch() URLs.
       ========================================================= */

    /* =========================================================
       BUTTON LOADING STATE HELPER
       ========================================================= */
    function setButtonLoading(btn, isLoading, loadingLabel) {
        if (!btn) return;

        if (isLoading) {
            btn.dataset.originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.classList.add('is-loading');
            btn.innerHTML = '<i class="bi bi-arrow-repeat sa-spin"></i> ' + (loadingLabel || 'Saving...');
        } else {
            btn.disabled = false;
            btn.classList.remove('is-loading');
            if (btn.dataset.originalHtml) {
                btn.innerHTML = btn.dataset.originalHtml;
                delete btn.dataset.originalHtml;
            }
        }
    }

    /* =========================================================
       COPY STORE URL
       ========================================================= */
    const copyStoreUrlBtn = document.getElementById('saCopyStoreUrlBtn');

    if (copyStoreUrlBtn) {
        copyStoreUrlBtn.addEventListener('click', function () {
            const url = copyStoreUrlBtn.dataset.storeUrl || '';

            if (!url) {
                showToast('No store URL available to copy yet.', 'error');
                return;
            }

            const originalIcon = copyStoreUrlBtn.innerHTML;

            const markCopied = function () {
                copyStoreUrlBtn.classList.add('is-copied');
                copyStoreUrlBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
                showToast('Store URL copied to clipboard.', 'success');

                window.setTimeout(function () {
                    copyStoreUrlBtn.classList.remove('is-copied');
                    copyStoreUrlBtn.innerHTML = originalIcon;
                }, 1800);
            };

            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(url).then(markCopied).catch(function () {
                    showToast('Could not copy the store URL.', 'error');
                });
            } else {
                const tempInput = document.createElement('textarea');
                tempInput.value = url;
                tempInput.style.position = 'fixed';
                tempInput.style.opacity = '0';
                document.body.appendChild(tempInput);
                tempInput.select();

                try {
                    document.execCommand('copy');
                    markCopied();
                } catch (err) {
                    showToast('Could not copy the store URL.', 'error');
                }

                document.body.removeChild(tempInput);
            }
        });
    }

    /* =========================================================
       EDIT STORE INFORMATION
       ========================================================= */
    const editStoreModalEl = document.getElementById('saEditStoreModal');
    const saveStoreBtn = document.getElementById('saSaveStoreBtn');
    
    // File inputs for Store Info Modal UI
    const storeLogo = document.getElementById('store_logo');
    const storeBanner = document.getElementById('store_banner');
    const logoFileName = document.getElementById('logo-file-name');
    const bannerFileName = document.getElementById('banner-file-name');

    if (storeLogo && logoFileName) {
        storeLogo.addEventListener('change', function() {
            logoFileName.textContent = this.files.length > 0 ? this.files[0].name : '';
        });
    }
    
    if (storeBanner && bannerFileName) {
        storeBanner.addEventListener('change', function() {
            bannerFileName.textContent = this.files.length > 0 ? this.files[0].name : '';
        });
    }

    let editStoreModal = null;
    if (editStoreModalEl && window.bootstrap && window.bootstrap.Modal) {
        editStoreModal = new window.bootstrap.Modal(editStoreModalEl);
    }

    if (saveStoreBtn) {
        saveStoreBtn.addEventListener('click', function () {
            if (saveStoreBtn.classList.contains('is-loading')) return;

            const storeName = document.getElementById('saStoreNameInput');
            const storeEmail = document.getElementById('saStoreEmailInput');
            const description = document.getElementById('saStoreDescriptionInput');

            if (storeName && !storeName.value.trim()) {
                showToast('Please enter a store name before saving.', 'error');
                storeName.focus();
                return;
            }

            setButtonLoading(saveStoreBtn, true, 'Saving...');

            const formData = new FormData();

            formData.append("store_name", storeName.value.trim());
            formData.append("store_email", storeEmail.value.trim());
            formData.append("store_description", description.value.trim());

            if (storeLogo && storeLogo.files.length > 0) {
                formData.append("store_logo", storeLogo.files[0]);
            }

            if (storeBanner && storeBanner.files.length > 0) {
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
                    setButtonLoading(saveStoreBtn, false);

                    if (data.success) {
                        if (editStoreModal) {
                            editStoreModal.hide();
                        }
                        showToast(data.message, "success");
                        window.location.reload();
                    } else {
                        showToast(data.message || "Unable to update store information.", "error");
                    }
                })
                .catch(error => {
                    console.error(error);
                    setButtonLoading(saveStoreBtn, false);
                    showToast("Something went wrong. Please try again.", "error");
                });
        });
    }

    /* =========================================================
       UPDATE BUSINESS ADDRESS
       ========================================================= */
    const editAddressModalEl = document.getElementById('saEditAddressModal');
    const saveAddressBtn = document.getElementById('saSaveAddressBtn');

    let editAddressModal = null;
    if (editAddressModalEl && window.bootstrap && window.bootstrap.Modal) {
        editAddressModal = new window.bootstrap.Modal(editAddressModalEl);
    }

    if (saveAddressBtn) {
        saveAddressBtn.addEventListener('click', function () {
            if (saveAddressBtn.classList.contains('is-loading')) return;

            const fullName = document.getElementById('saAddrFullNameInput');
            const phone = document.getElementById('saAddrPhoneInput');
            const addressLine = document.getElementById('saAddrLineInput');
            const city = document.getElementById('saAddrCityInput');
            const postalCode = document.getElementById('saAddrPostalInput');

            if (fullName && !fullName.value.trim()) {
                showToast('Please enter a business contact name.', 'error');
                fullName.focus();
                return;
            }

            if (addressLine && !addressLine.value.trim()) {
                showToast('Please enter a business address.', 'error');
                addressLine.focus();
                return;
            }

            setButtonLoading(saveAddressBtn, true, 'Saving...');

            const formData = new FormData();
            formData.append("fullName", fullName.value.trim());
            formData.append("phone", phone.value.trim());
            formData.append("address", addressLine.value.trim());
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
                    setButtonLoading(saveAddressBtn, false);
                    if (data.success) {
                        if (editAddressModal) editAddressModal.hide();
                        showToast(data.message, "success");
                        window.location.reload();
                    } else {
                        showToast(data.message || "Unable to update business address.", "error");
                    }
                })
                .catch(error => {
                    console.error(error);
                    setButtonLoading(saveAddressBtn, false);
                    showToast("Something went wrong. Please try again.", "error");
                });
        });
    }

    /* =========================================================
       UPDATE SELLER PROFILE
       ========================================================= */
    const profileModalEl = document.getElementById("saProfileModal");
    const saveProfileBtn = document.getElementById("saProfileSaveBtn");

    let profileModal = null;
    if (profileModalEl && window.bootstrap?.Modal) {
        profileModal = new window.bootstrap.Modal(profileModalEl);
    }

    if (saveProfileBtn) {
        saveProfileBtn.addEventListener("click", function () {
            if (saveProfileBtn.classList.contains("is-loading")) return;

            const formData = new FormData();
            formData.append("business_category", document.getElementById("saBusinessCategoryInput").value.trim());
            formData.append("business_type", document.getElementById("saBusinessTypeInput").value.trim());
            formData.append("national_id_number", document.getElementById("saNationalIdInput").value.trim());
            formData.append("years_in_business", document.getElementById("saYearsBusinessInput").value.trim());
            formData.append("expected_monthly_volume", document.getElementById("saMonthlyVolumeInput").value.trim());
            formData.append("website", document.getElementById("saWebsiteInput").value.trim());
            formData.append("product_categories", document.getElementById("saProductCategoriesInput").value.trim());
            formData.append("facebook_label", document.getElementById("saFacebookLabelInput").value.trim());
            formData.append("facebook_url", document.getElementById("saFacebookUrlInput").value.trim());
            formData.append("linkedin_label", document.getElementById("saLinkedinLabelInput").value.trim());
            formData.append("linkedin_url", document.getElementById("saLinkedinUrlInput").value.trim());
            formData.append("instagram_label", document.getElementById("saInstagramLabelInput").value.trim());
            formData.append("instagram_url", document.getElementById("saInstagramUrlInput").value.trim());
            formData.append("twitter_label", document.getElementById("saTwitterLabelInput").value.trim());
            formData.append("twitter_url", document.getElementById("saTwitterUrlInput").value.trim());

            setButtonLoading(saveProfileBtn, true, "Saving...");

            fetch("/accounts/update-seller-profile/", {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: formData,
            })
                .then(async (response) => {
                    const data = await response.json();
                    setButtonLoading(saveProfileBtn, false);

                    if (!response.ok) {
                        showToast(data.message || "Unable to update seller profile.", "error");
                        return;
                    }

                    if (data.success) {
                        if (profileModal) profileModal.hide();
                        showToast(data.message, "success");
                        window.location.reload();
                    } else {
                        showToast(data.message || "Unable to update seller profile.", "error");
                    }
                })
                .catch((error) => {
                    console.error(error);
                    setButtonLoading(saveProfileBtn, false);
                    showToast("Something went wrong. Please try again.", "error");
                });
        });
    }

    /* =========================================================
       GO TO SELLER DASHBOARD
       ========================================================= */
    const dashboardBtn = document.getElementById('saDashboardBtn');

    if (dashboardBtn) {
        dashboardBtn.addEventListener('click', function (e) {
            e.preventDefault();
            window.location.href = "/seller";
        });
    }

    /* =========================================================
       REACTIVATE STORE
       ========================================================= */
    const reactivateBtn = document.getElementById('saReactivateBtn');

    if (reactivateBtn) {
        reactivateBtn.addEventListener("click", function () {
            if (reactivateBtn.classList.contains("is-loading")) return;

            const confirmed = window.confirm(
                "Are you sure you want to reactivate your seller account?\n\nYour store will become active and you'll be able to sell products again."
            );

            if (!confirmed) return;

            setButtonLoading(reactivateBtn, true, "Reactivating...");

            fetch("/accounts/reactivate-seller-account", {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                },
            })
                .then(response => response.json())
                .then(data => {
                    setButtonLoading(reactivateBtn, false);
                    if (data.status === "success") {
                        showToast(data.message || "Your seller account has been reactivated.", "success");
                        setTimeout(() => window.location.reload(), 1000);
                    } else {
                        showToast(data.message || "Unable to reactivate your account.", "error");
                    }
                })
                .catch(error => {
                    console.error(error);
                    setButtonLoading(reactivateBtn, false);
                    showToast("Something went wrong. Please try again.", "error");
                });
        });
    }

    /* =========================================================
       SELLER TOOLS GRID (Future Features)
       ========================================================= */
    const futureToolButtons = document.querySelectorAll('.sa-future-btn.is-disabled');

    futureToolButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            const feature = btn.dataset.feature || 'This tool';
            showToast(feature + ' isn\'t available yet — check back soon.', 'info');
        });
    });

    /* =========================================================
       BUTTON RIPPLE EFFECT
       ========================================================= */
    function bindRipple(el) {
        el.addEventListener('click', function (e) {
            const rect = el.getBoundingClientRect();
            const ripple = document.createElement('span');
            const size = Math.max(rect.width, rect.height);

            ripple.style.position = 'absolute';
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
            ripple.style.borderRadius = '50%';
            ripple.style.background = 'rgba(255, 255, 255, 0.45)';
            ripple.style.pointerEvents = 'none';
            ripple.style.transform = 'scale(0)';
            ripple.style.opacity = '1';
            ripple.style.transition = 'transform 0.5s ease, opacity 0.6s ease';

            el.style.position = el.style.position || 'relative';
            el.style.overflow = 'hidden';
            el.appendChild(ripple);

            requestAnimationFrame(function () {
                ripple.style.transform = 'scale(1)';
                ripple.style.opacity = '0';
            });

            window.setTimeout(function () {
                ripple.remove();
            }, 600);
        });
    }

    document.querySelectorAll('.sa-status-card-btn, .sa-edit-btn, .sa-future-btn')
        .forEach(bindRipple);

    /* =========================================================
       SCROLL REVEAL
       ========================================================= */
    const revealTargets = document.querySelectorAll('.sa-card, .sa-profile-card');

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

    /* =========================================================
       INITIALIZE SELLER APPLICATION DOCUMENTS
       ========================================================= */
    attachDocumentEvents();

});


/* =========================================================
   SELLER APPLICATION DOCUMENTS MODULE
   ========================================================= */

/**
 * Attach event listeners to all document cards (click, change, drag & drop)
 */
function attachDocumentEvents() {
    const documentCards = document.querySelectorAll(".sa-document-card");

    documentCards.forEach((card) => {
        const previewArea = card.querySelector(".sa-document-preview");
        let fileInput = card.querySelector('input[type="file"]');

        if (!fileInput) {
            fileInput = document.createElement("input");
            fileInput.type = "file";
            fileInput.accept = ".jpg,.jpeg,.png,.webp,.pdf,image/jpeg,image/png,image/webp,application/pdf";
            fileInput.style.display = "none";
            card.appendChild(fileInput);
        }

        // Event delegation for action buttons inside the card
        card.addEventListener("click", function (e) {
            const uploadBtn = e.target.closest(".btn-hero-primary, .sa-upload-document");
            const changeBtn = e.target.closest(".sa-change-document");
            const viewBtn = e.target.closest(".sa-view-document");

            if (uploadBtn || changeBtn) {
                const targetBtn = uploadBtn || changeBtn;
                fileInput._triggerBtn = targetBtn;
                fileInput.click();
            } else if (viewBtn) {
                openDocument(card);
            }
        });

        // File input selection event
        fileInput.addEventListener("change", function () {
            const file = fileInput.files[0];
            if (file) {
                const triggerBtn = fileInput._triggerBtn || card.querySelector(".btn-hero-primary");
                handleSelectedFile(file, card, triggerBtn);
            }
            fileInput.value = ""; // Reset input
        });

        // Drag & Drop functionality
        if (previewArea) {
            previewArea.addEventListener("dragover", function (e) {
                e.preventDefault();
                e.stopPropagation();
                previewArea.classList.add("drag-over");
            });

            previewArea.addEventListener("dragleave", function (e) {
                e.preventDefault();
                e.stopPropagation();
                previewArea.classList.remove("drag-over");
            });

            previewArea.addEventListener("drop", function (e) {
                e.preventDefault();
                e.stopPropagation();
                previewArea.classList.remove("drag-over");

                const files = e.dataTransfer.files;
                if (files && files.length > 0) {
                    const file = files[0];
                    const triggerBtn = card.querySelector(".btn-hero-primary, .sa-change-document");
                    handleSelectedFile(file, card, triggerBtn);
                }
            });
        }
    });
}

/**
 * Handle document selection and trigger validation/upload
 */
function handleSelectedFile(file, card, triggerBtn) {
    if (!validateDocument(file)) {
        return;
    }
    uploadSellerDocument(file, card, triggerBtn);
}

/**
 * Validate document type and file size
 */
function validateDocument(file) {
    const allowedTypes = [
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "application/pdf"
    ];

    const fileName = file.name.toLowerCase();
    const validExtension = /\.(jpg|jpeg|png|webp|pdf)$/.test(fileName);

    if (!allowedTypes.includes(file.type) && !validExtension) {
        showToast("Only JPG, PNG, WEBP and PDF files are allowed.", "error");
        return false;
    }

    const maxSize = 10 * 1024 * 1024; // 10 MB
    if (file.size > maxSize) {
        showToast("Maximum file size is 10 MB.", "error");
        return false;
    }

    return true;
}

/**
 * Upload document to backend via fetch
 */
function uploadSellerDocument(file, card, triggerBtn) {
    const documentType = card.dataset.documentType;

    if (!documentType) {
        showToast("Document type is missing on card.", "error");
        return;
    }

    const formData = new FormData();
    formData.append("document", file);
    formData.append("document_type", documentType);

    if (triggerBtn) {
        // Temporarily change button visual to loading state
        const originalHtml = triggerBtn.innerHTML;
        triggerBtn.dataset.originalHtml = originalHtml;
        triggerBtn.innerHTML = '<i class="bi bi-arrow-repeat sa-spin"></i> Uploading...';
        triggerBtn.disabled = true;
    }

    fetch("/accounts/update-seller-document/", {
        method: "POST",
        headers: {
            "X-CSRFToken": getCookie("csrftoken"),
        },
        body: formData,
    })
        .then(async (response) => {
            let data = {};
            try {
                data = await response.json();
            } catch (jsonError) {
                // Response was not JSON
            }

            if (!response.ok) {
                const errorMessage =
                    data.message || data.error || data.detail || `Server error (${response.status}).`;
                throw new Error(errorMessage);
            }

            if (data.success !== false) {
                updateDocumentCard(card, file, data);
                showToast(data.message || "Document uploaded successfully.", "success");
            } else {
                showToast(data.message || "Unable to upload document.", "error");
            }
        })
        .catch((error) => {
            console.error("Upload Error:", error);
            showToast(error.message || "Something went wrong.", "error");
        })
        .finally(() => {
            if (triggerBtn) {
                triggerBtn.disabled = false;
                if (triggerBtn.dataset.originalHtml) {
                    triggerBtn.innerHTML = triggerBtn.dataset.originalHtml;
                    delete triggerBtn.dataset.originalHtml;
                }
            }
        });
}

/**
 * Update UI elements only after successful upload
 */
function updateDocumentCard(card, file, responseData) {
    const previewArea = card.querySelector(".sa-document-preview");
    const metaValue = card.querySelector(".sa-document-meta-value");
    const statusBadge = card.querySelector(".sa-document-status");
    const actions = card.querySelector(".sa-document-actions");

    // Assign fileUrl based on backend response or fallback to local preview
    if (responseData && responseData.document_url) {
        card.dataset.fileUrl = responseData.document_url;
    } else {
        card.dataset.fileUrl = URL.createObjectURL(file);
    }
    
    card.dataset.fileName = (responseData && responseData.file_name) ? responseData.file_name : file.name;

    // Status Badge
    if (statusBadge) {
        statusBadge.className = "sa-document-status pending";
        statusBadge.innerHTML = '<i class="bi bi-hourglass-split"></i> Pending Review';
    }

    // Upload Date
    if (metaValue) {
        metaValue.textContent = responseData && responseData.uploaded_at
            ? responseData.uploaded_at
            : new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    }

    // Preview Area
    if (previewArea) {
        if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
            previewArea.innerHTML = `
                <div class="sa-document-pdf">
                    <i class="bi bi-file-earmark-pdf-fill sa-doc-icon"></i>
                    <span class="sa-document-file-name">${file.name}</span>
                </div>
            `;
        } else {
            const reader = new FileReader();
            reader.onload = function (e) {
                previewArea.innerHTML = `<img class="sa-document-image" src="${e.target.result}" alt="Document Preview">`;
            };
            reader.readAsDataURL(file);
        }
    }

    // Action Buttons
    if (actions) {
        actions.innerHTML = `
            <button type="button" class="btn sa-edit-btn sa-view-document">
                <i class="bi bi-eye"></i> View
            </button>
            <button type="button" class="btn btn-hero-primary sa-change-document">
                <i class="bi bi-arrow-repeat"></i> Update
            </button>
        `;
    }
}

/**
 * Open uploaded document handles Cloudinary URLs safely
 */
function openDocument(card) {
    const fileUrl = card.dataset.fileUrl;
    const fileName = (card.dataset.fileName || "").toLowerCase();

    if (!fileUrl) {
        showToast("No document available to view.", "error");
        return;
    }

    // Cloudinary URLs sometimes append query strings (e.g., ?v=16234). 
    // Strip them off before checking the extension.
    const cleanUrl = fileUrl.split('?')[0].toLowerCase();
    const isPdf = fileName.endsWith(".pdf") || cleanUrl.endsWith(".pdf");

    if (isPdf) {
        window.open(fileUrl, "_blank");
        return;
    }

    // Open image in a new tab with dark background and centered content
    const imageWindow = window.open("");

    if (imageWindow) {
        imageWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Document Preview</title>
                <style>
                    body {
                        margin: 0;
                        background: #111;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                    }
                    img {
                        max-width: 100%;
                        max-height: 100vh;
                        object-fit: contain;
                    }
                </style>
            </head>
            <body>
                <img src="${fileUrl}" alt="Document Preview">
            </body>
            </html>
        `);
        imageWindow.document.close();
    } else {
        // Fallback if popup blocker stops document write 
        window.open(fileUrl, "_blank");
    }
}