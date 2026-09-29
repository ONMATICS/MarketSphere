document.addEventListener('DOMContentLoaded', function () {

    /* =========================================================
       NOTE: This file is intentionally frontend-only.
       No fetch() calls, no API requests, no form submission.
       All interactions here simulate UI feedback until the
       backend (orders app) is wired up.
       ========================================================= */

    /* =========================================================
       ADDRESS SELECTION
       ========================================================= */
    const addressOptions = Array.from(document.querySelectorAll('.co-address-option'));

    addressOptions.forEach(function (option) {
        option.addEventListener('click', function () {
            const radio = option.querySelector('input[type="radio"]');
            if (!radio) return;

            addressOptions.forEach(function (opt) {
                opt.classList.remove('is-selected');
            });

            option.classList.add('is-selected');
            radio.checked = true;
        });
    });

    /* =========================================================
       PAYMENT METHOD SELECTION
       ========================================================= */
    const paymentOptions = Array.from(document.querySelectorAll('.co-payment-option:not(.is-disabled)'));

    paymentOptions.forEach(function (option) {
        option.addEventListener('click', function () {
            const radio = option.querySelector('input[type="radio"]');
            if (!radio || radio.disabled) return;

            document.querySelectorAll('.co-payment-option').forEach(function (opt) {
                opt.classList.remove('is-selected');
            });

            option.classList.add('is-selected');
            radio.checked = true;
        });
    });

    // Disabled ("Coming Soon") payment options gently notify instead of doing nothing.
    document.querySelectorAll('.co-payment-option.is-disabled').forEach(function (option) {
        option.addEventListener('click', function () {
            const nameEl = option.querySelector('.co-payment-name');
            const name = nameEl ? nameEl.textContent.trim() : 'This payment method';
            showToast(name + ' isn\'t available yet — check back soon.', 'info');
        });
    });

    /* =========================================================
       ADD NEW ADDRESS MODAL (placeholder only)
       ========================================================= */
    const addAddressBtn = document.getElementById('coAddAddressBtn');
    const addAddressModalEl = document.getElementById('coAddAddressModal');
    const saveAddressBtn = document.getElementById('coSaveAddressBtn');
    const editAddressBtns = document.querySelectorAll(".edit-button");

    let addAddressModal = null;
    if (addAddressModalEl && window.bootstrap && window.bootstrap.Modal) {
        addAddressModal = new window.bootstrap.Modal(addAddressModalEl);
    }

    if (addAddressBtn) {
        addAddressBtn.addEventListener('click', function () {
            if (addAddressModal) {
                saveAddressBtn.dataset.addressId = null;
                addAddressModal.show();
            } else {
                showToast('Adding new addresses isn\'t available yet.', 'info');
            }
        });
    }

    if (saveAddressBtn) {
        saveAddressBtn.addEventListener('click', function () {
            if (addAddressModal) {
                addAddressModal.hide();
            }
            let fullName = document.getElementById('coNewAddrName').value;
            let phone = document.getElementById('coNewAddrPhone').value;
            let line = document.getElementById('coNewAddrLine').value;
            let city = document.getElementById('coNewAddrCity').value;
            let ptCode = document.getElementById('coNewAddrPtCode').value;
            let tag = document.getElementById('coNewAddrTag').value;
            let addressId = saveAddressBtn.dataset.addressId;
            const data = {
                "fullName": fullName,
                "phoneNumber": phone,
                "label": tag,
                "city": city,
                "ptCode": ptCode,
                "address": line,
                "addressId": addressId
            }
            fetch("/accounts/save-address/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: JSON.stringify(data),
            })
                .then(response => response.json())
                .then(data => {
                    console.log(data);
                    showToast('The new Address has been added successfully.', 'success');
                    document.getElementById('coNewAddrName').value = '';
                    document.getElementById('coNewAddrPhone').value = '';
                    document.getElementById('coNewAddrLine').value = '';
                    document.getElementById('coNewAddrCity').value = '';
                    document.getElementById('coNewAddrPtCode').value = '';
                    document.getElementById('coNewAddrTag').value = '';
                })
                .catch(error => {
                    console.error(error);
                    showToast('There is an error while saving address.', 'error');
                });
        });
    }

    const editButtons = document.querySelectorAll(".edit-button");

    editButtons.forEach((button) => {
        button.addEventListener("click", function (e) {

            e.stopPropagation();

            const addressCard = this.closest(".co-address-option");

            const addressId = this.dataset.addressId;

            const fullName = addressCard.querySelector(".co-address-name").textContent.trim();
            console.log(addressCard);
            const phone = addressCard
                .querySelector(".co-address-phone")
                .textContent
                .replace("📞", "")
                .trim();

            const postalCode = addressCard
                .querySelector(".co-address-ptCode")
                .textContent
                .trim();

            const addressLine = addressCard
                .querySelector(".co-address-line")
                .textContent
                .trim();

            const city = addressCard.dataset.city;

            const label = addressCard.dataset.label;

            document.getElementById("coNewAddrName").value = fullName;
            document.getElementById("coNewAddrPhone").value = phone;
            document.getElementById("coNewAddrLine").value = addressLine;
            document.getElementById("coNewAddrCity").value = city;
            document.getElementById("coNewAddrPtCode").value = postalCode;
            document.getElementById("coNewAddrTag").value =
                label.charAt(0).toUpperCase() + label.slice(1);

            saveAddressBtn.dataset.addressId = addressId;

            addAddressModal.show();
        });
    });

    /* =========================================================
       COUPON APPLY (frontend feedback only)
       ========================================================= */
    const couponForm = document.getElementById('coCouponForm');
    const couponInput = document.getElementById('coCouponInput');
    const couponBtn = document.getElementById('coCouponBtn');
    const couponFeedback = document.getElementById('coCouponFeedback');

    if (couponForm) {
        couponForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const code = couponInput ? couponInput.value.trim() : '';

            if (!code) {
                if (couponFeedback) {
                    couponFeedback.textContent = 'Please enter a coupon code.';
                    couponFeedback.classList.remove('success');
                    couponFeedback.classList.add('error');
                }
                return;
            }

            if (couponBtn) {
                couponBtn.classList.add('is-loading');
                couponBtn.disabled = true;
            }

            // Simulated delay only — no request is made. Django will replace
            // this with a real coupon-validation call against the backend.
            window.setTimeout(function () {
                if (couponBtn) {
                    couponBtn.classList.remove('is-loading');
                    couponBtn.disabled = false;
                }

                if (couponFeedback) {
                    couponFeedback.textContent = 'Coupon codes will be validated once checkout is connected to the backend.';
                    couponFeedback.classList.remove('error');
                    couponFeedback.classList.add('success');
                }

                showToast('Coupon feature is coming soon.', 'info');
            }, 700);
        });
    }

    /* =========================================================
       PLACE ORDER (frontend feedback only)
       ========================================================= */
    const checkoutForm = document.getElementById('checkoutForm');
    const placeOrderBtn = document.getElementById('coPlaceOrderBtn');

    if (checkoutForm && placeOrderBtn) {
        checkoutForm.addEventListener('submit', function (e) {
            e.preventDefault();
            if (placeOrderBtn.classList.contains("is-loading")) return;

            const originalHTML = placeOrderBtn.innerHTML;

            placeOrderBtn.classList.add("is-loading");
            placeOrderBtn.innerHTML =
                '<i class="bi bi-arrow-repeat spin"></i> <span>Placing Order...</span>';

            const selectedAddress = document.querySelector(".co-address-option.is-selected");
            const cartItemId = window.location.pathname.match(/\/checkout\/item\/(\d+)\/?/)?.[1] || "";

            if (!selectedAddress) {
                showToast("Please select a shipping address.", "warning");

                placeOrderBtn.classList.remove("is-loading");
                placeOrderBtn.innerHTML = originalHTML;
                return;
            }

            const data = {
                addressId: selectedAddress.dataset.addressId,
                fullName: document.querySelector('input[name="full_name"]').value,
                email: document.querySelector('input[name="email"]').value,
                phone: document.querySelector('input[name="phone"]').value,
                notes: document.getElementById("coOrderNotes")?.value || "",
                cartItemId: cartItemId,
            };

            fetch("/order/place-order/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                },
                body: JSON.stringify(data),
            })
                .then((response) => {
                    if (!response.ok) {
                        throw new Error("Failed to place order.");
                    }

                    return response.json();
                })
                .then((response) => {
                    placeOrderBtn.classList.remove("is-loading");
                    placeOrderBtn.innerHTML = originalHTML;

                    if (response.status === "success") {
                        showToast("Order placed successfully!", "success");

                        window.location.href = `/order/confirmation/${response.orderNumber}/`;
                    } else {
                        showToast(response.message || "Unable to place order.", "danger");
                    }
                })
                .catch((error) => {
                    console.error(error);

                    placeOrderBtn.classList.remove("is-loading");
                    placeOrderBtn.innerHTML = originalHTML;

                    showToast("Something went wrong. Please try again.", "danger");
                });
        });
    }
});
