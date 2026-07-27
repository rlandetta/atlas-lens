const deleteDialog = document.getElementById("delete-coverage-dialog");
const deleteForm = document.getElementById("delete-coverage-form");
const deleteCoverageName = document.getElementById("delete-coverage-name");
const cancelDeleteButton = document.getElementById("cancel-delete-coverage-button");
const deleteCoverageButtons = document.querySelectorAll("[data-delete-coverage-button]");

let deleteTriggerButton = null;

if (
    deleteDialog
    && deleteForm
    && deleteCoverageName
    && cancelDeleteButton
    && deleteCoverageButtons.length > 0
) {
    const openDeleteDialog = (button) => {
        deleteTriggerButton = button;
        deleteForm.action = button.dataset.deleteAction;
        deleteCoverageName.textContent = button.dataset.deleteTitle;

        if (typeof deleteDialog.showModal === "function") {
            deleteDialog.showModal();
        } else {
            deleteDialog.setAttribute("open", "open");
        }

        cancelDeleteButton.focus();
    };

    const closeDeleteDialog = () => {
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

    deleteDialog.addEventListener("close", () => {
        if (deleteTriggerButton) {
            deleteTriggerButton.focus();
        }
    });
}
