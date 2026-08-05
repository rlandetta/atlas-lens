document.addEventListener("DOMContentLoaded", () => {
    const fallbackTimezone = "America/Guayaquil";
    const scheduleFields = document.querySelector("[data-dispatch-schedule-fields]");
    const immediateHelp = document.querySelector("[data-dispatch-immediate-help]");
    const modeInputs = document.querySelectorAll('input[name="mode"]');
    const timezoneSelect = document.getElementById("timezone");
    const timezoneToggle = document.querySelector("[data-timezone-toggle]");
    const timezoneSelector = document.querySelector("[data-timezone-selector]");
    const timezoneSummaries = document.querySelectorAll("[data-timezone-summary]");
    const timezoneDetection = document.querySelector("[data-timezone-detection]");
    const scheduledDate = document.getElementById("scheduled_date");
    const scheduledTime = document.getElementById("scheduled_time");
    const summary = document.querySelector("[data-dispatch-form-summary]");
    const submitButton = document.querySelector("[data-dispatch-submit-button]");
    const recipientList = document.querySelector("[data-recipient-list]");
    const addRecipientButton = document.querySelector("[data-recipient-add]");
    const photoInputs = document.querySelectorAll('input[name="photo_ids"]');
    const docxInput = document.getElementById("include_caption_docx");

    const getSelectedMode = () => {
        const selectedMode = document.querySelector('input[name="mode"]:checked');
        return selectedMode ? selectedMode.value : "draft";
    };

    const getTimezone = () => (timezoneSelect && timezoneSelect.value ? timezoneSelect.value : fallbackTimezone);

    const formatOffset = (timeZone) => {
        try {
            const parts = new Intl.DateTimeFormat("en-US", {
                timeZone,
                timeZoneName: "shortOffset",
            }).formatToParts(new Date());
            const offset = parts.find((part) => part.type === "timeZoneName");
            return offset ? offset.value.replace("GMT", "UTC") : "";
        } catch (error) {
            return "";
        }
    };

    const formatTimezoneLabel = (timeZone) => {
        const offset = formatOffset(timeZone);
        return offset ? `${timeZone} (${offset})` : timeZone;
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

    const syncTimezoneLabels = () => {
        const label = formatTimezoneLabel(getTimezone());
        timezoneSummaries.forEach((item) => {
            item.textContent = label;
        });
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
        if (timezoneDetection) {
            timezoneDetection.textContent = detected === fallbackTimezone
                ? "Zona horaria predeterminada"
                : "Detectada automáticamente";
        }
        syncTimezoneLabels();
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

    const syncSummary = () => {
        const mode = getSelectedMode();
        const recipients = countRecipients();
        const photos = countSelectedPhotos();
        const docxText = docxInput && docxInput.checked ? " y un documento Word con captions" : "";
        if (summary) {
            if (mode === "immediate") {
                summary.textContent = `Este despacho se preparará inmediatamente para ${recipients} destinatario(s). Incluye ${photos} fotografía(s)${docxText}.`;
            } else if (mode === "schedule") {
                const dateText = scheduledDate && scheduledDate.value ? scheduledDate.value : "la fecha seleccionada";
                const timeText = scheduledTime && scheduledTime.value ? scheduledTime.value : "la hora seleccionada";
                summary.textContent = `Este despacho se preparará para ${dateText} a las ${timeText}, hora de ${formatTimezoneLabel(getTimezone())}, para ${recipients} destinatario(s).`;
            } else {
                summary.textContent = "Este despacho se guardará como borrador.";
            }
        }
        if (submitButton) {
            submitButton.textContent = mode === "immediate"
                ? "Preparar envío ahora"
                : mode === "schedule"
                    ? "Programar envío"
                    : "Guardar borrador";
        }
    };

    const syncScheduleFields = () => {
        const mode = getSelectedMode();
        if (scheduleFields) {
            scheduleFields.hidden = mode !== "schedule";
        }
        if (immediateHelp) {
            immediateHelp.hidden = mode !== "immediate";
        }
        syncSummary();
    };

    modeInputs.forEach((input) => input.addEventListener("change", syncScheduleFields));
    if (timezoneSelect) {
        timezoneSelect.addEventListener("change", () => {
            syncTimezoneLabels();
            syncSummary();
        });
    }
    if (timezoneToggle && timezoneSelector) {
        timezoneToggle.addEventListener("click", () => {
            timezoneSelector.hidden = !timezoneSelector.hidden;
            timezoneToggle.textContent = timezoneSelector.hidden ? "Cambiar" : "Ocultar";
        });
    }
    [scheduledDate, scheduledTime, docxInput].forEach((input) => {
        if (input) {
            input.addEventListener("input", syncSummary);
            input.addEventListener("change", syncSummary);
        }
    });
    photoInputs.forEach((input) => input.addEventListener("change", syncSummary));
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
        syncSummary();
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
        syncSummary();
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
                    syncSummary();
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
    syncScheduleFields();
});
