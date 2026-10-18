document.addEventListener('DOMContentLoaded', function () {

    /* ================= BACK TO TOP BUTTON ================= */
    const backToTopBtn = document.getElementById('backToTopBtn');

    function toggleBackToTop() {
        if (!backToTopBtn) return;
        backToTopBtn.classList.toggle('visible', window.scrollY > 400);
    }

    window.addEventListener('scroll', toggleBackToTop);
    toggleBackToTop();

    if (backToTopBtn) {
        backToTopBtn.addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    /* ================= IMAGE GALLERY ================= */
    // Placeholder icon set used until Django wires real product images per thumbnail.
    const mainImage = document.getElementById("pdMainImage");
    const thumbs = Array.from(document.querySelectorAll(".pd-thumb"));

    const imageCounter = document.getElementById("pdImageCounter");
    const prevBtn = document.getElementById("pdPrevBtn");
    const nextBtn = document.getElementById("pdNextBtn");

    let currentImageIndex = 0;
    const totalImages = thumbs.length;

    function setActiveThumb(index) {
        thumbs.forEach((thumb, i) => {
            thumb.classList.toggle("is-active", i === index);
        });
    }

    function updateCounter(index) {
        if (imageCounter) {
            imageCounter.textContent = `${index + 1} / ${totalImages}`;
        }
    }

    function goToImage(index) {

        if (totalImages === 0) return;

        currentImageIndex = (index + totalImages) % totalImages;

        const selectedThumb = thumbs[currentImageIndex];
        const imageUrl = selectedThumb.dataset.image;

        mainImage.classList.add("pd-fade-out");

        setTimeout(() => {

            mainImage.src = imageUrl;

            mainImage.onload = () => {
                mainImage.classList.remove("pd-fade-out");
            };

        }, 180);

        setActiveThumb(currentImageIndex);
        updateCounter(currentImageIndex);
    }

    thumbs.forEach((thumb) => {

        thumb.addEventListener("click", () => {

            const index = Number(thumb.dataset.index);

            goToImage(index);

        });

    });

    prevBtn?.addEventListener("click", () => {
        goToImage(currentImageIndex - 1);
    });

    nextBtn?.addEventListener("click", () => {
        goToImage(currentImageIndex + 1);
    });

    updateCounter(0);
    setActiveThumb(0);
/* ================= FULLSCREEN VIEWER (Updated to handle Reviews) ================= */

    const fullscreenBtn = document.getElementById("pdFullscreenBtn");
    const fullscreenOverlay = document.getElementById("pdFullscreenOverlay");
    const fullscreenImage = document.getElementById("pdFullscreenImage");
    const fullscreenClose = document.getElementById("pdFullscreenClose");
    
    // NEW: Grab all review images
    const reviewImages = document.querySelectorAll('.pdp-review-image img');

    // UPDATED: Now accepts image source and alt text as parameters
    function openFullscreen(imgSrc, imgAlt) {
        if (!fullscreenOverlay || !fullscreenImage || !imgSrc) return;

        fullscreenImage.src = imgSrc;
        fullscreenImage.alt = imgAlt || "Fullscreen Image";

        fullscreenOverlay.classList.remove("d-none");
        document.body.style.overflow = "hidden";
    }

    function closeFullscreen() {
        if (!fullscreenOverlay) return;

        fullscreenOverlay.classList.add("d-none");
        document.body.style.overflow = "";
    }

    // 1. Existing trigger for main product image
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener("click", function() {
            // Assuming mainImage is defined earlier in your script
            if (typeof mainImage !== 'undefined' && mainImage) {
                openFullscreen(mainImage.src, mainImage.alt);
            }
        });
    }

    // 2. NEW: Trigger for Review Images
    reviewImages.forEach(img => {
        img.addEventListener("click", function() {
            // Pass the clicked review image's src and alt
            openFullscreen(this.src, this.alt);
        });
    });

    // 3. Close Triggers
    if (fullscreenClose) {
        fullscreenClose.addEventListener("click", closeFullscreen);
    }

    if (fullscreenOverlay) {
        fullscreenOverlay.addEventListener("click", function (e) {
            // Close only when clicking the dark overlay, not the image itself.
            if (e.target === fullscreenOverlay) {
                closeFullscreen();
            }
        });
    }

    document.addEventListener("keydown", function (e) {
        // Only trigger close if the overlay is actually visible
        if (e.key === "Escape" && fullscreenOverlay && !fullscreenOverlay.classList.contains("d-none")) {
            closeFullscreen();
        }
    });
    /* ================= QUANTITY SELECTOR ================= */
    const qtyInput = document.getElementById('pdQtyInput');
    const qtyMinus = document.getElementById('pdQtyMinus');
    const qtyPlus = document.getElementById('pdQtyPlus');

    function pulseQtyBtn(btn) {
        if (!btn) return;
        btn.classList.add('pd-qty-pop');
        window.setTimeout(function () {
            btn.classList.remove('pd-qty-pop');
        }, 150);
    }

    function clampQty(value) {
        if (!qtyInput) return value;
        const min = parseInt(qtyInput.min, 10) || 1;
        const max = parseInt(qtyInput.max, 10) || 99;
        return Math.min(Math.max(value, min), max);
    }

    if (qtyMinus && qtyInput) {
        qtyMinus.addEventListener('click', function () {
            const current = parseInt(qtyInput.value, 10) || 1;
            qtyInput.value = clampQty(current - 1);
            pulseQtyBtn(qtyMinus);
        });
    }

    if (qtyPlus && qtyInput) {
        qtyPlus.addEventListener('click', function () {
            const current = parseInt(qtyInput.value, 10) || 1;
            qtyInput.value = clampQty(current + 1);
            pulseQtyBtn(qtyPlus);
        });
    }

    if (qtyInput) {
        qtyInput.addEventListener('change', function () {
            const current = parseInt(qtyInput.value, 10) || 1;
            qtyInput.value = clampQty(current);
        });
    }

    /* ================= SHARE POPOVER ================= */

    const shareBtn = document.getElementById('pdShareBtn');
    const sharePopover = document.getElementById('pdSharePopover');
    const copyLinkBtn = document.getElementById('pdCopyLinkBtn');

    const shareWrap = document.querySelector('.pd-share-wrap');

    const productUrl = window.location.href;

    const productName =
        shareWrap?.dataset.productName ||
        'Check out this product';

    const shareText = `Check out ${productName} on MarketSphere`;
    if (shareBtn && sharePopover) {

        shareBtn.addEventListener('click', function (e) {
            e.stopPropagation();

            const isOpen = sharePopover.classList.toggle('is-open');

            shareBtn.setAttribute(
                'aria-expanded',
                isOpen ? 'true' : 'false'
            );
        });

        document.addEventListener('click', function (e) {
            if (
                !sharePopover.contains(e.target) &&
                e.target !== shareBtn
            ) {
                sharePopover.classList.remove('is-open');
                shareBtn.setAttribute('aria-expanded', 'false');
            }
        });
    }


    /* ================= SOCIAL SHARING ================= */

    const facebookShareBtn = document.querySelector('.pd-share-facebook');
    const twitterShareBtn = document.querySelector('.pd-share-twitter');
    const whatsappShareBtn = document.querySelector('.pd-share-whatsapp');
    const linkedinShareBtn = document.querySelector('.pd-share-linkedin');

    function openShareWindow(url) {
        window.open(
            url,
            '_blank',
            'width=600,height=600,noopener,noreferrer'
        );
    }


    /* Facebook */

    if (facebookShareBtn) {
        facebookShareBtn.addEventListener('click', function (e) {
            e.preventDefault();

            const url = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(productUrl)}`;

            openShareWindow(url);
        });
    }


    /* X */

    if (twitterShareBtn) {
        twitterShareBtn.addEventListener('click', function (e) {
            e.preventDefault();

            const url =
                `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(productUrl)}`;

            openShareWindow(url);
        });
    }


    /* WhatsApp */

    if (whatsappShareBtn) {
        whatsappShareBtn.addEventListener('click', function (e) {
            e.preventDefault();

            const message = `${shareText}\n${productUrl}`;

            const url =
                `https://wa.me/?text=${encodeURIComponent(message)}`;

            openShareWindow(url);
        });
    }


    /* LinkedIn */

    if (linkedinShareBtn) {
        linkedinShareBtn.addEventListener('click', function (e) {
            e.preventDefault();

            const url =
                `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(productUrl)}`;

            openShareWindow(url);
        });
    }


    /* ================= COPY LINK ================= */

    if (copyLinkBtn) {

        copyLinkBtn.addEventListener('click', async function () {

            try {

                await navigator.clipboard.writeText(productUrl);

                const icon = copyLinkBtn.querySelector('i');

                if (!icon) return;

                const originalClass = 'bi-link-45deg';

                icon.classList.remove(originalClass);
                icon.classList.add('bi-check2');

                window.setTimeout(function () {
                    icon.classList.remove('bi-check2');
                    icon.classList.add(originalClass);
                }, 1500);

            } catch (error) {

                console.error('Failed to copy product link:', error);

            }
        });
    }
    /* ================= ADD TO CART FEEDBACK ================= */
    function bindAddToCartFeedback(btn) {
        if (!btn) return;

        const originalHTML = btn.innerHTML;

        btn.addEventListener("click", async function () {
            if (btn.disabled) return;

            btn.disabled = true;

            try {
                const addUrl = new URL(btn.dataset.addUrl, window.location.origin);
                const quantity = document.getElementById('pdQtyInput');
                if (quantity) addUrl.searchParams.set('quantity', quantity.value || '1');
                const response = await fetch(addUrl.toString(), {
                    method: "GET",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });

                const data = await response.json();

                if (data.success) {
                    btn.classList.add("pd-btn-pulse");
                    btn.innerHTML = '<i class="bi bi-check2"></i> Added';
                    document.getElementById('pdBuyNowBtn').dataset.cartItemId = data.cart_item_id; // Update cart item ID for Buy Now button
                    // Update navbar cart counter
                    const counter = document.querySelector("#cartCounter");
                    if (counter) {
                        counter.textContent = data.cart_count;
                    }
                } else {
                    alert("Unable to add product to cart.");
                }
            } catch (error) {
                console.error("Cart Error:", error);
                alert("Something went wrong. Please try again.");
            }

            setTimeout(() => {
                btn.innerHTML = originalHTML;
                btn.classList.remove("pd-btn-pulse");
                btn.disabled = false;
            }, 1500);

        });
    }

    bindAddToCartFeedback(document.getElementById('pdAddToCartBtn'));
    bindAddToCartFeedback(document.getElementById('pdMobileAddToCartBtn'));

    document.querySelectorAll('.add-to-cart-btn:not([disabled])').forEach(function (btn) {
        const originalHTML = btn.innerHTML;

        btn.addEventListener('click', function () {
            btn.innerHTML = '<i class="bi bi-check2"></i> Added';
            btn.disabled = true;

            window.setTimeout(function () {
                btn.innerHTML = originalHTML;
                btn.disabled = false;
            }, 1500);
        });
    });

    /* ================= BUY NOW ================= */

    ['pdBuyNowBtn', 'pdMobileBuyNowBtn'].forEach(function (id) {

        const btn = document.getElementById(id);
        if (!btn) return;

        btn.addEventListener('click', async function () {

            if (btn.disabled) return;

            const cartItemId = btn.dataset.cartItemId;

            // Product is already in the cart.
            if (cartItemId) {
                btn.classList.add('pd-btn-pulse');
                window.location.href = `/order/checkout/item/${cartItemId}/`;
                return;
            }

            // Product is not in the cart yet.
            const addToCartBtn = document.getElementById('pdAddToCartBtn');

            if (!addToCartBtn) return;

            btn.disabled = true;
            btn.classList.add('pd-btn-pulse');

            try {

                const addUrl = new URL(
                    addToCartBtn.dataset.addUrl,
                    window.location.origin
                );

                const quantity = document.getElementById('pdQtyInput');

                if (quantity) {
                    addUrl.searchParams.set(
                        'quantity',
                        quantity.value || '1'
                    );
                }

                const response = await fetch(addUrl.toString(), {
                    method: "GET",
                    headers: {
                        "X-CSRFToken": getCookie("csrftoken"),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });

                const data = await response.json();

                if (!data.success) {
                    alert("Unable to add product to cart.");
                    return;
                }

                // Store the newly created/found CartItem ID.
                btn.dataset.cartItemId = data.cart_item_id;

                // Update navbar cart counter.
                const counter = document.querySelector("#cartCounter");

                if (counter) {
                    counter.textContent = data.cart_count;
                }

                // Now proceed directly to checkout for this item.
                window.location.href =
                    `/order/checkout/item/${data.cart_item_id}/`;

            } catch (error) {

                console.error("Buy Now Error:", error);
                alert("Something went wrong. Please try again.");

            } finally {

                btn.disabled = false;
            }
        });
    });

    /* ================= HELPFUL / REPORT REVIEW ACTIONS ================= */
    document.querySelectorAll('.pd-helpful-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const countEl = btn.querySelector('span');
            if (!countEl) return;

            const isActive = btn.classList.toggle('is-active');
            let count = parseInt(countEl.textContent, 10) || 0;
            count = isActive ? count + 1 : Math.max(count - 1, 0);
            countEl.textContent = String(count);
        });
    });

    document.querySelectorAll('.pd-report-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const originalHTML = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-flag-fill"></i> Reported';
            btn.disabled = true;

            window.setTimeout(function () {
                btn.innerHTML = originalHTML;
                btn.disabled = false;
            }, 2000);
        });
    });

    /* ================= FREQUENTLY BOUGHT TOGETHER TOTAL ================= */
    const fbtCheckboxes = Array.from(document.querySelectorAll('.pd-fbt-check .form-check-input'));
    const fbtTotalEl = document.getElementById('pdFbtTotal');
    const fbtAddAllBtn = document.getElementById('pdFbtAddAll');

    function formatFbtPrice(value) {
        return 'Rs. ' + Number(value || 0).toLocaleString('en-IN');
    }

    function recalcFbtTotal() {
        if (!fbtTotalEl) return;

        let total = 0;
        fbtCheckboxes.forEach(function (checkbox) {
            if (!checkbox.checked) return;
            const priceEl = checkbox.closest('.pd-fbt-item').querySelector('.pd-fbt-price');
            if (priceEl) {
                total += parseInt(priceEl.dataset.price, 10) || 0;
            }
        });

        fbtTotalEl.textContent = formatFbtPrice(total);
    }

    fbtCheckboxes.forEach(function (checkbox) {
        checkbox.addEventListener('change', recalcFbtTotal);
    });

    recalcFbtTotal();

    async function addFrequentlyBoughtTogether(btn) {
        if (btn.disabled) return;

        const selectedProducts = [];

        document
            .querySelectorAll(".form-check-input:checked")
            .forEach((checkbox) => {
                selectedProducts.push(checkbox.dataset.productId);
            });

        if (!selectedProducts.length) {
            alert("Please select at least one product.");
            return;
        }

        btn.disabled = true;

        try {
            const response = await fetch(btn.dataset.addUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({
                    products: selectedProducts,
                }),
            });

            const data = await response.json();

            if (data.success) {
                const counter = document.querySelector("#cartCounter");

                if (counter) {
                    counter.textContent = data.cart_count;
                }

                btn.innerHTML = '<i class="bi bi-check2"></i> Added';


                setTimeout(() => {
                    btn.innerHTML =
                        '<i class="bi bi-cart-plus"></i> Add All to Cart';
                    btn.disabled = false;
                }, 1500);
            } else {
                alert(data.message);
                btn.disabled = false;
            }
        } catch (error) {
            console.error(error);
            alert("Something went wrong.");
            btn.disabled = false;
        }
    }

    document
        .getElementById("pdFbtAddAll")
        ?.addEventListener("click", function () {
            addFrequentlyBoughtTogether(this);
        });
    /* ================= NEWSLETTER VALIDATION ================= */
    const newsletterForm = document.getElementById('newsletterForm');
    const newsletterEmail = document.getElementById('newsletterEmail');
    const newsletterFeedback = document.getElementById('newsletterFeedback');

    if (newsletterForm) {
        newsletterForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const email = newsletterEmail.value.trim();
            const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

            if (!emailPattern.test(email)) {
                newsletterFeedback.textContent = 'Please enter a valid email address.';
                newsletterFeedback.classList.remove('success');
                newsletterFeedback.classList.add('error');
                newsletterEmail.classList.add('is-invalid');
                return;
            }

            newsletterEmail.classList.remove('is-invalid');
            newsletterFeedback.textContent = 'Thanks for subscribing! Check your inbox soon.';
            newsletterFeedback.classList.remove('error');
            newsletterFeedback.classList.add('success');
            newsletterForm.reset();
        });
    }

    /* ================= RECENTLY VIEWED SLIDER ================= */
    const recentSlider = document.getElementById('pdRecentSlider');
    const recentPrevBtn = document.getElementById('pdRecentPrev');
    const recentNextBtn = document.getElementById('pdRecentNext');

    function scrollRecentSlider(direction) {
        if (!recentSlider) return;
        const scrollAmount = recentSlider.clientWidth * 0.8 * direction;
        recentSlider.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }

    if (recentPrevBtn) {
        recentPrevBtn.addEventListener('click', function () {
            scrollRecentSlider(-1);
        });
    }

    if (recentNextBtn) {
        recentNextBtn.addEventListener('click', function () {
            scrollRecentSlider(1);
        });
    }

    /* ================= STICKY MOBILE PURCHASE BAR ================= */
    const mobileStickyBar = document.getElementById('pdMobileStickyBar');
    const purchaseControls = document.querySelector('.pd-purchase-controls');

    function toggleMobileStickyBar() {
        if (!mobileStickyBar || !purchaseControls || window.innerWidth > 767.98) {
            if (mobileStickyBar) mobileStickyBar.classList.remove('is-visible');
            return;
        }

        const rect = purchaseControls.getBoundingClientRect();
        const isPastControls = rect.bottom < 0;

        mobileStickyBar.classList.toggle('is-visible', isPastControls);
    }

    window.addEventListener('scroll', toggleMobileStickyBar);
    window.addEventListener('resize', toggleMobileStickyBar);
    toggleMobileStickyBar();

    /* ================= SCROLL REVEAL ANIMATIONS ================= */
    const revealTargets = document.querySelectorAll(
        '.pd-feature-card, .why-us-card, .product-card, .pd-review-card, .pd-seller-card, .newsletter-inner'
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
        }, { threshold: 0.12 });

        revealTargets.forEach(function (el) {
            observer.observe(el);
        });
    } else {
        revealTargets.forEach(function (el) {
            el.classList.add('is-visible');
        });
    }
});
document.addEventListener('DOMContentLoaded', function () {
    // Helper function to get the CSRF token from Django's cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const helpfulButtons = document.querySelectorAll('.pdp-review-helpful');

    helpfulButtons.forEach(button => {
        button.addEventListener('click', function () {
            const reviewId = this.getAttribute('data-review-id');
            const buttonElement = this;
            const countSpan = this.querySelector('span[data-count]');
            const icon = this.querySelector('i');

            // Prevent double clicking while processing
            if (buttonElement.disabled) return;
            buttonElement.disabled = true;

            fetch(`/reviews/${reviewId}/helpful/`, { // Ensure this matches your urls.py path
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Update the count number
                    countSpan.innerText = data.new_count;
                    countSpan.setAttribute('data-count', data.new_count);
                    
                    // Change the icon from outline to filled
                    icon.classList.remove('bi-hand-thumbs-up');
                    icon.classList.add('bi-hand-thumbs-up-fill');
                    icon.style.color = 'var(--od-selection-active-color, #a06e40)'; // Optional: highlight color
                    
                } else {
                    // Show error message (e.g., "Cannot mark your own review" or "Not logged in")
                    alert(data.message);
                    buttonElement.disabled = false; // Re-enable if it failed
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert("An unexpected error occurred.");
                buttonElement.disabled = false;
            });
        });
    });
});