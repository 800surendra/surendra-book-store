document.addEventListener("DOMContentLoaded", () => {
    const header = document.querySelector(".site-header");
    const mobileMenuButton = document.querySelector(".mobile-menu-button");
    const navigation = document.querySelector(".nav-links");
    const navigationLinks = document.querySelectorAll(".nav-links a");

    const updateHeader = () => {
        if (header) {
            header.classList.toggle("is-scrolled", window.scrollY > 24);
        }
    };

    window.addEventListener("scroll", updateHeader, { passive: true });
    updateHeader();

    if (mobileMenuButton && navigation) {
        mobileMenuButton.addEventListener("click", () => {
            const isOpen = navigation.classList.toggle("is-open");

            mobileMenuButton.setAttribute("aria-expanded", String(isOpen));
            document.body.classList.toggle("menu-open", isOpen);
        });

        navigationLinks.forEach((link) => {
            link.addEventListener("click", () => {
                navigation.classList.remove("is-open");
                mobileMenuButton.setAttribute("aria-expanded", "false");
                document.body.classList.remove("menu-open");
            });
        });
    }

    const mainProductImage = document.querySelector(".product-main-image img");
    const thumbnailButtons = document.querySelectorAll(".thumbnail-button");

    thumbnailButtons.forEach((thumbnailButton) => {
        thumbnailButton.addEventListener("click", () => {
            const thumbnailImage = thumbnailButton.querySelector("img");

            if (!mainProductImage || !thumbnailImage) {
                return;
            }

            mainProductImage.src = thumbnailImage.src;
            mainProductImage.alt = thumbnailImage.alt;

            thumbnailButtons.forEach((button) => {
                button.classList.remove("is-active");
            });

            thumbnailButton.classList.add("is-active");
        });
    });

    const quantitySelector = document.querySelector(".quantity-selector");

    if (quantitySelector) {
        const decreaseButton = quantitySelector.querySelector(
            'button[aria-label="Decrease quantity"]'
        );
        const increaseButton = quantitySelector.querySelector(
            'button[aria-label="Increase quantity"]'
        );
        const quantityDisplay = quantitySelector.querySelector("span");
        let quantity = 1;

        const renderQuantity = () => {
            quantityDisplay.textContent = quantity;
            quantitySelector.closest("form").querySelector(".quantity-input").value = quantity;
            decreaseButton.disabled = quantity === 1;
            decreaseButton.setAttribute(
                "aria-disabled",
                String(quantity === 1)
            );
        };

        decreaseButton.addEventListener("click", () => {
            if (quantity > 1) {
                quantity -= 1;
                renderQuantity();
            }
        });

        increaseButton.addEventListener("click", () => {
            quantity += 1;
            renderQuantity();
        });

        renderQuantity();
    }
});
    const deliveryForm = document.querySelector("#delivery-form");
    const pincodeInput = document.querySelector("#pincode");
    const deliveryResult = document.querySelector("#delivery-result");

    if (deliveryForm && pincodeInput && deliveryResult) {
        deliveryForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const pincode = pincodeInput.value.trim();
            deliveryResult.textContent = "Checking delivery availability...";
            deliveryResult.className = "delivery-result";

            try {
                const response = await fetch(
                    `/api/delivery/check/?pincode=${encodeURIComponent(pincode)}`
                );
                const data = await response.json();

                deliveryResult.textContent = data.message;
                deliveryResult.classList.add(
                    data.available ? "is-available" : "is-unavailable"
                );
            } catch {
                deliveryResult.textContent =
                    "Unable to check delivery right now. Please try again.";
                deliveryResult.classList.add("is-unavailable");
            }
        });
    }