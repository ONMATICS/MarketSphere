/* =========================================================
   MARKETSPHERE — BUYER PROFILE / MY ACCOUNT PAGE JS
   Frontend-only. No fetch()/XHR/AJAX — every action here
   simulates a short delay and updates the visible UI, matching
   the pattern used in seller_account.js. Once the buyer profile
   backend (views/URLs) exists, replace the simulated blocks
   below with real requests without touching the surrounding
   DOM/animation logic.
   ========================================================= */

(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        initButtonLoadingHelper();
        initAccountNav();
        initToastSystem();
        initEditProfileModal();
        initAddressModals();
        initWishlistRemoval();
        initPasswordModal();
        initPreferenceToggles();
        initDangerZone();
        initComingSoonLinks();
        initScrollReveal();
    });

    /* =========================================================
       BUTTON LOADING STATE HELPER (shared)
       ========================================================= */
    function setButtonLoading(btn, isLoading, loadingLabel) {
        if (!btn) return;

        if (isLoading) {
            btn.dataset.originalHtml = btn.innerHTML;
            btn.disabled = true;
            btn.classList.add("is-loading");
            btn.innerHTML = '<i class="bi bi-arrow-repeat bp-spin"></i> ' + (loadingLabel || "Saving...");
        } else {
            btn.disabled = false;
            btn.classList.remove("is-loading");
            if (btn.dataset.originalHtml) {
                btn.innerHTML = btn.dataset.originalHtml;
                delete btn.dataset.originalHtml;
            }
        }
    }

    function initButtonLoadingHelper() {
        window.bpSetButtonLoading = setButtonLoading;
    }

    /* =========================================================
       TOAST SYSTEM
       ========================================================= */
    function initToastSystem() {
        window.bpShowToast = function (message, type) {
            type = type || "info";

            const container = document.getElementById("bpToastContainer");
            if (!container) return;

            const icons = {
                success: "bi-check2-circle",
                error: "bi-exclamation-triangle",
                warning: "bi-exclamation-circle",
                info: "bi-info-circle",
            };

            const toast = document.createElement("div");
            toast.className = "bp-toast bp-toast-" + type;
            toast.setAttribute("role", "status");
            toast.innerHTML =
                '<i class="bi ' + (icons[type] || icons.info) + '"></i>' +
                '<span>' + message + '</span>';

            container.appendChild(toast);

            window.setTimeout(function () {
                toast.classList.add("is-leaving");
                window.setTimeout(function () {
                    toast.remove();
                }, 220);
            }, 4200);
        };

        document.querySelectorAll("[data-bp-toast-info]").forEach(function (el) {
            el.addEventListener("click", function () {
                window.bpShowToast(el.getAttribute("data-bp-toast-info"), "info");
            });
        });
    }

    /* =========================================================
       ACCOUNT NAVIGATION (mobile toggle + scroll spy)
       ========================================================= */
    function initAccountNav() {
        const toggle = document.getElementById("bpNavToggle");
        const list = document.getElementById("bpNavList");

        if (toggle && list) {
            toggle.addEventListener("click", function () {
                const isOpen = list.classList.toggle("is-open");
                toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
            });
        }

        const navLinks = document.querySelectorAll("[data-bp-nav]");
        const sectionMap = [];

        navLinks.forEach(function (link) {
            const href = link.getAttribute("href");
            if (href && href.indexOf("#") === 0 && href.length > 1) {
                const target = document.querySelector(href);
                if (target) {
                    sectionMap.push({ link: link, target: target });
                }
            }
        });

        if (!sectionMap.length || !("IntersectionObserver" in window)) {
            return;
        }

        const observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) return;

                    const match = sectionMap.find(function (item) {
                        return item.target === entry.target;
                    });

                    if (!match) return;

                    navLinks.forEach(function (link) {
                        link.classList.remove("is-active");
                    });

                    match.link.classList.add("is-active");
                });
            },
            { rootMargin: "-45% 0px -50% 0px", threshold: 0 }
        );

        sectionMap.forEach(function (item) {
            observer.observe(item.target);
        });

        // Close mobile nav after choosing a section
        navLinks.forEach(function (link) {
            link.addEventListener("click", function () {
                if (list && list.classList.contains("is-open")) {
                    list.classList.remove("is-open");
                    if (toggle) toggle.setAttribute("aria-expanded", "false");
                }
            });
        });
    }

    function initComingSoonLinks() {
        document.querySelectorAll("[data-bp-coming-soon]").forEach(function (link) {
            link.addEventListener("click", function (e) {
                e.preventDefault();
                window.bpShowToast("This section isn't available yet — check back soon.", "info");
            });
        });
    }

    /* =========================================================
       EDIT PROFILE MODAL (avatar preview + save)
       ========================================================= */
    function initEditProfileModal() {
        const uploadInput = document.getElementById("bpAvatarUploadInput");
        const previewImg = document.getElementById("bpAvatarPreviewImg");
        const previewFallback = document.getElementById("bpAvatarPreviewFallback");
        const removeBtn = document.getElementById("bpAvatarRemoveBtn");
        const saveBtn = document.getElementById("bpSaveProfileBtn");

        if (uploadInput) {
            uploadInput.addEventListener("change", function () {
                const file = uploadInput.files && uploadInput.files[0];
                if (!file) return;

                if (!/^image\/(png|jpeg|webp)$/.test(file.type)) {
                    window.bpShowToast("Please choose a JPG, PNG or WEBP image.", "error");
                    uploadInput.value = "";
                    return;
                }

                if (file.size > 5 * 1024 * 1024) {
                    window.bpShowToast("Image must be smaller than 5 MB.", "error");
                    uploadInput.value = "";
                    return;
                }

                const reader = new FileReader();
                reader.onload = function (e) {
                    if (previewImg) {
                        previewImg.src = e.target.result;
                        previewImg.hidden = false;
                    }
                    if (previewFallback) {
                        previewFallback.style.display = "none";
                    }
                };
                reader.readAsDataURL(file);
            });
        }

        if (removeBtn) {
            removeBtn.addEventListener("click", function () {
                if (previewImg) {
                    previewImg.src = "";
                    previewImg.hidden = true;
                }
                if (previewFallback) {
                    previewFallback.style.display = "";
                }
                if (uploadInput) {
                    uploadInput.value = "";
                }
                window.bpShowToast("Profile photo removed.", "info");
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener("click", async function () {
                const firstName = document.getElementById("bpFirstNameInput");
                const lastName = document.getElementById("bpLastNameInput");
                const username = document.getElementById("bpUsernameInput");
                const email = document.getElementById("bpEmailInput");
                const phone = document.getElementById("bpPhoneInput");

                if (firstName && !firstName.value.trim()) {
                    window.bpShowToast("Please enter your first name.", "error");
                    firstName.focus();
                    return;
                }

                if (username && !username.value.trim()) {
                    window.bpShowToast("Please enter a username.", "error");
                    username.focus();
                    return;
                }

                if (
                    email &&
                    !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())
                ) {
                    window.bpShowToast("Please enter a valid email address.", "error");
                    email.focus();
                    return;
                }

                if (
                    phone &&
                    phone.value.trim() &&
                    !/^\+?[\d\s\-()]+$/.test(phone.value.trim())
                ) {
                    window.bpShowToast("Please enter a valid phone number.", "error");
                    phone.focus();
                    return;
                }

                const endpoint = saveBtn.dataset.url;

                if (!endpoint) {
                    window.bpShowToast(
                        "Profile update endpoint is not configured.",
                        "error"
                    );
                    return;
                }

                const csrfToken = document.querySelector(
                    "[name=csrfmiddlewaretoken]"
                )?.value;

                if (!csrfToken) {
                    window.bpShowToast(
                        "Security token missing. Please refresh the page.",
                        "error"
                    );
                    return;
                }

                const payload = new FormData();
                payload.append("first_name", firstName ? firstName.value.trim() : "");
                payload.append("last_name", lastName ? lastName.value.trim() : "");
                payload.append("username", username ? username.value.trim() : "");
                payload.append("email", email ? email.value.trim() : "");
                payload.append("phone", phone ? phone.value.trim() : "");

                const profileImage = uploadInput && uploadInput.files && uploadInput.files[0];
                if (profileImage) payload.append("profile_image", profileImage);

                setButtonLoading(saveBtn, true, "Saving...");

                try {
                    const response = await fetch(endpoint, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": csrfToken,
                            "X-Requested-With": "XMLHttpRequest",
                        },
                        credentials: "same-origin",
                        body: payload,
                    });

                    let data = {};

                    try {
                        data = await response.json();
                    } catch (error) {
                        data = {};
                    }

                    if (!response.ok) {
                        if (data.errors) {
                            const firstError = Object.values(data.errors).flat()[0];

                            window.bpShowToast(
                                firstError || "Unable to update your profile.",
                                "error"
                            );
                        } else {
                            window.bpShowToast(
                                data.message || "Unable to update your profile.",
                                "error"
                            );
                        }

                        return;
                    }

                    const heroName = document.querySelector(".bp-hero-name");

                    if (heroName) {
                        const fullName = [
                            data.user?.first_name ?? firstName?.value.trim(),
                            data.user?.last_name ?? lastName?.value.trim(),
                        ]
                            .filter(Boolean)
                            .join(" ")
                            .trim();

                        if (fullName) {
                            heroName.textContent = fullName;
                        }
                    }

                    const heroUsername = document.querySelector(".bp-hero-username");

                    if (heroUsername) {
                        heroUsername.textContent =
                            data.user?.username ?? username?.value.trim();
                    }

                    if (data.user?.profile_image_url) {
                        const heroAvatarWrap = document.querySelector(".bp-hero-avatar-wrap");
                        const heroAvatar = heroAvatarWrap?.querySelector(".bp-hero-avatar");
                        if (heroAvatar) {
                            if (heroAvatar.tagName === "IMG") {
                                heroAvatar.src = data.user.profile_image_url;
                            } else {
                                const image = document.createElement("img");
                                image.src = data.user.profile_image_url;
                                image.alt = data.user.username || "Profile";
                                image.className = "bp-hero-avatar";
                                heroAvatar.replaceWith(image);
                            }
                        }
                    }

                    const modalEl = document.getElementById("bpEditProfileModal");

                    if (
                        modalEl &&
                        window.bootstrap &&
                        window.bootstrap.Modal
                    ) {
                        const instance =
                            window.bootstrap.Modal.getInstance(modalEl) ||
                            new window.bootstrap.Modal(modalEl);

                        instance.hide();
                    }

                    if (data.email_changed) {
                        window.bpShowToast(
                            data.message ||
                            "Your email was changed. Please verify your new email address.",
                            "success"
                        );
                    } else {
                        window.bpShowToast(
                            data.message || "Profile updated successfully.",
                            "success"
                        );
                    }

                    if (data.user?.email) {
                        const emailDisplay = document.querySelector(
                            ".bp-profile-email"
                        );

                        if (emailDisplay) {
                            emailDisplay.textContent = data.user.email;
                        }
                    }
                } catch (error) {
                    console.error("Profile update error:", error);

                    window.bpShowToast(
                        "Something went wrong while updating your profile. Please try again.",
                        "error"
                    );
                } finally {
                    setButtonLoading(saveBtn, false);
                }
            });
        }
    }

    /* =========================================================
       ADDRESS MODALS (add / edit / view / delete / set default)
       ========================================================= */
    function initAddressModals() {
        const addressModalEl = document.getElementById("bpAddressModal");
        const addressModalTitle = document.getElementById("bpAddressModalTitle");
        const addAddressBtn = document.getElementById("bpAddAddressBtn");
        const saveAddressBtn = document.getElementById("bpSaveAddressBtn");
        const addressIdInput = document.getElementById("bpAddressIdInput");

        const fields = {
            type: document.getElementById("bpAddressTypeInput"),
            fullName: document.getElementById("bpAddrFullNameInput"),
            phone: document.getElementById("bpAddrPhoneInput"),
            line1: document.getElementById("bpAddrLine1Input"),
            line2: document.getElementById("bpAddrLine2Input"),
            city: document.getElementById("bpAddrCityInput"),
            postal: document.getElementById("bpAddrPostalInput"),
            isDefault: document.getElementById("bpAddrDefaultInput"),
        };

        function resetAddressForm() {
            if (addressIdInput) {
                addressIdInput.value = "";
            }

            if (fields.type) {
                fields.type.value = "home";
            }

            if (fields.fullName) {
                fields.fullName.value = "";
            }

            if (fields.phone) {
                fields.phone.value = "";
            }

            if (fields.line1) {
                fields.line1.value = "";
            }

            if (fields.line2) {
                fields.line2.value = "";
            }

            if (fields.city) {
                fields.city.value = "";
            }

            if (fields.postal) {
                fields.postal.value = "";
            }

            if (fields.isDefault) {
                fields.isDefault.checked = false;
            }

            if (addressModalTitle) {
                addressModalTitle.textContent = "Add New Address";
            }
        }

        function openAddressModal() {
            const modalEl = document.getElementById("bpAddressModal");

            if (
                modalEl &&
                window.bootstrap &&
                window.bootstrap.Modal
            ) {
                const instance =
                    window.bootstrap.Modal.getInstance(modalEl) ||
                    new window.bootstrap.Modal(modalEl);

                instance.show();
            }
        }

        function closeAddressModal() {
            const modalEl = document.getElementById("bpAddressModal");

            if (
                modalEl &&
                window.bootstrap &&
                window.bootstrap.Modal
            ) {
                const instance =
                    window.bootstrap.Modal.getInstance(modalEl) ||
                    new window.bootstrap.Modal(modalEl);

                instance.hide();
            }
        }

        if (addAddressBtn) {
            addAddressBtn.addEventListener("click", function () {
                resetAddressForm();
                openAddressModal();
            });
        }

        document.querySelectorAll(".bp-edit-address-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const card = btn.closest(".bp-address-card");

                if (!card) {
                    return;
                }

                if (addressModalTitle) {
                    addressModalTitle.textContent = "Edit Address";
                }

                if (addressIdInput) {
                    addressIdInput.value =
                        card.dataset.addressId || "";
                }

                if (fields.type) {
                    fields.type.value =
                        card.dataset.addressType || "home";
                }

                if (fields.fullName) {
                    fields.fullName.value =
                        card.dataset.fullName || "";
                }

                if (fields.phone) {
                    fields.phone.value =
                        card.dataset.phone || "";
                }

                if (fields.line1) {
                    fields.line1.value =
                        card.dataset.addressLine1 || "";
                }

                if (fields.line2) {
                    fields.line2.value =
                        card.dataset.addressLine2 || "";
                }

                if (fields.city) {
                    fields.city.value =
                        card.dataset.city || "";
                }

                if (fields.postal) {
                    fields.postal.value =
                        card.dataset.postalCode || "";
                }

                if (fields.isDefault) {
                    fields.isDefault.checked =
                        card.dataset.isDefault === "true";
                }

                openAddressModal();
            });
        });

        function updateDefaultAddressUI(addressId, isDefault) {
            document.querySelectorAll(".bp-address-card").forEach(function (card) {
                const cardAddressId =
                    card.dataset.addressId || "";

                const isCurrentAddress =
                    String(cardAddressId) === String(addressId);

                const shouldBeDefault =
                    isCurrentAddress
                        ? Boolean(isDefault)
                        : false;

                card.dataset.isDefault =
                    String(shouldBeDefault);

                const badge =
                    card.querySelector(".bp-default-address-badge");

                if (badge) {
                    badge.classList.toggle(
                        "d-none",
                        !shouldBeDefault
                    );
                }
            });
        }

        function updateBuyerAddressCard(address) {
            const card = document.querySelector(
                `.bp-address-card[data-address-id="${address.id}"]`
            );

            if (!card) {
                window.location.reload();
                return;
            }

            card.dataset.addressType =
                address.address_type || "";

            card.dataset.fullName =
                address.full_name || "";

            card.dataset.phone =
                address.phone || "";

            card.dataset.addressLine1 =
                address.address_line_1 || "";

            card.dataset.addressLine2 =
                address.address_line_2 || "";

            card.dataset.city =
                address.city || "";

            card.dataset.postalCode =
                address.postal_code || "";

            card.dataset.isDefault =
                String(Boolean(address.is_default));

            const typeElement =
                card.querySelector(".bp-address-type");

            const nameElement =
                card.querySelector(".bp-address-name");

            const phoneElement =
                card.querySelector(".bp-address-phone");

            const line1Element =
                card.querySelector(".bp-address-line1");

            const line2Element =
                card.querySelector(".bp-address-line2");

            const cityElement =
                card.querySelector(".bp-address-city");

            const postalElement =
                card.querySelector(".bp-address-postal");

            if (typeElement) {
                typeElement.textContent =
                    address.address_type_display ||
                    address.address_type ||
                    "";
            }

            if (nameElement) {
                nameElement.textContent =
                    address.full_name || "";
            }

            if (phoneElement) {
                phoneElement.textContent =
                    address.phone || "";
            }

            if (line1Element) {
                line1Element.textContent =
                    address.address_line_1 || "";
            }

            if (line2Element) {
                line2Element.textContent =
                    address.address_line_2 || "";
            }

            if (cityElement) {
                cityElement.textContent =
                    address.city || "";
            }

            if (postalElement) {
                postalElement.textContent =
                    address.postal_code || "";
            }

            updateDefaultAddressUI(
                address.id,
                address.is_default
            );
        }

        if (saveAddressBtn) {
            saveAddressBtn.addEventListener("click", async function () {
                if (
                    fields.fullName &&
                    !fields.fullName.value.trim()
                ) {
                    window.bpShowToast(
                        "Please enter a full name.",
                        "error"
                    );

                    fields.fullName.focus();
                    return;
                }

                if (
                    fields.phone &&
                    !fields.phone.value.trim()
                ) {
                    window.bpShowToast(
                        "Please enter a phone number.",
                        "error"
                    );

                    fields.phone.focus();
                    return;
                }

                if (
                    fields.line1 &&
                    !fields.line1.value.trim()
                ) {
                    window.bpShowToast(
                        "Please enter an address.",
                        "error"
                    );

                    fields.line1.focus();
                    return;
                }

                if (
                    fields.city &&
                    !fields.city.value.trim()
                ) {
                    window.bpShowToast(
                        "Please enter a city.",
                        "error"
                    );

                    fields.city.focus();
                    return;
                }

                if (
                    fields.postal &&
                    !fields.postal.value.trim()
                ) {
                    window.bpShowToast(
                        "Please enter a postal code.",
                        "error"
                    );

                    fields.postal.focus();
                    return;
                }

                const csrfToken =
                    document.querySelector(
                        "[name=csrfmiddlewaretoken]"
                    )?.value;

                if (!csrfToken) {
                    window.bpShowToast(
                        "Security token missing. Please refresh the page.",
                        "error"
                    );

                    return;
                }

                const addressId =
                    addressIdInput?.value.trim() || "";

                const isEditing =
                    Boolean(addressId);

                const endpoint = isEditing
                    ? saveAddressBtn.dataset.updateUrl
                    : saveAddressBtn.dataset.saveUrl;

                if (!endpoint) {
                    window.bpShowToast(
                        "Address endpoint is not configured.",
                        "error"
                    );

                    return;
                }

                let payload;

                if (isEditing) {
                    payload = {
                        addressId: addressId,

                        fullName:
                            fields.fullName?.value.trim() ||
                            "",

                        phone:
                            fields.phone?.value.trim() ||
                            "",

                        address:
                            fields.line1?.value.trim() ||
                            "",

                        addressLine2:
                            fields.line2?.value.trim() ||
                            "",

                        city:
                            fields.city?.value.trim() ||
                            "",

                        postalCode:
                            fields.postal?.value.trim() ||
                            "",

                        type:
                            fields.type?.value ||
                            "home",

                        isDefault:
                            fields.isDefault?.checked ||
                            false,
                    };
                } else {
                    payload = {
                        addressId: "null",

                        label:
                            fields.type?.value ||
                            "home",

                        fullName:
                            fields.fullName?.value.trim() ||
                            "",

                        phoneNumber:
                            fields.phone?.value.trim() ||
                            "",

                        address:
                            fields.line1?.value.trim() ||
                            "",

                        addressLine2:
                            fields.line2?.value.trim() ||
                            "",

                        city:
                            fields.city?.value.trim() ||
                            "",

                        ptCode:
                            fields.postal?.value.trim() ||
                            "",

                        isDefault:
                            fields.isDefault?.checked ||
                            false,
                    };
                }

                setButtonLoading(
                    saveAddressBtn,
                    true,
                    "Saving..."
                );

                try {
                    const response = await fetch(
                        endpoint,
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",

                                "X-CSRFToken":
                                    csrfToken,

                                "X-Requested-With":
                                    "XMLHttpRequest",
                            },

                            credentials:
                                "same-origin",

                            body:
                                JSON.stringify(payload),
                        }
                    );

                    let data = {};

                    try {
                        data =
                            await response.json();
                    } catch (error) {
                        data = {};
                    }

                    if (
                        !response.ok ||
                        !data.success
                    ) {
                        window.bpShowToast(
                            data.message ||
                            "Unable to save the address.",
                            "error"
                        );

                        return;
                    }

                    closeAddressModal();

                    window.bpShowToast(
                        isEditing
                            ? "Address updated successfully."
                            : "Address added successfully.",
                        "success"
                    );

                    if (data.address) {
                        updateBuyerAddressCard(
                            data.address
                        );
                    } else {
                        window.location.reload();
                    }

                    resetAddressForm();

                } catch (error) {
                    console.error(
                        "Address save error:",
                        error
                    );

                    window.bpShowToast(
                        "Something went wrong while saving the address. Please try again.",
                        "error"
                    );

                } finally {
                    setButtonLoading(
                        saveAddressBtn,
                        false
                    );
                }
            });
        }
        // View address
        document.querySelectorAll(".bp-view-address-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const card = btn.closest(".bp-address-card");
                if (!card) return;

                const body = document.getElementById("bpViewAddressBody");
                if (!body) return;

                const typeLabel = (card.querySelector(".bp-address-type-badge") || {}).textContent || "—";

                body.innerHTML =
                    '<div class="bp-view-item"><span class="bp-view-label">Type</span><span class="bp-view-value">' + typeLabel.trim() + '</span></div>' +
                    '<div class="bp-view-item"><span class="bp-view-label">Full Name</span><span class="bp-view-value">' + (card.dataset.fullName || "—") + '</span></div>' +
                    '<div class="bp-view-item"><span class="bp-view-label">Phone</span><span class="bp-view-value">' + (card.dataset.phone || "—") + '</span></div>' +
                    '<div class="bp-view-item"><span class="bp-view-label">City</span><span class="bp-view-value">' + (card.dataset.city || "—") + '</span></div>' +
                    '<div class="bp-view-item is-wide"><span class="bp-view-label">Address Line 1</span><span class="bp-view-value">' + (card.dataset.addressLine1 || "—") + '</span></div>' +
                    '<div class="bp-view-item is-wide"><span class="bp-view-label">Address Line 2</span><span class="bp-view-value">' + (card.dataset.addressLine2 || "Not provided") + '</span></div>' +
                    '<div class="bp-view-item"><span class="bp-view-label">Postal Code</span><span class="bp-view-value">' + (card.dataset.postalCode || "—") + '</span></div>' +
                    '<div class="bp-view-item"><span class="bp-view-label">Default</span><span class="bp-view-value">' + (card.dataset.isDefault === "true" ? "Yes" : "No") + '</span></div>';

                const modalEl = document.getElementById("bpViewAddressModal");
                if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                    new window.bootstrap.Modal(modalEl).show();
                }
            });
        });

        // Set default address
        document.querySelectorAll(".bp-default-address-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const card = btn.closest(".bp-address-card");
                if (!card) return;

                document.querySelectorAll(".bp-address-card").forEach(function (otherCard) {
                    otherCard.classList.remove("is-default");
                    otherCard.dataset.isDefault = "false";
                    const pill = otherCard.querySelector(".bp-default-pill");
                    if (pill) pill.remove();
                });

                card.classList.add("is-default");
                card.dataset.isDefault = "true";

                const top = card.querySelector(".bp-address-card-top");
                if (top && !top.querySelector(".bp-default-pill")) {
                    const pill = document.createElement("span");
                    pill.className = "bp-default-pill";
                    pill.innerHTML = '<i class="bi bi-star-fill"></i> Default';
                    top.appendChild(pill);
                }

                window.bpShowToast("Default address updated.", "success");
            });
        });

        // Delete address — custom confirmation modal
        let addressCardPendingDelete = null;

        document.querySelectorAll(".bp-delete-address-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                addressCardPendingDelete = btn.closest(".bp-address-card");
                const modalEl = document.getElementById("bpDeleteAddressModal");
                if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                    new window.bootstrap.Modal(modalEl).show();
                }
            });
        });

        const confirmDeleteBtn = document.getElementById(
            "bpConfirmDeleteAddressBtn"
        );

        if (confirmDeleteBtn) {
            confirmDeleteBtn.addEventListener(
                "click",
                async function () {
                    if (!addressCardPendingDelete) {
                        return;
                    }

                    const addressId =
                        addressCardPendingDelete.dataset.addressId;

                    if (!addressId) {
                        window.bpShowToast(
                            "Unable to identify the address.",
                            "error"
                        );
                        return;
                    }

                    const endpoint =
                        confirmDeleteBtn.dataset.url;

                    if (!endpoint) {
                        window.bpShowToast(
                            "Delete address endpoint is not configured.",
                            "error"
                        );
                        return;
                    }

                    const csrfToken =
                        document.querySelector(
                            "[name=csrfmiddlewaretoken]"
                        )?.value;

                    if (!csrfToken) {
                        window.bpShowToast(
                            "Security token missing. Please refresh the page.",
                            "error"
                        );
                        return;
                    }

                    setButtonLoading(
                        confirmDeleteBtn,
                        true,
                        "Removing..."
                    );

                    try {
                        const response = await fetch(
                            endpoint,
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json",

                                    "X-CSRFToken":
                                        csrfToken,

                                    "X-Requested-With":
                                        "XMLHttpRequest",
                                },

                                credentials:
                                    "same-origin",

                                body: JSON.stringify({
                                    addressId: addressId,
                                }),
                            }
                        );

                        let data = {};

                        try {
                            data =
                                await response.json();
                        } catch (error) {
                            data = {};
                        }

                        if (
                            !response.ok ||
                            !data.success
                        ) {
                            window.bpShowToast(
                                data.message ||
                                "Unable to delete the address.",
                                "error"
                            );

                            return;
                        }

                        const cardToRemove =
                            addressCardPendingDelete;

                        addressCardPendingDelete = null;

                        const modalEl =
                            document.getElementById(
                                "bpDeleteAddressModal"
                            );

                        if (
                            modalEl &&
                            window.bootstrap &&
                            window.bootstrap.Modal
                        ) {
                            const instance =
                                window.bootstrap.Modal.getInstance(
                                    modalEl
                                ) ||
                                new window.bootstrap.Modal(
                                    modalEl
                                );

                            instance.hide();
                        }

                        if (cardToRemove) {
                            cardToRemove.style.transition =
                                "opacity 0.2s ease";

                            cardToRemove.style.opacity =
                                "0";

                            window.setTimeout(
                                function () {
                                    cardToRemove.remove();

                                    updateAddressEmptyState();
                                },
                                200
                            );
                        }

                        window.bpShowToast(
                            data.message ||
                            "Address deleted successfully.",
                            "success"
                        );

                    } catch (error) {
                        console.error(
                            "Address delete error:",
                            error
                        );

                        window.bpShowToast(
                            "Something went wrong while deleting the address. Please try again.",
                            "error"
                        );

                    } finally {
                        setButtonLoading(
                            confirmDeleteBtn,
                            false
                        );
                    }
                }
            );
        }
    }

    /* =========================================================
       WISHLIST — VISUAL REMOVAL
       ========================================================= */
    function initWishlistRemoval() {
        document.querySelectorAll(".bp-wishlist-remove-btn").forEach(function (btn) {
            btn.addEventListener("click", async function () {
                const card =
                    btn.closest(".bp-wishlist-product-card");

                if (!card) {
                    return;
                }

                const productSlug =
                    card.dataset.productSlug;

                const endpoint =
                    btn.dataset.url;

                if (!productSlug) {
                    window.bpShowToast(
                        "Unable to identify this product.",
                        "error"
                    );
                    return;
                }

                if (!endpoint) {
                    window.bpShowToast(
                        "Wishlist endpoint is not configured.",
                        "error"
                    );
                    return;
                }

                const csrfToken =
                    document.querySelector(
                        "[name=csrfmiddlewaretoken]"
                    )?.value;

                if (!csrfToken) {
                    window.bpShowToast(
                        "Security token missing. Please refresh the page.",
                        "error"
                    );
                    return;
                }

                setButtonLoading(
                    btn,
                    true,
                    " "
                );

                try {
                    const response = await fetch(
                        endpoint.replace(
                            "__PRODUCT_SLUG__",
                            encodeURIComponent(productSlug)
                        ),
                        {
                            method: "POST",

                            headers: {
                                "X-CSRFToken":
                                    csrfToken,

                                "X-Requested-With":
                                    "XMLHttpRequest",
                            },

                            credentials:
                                "same-origin",
                        }
                    );

                    let data = {};

                    try {
                        data =
                            await response.json();
                    } catch (error) {
                        data = {};
                    }

                    if (
                        !response.ok ||
                        !data.success
                    ) {
                        window.bpShowToast(
                            data.message ||
                            "Unable to remove this item from your wishlist.",
                            "error"
                        );

                        return;
                    }

                    /*
                     * The existing toggle endpoint returns
                     * is_added. Since this action is specifically
                     * for removing an existing wishlist item,
                     * the expected result is false.
                     */
                    if (data.is_added) {
                        window.bpShowToast(
                            "Wishlist item could not be removed.",
                            "error"
                        );

                        return;
                    }

                    card.style.transition =
                        "opacity 0.25s ease, transform 0.25s ease";

                    card.style.opacity = "0";
                    card.style.transform = "scale(0.95)";

                    window.setTimeout(function () {
                        card.remove();

                        updateWishlistEmptyState();
                    }, 250);

                    updateWishlistCount(
                        data.wishlist_count
                    );

                    window.bpShowToast(
                        "Wishlist item removed.",
                        "success"
                    );

                } catch (error) {
                    console.error(
                        "Wishlist removal error:",
                        error
                    );

                    window.bpShowToast(
                        "Something went wrong while removing the wishlist item. Please try again.",
                        "error"
                    );

                } finally {
                    setButtonLoading(
                        btn,
                        false
                    );
                }
            });
        });
    }

    function updateWishlistCount(count) {
        if (count === undefined || count === null) {
            return;
        }

        document
            .querySelectorAll(".bp-wishlist-count")
            .forEach(function (element) {
                element.textContent = count;
            });
    }

    function updateWishlistEmptyState() {
        const cards =
            document.querySelectorAll(
                ".bp-wishlist-product-card"
            );

        if (cards.length > 0) {
            return;
        }

        const container =
            document.querySelector(
                ".bp-wishlist-products"
            );

        if (!container) {
            return;
        }

        container.innerHTML = `
        <div class="bp-wishlist-empty">
            <i class="bi bi-heart"></i>
            <h4>Your wishlist is empty</h4>
            <p>Save products you love and find them here later.</p>
        </div>
    `;
    }
    /* =========================================================
       CHANGE PASSWORD MODAL
       ========================================================= */
    function initPasswordModal() {
        document.querySelectorAll(".bp-password-toggle").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const targetId = btn.getAttribute("data-target");
                const input = document.getElementById(targetId);
                if (!input) return;

                const isHidden = input.type === "password";
                input.type = isHidden ? "text" : "password";

                const icon = btn.querySelector("i");
                if (icon) {
                    icon.classList.toggle("bi-eye", !isHidden);
                    icon.classList.toggle("bi-eye-slash", isHidden);
                }

                btn.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
            });
        });

        const newPasswordInput = document.getElementById("bpNewPasswordInput");
        const confirmPasswordInput = document.getElementById("bpConfirmPasswordInput");
        const currentPasswordInput = document.getElementById("bpCurrentPasswordInput");
        const strengthFill = document.getElementById("bpPasswordStrengthFill");
        const strengthLabel = document.getElementById("bpPasswordStrengthLabel");
        const matchError = document.getElementById("bpPasswordMatchError");
        const requirementItems = document.querySelectorAll("#bpPasswordRequirements li");
        const saveBtn = document.getElementById("bpSavePasswordBtn");

        function evaluatePassword(value) {
            const rules = {
                length: value.length >= 8,
                upper: /[A-Z]/.test(value),
                lower: /[a-z]/.test(value),
                number: /\d/.test(value),
                special: /[^A-Za-z0-9]/.test(value),
            };

            requirementItems.forEach(function (item) {
                const rule = item.getAttribute("data-rule");
                const met = rules[rule];
                item.classList.toggle("is-met", Boolean(met));
                const icon = item.querySelector("i");
                if (icon) {
                    icon.classList.toggle("bi-circle", !met);
                    icon.classList.toggle("bi-check-circle-fill", Boolean(met));
                }
            });

            const metCount = Object.values(rules).filter(Boolean).length;
            const pct = (metCount / 5) * 100;

            if (strengthFill) {
                strengthFill.style.width = pct + "%";
                if (metCount <= 2) {
                    strengthFill.style.backgroundColor = "#b54b3b";
                } else if (metCount <= 4) {
                    strengthFill.style.backgroundColor = "#b7802b";
                } else {
                    strengthFill.style.backgroundColor = "#4f7d54";
                }
            }

            if (strengthLabel) {
                if (!value) {
                    strengthLabel.textContent = "Password strength";
                } else if (metCount <= 2) {
                    strengthLabel.textContent = "Weak password";
                } else if (metCount <= 4) {
                    strengthLabel.textContent = "Good password";
                } else {
                    strengthLabel.textContent = "Strong password";
                }
            }

            return metCount === 5;
        }

        if (newPasswordInput) {
            newPasswordInput.addEventListener("input", function () {
                evaluatePassword(newPasswordInput.value);
            });
        }

        function checkMatch() {
            if (!newPasswordInput || !confirmPasswordInput || !matchError) return true;

            if (!confirmPasswordInput.value) {
                matchError.hidden = true;
                return true;
            }

            const matches = newPasswordInput.value === confirmPasswordInput.value;
            matchError.hidden = matches;
            return matches;
        }

        if (confirmPasswordInput) {
            confirmPasswordInput.addEventListener("input", checkMatch);
        }

        if (saveBtn) {
            saveBtn.addEventListener("click", async function () {

                if (currentPasswordInput && !currentPasswordInput.value) {
                    window.bpShowToast("Please enter your current password.", "error");
                    currentPasswordInput.focus();
                    return;
                }

                const strong = newPasswordInput
                    ? evaluatePassword(newPasswordInput.value)
                    : false;

                if (!strong) {
                    window.bpShowToast(
                        "Your new password doesn't meet all requirements yet.",
                        "error"
                    );
                    return;
                }

                if (!checkMatch()) {
                    window.bpShowToast(
                        "New password and confirmation don't match.",
                        "error"
                    );
                    return;
                }

                const endpoint = saveBtn.dataset.url;

                if (!endpoint) {
                    window.bpShowToast(
                        "Password change endpoint is not configured.",
                        "error"
                    );
                    return;
                }

                const csrfToken = document.querySelector(
                    "[name=csrfmiddlewaretoken]"
                )?.value;

                if (!csrfToken) {
                    window.bpShowToast(
                        "Security token is missing. Please refresh the page.",
                        "error"
                    );
                    return;
                }

                setButtonLoading(saveBtn, true, "Updating...");

                try {
                    const response = await fetch(endpoint, {
                        method: "POST",
                        credentials: "same-origin",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": csrfToken,
                            "X-Requested-With": "XMLHttpRequest"
                        },
                        body: JSON.stringify({
                            current_password: currentPasswordInput.value,
                            new_password: newPasswordInput.value,
                            confirm_password: confirmPasswordInput.value
                        })
                    });

                    let data;

                    try {
                        data = await response.json();
                    } catch (error) {
                        throw new Error(
                            "The server returned an unexpected response."
                        );
                    }

                    if (!response.ok || !data.success) {
                        throw new Error(
                            data.message || "Unable to change your password."
                        );
                    }

                    const modalEl = document.getElementById(
                        "bpChangePasswordModal"
                    );

                    if (
                        modalEl &&
                        window.bootstrap &&
                        window.bootstrap.Modal
                    ) {
                        const instance =
                            window.bootstrap.Modal.getInstance(modalEl) ||
                            new window.bootstrap.Modal(modalEl);

                        instance.hide();
                    }

                    if (currentPasswordInput) {
                        currentPasswordInput.value = "";
                    }

                    if (newPasswordInput) {
                        newPasswordInput.value = "";
                    }

                    if (confirmPasswordInput) {
                        confirmPasswordInput.value = "";
                    }

                    evaluatePassword("");
                    checkMatch();

                    window.bpShowToast(
                        data.message || "Your password has been changed successfully.",
                        "success"
                    );

                } catch (error) {
                    window.bpShowToast(
                        error.message || "Unable to change your password.",
                        "error"
                    );
                } finally {
                    setButtonLoading(saveBtn, false);
                }
            });
        }
    }

    /* =========================================================
       2FA URL
       ========================================================= */
    const twoFactorToggle = document.getElementById("bp2faToggle");

    if (twoFactorToggle) {
        twoFactorToggle.addEventListener("change", function () {
            window.location.href = this.dataset["2faUrl"];
        });
    }
    /* =========================================================
       COMMUNICATION PREFERENCES
       ========================================================= */

    function initPreferenceToggles() {
        document.querySelectorAll(".bp-channel-chip").forEach(function (chip) {
            chip.addEventListener("click", function () {
                chip.classList.toggle("is-active");
            });
        });

        const saveBtn = document.getElementById("bpSavePrefsBtn");

        if (!saveBtn) {
            return;
        }

        saveBtn.addEventListener("click", async function () {
            const preferenceInputs = document.querySelectorAll(
                'input[type="checkbox"][data-pref]'
            );

            const preferences = {};

            preferenceInputs.forEach(function (input) {
                preferences[input.dataset.pref] = input.checked;
            });

            const channels = {};

            document.querySelectorAll(".bp-channel-chip[data-channel]").forEach(
                function (chip) {
                    channels[chip.dataset.channel] =
                        chip.classList.contains("is-active");
                }
            );

            const payload = {
                preferences: preferences,
                channels: channels
            };

            const endpoint = saveBtn.dataset.url;

            if (!endpoint) {
                window.bpShowToast(
                    "Preferences save endpoint is not configured.",
                    "error"
                );
                return;
            }

            const csrfToken = document.querySelector(
                "[name=csrfmiddlewaretoken]"
            )?.value;

            if (!csrfToken) {
                window.bpShowToast(
                    "Security token is missing. Please refresh the page.",
                    "error"
                );
                return;
            }

            setButtonLoading(saveBtn, true, "Saving...");

            try {
                const response = await fetch(endpoint, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken,
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    body: JSON.stringify(payload)
                });

                let data;

                try {
                    data = await response.json();
                } catch (error) {
                    throw new Error(
                        "The server returned an unexpected response."
                    );
                }

                if (!response.ok || !data.success) {
                    throw new Error(
                        data.message || "Unable to save your preferences."
                    );
                }

                window.bpShowToast(
                    data.message || "Preferences saved.",
                    "success"
                );

            } catch (error) {
                window.bpShowToast(
                    error.message || "Unable to save your preferences.",
                    "error"
                );
            } finally {
                setButtonLoading(saveBtn, false);
            }
        });
    }
    /* =========================================================
       DANGER ZONE — DEACTIVATE / DELETE ACCOUNT
       ========================================================= */
    function initDangerZone() {
        const deactivateBtn = document.getElementById("bpConfirmDeactivateBtn");
        if (deactivateBtn) {
            deactivateBtn.addEventListener("click", function () {
                setButtonLoading(deactivateBtn, true, "Deactivating...");

                window.setTimeout(function () {
                    setButtonLoading(deactivateBtn, false);

                    const modalEl = document.getElementById("bpDeactivateModal");
                    if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                        const instance = window.bootstrap.Modal.getInstance(modalEl) || new window.bootstrap.Modal(modalEl);
                        instance.hide();
                    }

                    window.bpShowToast("Your account deactivation request has been prepared.", "warning");
                }, 900);
            });
        }

        const confirmInput = document.getElementById("bpDeleteConfirmInput");
        const ackCheckbox = document.getElementById("bpDeleteAckCheckbox");
        const deleteBtn = document.getElementById("bpConfirmDeleteAccountBtn");

        function refreshDeleteButtonState() {
            if (!deleteBtn) return;
            const typedOk = confirmInput && confirmInput.value.trim().toUpperCase() === "DELETE";
            const ackOk = ackCheckbox && ackCheckbox.checked;
            deleteBtn.disabled = !(typedOk && ackOk);
        }

        if (confirmInput) confirmInput.addEventListener("input", refreshDeleteButtonState);
        if (ackCheckbox) ackCheckbox.addEventListener("change", refreshDeleteButtonState);

        if (deleteBtn) {
            deleteBtn.addEventListener("click", function () {
                if (deleteBtn.disabled) return;

                setButtonLoading(deleteBtn, true, "Deleting...");

                window.setTimeout(function () {
                    setButtonLoading(deleteBtn, false);

                    const modalEl = document.getElementById("bpDeleteAccountModal");
                    if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                        const instance = window.bootstrap.Modal.getInstance(modalEl) || new window.bootstrap.Modal(modalEl);
                        instance.hide();
                    }

                    window.bpShowToast("Your account deletion request has been prepared.", "warning");
                }, 1000);
            });
        }

        // Reset the delete-account modal state when it's closed
        const deleteModalEl = document.getElementById("bpDeleteAccountModal");
        if (deleteModalEl) {
            deleteModalEl.addEventListener("hidden.bs.modal", function () {
                if (confirmInput) confirmInput.value = "";
                if (ackCheckbox) ackCheckbox.checked = false;
                refreshDeleteButtonState();
            });
        }
    }

    /* =========================================================
       SCROLL REVEAL (matches home.js / seller_account.js pattern)
       ========================================================= */
    function initScrollReveal() {
        const revealTargets = document.querySelectorAll(".bp-card");

        revealTargets.forEach(function (el) {
            el.classList.add("reveal-on-scroll");
        });

        if ("IntersectionObserver" in window) {
            const observer = new IntersectionObserver(
                function (entries, obs) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            entry.target.classList.add("is-visible");
                            obs.unobserve(entry.target);
                        }
                    });
                },
                { threshold: 0.08 }
            );

            revealTargets.forEach(function (el) {
                observer.observe(el);
            });
        } else {
            revealTargets.forEach(function (el) {
                el.classList.add("is-visible");
            });
        }
    }
})();
