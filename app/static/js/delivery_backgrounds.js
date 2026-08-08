(() => {
    const startDeliveryBackgrounds = () => {
        const page = document.querySelector("[data-delivery-backgrounds]");
        const layers = Array.from(document.querySelectorAll("[data-delivery-background-layer]"));
        if (!page || layers.length < 2) {
            return;
        }

        let backgrounds = [];
        try {
            backgrounds = JSON.parse(page.dataset.deliveryBackgrounds || "[]");
        } catch (error) {
            backgrounds = [];
        }
        const mobile = window.matchMedia("(max-width: 720px)").matches;
        backgrounds = backgrounds
            .map((item) => item && item.url)
            .filter(Boolean)
            .slice(0, mobile ? 1 : 4);
        if (!backgrounds.length) {
            return;
        }

        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        let activeIndex = 0;
        let layerIndex = 0;

        const loadLayer = (layer, url, activate) => {
            const image = new Image();
            image.decoding = "async";
            image.onload = () => {
                layer.style.backgroundImage = `url("${url}")`;
                layer.classList.add("is-loaded");
                if (activate) {
                    layer.classList.add("is-active");
                }
            };
            image.onerror = () => {};
            image.src = url;
        };

        loadLayer(layers[0], backgrounds[0], true);
        if (reducedMotion || backgrounds.length === 1) {
            return;
        }

        window.setInterval(() => {
            activeIndex = (activeIndex + 1) % backgrounds.length;
            layerIndex = layerIndex === 0 ? 1 : 0;
            const nextLayer = layers[layerIndex];
            const previousLayer = layers[layerIndex === 0 ? 1 : 0];
            loadLayer(nextLayer, backgrounds[activeIndex], true);
            previousLayer.classList.remove("is-active");
        }, 9000);
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", startDeliveryBackgrounds, { once: true });
    } else {
        startDeliveryBackgrounds();
    }
})();
