const exportSection = document.querySelector("#tab-exportaciones");
const exportForm = document.querySelector("#export-form");
const exportMessage = document.querySelector("#export-message");
const exportResultPanel = document.querySelector("#export-result-panel");
const exportConfirmWarnings = document.querySelector("#export-confirm-warnings");
const exportDownloadButton = document.querySelector("#export-download-button");
const exportDispatchButton = document.querySelector("#export-dispatch-button");
const exportHistoryList = document.querySelector("#export-history-list");
const exportHistoryEmpty = document.querySelector("#export-history-empty");
const exportOutputName = document.querySelector("#export-output-name");
const partialDispatchDialog = document.querySelector("#export-partial-dispatch-dialog");
const partialDispatchMessage = document.querySelector("#export-partial-dispatch-message");
const cancelPartialDispatchButton = document.querySelector("#cancel-partial-dispatch-button");
const confirmPartialDispatchButton = document.querySelector("#confirm-partial-dispatch-button");

let partialDispatchConfirmed = false;

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

function getWorkspacePhotos() {
    if (window.ATLAS_LENS_PHOTO_API && typeof window.ATLAS_LENS_PHOTO_API.getPhotos === "function") {
        return window.ATLAS_LENS_PHOTO_API.getPhotos();
    }
    return [];
}

function getFailedWorkspacePhotos() {
    return getWorkspacePhotos().filter((photo) => photo.importStatus === "Error");
}

function omittedPhotosFromWorkspace() {
    return getFailedWorkspacePhotos().map((photo) => ({
        id: photo.id || "",
        filename: photo.name || photo.filename || "Fotografía",
        stage: "import",
        reason: photo.processingError || "No fue importada a LENS."
    }));
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

function formatList(values) {
    return values.filter(Boolean).map((value) => String(value).toUpperCase()).join(" · ");
}

function artifactLabel(result) {
    const files = result?.files || [];
    if (files.length === 1 && files[0].format === "zip") {
        return "Descargar paquete";
    }
    return "Descargar";
}

function renderExportResult(result) {
    if (!exportResultPanel || !result) {
        return;
    }
    const status = result.status || "COMPLETE";
    const title = {
        COMPLETE: "Exportación completada",
        PARTIAL: "Exportación parcial",
        FAILED: "Exportación fallida"
    }[status] || "Exportación";
    const omitted = result.omitted_photos || [];
    const files = result.files || [];
    const primaryFilename = result.filename || files.map((file) => file.filename).join(", ");
    exportResultPanel.hidden = false;
    exportResultPanel.dataset.status = status.toLowerCase();
    exportResultPanel.innerHTML = "";

    const heading = document.createElement("h3");
    heading.textContent = title;
    const filename = document.createElement("p");
    filename.className = "export-result-filename";
    filename.textContent = primaryFilename || "Sin archivo";
    const counts = document.createElement("p");
    counts.textContent = `${result.exported_photo_count || 0} de ${result.requested_photo_count || 0} fotografías exportadas`;
    const captions = document.createElement("p");
    captions.textContent = `${result.captions_included || 0} captions incluidos`;
    const formats = document.createElement("p");
    formats.textContent = `Formatos generados: ${formatList((result.formats_generated || []).filter((format) => format !== "zip")) || "Ninguno"}`;
    exportResultPanel.append(heading, filename, counts, captions, formats);

    if ((result.formats_generated || []).includes("zip")) {
        const packageLine = document.createElement("p");
        packageLine.textContent = "Paquete: ZIP";
        exportResultPanel.appendChild(packageLine);
    }

    if (omitted.length) {
        const summary = document.createElement("p");
        summary.textContent = `${omitted.length} fotografía${omitted.length === 1 ? "" : "s"} no pudo${omitted.length === 1 ? "" : "ieron"} procesarse`;
        const list = document.createElement("ul");
        omitted.forEach((item) => {
            const row = document.createElement("li");
            row.textContent = `${item.filename || "Fotografía"} · No incluida · ${item.reason || "Sin motivo registrado."}`;
            list.appendChild(row);
        });
        exportResultPanel.append(summary, list);
    } else {
        const ok = document.createElement("p");
        ok.textContent = "Sin errores";
        exportResultPanel.appendChild(ok);
    }

}

function appendHistory(result, destination) {
    if (!exportHistoryList || !result) {
        return;
    }
    if (exportHistoryEmpty) {
        exportHistoryEmpty.hidden = true;
    }
    const item = document.createElement("li");
    item.dataset.exportHistoryItem = "true";
    item.dataset.exportId = result.export_id || result.created_at || "";
    const formats = formatList(result.formats_generated || []);
    item.innerHTML = `<div><strong>${new Date().toISOString()}</strong> <span>${exportSection?.dataset.exportCoverage || ""}</span> <span>${formats}</span> <span>${result.exported_photo_count || 0}/${result.requested_photo_count || 0} fotografías</span> <span>${result.status || "COMPLETE"}</span></div>`;
    exportHistoryList.prepend(item);
}

function downloadExport(result) {
    const files = result?.files || [];
    files.forEach(downloadFile);
    appendHistory(result, "download");
    renderExportResult(result);
    setExportMessage(`${artifactLabel(result)} preparado: ${files.map((file) => file.filename).join(", ")}`, result.status === "PARTIAL" ? "warning" : "success");
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
    const photos = getWorkspacePhotos();
    return {
        formats,
        include_photos: formData.has("include_photos"),
        include_captions: formats.length > 0,
        include_metadata: false,
        include_manifest: false,
        output_name: formData.get("output_name") || "",
        destination: submitter?.value || "download",
        confirm_warnings: exportConfirmWarnings?.value === "true",
        partial_confirmed: partialDispatchConfirmed,
        requested_photo_count: photos.length,
        requested_photos: photos.map((photo) => ({
            id: photo.id || "",
            filename: photo.name || photo.filename || "Fotografía"
        })),
        omitted_photos: omittedPhotosFromWorkspace()
    };
}

function confirmPartialDispatch(payload) {
    if (!partialDispatchDialog || payload.destination !== "dispatch" || !payload.omitted_photos.length || partialDispatchConfirmed) {
        return Promise.resolve(true);
    }
    const exported = Math.max((payload.requested_photo_count || 0) - payload.omitted_photos.length, 0);
    if (partialDispatchMessage) {
        partialDispatchMessage.textContent = `Esta exportación está incompleta. Se exportaron ${exported} de ${payload.requested_photo_count || 0} fotografías. ¿Desea enviarla a DISPATCH de todas formas?`;
    }
    return new Promise((resolve) => {
        const cleanup = () => {
            cancelPartialDispatchButton?.removeEventListener("click", cancel);
            confirmPartialDispatchButton?.removeEventListener("click", confirm);
            partialDispatchDialog.removeEventListener("close", close);
        };
        const cancel = () => {
            cleanup();
            partialDispatchDialog.close("cancel");
            resolve(false);
        };
        const confirm = () => {
            cleanup();
            partialDispatchConfirmed = true;
            partialDispatchDialog.close("confirm");
            resolve(true);
        };
        const close = () => {
            cleanup();
            resolve(partialDispatchDialog.returnValue === "confirm");
        };
        cancelPartialDispatchButton?.addEventListener("click", cancel, {once: true});
        confirmPartialDispatchButton?.addEventListener("click", confirm, {once: true});
        partialDispatchDialog.addEventListener("close", close, {once: true});
        partialDispatchDialog.showModal();
    });
}

async function submitExport(event) {
    event.preventDefault();
    if (!exportSection || !exportForm) {
        return;
    }

    const payload = buildExportPayload(new FormData(exportForm), event.submitter);
    if (!payload.formats.length && !payload.include_photos) {
        setExportMessage("Selecciona al menos un formato o incluye fotografías originales.", "error");
        return;
    }
    if (!(await confirmPartialDispatch(payload))) {
        setExportMessage("Envío parcial cancelado.", "info");
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
            if (data.status === "PARTIAL") {
                partialDispatchConfirmed = true;
            }
            setExportMessage(`${data.warnings.join(" ")} Vuelve a ejecutar la acción para continuar.`, "warning");
            return;
        }
        if (!response.ok || !data.ok) {
            if (data.result) {
                renderExportResult(data.result);
            }
            setExportMessage(data.error || "No fue posible generar la exportación.", "error");
            return;
        }

        exportConfirmWarnings.value = "false";
        partialDispatchConfirmed = false;
        if (data.destination === "dispatch") {
            appendHistory(data.result, "dispatch");
            renderExportResult(data.result);
            setExportMessage(`Archivos preparados para DISPATCH: ${data.result.files.length} archivo(s).`, data.result.status === "PARTIAL" ? "warning" : "success");
            return;
        }
        downloadExport(data.result);
    } catch (error) {
        setExportMessage("Error de conexión al generar la exportación.", "error");
    } finally {
        setExportButtonsDisabled(false);
    }
}

