const deleteDialog = document.getElementById("delete-coverage-dialog");
const deleteForm = document.getElementById("delete-coverage-form");
const deleteCoverageName = document.getElementById("delete-coverage-name");
const deleteCoverageId = document.getElementById("delete-coverage-id");
const deleteDispatchWarning = document.getElementById("delete-coverage-dispatch-warning");
const deleteCoverageError = document.getElementById("delete-coverage-error");
const confirmCoverageIdField = document.getElementById("confirm-coverage-id-field");
const preserveFlowOriginalsField = document.getElementById("preserve-flow-originals-field");
const cancelDeleteButton = document.getElementById("cancel-delete-coverage-button");
const confirmDeleteButton = deleteForm ? deleteForm.querySelector(".danger-confirm-button") : null;
const deleteCoverageButtons = document.querySelectorAll("[data-delete-coverage-button]");

let deleteTriggerButton = null;

if (
    deleteDialog
    && deleteForm
    && deleteCoverageName
    && deleteCoverageId
    && deleteDispatchWarning
    && deleteCoverageError
    && confirmCoverageIdField
    && preserveFlowOriginalsField
    && cancelDeleteButton
    && confirmDeleteButton
    && deleteCoverageButtons.length > 0
) {
    const setDeleteError = (message = "") => {
        deleteCoverageError.textContent = message;
        deleteCoverageError.hidden = !message;
    };

    const setSubmitting = (isSubmitting) => {
        confirmDeleteButton.disabled = isSubmitting;
        cancelDeleteButton.disabled = isSubmitting;
        confirmCoverageIdField.disabled = isSubmitting;
        preserveFlowOriginalsField.disabled = isSubmitting;
        confirmDeleteButton.textContent = isSubmitting ? "Eliminando..." : "Eliminar cobertura";
    };

    const openDeleteDialog = (button) => {
        deleteTriggerButton = button;
        deleteForm.action = button.dataset.deleteAction;
        const coverageId = button.dataset.deleteCoverageId || "";
        const dispatchCount = Number.parseInt(button.dataset.deleteDispatchCount || "0", 10);
        deleteCoverageName.textContent = button.dataset.deleteTitle || "Cobertura sin título";
        deleteCoverageId.textContent = coverageId;
        confirmCoverageIdField.value = "";
        confirmCoverageIdField.placeholder = coverageId;
        preserveFlowOriginalsField.checked = false;
        setDeleteError("");
        setSubmitting(false);
        if (dispatchCount > 0) {
            deleteDispatchWarning.textContent = `Hay ${dispatchCount} despacho(s) relacionado(s). No se eliminarán ni se modificarán.`;
            deleteDispatchWarning.hidden = false;
        } else {
            deleteDispatchWarning.textContent = "";
            deleteDispatchWarning.hidden = true;
        }

        if (typeof deleteDialog.showModal === "function") {
            deleteDialog.showModal();
        } else {
            deleteDialog.setAttribute("open", "open");
        }

        confirmCoverageIdField.focus();
    };

    const closeDeleteDialog = () => {
        confirmCoverageIdField.value = "";
        preserveFlowOriginalsField.checked = false;
        setDeleteError("");
        setSubmitting(false);
        if (typeof deleteDialog.close === "function") {
            deleteDialog.close();
        } else {
            deleteDialog.removeAttribute("open");
        }
    };

    deleteCoverageButtons.forEach((button) => {
        button.addEventListener("click", () => {
            openDeleteDialog(button);
        });
    });

    cancelDeleteButton.addEventListener("click", closeDeleteDialog);

    deleteForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(deleteForm);
        setDeleteError("");
        setSubmitting(true);

        try {
            const response = await fetch(deleteForm.action, {
                method: "POST",
                body: formData,
                headers: {
                    "X-Requested-With": "fetch"
                },
                credentials: "same-origin",
                redirect: "follow"
            });

            if (response.ok) {
                window.location.assign(response.url || window.location.href);
                return;
            }

            const message = await response.text();
            setDeleteError(message || "No fue posible eliminar la cobertura. Inténtelo nuevamente.");
        } catch (error) {
            setDeleteError("No fue posible eliminar la cobertura. Inténtelo nuevamente.");
        } finally {
            setSubmitting(false);
        }
    });

    deleteDialog.addEventListener("close", () => {
        if (deleteTriggerButton) {
            deleteTriggerButton.focus();
        }
    });
}
