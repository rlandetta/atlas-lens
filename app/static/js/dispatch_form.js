document.addEventListener("DOMContentLoaded", () => {
    const fallbackTimezone = "America/Guayaquil";
    const scheduledFields = document.querySelector("[data-scheduled-delivery-fields]");
    const modeInputs = document.querySelectorAll('input[name="mode"]');
    const timezoneSelect = document.getElementById("timezone");
    const scheduledDate = document.getElementById("scheduled_date");
    const scheduledTime = document.getElementById("scheduled_time");
    const deliveryModeSummary = document.querySelector("[data-delivery-mode-summary]");
    const formSummary = document.querySelector("[data-dispatch-form-summary]");
    const contentSummary = document.querySelector("[data-content-summary]");
    const submitButton = document.querySelector("[data-dispatch-submit-button]");
    const recipientList = document.querySelector("[data-recipient-list]");
    const addRecipientButton = document.querySelector("[data-recipient-add]");
    const photoInputs = document.querySelectorAll('input[name="photo_ids"]');
    const docxInput = document.getElementById("include_caption_docx");
    const deliveryMethodSelect = document.getElementById("delivery_method");
    const smtpChannelSelect = document.querySelector("[data-smtp-channel-select]");
    const deliveryChannelName = document.querySelector("[data-delivery-channel-name]");
    const linkOnlyHelp = document.querySelector("[data-link-only-help]");
    const smtpHelp = document.querySelector("[data-smtp-help]");

    const getSelectedMode = () => {
        const selectedMode = document.querySelector('input[name="mode"]:checked');
        return selectedMode ? selectedMode.value : "draft";
    };

    const ensureTimezoneOption = (timeZone) => {
        if (!timezoneSelect || !timeZone) {
            return;
        }
        const exists = Array.from(timezoneSelect.options).some((option) => option.value === timeZone);
        if (!exists) {
            timezoneSelect.add(new Option(timeZone, timeZone));
        }
    };

    const detectTimezone = () => {
        let detected = fallbackTimezone;
        try {
            detected = Intl.DateTimeFormat().resolvedOptions().timeZone || fallbackTimezone;
        } catch (error) {
            detected = fallbackTimezone;
        }
        ensureTimezoneOption(detected);
        const preserveTimezone = timezoneSelect && timezoneSelect.dataset.preserveTimezone === "true";
        if (timezoneSelect && !preserveTimezone && (!timezoneSelect.value || timezoneSelect.value === fallbackTimezone)) {
            timezoneSelect.value = detected;
        }
    };

    const setElementVisibility = (element, visible) => {
        if (!element) {
            return;
        }
        element.hidden = !visible;
        element.setAttribute("aria-hidden", visible ? "false" : "true");
    };

    const setScheduleInputsEnabled = (enabled) => {
        [scheduledDate, scheduledTime, timezoneSelect].forEach((input) => {
            if (input) {
                input.disabled = !enabled;
            }
        });
    };

    const countRecipients = () => {
        if (!recipientList) {
            return 0;
        }
        return Array.from(recipientList.querySelectorAll("[data-recipient-row]")).filter((row) => {
            const name = row.querySelector("[data-recipient-name]");
            const email = row.querySelector("[data-recipient-email]");
            return (name && name.value.trim()) || (email && email.value.trim());
        }).length;
    };

    const countSelectedPhotos = () => Array.from(photoInputs).filter((input) => input.checked && !input.disabled).length;

    const formatPhotoCount = (photos) => `${photos} fotografía${photos === 1 ? "" : "s"}`;

    const buildContentText = () => {
        const photos = countSelectedPhotos();
        const includesDocx = Boolean(docxInput && docxInput.checked);
        if (photos > 0 && includesDocx) {
            return `${formatPhotoCount(photos)} · documento Word incluido`;
        }
        if (photos > 0) {
            return `${formatPhotoCount(photos)} · sin documento Word`;
        }
        if (includesDocx) {
            return "Documento Word incluido";
        }
        return "Sin contenido seleccionado";
    };

    const applyDeliveryModeState = () => {
        const mode = getSelectedMode();
        const isSchedule = mode === "schedule";
        const deliveryMethod = deliveryMethodSelect ? deliveryMethodSelect.value : "download_link";
        const usesSmtp = deliveryMethod === "download_link_email";
        setElementVisibility(scheduledFields, isSchedule);
        setElementVisibility(linkOnlyHelp, !usesSmtp);
        setElementVisibility(smtpHelp, usesSmtp);
        setScheduleInputsEnabled(isSchedule);
        if (smtpChannelSelect) {
            smtpChannelSelect.disabled = !usesSmtp || smtpChannelSelect.tagName === "INPUT";
        }
        if (deliveryChannelName) {
            deliveryChannelName.value = usesSmtp ? "Correo (SMTP)" : "Enlace de descarga";
        }

        if (contentSummary) {
            contentSummary.textContent = buildContentText();
        }

        if (mode === "immediate") {
            if (deliveryModeSummary) {
                deliveryModeSummary.textContent = "Este despacho se preparará para envío inmediato.";
            }
            if (formSummary) {
                formSummary.textContent = "Este despacho se preparará para envío inmediato.";
            }
            if (submitButton) {
                submitButton.textContent = "Preparar envío ahora";
            }
            return;
        }

        if (mode === "schedule") {
            const hasSchedule = scheduledDate && scheduledDate.value && scheduledTime && scheduledTime.value && timezoneSelect && timezoneSelect.value;
            if (deliveryModeSummary) {
                deliveryModeSummary.textContent = hasSchedule
                    ? `Este despacho se programará para el ${scheduledDate.value} a las ${scheduledTime.value}, en la zona ${timezoneSelect.value}.`
                    : "Seleccione fecha, hora y zona horaria para programar el despacho.";
            }
            if (formSummary) {
                formSummary.textContent = hasSchedule
                    ? `Este despacho se programará para el ${scheduledDate.value} a las ${scheduledTime.value}, en la zona ${timezoneSelect.value}.`
                    : "Seleccione fecha, hora y zona horaria para programar el despacho.";
            }
            if (submitButton) {
                submitButton.textContent = "Programar envío";
            }
            return;
        }

        if (deliveryModeSummary) {
            deliveryModeSummary.textContent = "Este despacho se guardará como borrador.";
        }
        if (formSummary) {
            formSummary.textContent = "Este despacho se guardará como borrador.";
        }
        if (submitButton) {
            submitButton.textContent = "Guardar borrador";
        }
    };

    modeInputs.forEach((input) => input.addEventListener("change", applyDeliveryModeState));
    if (deliveryMethodSelect) {
        deliveryMethodSelect.addEventListener("change", applyDeliveryModeState);
    }
    [scheduledDate, scheduledTime, timezoneSelect, docxInput].forEach((input) => {
        if (input) {
            input.addEventListener("input", applyDeliveryModeState);
            input.addEventListener("change", applyDeliveryModeState);
        }
    });
    photoInputs.forEach((input) => input.addEventListener("change", applyDeliveryModeState));

    document.querySelectorAll(".dispatch-photo-option").forEach((card) => {
        card.addEventListener("click", (event) => {
            if (event.target.closest("input, label")) {
                return;
            }
            const checkbox = card.querySelector('input[type="checkbox"]');
            if (!checkbox || checkbox.disabled) {
                return;
            }
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event("change", { bubbles: true }));
        });
    });

    const sanitizeRecipientInput = (input) => {
        input.value = input.value.replaceAll("|", "");
        applyDeliveryModeState();
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
        applyDeliveryModeState();
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
                    applyDeliveryModeState();
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

    detectTimezone();
    applyDeliveryModeState();
});
