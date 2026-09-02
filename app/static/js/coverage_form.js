const coverageForms = document.querySelectorAll(".coverage-form, .edit-dialog-form");

coverageForms.forEach((form) => {
    const localityTypeField = form.querySelector('[name="locality_type"]');
    const adminAreaFields = form.querySelectorAll("[data-admin-area-field]");

    const syncAdminAreaVisibility = () => {
        const shouldShow = localityTypeField && localityTypeField.value === "locality";
        adminAreaFields.forEach((field) => {
            field.hidden = !shouldShow;
        });
    };

    localityTypeField?.addEventListener("change", syncAdminAreaVisibility);
    syncAdminAreaVisibility();
});