async function deleteHistoryItem(button) {
    const item = button.closest("[data-export-history-item]");
    const exportId = item?.dataset.exportId;
    if (!exportSection || !item || !exportId) {
        return;
    }
    if (!window.confirm("¿Eliminar este registro del historial? No se borrarán coberturas, fotografías ni archivos exportados.")) {
        return;
    }
    const url = exportSection.dataset.exportHistoryDeleteUrlTemplate.replace("__EXPORT_ID__", encodeURIComponent(exportId));
    const response = await fetch(url, {method: "POST"});
    if (!response.ok) {
        setExportMessage("No se pudo eliminar el registro del historial.", "error");
        return;
    }
    item.remove();
    if (exportHistoryEmpty && !exportHistoryList.querySelector("[data-export-history-item]")) {
        exportHistoryEmpty.hidden = false;
    }
    setExportMessage("Registro de historial eliminado. Los archivos exportados se conservaron.", "success");
}

exportForm?.addEventListener("change", () => {
    if (exportConfirmWarnings) {
        exportConfirmWarnings.value = "false";
    }
    partialDispatchConfirmed = false;
});
exportForm?.addEventListener("submit", submitExport);
exportHistoryList?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-export-history-delete]");
    if (button) {
        deleteHistoryItem(button);
    }
});
document.getElementById("edit_coverage_name")?.addEventListener("input", syncExportNamePreview);
document.getElementById("edit_country")?.addEventListener("change", syncExportNamePreview);
syncExportNamePreview();
