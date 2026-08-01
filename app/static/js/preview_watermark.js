const watermarkPanel = document.querySelector("[data-watermark-panel]");

if (watermarkPanel) {
    const imageSelect = document.getElementById("watermark-image-select");
    const agencyField = document.getElementById("watermark-agency");
    const photographerField = document.getElementById("watermark-photographer");
    const resolutionSelect = document.getElementById("watermark-resolution");
    const customResolutionField = document.getElementById("watermark-custom-resolution");
    const positionField = document.getElementById("watermark-position");
    const opacityField = document.getElementById("watermark-opacity");
    const bandColorField = document.getElementById("watermark-band-color");
    const textColorField = document.getElementById("watermark-text-color");
    const preserveExifField = document.getElementById("watermark-preserve-exif");
    const preserveIptcField = document.getElementById("watermark-preserve-iptc");
    const preserveIccField = document.getElementById("watermark-preserve-icc");
    const applyScopeFields = Array.from(document.querySelectorAll("input[name='watermark_scope']"));
    const selectedList = document.getElementById("watermark-selected-list");
    const previewCanvas = document.getElementById("watermark-preview-canvas");
    const previewEmpty = document.getElementById("watermark-preview-empty");
    const previewMeta = document.getElementById("watermark-preview-meta");
    const exportButton = document.getElementById("watermark-export-button");
    const selectAllButton = document.getElementById("watermark-select-all-button");
    const clearSelectionButton = document.getElementById("watermark-clear-selection-button");
    const opacityValue = document.getElementById("watermark-opacity-value");
    const bandColorValue = document.getElementById("watermark-band-color-value");
    const textColorValue = document.getElementById("watermark-text-color-value");
    const message = document.getElementById("watermark-message");
    const context = previewCanvas ? previewCanvas.getContext("2d") : null;
    const selectedPhotoIds = new Set();
    const previewTemplateRegistry = {
        xinhua: {
            agencyLabel: "XINHUA News Agency",
            buildSecondLine(settings) {
                const agencyCredit = /^xinhua$/i.test(settings.agency || "")
                    ? this.agencyLabel
                    : settings.agency || this.agencyLabel;
                return `${settings.photographer || "Fotógrafo"} / ${agencyCredit}`;
            },
            measure(canvas, settings) {
                const width = canvas.width;
                const height = canvas.height;
                const bandWidth = Math.max(1, Math.round(width * 0.425));
                const margin = Math.max(18, Math.round(Math.min(width, height) * 0.035));
                const verticalLift = Math.max(96, Math.round(width * 0.05));
                const firstLineSize = Math.max(12, Math.round(bandWidth * 0.07));
                const secondLineSize = Math.max(9, Math.round(bandWidth * 0.045));
                const lineGap = Math.max(4, Math.round(secondLineSize * 0.42));
                const paddingX = Math.max(12, Math.round(bandWidth * 0.08));
                const paddingY = Math.max(8, Math.round(secondLineSize * 0.8));
                const bandHeight = Math.round(paddingY * 2 + firstLineSize + lineGap + secondLineSize);
                const left = settings.position === "bottom-left"
                    ? 0
                    : width - bandWidth;
                const top = height - bandHeight - margin - verticalLift;

                return {
                    width,
                    height,
                    bandWidth,
                    bandHeight,
                    margin,
                    verticalLift,
                    left,
                    top,
                    paddingX,
                    paddingY,
                    firstLineSize,
                    secondLineSize,
                    lineGap
                };
            },
            draw(drawContext, canvas, settings) {
                const metrics = this.measure(canvas, settings);
                drawContext.save();
                drawContext.globalAlpha = settings.opacity;
                drawContext.fillStyle = settings.bandColor;
                drawContext.fillRect(metrics.left, metrics.top, metrics.bandWidth, metrics.bandHeight);
                drawContext.globalAlpha = 1;
                drawContext.fillStyle = settings.textColor;
                drawContext.textBaseline = "top";
                drawContext.font = `700 ${metrics.firstLineSize}px Arial, Helvetica, sans-serif`;
                drawContext.fillText(this.agencyLabel, metrics.left + metrics.paddingX, metrics.top + metrics.paddingY);
                drawContext.font = `400 ${metrics.secondLineSize}px Arial, Helvetica, sans-serif`;
                drawContext.fillText(this.buildSecondLine(settings), metrics.left + metrics.paddingX, metrics.top + metrics.paddingY + metrics.firstLineSize + metrics.lineGap);
                drawContext.restore();
                return metrics;
            }
        }
    };

    const getPhotoApi = () => window.ATLAS_LENS_PHOTO_API || null;
    const getPhotos = () => {
        const api = getPhotoApi();
        return api ? api.getPhotos() : [];
    };
    const getActivePhoto = () => {
        const api = getPhotoApi();
        return api ? api.getActivePhoto() : null;
    };
    const getPhotoById = (photoId) => getPhotos().find((photo) => photo.id === photoId) || null;
    const getPhotoSource = (photo) => photo.dataUrl || photo.objectUrl || photo.thumbnailDataUrl || "";

    const setMessage = (text, status = "idle") => {
        message.textContent = text;
        message.dataset.status = status;
    };

    const normalizeFilename = (value) => (
        (value || "preview")
            .replace(/\.[^.]+$/, "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^A-Za-z0-9_-]+/g, "-")
            .replace(/-+/g, "-")
            .replace(/^-|-$/g, "") || "preview"
    );

    const parseHexColor = (value, fallback) => (/^#[0-9a-f]{6}$/i.test(value) ? value : fallback);
    const getOutputResolution = () => {
        if (resolutionSelect.value === "custom") {
            const customValue = Number(customResolutionField.value);
            return Number.isFinite(customValue) ? Math.min(6000, Math.max(600, Math.round(customValue))) : 3000;
        }
        return Number(resolutionSelect.value) || 3000;
    };

    const getSettings = () => ({
        agency: agencyField.value.trim() || "Xinhua",
        photographer: photographerField.value.trim() || "Fotógrafo",
        resolution: getOutputResolution(),
        position: positionField.value === "bottom-left" ? "bottom-left" : "bottom-right",
        opacity: Math.min(1, Math.max(0.05, Number(opacityField.value) / 100 || 0.8)),
        bandColor: parseHexColor(bandColorField.value, "#001450"),
        textColor: parseHexColor(textColorField.value, "#ffffff"),
        preserveExif: preserveExifField.checked,
        preserveIptc: preserveIptcField.checked,
        preserveIcc: preserveIccField.checked,
        template: "xinhua"
    });

    const loadImage = (source) => new Promise((resolve, reject) => {
        const image = new Image();
        image.addEventListener("load", () => resolve(image), { once: true });
        image.addEventListener("error", () => reject(new Error("No fue posible cargar la fotografía.")), { once: true });
        image.src = source;
    });

    const calculateSize = (width, height, longestSide) => {
        const scale = Math.min(1, longestSide / Math.max(width, height));
        return {
            width: Math.max(1, Math.round(width * scale)),
            height: Math.max(1, Math.round(height * scale))
        };
    };

    const drawWatermarkedImage = async (photo, longestSide) => {
        const source = getPhotoSource(photo);
        if (!source || !context) {
            throw new Error("La fotografía seleccionada no tiene datos disponibles.");
        }
        const image = await loadImage(source);
        const size = calculateSize(image.naturalWidth, image.naturalHeight, longestSide);
        previewCanvas.width = size.width;
        previewCanvas.height = size.height;
        context.clearRect(0, 0, size.width, size.height);
        context.drawImage(image, 0, 0, size.width, size.height);
        const metrics = previewTemplateRegistry.xinhua.draw(context, previewCanvas, getSettings());
        return { ...size, watermark: metrics };
    };

    const bytesFromDataUrl = (dataUrl) => {
        const base64 = dataUrl.split(",")[1] || "";
        const binary = atob(base64);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
        }
        return bytes;
    };

    const blobToBytes = (blob) => new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.addEventListener("load", () => resolve(new Uint8Array(reader.result)), { once: true });
        reader.addEventListener("error", () => reject(reader.error), { once: true });
        reader.readAsArrayBuffer(blob);
    });

    const isJpegSegmentPreserved = (segment, settings) => {
        const marker = segment[1];
        const payload = new TextDecoder("latin1").decode(segment.slice(4, Math.min(segment.length, 80)));
        if (settings.preserveExif && marker === 0xe1 && payload.startsWith("Exif")) {
            return true;
        }
        if (settings.preserveIptc && marker === 0xed) {
            return true;
        }
        if (settings.preserveIptc && marker === 0xe1 && payload.includes("http://ns.adobe.com/xap/1.0/")) {
            return true;
        }
        if (settings.preserveIcc && marker === 0xe2 && payload.startsWith("ICC_PROFILE")) {
            return true;
        }
        return false;
    };

    const extractPreservedJpegSegments = (sourceBytes, settings) => {
        if (sourceBytes.length < 4 || sourceBytes[0] !== 0xff || sourceBytes[1] !== 0xd8) {
            return [];
        }
        const segments = [];
        let offset = 2;
        while (offset + 4 < sourceBytes.length && sourceBytes[offset] === 0xff) {
            const marker = sourceBytes[offset + 1];
            if (marker === 0xda || marker === 0xd9) {
                break;
            }
            const length = (sourceBytes[offset + 2] << 8) + sourceBytes[offset + 3];
            const end = offset + 2 + length;
            if (length < 2 || end > sourceBytes.length) {
                break;
            }
            const segment = sourceBytes.slice(offset, end);
            if (isJpegSegmentPreserved(segment, settings)) {
                segments.push(segment);
            }
            offset = end;
        }
        return segments;
    };

    const getMetadataInsertOffset = (jpegBytes) => {
        if (jpegBytes.length < 6 || jpegBytes[0] !== 0xff || jpegBytes[1] !== 0xd8) {
            return 2;
        }
        let offset = 2;
        while (offset + 4 < jpegBytes.length && jpegBytes[offset] === 0xff) {
            const marker = jpegBytes[offset + 1];
            if (marker !== 0xe0 && marker !== 0xee) {
                break;
            }
            const length = (jpegBytes[offset + 2] << 8) + jpegBytes[offset + 3];
            const end = offset + 2 + length;
            if (length < 2 || end > jpegBytes.length) {
                break;
            }
            offset = end;
        }
        return offset;
    };

    const injectJpegSegments = (jpegBytes, segments) => {
        if (segments.length === 0 || jpegBytes.length < 2 || jpegBytes[0] !== 0xff || jpegBytes[1] !== 0xd8) {
            return jpegBytes;
        }
        const insertOffset = getMetadataInsertOffset(jpegBytes);
        const totalLength = jpegBytes.length + segments.reduce((sum, segment) => sum + segment.length, 0);
        const output = new Uint8Array(totalLength);
        let cursor = 0;
        output.set(jpegBytes.slice(0, insertOffset), cursor);
        cursor += insertOffset;
        segments.forEach((segment) => {
            output.set(segment, cursor);
            cursor += segment.length;
        });
        output.set(jpegBytes.slice(insertOffset), cursor);
        return output;
    };

    const buildExportBlob = async (photo) => {
        const settings = getSettings();
        await drawWatermarkedImage(photo, settings.resolution);
        const canvasBlob = await new Promise((resolve) => previewCanvas.toBlob(resolve, "image/jpeg", 0.92));
        if (!canvasBlob) {
            throw new Error("No fue posible generar el JPG de previsualización.");
        }
        let exportBytes = await blobToBytes(canvasBlob);
        if (settings.preserveExif || settings.preserveIptc || settings.preserveIcc) {
            const sourceDataUrl = photo.dataUrl || photo.thumbnailDataUrl;
            if (sourceDataUrl && sourceDataUrl.startsWith("data:image/jpeg")) {
                const segments = extractPreservedJpegSegments(bytesFromDataUrl(sourceDataUrl), settings);
                exportBytes = injectJpegSegments(exportBytes, segments);
            }
        }
        return new Blob([exportBytes], { type: "image/jpeg" });
    };

    const downloadBlob = (blob, filename) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    };

    const getScope = () => {
        const checkedScope = applyScopeFields.find((field) => field.checked);
        return checkedScope ? checkedScope.value : "current";
    };

    const getTargetPhotos = () => {
        const photos = getPhotos().filter((photo) => getPhotoSource(photo));
        const scope = getScope();
        if (scope === "coverage") {
            return photos;
        }
        if (scope === "selected") {
            return photos.filter((photo) => selectedPhotoIds.has(photo.id));
        }
        const selectedId = imageSelect.value;
        return [getPhotoById(selectedId) || getActivePhoto()].filter(Boolean);
    };

    const syncCustomResolution = () => {
        customResolutionField.hidden = resolutionSelect.value !== "custom";
    };

    const renderImageOptions = () => {
        const photos = getPhotos();
        const previousValue = imageSelect.value;
        imageSelect.innerHTML = "";
        photos.forEach((photo, index) => {
            const option = document.createElement("option");
            option.value = photo.id;
            option.textContent = `${index + 1}. ${photo.name}`;
            imageSelect.appendChild(option);
        });
        const activePhoto = getActivePhoto();
        const nextValue = photos.some((photo) => photo.id === previousValue)
            ? previousValue
            : activePhoto && photos.some((photo) => photo.id === activePhoto.id)
                ? activePhoto.id
                : photos[0] && photos[0].id;
        if (nextValue) {
            imageSelect.value = nextValue;
        }
        imageSelect.disabled = photos.length === 0;
    };

    const renderSelectedList = () => {
        const photos = getPhotos();
        selectedList.innerHTML = "";
        if (photos.length === 0) {
            const emptyItem = document.createElement("li");
            emptyItem.textContent = "Importe fotografías para preparar marcas de agua.";
            selectedList.appendChild(emptyItem);
            return;
        }
        photos.forEach((photo) => {
            const item = document.createElement("li");
            const label = document.createElement("label");
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = photo.id;
            checkbox.checked = selectedPhotoIds.has(photo.id);
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) {
                    selectedPhotoIds.add(photo.id);
                } else {
                    selectedPhotoIds.delete(photo.id);
                }
            });
            label.append(checkbox, document.createTextNode(photo.name));
            item.appendChild(label);
            selectedList.appendChild(item);
        });
    };

    let previewTimer = 0;
    const schedulePreviewRender = () => {
        window.clearTimeout(previewTimer);
        previewTimer = window.setTimeout(renderPreview, 80);
    };

    const renderPreview = async () => {
        const photo = getPhotoById(imageSelect.value) || getActivePhoto();
        if (!photo || !getPhotoSource(photo)) {
            previewCanvas.hidden = true;
            previewEmpty.hidden = false;
            previewMeta.textContent = "Sin fotografía seleccionada.";
            exportButton.disabled = true;
            return;
        }
        try {
            exportButton.disabled = false;
            previewEmpty.hidden = true;
            previewCanvas.hidden = false;
            const size = await drawWatermarkedImage(photo, 1100);
            previewMeta.textContent = `${photo.name} · marca ${size.width} x ${size.height} px · banda ${size.watermark.bandWidth} x ${size.watermark.bandHeight} px (${Math.round((size.watermark.bandWidth / size.width) * 100)} %) · salida ${getOutputResolution()} px lado mayor`;
            setMessage("Vista previa actualizada. El original no se modifica.");
        } catch (error) {
            previewCanvas.hidden = true;
            previewEmpty.hidden = false;
            previewMeta.textContent = error.message;
            exportButton.disabled = true;
        }
    };

    const refreshPanel = () => {
        const validIds = new Set(getPhotos().map((photo) => photo.id));
        Array.from(selectedPhotoIds).forEach((photoId) => {
            if (!validIds.has(photoId)) {
                selectedPhotoIds.delete(photoId);
            }
        });
        renderImageOptions();
        renderSelectedList();
        schedulePreviewRender();
    };

    const exportWatermarkedPhotos = async () => {
        const targets = getTargetPhotos();
        if (targets.length === 0) {
            setMessage("No hay fotografías disponibles para exportar.", "error");
            return;
        }
        exportButton.disabled = true;
        setMessage(`Generando ${targets.length} JPG con marca de agua...`, "warning");
        try {
            for (const photo of targets) {
                const blob = await buildExportBlob(photo);
                const filename = `${normalizeFilename(photo.name)}_marca_${getSettings().resolution}px.jpg`;
                downloadBlob(blob, filename);
            }
            setMessage(`${targets.length} JPG generado(s). Las fotografías originales permanecen intactas.`, "success");
        } catch (error) {
            setMessage(error.message || "No fue posible generar la marca de agua.", "error");
        } finally {
            exportButton.disabled = false;
            schedulePreviewRender();
        }
    };

    const preloadCoverageFields = () => {
        agencyField.value = watermarkPanel.dataset.agency || "Xinhua";
        photographerField.value = watermarkPanel.dataset.photographer || "";
    };

    preloadCoverageFields();
    syncCustomResolution();
    refreshPanel();

    const syncCompactControlLabels = () => {
        opacityValue.textContent = `${Number(opacityField.value) || 0} %`;
        bandColorValue.textContent = bandColorField.value.toUpperCase();
        textColorValue.textContent = textColorField.value.toUpperCase();
    };

    syncCompactControlLabels();

    [agencyField, photographerField, resolutionSelect, customResolutionField, positionField, opacityField, bandColorField, textColorField, preserveExifField, preserveIptcField, preserveIccField].forEach((field) => {
        field.addEventListener("input", () => {
            syncCompactControlLabels();
            schedulePreviewRender();
        });
        field.addEventListener("change", () => {
            syncCustomResolution();
            syncCompactControlLabels();
            schedulePreviewRender();
        });
    });
    imageSelect.addEventListener("change", schedulePreviewRender);
    exportButton.addEventListener("click", exportWatermarkedPhotos);
    selectAllButton.addEventListener("click", () => {
        getPhotos().forEach((photo) => selectedPhotoIds.add(photo.id));
        renderSelectedList();
    });
    clearSelectionButton.addEventListener("click", () => {
        selectedPhotoIds.clear();
        renderSelectedList();
    });
    window.addEventListener("atlas:photos-changed", refreshPanel);
}
