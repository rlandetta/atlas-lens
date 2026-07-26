const editDialog = document.getElementById("edit-coverage-dialog");
const openEditDialogButton = document.getElementById("open-edit-dialog-button");
const closeEditDialogButton = document.getElementById("close-edit-dialog-button");

if (editDialog && openEditDialogButton && closeEditDialogButton) {
    const openDialog = () => {
        if (typeof editDialog.showModal === "function") {
            editDialog.showModal();
            return;
        }

        editDialog.setAttribute("open", "open");
    };

    const closeDialog = () => {
        if (typeof editDialog.close === "function") {
            editDialog.close();
            return;
        }

        editDialog.removeAttribute("open");
    };

    openEditDialogButton.addEventListener("click", openDialog);
    closeEditDialogButton.addEventListener("click", closeDialog);

    if (editDialog.dataset.openOnLoad === "true" && !editDialog.open) {
        openDialog();
    }
}
