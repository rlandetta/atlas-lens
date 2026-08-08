(() => {
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
    backgrounds = backgrounds
        .map((item) => item && item.url)
        .filter(Boolean)
        .slice(0, window.matchMedia("(max-width: 720px)").matches ? 2 : 4);
    if (!backgrounds.length) {
        return;
    }

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let activeIndex = 0;
    let layerIndex = 0;

    const setLayerImage = (layer, url) => {
        const image = new Image();
        image.decoding = "async";
        image.onload = () => {
            layer.style.backgroundImage = `url("${url}")`;
            layer.classList.add("is-loaded");
        };
        image.onerror = () => {};
        image.src = url;
    };

    window.setTimeout(() => {
        setLayerImage(layers[0], backgrounds[0]);
        if (reducedMotion || backgrounds.length === 1) {
            return;
        }
        window.setInterval(() => {
            activeIndex = (activeIndex + 1) % backgrounds.length;
            layerIndex = layerIndex === 0 ? 1 : 0;
            const nextLayer = layers[layerIndex];
            const previousLayer = layers[layerIndex === 0 ? 1 : 0];
            setLayerImage(nextLayer, backgrounds[activeIndex]);
            nextLayer.classList.add("is-active");
            previousLayer.classList.remove("is-active");
        }, 9000);
    }, 250);
})();
