const exportSection = document.querySelector("#tab-exportaciones");
const exportForm = document.querySelector("#export-form");
const exportMessage = document.querySelector("#export-message");
const exportConfirmWarnings = document.querySelector("#export-confirm-warnings");
const exportDownloadButton = document.querySelector("#export-download-button");
const exportDispatchButton = document.querySelector("#export-dispatch-button");
const exportHistoryList = document.querySelector("#export-history-list");
const exportHistoryEmpty = document.querySelector("#export-history-empty");
const exportOutputName = document.querySelector("#export-output-name");
const exportContentCard = document.querySelector("#export-content-card");

function normalizeExportSegment(value) {
    return (value || "Exportacion")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^A-Za-z0-9]+/g, "-")
        .replace(/-{2,}/g, "-")
        .replace(/^-+|-+$/g, "") || "Exportacion";
}

function buildExportBaseName(dateValue, coverageName, country) {
    const dateToken = (dateValue || "00000000").replace(/-/g, "") || "00000000";
    return `${dateToken}-${normalizeExportSegment(coverageName)}-${normalizeExportSegment(country)}`;
}

function syncExportNamePreview() {
    if (!exportSection || !exportOutputName) {
        return;
    }
    const coverageField = document.getElementById("edit_coverage_name");
    const countryField = document.getElementById("edit_country");
    const coverageName = coverageField?.value || exportSection.dataset.exportCoverage || "Cobertura";
    const country = countryField?.value || exportSection.dataset.exportCountry || "Pais";
    exportOutputName.value = buildExportBaseName(exportSection.dataset.exportDate, coverageName, country);
}

function setExportMessage(message, status = "info") {
    if (!exportMessage) {
        return;
    }
    exportMessage.textContent = message;
    exportMessage.dataset.status = status;
}

function getSelectedFormats(formData) {
    return formData.getAll("formats").map((format) => String(format).toLowerCase());
}

function syncZipContentVisibility() {
    if (!exportForm || !exportContentCard) {
        return;
    }
    const formData = new FormData(exportForm);
    exportContentCard.hidden = !getSelectedFormats(formData).includes("zip");
}

function appendHistory(result, destination) {
    if (!exportHistoryList || !result) {
        return;
    }
    if (exportHistoryEmpty) {
        exportHistoryEmpty.hidden = true;
    }
    const item = document.createElement("li");
    const formats = (result.formats_generated || []).join("+").toUpperCase();
    item.textContent = `${new Date().toISOString()} · Navegador · ${destination} · ${formats} · ${result.photo_count || 0} foto(s) · ${result.files?.length || 0} archivo(s)`;
    exportHistoryList.prepend(item);
}

function base64ToBlob(base64Value, mimetype) {
    const binary = atob(base64Value);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
    }
    return new Blob([bytes], {type: mimetype || "application/octet-stream"});
}

function downloadFile(exportFile) {
    const blob = base64ToBlob(exportFile.content_base64, exportFile.mimetype);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = exportFile.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
}

function downloadExport(result) {
    const files = result?.files || [];
    files.forEach(downloadFile);
    appendHistory(result, "download");
    const filenames = files.map((file) => file.filename).join(", ");
    setExportMessage(`Exportación generada: ${filenames}`, "success");
}

function setExportButtonsDisabled(disabled) {
    if (exportDownloadButton) {
        exportDownloadButton.disabled = disabled;
    }
    if (exportDispatchButton) {
        exportDispatchButton.disabled = disabled;
    }
}

function buildExportPayload(formData, submitter) {
    const formats = getSelectedFormats(formData);
    const usesZip = formats.includes("zip");
    return {
        formats,
        include_photos: usesZip ? formData.has("include_photos") : false,
        include_captions: usesZip ? formData.has("include_captions") : false,
        include_metadata: usesZip ? formData.has("include_metadata") : false,
        include_manifest: usesZip ? formData.has("include_manifest") : false,
        output_name: formData.get("output_name") || "",
        destination: submitter?.value || "download",
        confirm_warnings: exportConfirmWarnings?.value === "true"
    };
}

async function submitExport(event) {
    event.preventDefault();
    if (!exportSection || !exportForm) {
        return;
    }

    const payload = buildExportPayload(new FormData(exportForm), event.submitter);
    if (!payload.formats.length) {
        setExportMessage("Selecciona al menos un formato.", "error");
        return;
    }

    setExportButtonsDisabled(true);
    setExportMessage(
        payload.destination === "dispatch"
            ? "Generando archivos para DISPATCH…"
            : "Generando archivos editoriales…",
        "info"
    );

    try {
        const response = await fetch(exportSection.dataset.exportUrl, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (response.status === 409 && data.requires_confirmation) {
            exportConfirmWarnings.value = "true";
            setExportMessage(`${data.warnings.join(" ")} Vuelve a ejecutar la acción para continuar.`, "warning");
            return;
        }
        if (!response.ok || !data.ok) {
            setExportMessage(data.error || "No fue posible generar la exportación.", "error");
            return;
        }

        exportConfirmWarnings.value = "false";
        if (data.destination === "dispatch") {
            appendHistory(data.result, "dispatch");
            setExportMessage(`Archivos preparados para DISPATCH: ${data.result.files.length} archivo(s).`, "success");
            return;
        }
        downloadExport(data.result);
    } catch (error) {
        setExportMessage("Error de conexión al generar la exportación.", "error");
    } finally {
        setExportButtonsDisabled(false);
    }
}

exportForm?.addEventListener("change", () => {
    if (exportConfirmWarnings) {
        exportConfirmWarnings.value = "false";
    }
    syncZipContentVisibility();
});
exportForm?.addEventListener("submit", submitExport);
document.getElementById("edit_coverage_name")?.addEventListener("input", syncExportNamePreview);
document.getElementById("edit_country")?.addEventListener("change", syncExportNamePreview);
syncExportNamePreview();
syncZipContentVisibility();
