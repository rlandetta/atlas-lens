const tabButtons = document.querySelectorAll("[data-tab-button]");
const tabPanels = document.querySelectorAll("[data-tab-panel]");

if (tabButtons.length > 0 && tabPanels.length > 0) {
    const activateTab = (targetId) => {
        tabButtons.forEach((button) => {
            const isActive = button.dataset.tabTarget === targetId;
            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-selected", String(isActive));
        });

        tabPanels.forEach((panel) => {
            const isActive = panel.id === targetId;
            panel.classList.toggle("is-active", isActive);
            panel.hidden = !isActive;
        });
    };

    tabButtons.forEach((button) => {
        button.addEventListener("click", () => {
            activateTab(button.dataset.tabTarget);
        });
    });
}
