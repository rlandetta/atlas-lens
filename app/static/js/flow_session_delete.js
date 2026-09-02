const deleteDialog = document.getElementById("flow-session-delete-dialog");
const deleteButtons = document.querySelectorAll(".flow-session-delete-button");

if (deleteDialog && deleteButtons.length) {
    const title = document.getElementById("flow-session-delete-title");
    const loadingPanel = deleteDialog.querySelector("[data-flow-delete-loading]");
    const freePanel = deleteDialog.querySelector("[data-flow-delete-free]");
    const blockedPanel = deleteDialog.querySelector("[data-flow-delete-blocked]");
    const freeSummary = deleteDialog.querySelector("[data-flow-delete-free-summary]");
    const blockedSummary = deleteDialog.querySelector("[data-flow-delete-blocked-summary]");
    const coveragePanel = deleteDialog.querySelector("[data-flow-delete-coverages-panel]");
    const coverageList = deleteDialog.querySelector("[data-flow-delete-coverages]");
    const confirmCheckbox = deleteDialog.querySelector("[data-flow-delete-confirm-checkbox]");
    const submitButton = deleteDialog.querySelector("[data-flow-delete-submit]");
    const cancelButton = deleteDialog.querySelector("[data-flow-delete-cancel]");
    const errorMessage = deleteDialog.querySelector("[data-flow-delete-error]");
    let activeDeleteUrl = "";

    const plural = (count, singular, pluralText) => count === 1 ? singular : pluralText;

    const setError = (message) => {
        if (!errorMessage) {
            return;
        }
        errorMessage.textContent = message;
        errorMessage.hidden = !message;
    };

    const setMode = (mode) => {
        if (loadingPanel) {
            loadingPanel.hidden = mode !== "loading";
        }
        if (freePanel) {
            freePanel.hidden = mode !== "free";
        }
        if (blockedPanel) {
            blockedPanel.hidden = mode !== "blocked";
        }
        if (coveragePanel) {
            coveragePanel.hidden = true;
        }
        if (submitButton) {
            submitButton.hidden = mode !== "free";
            submitButton.disabled = true;
        }
        if (confirmCheckbox) {
            confirmCheckbox.checked = false;
        }
        setError("");
    };

    const renderCoverages = (coverages) => {
        if (!coverageList) {
            return;
        }
        coverageList.replaceChildren();
        if (coveragePanel) {
            coveragePanel.hidden = coverages.length === 0;
        }
        coverages.forEach((coverage) => {
            const item = document.createElement("article");
            item.className = "flow-session-delete-coverage";

            const copy = document.createElement("div");
            const name = document.createElement("strong");
            name.textContent = coverage.title || coverage.coverage_id || "Cobertura";
            const count = document.createElement("span");
            const photoCount = Number(coverage.photo_count || 0);
            count.textContent = `${photoCount} ${plural(photoCount, "fotografía utilizada", "fotografías utilizadas")}`;
            copy.append(name, count);

            const link = document.createElement("a");
            link.className = "secondary-button compact-action";
            link.href = coverage.url;
            link.textContent = "Abrir cobertura";

            item.append(copy, link);
            coverageList.append(item);
        });
    };

    const renderCheck = (payload) => {
        const totalPhotos = Number(payload.total_photos || 0);
        const usedPhotos = Number(payload.used_photos || 0);
        if (payload.ok) {
            if (title) {
                title.textContent = "Eliminar sesión de FLOW";
            }
            if (freeSummary) {
                freeSummary.textContent = `Esta sesión contiene ${totalPhotos} ${plural(totalPhotos, "fotografía", "fotografías")}. Al eliminarla se borrarán la sesión y sus fotografías originales almacenadas en FLOW.`;
            }
            setMode("free");
            return;
        }

        if (payload.reason && payload.reason !== "photos_in_use") {
            if (title) {
                title.textContent = payload.reason === "session_active" ? "Esta sesión no puede eliminarse" : "No se pudo eliminar la sesión";
            }
            setMode("blocked");
            if (blockedSummary) {
                blockedSummary.textContent = payload.message || "La sesión no puede eliminarse en este momento.";
            }
            renderCoverages([]);
            return;
        }

        if (title) {
            title.textContent = "No se puede eliminar la sesión";
        }
        if (blockedSummary) {
            blockedSummary.textContent = `${usedPhotos} de las ${totalPhotos} ${plural(totalPhotos, "fotografías está", "fotografías están")} siendo utilizadas por coberturas.`;
        }
        setMode("blocked");
        renderCoverages(payload.coverages || []);
    };

    confirmCheckbox?.addEventListener("change", () => {
        if (submitButton) {
            submitButton.disabled = !confirmCheckbox.checked;
        }
    });

    cancelButton?.addEventListener("click", () => {
        deleteDialog.close();
    });

    submitButton?.addEventListener("click", async () => {
        if (!activeDeleteUrl || submitButton.disabled) {
            return;
        }
        submitButton.disabled = true;
        setError("");
        try {
            const response = await fetch(activeDeleteUrl, {
                method: "POST",
                headers: {
                    "Accept": "application/json",
                },
            });
            const payload = await response.json();
            if (response.status === 409) {
                renderCheck(payload);
                return;
            }
            if (!response.ok || !payload.ok) {
                setError("No se pudo eliminar la sesión. Inténtelo nuevamente.");
                submitButton.disabled = false;
                return;
            }
            window.location.reload();
        } catch (error) {
            setError("No se pudo eliminar la sesión. Revise la conexión e inténtelo nuevamente.");
            submitButton.disabled = false;
        }
    });

    deleteButtons.forEach((button) => {
        button.addEventListener("click", async () => {
            activeDeleteUrl = button.dataset.deleteUrl || "";
            setMode("loading");
            if (title) {
                title.textContent = "Eliminar sesión de FLOW";
            }
            deleteDialog.showModal();
            try {
                const response = await fetch(button.dataset.deleteCheckUrl || "", {
                    headers: {
                        "Accept": "application/json",
                    },
                });
                if (!response.ok) {
                    setError("No se pudo revisar la sesión solicitada.");
                    setMode("blocked");
                    return;
                }
                renderCheck(await response.json());
            } catch (error) {
                setError("No se pudo revisar la sesión solicitada.");
                setMode("blocked");
            }
        });
    });
}
