document.addEventListener("DOMContentLoaded", () => {
    const scheduleFields = document.querySelector("[data-dispatch-schedule-fields]");
    const modeInputs = document.querySelectorAll('input[name="mode"]');
    const syncScheduleFields = () => {
        if (!scheduleFields) {
            return;
        }
        const selectedMode = document.querySelector('input[name="mode"]:checked');
        scheduleFields.hidden = !selectedMode || selectedMode.value !== "schedule";
    };
    modeInputs.forEach((input) => input.addEventListener("change", syncScheduleFields));
    syncScheduleFields();

    const recipientList = document.querySelector("[data-recipient-list]");
    const addRecipientButton = document.querySelector("[data-recipient-add]");

    const sanitizeRecipientInput = (input) => {
        input.value = input.value.replaceAll("|", "");
    };

    const renumberRecipients = () => {
        if (!recipientList) {
            return;
        }
        const rows = recipientList.querySelectorAll("[data-recipient-row]");
        rows.forEach((row, index) => {
            const rowNumber = index + 1;
            const nameInput = row.querySelector("[data-recipient-name]");
            const emailInput = row.querySelector("[data-recipient-email]");
            const nameLabel = nameInput ? row.querySelector(`label[for="${nameInput.id}"]`) : null;
            const emailLabel = emailInput ? row.querySelector(`label[for="${emailInput.id}"]`) : null;
            if (nameInput) {
                nameInput.id = `recipient_name_${rowNumber}`;
                if (nameLabel) {
                    nameLabel.setAttribute("for", nameInput.id);
                }
            }
            if (emailInput) {
                emailInput.id = `recipient_email_${rowNumber}`;
                if (emailLabel) {
                    emailLabel.setAttribute("for", emailInput.id);
                }
            }
        });
    };

    const attachRecipientEvents = (row) => {
        row.querySelectorAll("input").forEach((input) => {
            input.addEventListener("input", () => sanitizeRecipientInput(input));
        });
        const removeButton = row.querySelector("[data-recipient-remove]");
        if (removeButton) {
            removeButton.addEventListener("click", () => {
                const rows = recipientList.querySelectorAll("[data-recipient-row]");
                if (rows.length === 1) {
                    row.querySelectorAll("input").forEach((input) => {
                        input.value = "";
                    });
                    return;
                }
                row.remove();
                renumberRecipients();
            });
        }
    };

    if (recipientList) {
        recipientList.querySelectorAll("[data-recipient-row]").forEach(attachRecipientEvents);
    }

    if (addRecipientButton && recipientList) {
        addRecipientButton.addEventListener("click", () => {
            const rows = recipientList.querySelectorAll("[data-recipient-row]");
            const sourceRow = rows[rows.length - 1];
            const newRow = sourceRow.cloneNode(true);
            newRow.querySelectorAll("input").forEach((input) => {
                input.value = "";
            });
            newRow.querySelectorAll(".field-error").forEach((error) => error.remove());
            recipientList.appendChild(newRow);
            attachRecipientEvents(newRow);
            renumberRecipients();
        });
    }
});
