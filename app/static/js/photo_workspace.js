const photoWorkspace = document.querySelector(".photo-workspace");
const dropZone = document.getElementById("drop-zone");
const dropZoneMainText = dropZone ? dropZone.querySelector(".drop-main") : null;
const photoInput = document.getElementById("photo-input");
const selectPhotosButton = document.getElementById("select-photos-button");
const photoGrid = document.getElementById("photo-grid");
const photoEmptyMessage = document.getElementById("photo-empty-message");
const totalCount = document.getElementById("photo-total-count");
const selectedCount = document.getElementById("photo-selected-count");
const removeSelectedButton = document.getElementById("remove-selected-photo-button");
const clearSelectionButton = document.getElementById("clear-photo-selection-button");
const selectedPhotoPreview = document.getElementById("selected-photo-preview");
const photoPreviewEmpty = document.getElementById("photo-preview-empty");
const photoUploadMessage = document.getElementById("photo-upload-message");
const photoInfoEmpty = document.getElementById("photo-info-empty");
const photoInfoDetails = document.getElementById("photo-info-details");
const photoInfoName = document.getElementById("photo-info-name");
const photoInfoSize = document.getElementById("photo-info-size");
const photoInfoType = document.getElementById("photo-info-type");
const photoInfoDimensions = document.getElementById("photo-info-dimensions");
const photoInfoCamera = document.getElementById("photo-info-camera");
const photoInfoDate = document.getElementById("photo-info-date");
const photoInfoPhotographer = document.getElementById("photo-info-photographer");
const photoCaptionPreview = document.getElementById("photo-caption-preview");
const captionPhotoCounter = document.getElementById("caption-photo-counter");
const captionPhotoStatusIndicator = document.getElementById("caption-photo-status-indicator");
const captionPrevPhotoButton = document.getElementById("caption-prev-photo-button");
const captionNextPhotoButton = document.getElementById("caption-next-photo-button");
const captionNarrativeField = document.getElementById("caption-narrative-field");
const captionAiButton = document.getElementById("caption-ai-button");
const captionAiContextButton = document.getElementById("caption-ai-context-button");
const captionAiStatus = document.getElementById("caption-ai-status");
const captionReviewStatusField = document.getElementById("caption-review-status-field");
const captionFooterStatus = document.getElementById("caption-footer-status");
const captionCharacterCount = document.getElementById("caption-character-count");
const captionWordCount = document.getElementById("caption-word-count");
const captionFullPreview = document.getElementById("caption-full-preview");
const captionLocationWarning = document.getElementById("caption-location-warning");
const captionSaveStatus = document.getElementById("caption-save-status");
const captionSaveStatusDetail = document.getElementById("caption-save-status-detail");
const initialPhotosScript = document.getElementById("coverage-photos-data");
const photoDeleteDialog = document.getElementById("photo-delete-dialog");
const photoDeleteName = document.getElementById("photo-delete-name");
const cancelPhotoDeleteButton = document.getElementById("cancel-photo-delete-button");
const confirmPhotoDeleteButton = document.getElementById("confirm-photo-delete-button");
const captionAiReplaceDialog = document.getElementById("caption-ai-replace-dialog");
const cancelCaptionAiReplaceButton = document.getElementById("cancel-caption-ai-replace-button");
const confirmCaptionAiReplaceButton = document.getElementById("confirm-caption-ai-replace-button");
const captionAiContextDialog = document.getElementById("caption-ai-context-dialog");
const captionAiContextJson = document.getElementById("caption-ai-context-json");
const closeCaptionAiContextButton = document.getElementById("close-caption-ai-context-button");
const photoViewerDialog = document.getElementById("photo-viewer-dialog");
const photoViewerTitle = document.getElementById("photo-viewer-title");
const photoViewerMeta = document.getElementById("photo-viewer-meta");
const photoViewerZoom = document.getElementById("photo-viewer-zoom");
const photoViewerFitButton = document.getElementById("photo-viewer-fit-button");
const photoViewerActualButton = document.getElementById("photo-viewer-actual-button");
const photoViewerCloseButton = document.getElementById("photo-viewer-close-button");
const photoViewerPrevButton = document.getElementById("photo-viewer-prev-button");
const photoViewerNextButton = document.getElementById("photo-viewer-next-button");
const photoViewerImage = document.getElementById("photo-viewer-image");
const copyCaptionEmptyButton = document.getElementById("copy-caption-empty-button");
const copyCaptionStatus = document.getElementById("copy-caption-status");
const copyCaptionConfirmDialog = document.getElementById("copy-caption-confirm-dialog");
const copyCaptionConfirmMessage = document.getElementById("copy-caption-confirm-message");
const cancelCopyCaptionButton = document.getElementById("cancel-copy-caption-button");
const confirmCopyCaptionButton = document.getElementById("confirm-copy-caption-button");
const createDispatchLink = document.getElementById("create-dispatch-link");
const createDispatchDisabledButton = document.getElementById("create-dispatch-disabled-button");
const createDispatchMessage = document.getElementById("create-dispatch-message");

const selectedPhotos = [];
const captionStatusOptions = ["Sin editar", "En edición", "Revisado", "Aprobado"];
const maxPhotoProcessingConcurrency = 3;
let activePhotoId = null;
let pendingDeletePhotoId = null;
let deleteTriggerButton = null;
let viewerPhotoId = null;
let viewerZoomMode = "fit";
let renderToken = 0;
let dropZoneDragDepth = 0;
let activePhotoProcessingCount = 0;
let queuedPhotoCount = 0;
let completedPhotoCount = 0;
let activeAiGenerationPhotoId = null;
const photoProcessingQueue = [];
const captionRecords = new Map();
const defaultDropZoneMainText = dropZoneMainText ? dropZoneMainText.textContent : "";
const isAiInterfaceEnabled = Boolean(
    photoWorkspace &&
    photoWorkspace.dataset.aiEnabled === "true" &&
    captionAiButton &&
    captionAiContextButton
);

function generatePhotoId() {
    if (
        window.crypto &&
        typeof window.crypto.randomUUID === "function"
    ) {
        return window.crypto.randomUUID();
    }

    return `photo-${Date.now()}-${Math.random()
        .toString(16)
        .slice(2)}`;
}

const formatSize = (bytes) => {
    if (bytes < 1024) {
        return bytes + " B";
    }

    const kb = bytes / 1024;
    if (kb < 1024) {
        return kb.toFixed(1) + " KB";
    }

    return (kb / 1024).toFixed(2) + " MB";
};

const getPhotoThumbnailSource = (photo) => (
    photo.thumbnailDataUrl || photo.objectUrl || photo.dataUrl || photo.mediaUrl || ""
);

const getPhotoPreviewSource = (photo) => (
    photo.objectUrl || photo.dataUrl || photo.thumbnailDataUrl || photo.mediaUrl || ""
);

const getActivePhoto = () => (
    selectedPhotos.find((photo) => photo.id === activePhotoId) || null
);

const getPhotoById = (photoId) => (
    selectedPhotos.find((photo) => photo.id === photoId) || null
);

const getPhotoIndex = (photoId) => (
    selectedPhotos.findIndex((photo) => photo.id === photoId)
);

const emitPhotoWorkspaceChange = () => {
    window.dispatchEvent(new CustomEvent("atlas:photos-changed", {
        detail: {
            activePhotoId,
            total: selectedPhotos.length
        }
    }));
};

window.ATLAS_LENS_PHOTO_API = {
    getPhotos: () => selectedPhotos.map((photo) => ({ ...photo })),
    getActivePhoto: () => {
        const photo = getActivePhoto();
        return photo ? { ...photo } : null;
    },
    getActivePhotoId: () => activePhotoId
};

const getCoverageCaptionData = () => ({
    template: photoWorkspace.dataset.captionTemplate || "xinhua",
    city: photoWorkspace.dataset.captionCity || "",
    country: photoWorkspace.dataset.captionCountry || "",
    date: photoWorkspace.dataset.captionDate || "",
    sendDate: photoWorkspace.dataset.captionSendDate || photoWorkspace.dataset.captionDate || "",
    eventDate: photoWorkspace.dataset.captionEventDate || photoWorkspace.dataset.captionDate || "",
    photographer: photoWorkspace.dataset.captionPhotographer || "",
    agency: photoWorkspace.dataset.captionAgency || "",
    editor: photoWorkspace.dataset.captionEditor || "",
    editorInitials: photoWorkspace.dataset.captionEditorInitials || ""
});

const setElementVisibility = (element, shouldShow) => {
    element.hidden = !shouldShow;
};

const isValidJpeg = (file) => {
    const hasValidExtension = /\.(jpg|jpeg)$/i.test(file.name);
    const hasValidMime = file.type === "image/jpeg" || file.type === "";
    return hasValidExtension && hasValidMime;
};

const readFileAsDataUrl = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(reader.result));
    reader.addEventListener("error", () => reject(reader.error));
    reader.readAsDataURL(file);
});

const readImageDimensions = (source) => new Promise((resolve) => {
    const probeImage = new Image();
    probeImage.addEventListener("load", () => {
        resolve({
            width: probeImage.naturalWidth,
            height: probeImage.naturalHeight
        });
    }, { once: true });
    probeImage.addEventListener("error", () => {
        resolve({ width: null, height: null });
    }, { once: true });
    probeImage.src = source;
});

const loadImageElement = (source) => new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener("load", () => resolve(image), { once: true });
    image.addEventListener("error", () => reject(new Error("Unable to load image.")), { once: true });
    image.src = source;
});

const createThumbnailDataUrl = async (file, objectUrl) => {
    const maxWidth = 420;
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    let source = null;
    let width = null;
    let height = null;

    if (!context) {
        return { thumbnailDataUrl: "", width, height };
    }

    if (typeof window.createImageBitmap === "function") {
        source = await window.createImageBitmap(file);
        width = source.width;
        height = source.height;
    } else {
        source = await loadImageElement(objectUrl);
        width = source.naturalWidth;
        height = source.naturalHeight;
    }

    if (!width || !height) {
        if (source && typeof source.close === "function") {
            source.close();
        }
        return { thumbnailDataUrl: "", width: null, height: null };
    }

    const scale = Math.min(1, maxWidth / width);
    canvas.width = Math.max(1, Math.round(width * scale));
    canvas.height = Math.max(1, Math.round(height * scale));
    context.drawImage(source, 0, 0, canvas.width, canvas.height);

    if (source && typeof source.close === "function") {
        source.close();
    }

    return {
        thumbnailDataUrl: canvas.toDataURL("image/jpeg", 0.82),
        width,
        height
    };
};

const normalizeInitialPhoto = (photo) => ({
    id: photo.id,
    name: photo.name,
    size: Number(photo.size) || 0,
    type: photo.type || "image/jpeg",
    width: photo.width || null,
    height: photo.height || null,
    dataUrl: photo.data_url || photo.dataUrl || "",
    thumbnailDataUrl: photo.thumbnail_data_url || photo.thumbnailDataUrl || photo.data_url || photo.dataUrl || photo.media_url || photo.mediaUrl || "",
    mediaUrl: photo.media_url || photo.mediaUrl || "",
    objectUrl: null,
    lastModified: photo.lastModified || null,
    camera: photo.camera || photo.source || "",
    photographer: photo.photographer || "",
    eventDate: photo.event_date || photo.eventDate || "",
    receivedAt: photo.received_at || photo.receivedAt || "",
    capturedAt: photo.captured_at || photo.capturedAt || "",
    sourceFile: null,
    importStatus: "Lista",
    processingError: "",
    captionNarrative: photo.caption_narrative || photo.captionNarrative || "",
    captionStatus: photo.caption_status || photo.captionStatus || "Sin editar"
});

const serializePhotoForServer = (photo) => ({
    id: photo.id,
    name: photo.name,
    size: photo.size,
    type: photo.type || "image/jpeg",
    width: photo.width,
    height: photo.height,
    data_url: photo.dataUrl,
    caption_narrative: photo.captionNarrative || "",
    caption_status: photo.captionStatus || "Sin editar"
});

const buildPhotoDeleteUrl = (photoId) => (
    photoWorkspace.dataset.photoDeleteUrlTemplate.replace("__PHOTO_ID__", encodeURIComponent(photoId))
);

const buildPhotoCaptionUrl = (photoId) => (
    photoWorkspace.dataset.photoCaptionUrlTemplate.replace("__PHOTO_ID__", encodeURIComponent(photoId))
);

const buildPhotoAiUrl = (photoId) => (
    photoWorkspace.dataset.photoAiUrlTemplate
        ? photoWorkspace.dataset.photoAiUrlTemplate.replace("__PHOTO_ID__", encodeURIComponent(photoId))
        : ""
);

const buildPhotoAiContextUrl = (photoId) => (
    photoWorkspace.dataset.photoAiContextUrlTemplate
        ? photoWorkspace.dataset.photoAiContextUrlTemplate.replace("__PHOTO_ID__", encodeURIComponent(photoId))
        : ""
);

const wait = (durationMs) => new Promise((resolve) => {
    window.setTimeout(resolve, durationMs);
});

const persistPhoto = async (photo) => {
    const response = await fetch(photoWorkspace.dataset.photosUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(serializePhotoForServer(photo))
    });

    if (!response.ok) {
        let errorMessage = "No se pudo guardar la fotografía en ATLAS.";
        try {
            const payload = await response.json();
            if (payload && payload.error) {
                errorMessage = payload.error;
            }
        } catch (error) {
            void error;
        }
        throw new Error(errorMessage);
    }

    return response.json();
};

const deletePhotoFromServer = async (photoId) => {
    const response = await fetch(buildPhotoDeleteUrl(photoId), {
        method: "POST"
    });

    if (!response.ok) {
        throw new Error("Unable to delete photo from coverage memory.");
    }

    return response.json();
};

const persistPhotoCaption = async (photoId, record, keepalive = false) => {
    const response = await fetch(buildPhotoCaptionUrl(photoId), {
        method: "POST",
        keepalive,
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            caption_narrative: record.narrative,
            caption_status: record.status
        })
    });

    if (!response.ok) {
        throw new Error("Unable to persist caption in coverage memory.");
    }

    return response.json();
};

const updateDispatchEntryState = (payload) => {
    if (!payload || typeof payload.can_create_dispatch === "undefined") {
        return;
    }

    const canCreateDispatch = Boolean(payload.can_create_dispatch);
    if (createDispatchLink) {
        createDispatchLink.hidden = !canCreateDispatch;
    }
    if (createDispatchDisabledButton) {
        createDispatchDisabledButton.hidden = canCreateDispatch;
    }
    if (createDispatchMessage) {
        createDispatchMessage.hidden = canCreateDispatch;
    }
};

const copyCaptionToEmptyPhotos = async (sourcePhotoId, record) => {
    const response = await fetch(photoWorkspace.dataset.copyCaptionUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            source_photo_id: sourcePhotoId,
            caption_narrative: record.narrative,
            caption_status: record.status
        })
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.error || "No fue posible copiar el caption.");
    }

    return payload;
};

const requestAiNarration = async (photoId, options = {}) => {
    const response = await fetch(buildPhotoAiUrl(photoId), {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            simulate_error: Boolean(options.simulateError)
        })
    });
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || !payload.ok) {
        const message = payload.error && payload.error.message
            ? payload.error.message
            : "No fue posible generar la narración. Intenta nuevamente.";
        throw new Error(message);
    }

    return payload;
};

const requestAiContext = async (photoId) => {
    const response = await fetch(buildPhotoAiContextUrl(photoId));
    const payload = await response.json().catch(() => ({}));

    if (!response.ok || !payload.ok) {
        throw new Error("No fue posible cargar el contexto IA.");
    }

    return payload.context || {};
};

const createIcon = (type) => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("aria-hidden", "true");

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("stroke", "currentColor");
    path.setAttribute("stroke-width", "1.8");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");

    if (type === "caption") {
        path.setAttribute("d", "m4 16.5-.5 4 4-.5L18.7 8.8a2.1 2.1 0 0 0-3-3L4 16.5Z");
        const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
        line.setAttribute("d", "m13.8 7.7 2.5 2.5");
        line.setAttribute("stroke", "currentColor");
        line.setAttribute("stroke-width", "1.8");
        line.setAttribute("stroke-linecap", "round");
        svg.append(path, line);
        return svg;
    }

    if (type === "review") {
        path.setAttribute("d", "M10.8 17.1a6.3 6.3 0 1 1 0-12.6 6.3 6.3 0 0 1 0 12.6ZM15.5 15.5 20 20");
        svg.appendChild(path);
        return svg;
    }

    path.setAttribute("d", "M6 6 18 18M18 6 6 18");
    svg.appendChild(path);
    return svg;
};

const createIconButton = (label, type, onClick) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "photo-thumb-action";
    button.setAttribute("aria-label", label);
    button.appendChild(createIcon(type));
    button.addEventListener("click", (event) => {
        event.stopPropagation();
        onClick(button);
    });
    return button;
};

const updateCounters = () => {
    totalCount.textContent = `Total: ${selectedPhotos.length}`;
    selectedCount.textContent = `Seleccionadas: ${activePhotoId ? 1 : 0}`;
    removeSelectedButton.disabled = activePhotoId === null;
    photoEmptyMessage.hidden = selectedPhotos.length > 0;
};

const clearPreview = () => {
    selectedPhotoPreview.hidden = true;
    selectedPhotoPreview.removeAttribute("src");
    selectedPhotoPreview.alt = "";
    photoPreviewEmpty.hidden = false;
};

const renderPhotoInfo = (photo) => {
    const dimensions = photo.width && photo.height
        ? `${photo.width} x ${photo.height} px`
        : "Dimensiones no disponibles";

    photoInfoName.textContent = photo.name;
    photoInfoSize.textContent = formatSize(photo.size);
    photoInfoType.textContent = photo.type || "image/jpeg";
    photoInfoDimensions.textContent = dimensions;
    photoInfoCamera.textContent = photo.camera || "Sin cámara";
    photoInfoDate.textContent = photo.capturedAt || photo.receivedAt || photo.eventDate || "Sin fecha";
    photoInfoPhotographer.textContent = photo.photographer || getCoverageCaptionData().photographer || "Sin fotógrafo";

    photoInfoEmpty.hidden = true;
    setElementVisibility(photoInfoDetails, true);
    setElementVisibility(photoCaptionPreview, true);
    renderCaptionEditor(photo);
};

const clearPhotoInfo = () => {
    photoInfoEmpty.hidden = false;
    setElementVisibility(photoInfoDetails, false);
    setElementVisibility(photoCaptionPreview, false);
    photoInfoName.textContent = "";
    photoInfoSize.textContent = "";
    photoInfoType.textContent = "";
    photoInfoDimensions.textContent = "";
    photoInfoCamera.textContent = "";
    photoInfoDate.textContent = "";
    photoInfoPhotographer.textContent = "";
    clearCaptionEditor();
};

const renderPreview = (photo) => {
    selectedPhotoPreview.src = getPhotoPreviewSource(photo);
    selectedPhotoPreview.alt = `Vista previa de ${photo.name}`;
    selectedPhotoPreview.hidden = false;
    photoPreviewEmpty.hidden = true;
};

const renderSelectionState = () => {
    const activePhoto = getActivePhoto();

    if (!activePhoto) {
        clearPreview();
        clearPhotoInfo();
        return;
    }

    renderPreview(activePhoto);
    renderPhotoInfo(activePhoto);
};

const selectPhoto = (photoId) => {
    if (activePhotoId !== null && activePhotoId !== photoId) {
        autosaveCaption(activePhotoId);
    }

    activePhotoId = photoId;
    renderSelectionState();
    updateCounters();
    photoGrid.querySelectorAll(".photo-grid-item").forEach((item) => {
        const isActive = item.dataset.photoId === activePhotoId;
        item.classList.toggle("is-active", isActive);
        item.setAttribute("aria-selected", String(isActive));
    });
    scrollActiveThumbnailIntoView();
};

const moveActivePhoto = (direction) => {
    const currentIndex = getPhotoIndex(activePhotoId);
    if (currentIndex === -1 || selectedPhotos.length === 0) {
        return;
    }

    const nextIndex = (currentIndex + direction + selectedPhotos.length) % selectedPhotos.length;
    selectPhoto(selectedPhotos[nextIndex].id);
};

const scrollActiveThumbnailIntoView = () => {
    if (activePhotoId === null) {
        return;
    }

    const activeItem = photoGrid.querySelector(`.photo-grid-item[data-photo-id="${CSS.escape(activePhotoId)}"]`);
    if (!activeItem) {
        return;
    }

    activeItem.scrollIntoView({
        block: "nearest",
        inline: "nearest"
    });
};

const spanishMonths = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre"
];

const referenceCountries = (
    window.ATLAS_EDITORIAL_REFERENCE &&
    window.ATLAS_EDITORIAL_REFERENCE.countries
) || {};

const resolveLocationPhrase = (city, country) => {
    const safeCity = city || "Ciudad pendiente";
    const safeCountry = country || "País pendiente";
    const validation = (
        window.ATLAS_EDITORIAL_REFERENCE &&
        typeof window.ATLAS_EDITORIAL_REFERENCE.validate_city_country === "function"
    )
        ? window.ATLAS_EDITORIAL_REFERENCE.validate_city_country(safeCity, safeCountry)
        : {
            is_capital: false,
            city_country_warning: ""
        };
    const isCapital = Boolean(validation.is_capital);

    return {
        text: isCapital
            ? `en ${safeCity}, capital de ${safeCountry},`
            : `en ${safeCity}, en ${safeCountry},`,
        isCapital,
        warning: Boolean(validation.city_country_warning),
        warningText: validation.city_country_warning || ""
    };
};

const parseCoverageDate = (dateValue) => {
    const [year, month, day] = (dateValue || "").split("-").map(Number);
    if (!year || !month || !day) {
        return null;
    }

    return { year, month, day };
};

const formatXinhuaShortDate = (dateValue) => {
    const date = parseCoverageDate(dateValue);
    if (!date) {
        return "fecha pendiente";
    }

    return `${date.day} ${spanishMonths[date.month - 1]}, ${date.year}`;
};

const formatXinhuaLongDate = (dateValue) => {
    const date = parseCoverageDate(dateValue);
    if (!date) {
        return "fecha pendiente";
    }

    return `${date.day} de ${spanishMonths[date.month - 1]} de ${date.year}`;
};

const formatXinhuaCode = (dateValue) => {
    const date = parseCoverageDate(dateValue);
    if (!date) {
        return "000000";
    }

    return [
        String(date.year).slice(-2),
        String(date.month).padStart(2, "0"),
        String(date.day).padStart(2, "0")
    ].join("");
};

const areCoverageDatesEqual = (firstDateValue, secondDateValue) => (
    formatXinhuaCode(firstDateValue) === formatXinhuaCode(secondDateValue)
);

const buildEditorInitials = (editorName) => {
    const normalizedSource = (editorName || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[()]/g, " ")
        .replace(/[^A-Za-z\s]/g, " ")
        .replace(/\s+/g, " ")
        .trim()

    const parts = normalizedSource.split(/\s+/).filter(Boolean);

    if (parts.length === 1 && /^[A-Za-z]{1,4}$/.test(parts[0])) {
        return parts[0].toLowerCase();
    }

    const initials = parts
        .map((part) => part[0])
        .join("")
        .toLowerCase();

    return initials || "xx";
};

const normalizeNarrative = (narrative) => {
    const cleanNarrative = (narrative || "")
        .trim()
        .replace(/\s+/g, " ")
        .replace(/\s+([,.;:])/g, "$1")
        .replace(/([,.;:]){2,}/g, "$1");

    if (!cleanNarrative) {
        return "[NARRACIÓN]";
    }

    return cleanNarrative.replace(/[.,\s]+$/g, "");
};

const lowerFirstLetter = (value) => (
    value
        ? value.charAt(0).toLowerCase() + value.slice(1)
        : value
);

const buildEventDateNarrative = (eventDate, narrative) => {
    const cleanNarrative = narrative.replace(/^[.,;:\s]+/g, "");
    const articleMatch = cleanNarrative.match(/^(el|la|los|las)\s+(.+)$/i);

    if (articleMatch) {
        const article = articleMatch[1].toLowerCase();
        const body = lowerFirstLetter(articleMatch[2]);
        const connector = article === "el" ? "del" : `de ${article}`;
        return `Imagen del ${eventDate} ${connector} ${body}`;
    }

    const prepositionMatch = cleanNarrative.match(/^(de|del|de la|de los|de las)\s+(.+)$/i);
    if (prepositionMatch) {
        return `Imagen del ${eventDate} ${lowerFirstLetter(cleanNarrative)}`;
    }

    return `Imagen del ${eventDate} de ${cleanNarrative}`;
};

const cleanCaptionString = (caption) => (
    caption
        .replace(/\s+/g, " ")
        .replace(/\s+([,.;:])/g, "$1")
        .replace(/,\s*,+/g, ",")
        .replace(/\.\s*\.+/g, ".")
        .replace(/:\s*:+/g, ":")
        .replace(/,\s*\./g, ".")
        .trim()
);

const captionTemplates = {
    xinhua: {
        buildContext(context) {
            const city = context.city || "Ciudad pendiente";
            const country = context.country || "País pendiente";
            const sendDate = context.sendDate || context.date;
            const eventDate = context.eventDate || context.date;
            const agency = context.agency || "Xinhua";
            const credit = `${agency}/${context.photographer || "Fotógrafo pendiente"}`;
            const editorInitials = buildEditorInitials(context.editorInitials || context.editor);
            const location = resolveLocationPhrase(city, country);
            const usesSameDate = areCoverageDatesEqual(sendDate, eventDate);

            return {
                header: `(${formatXinhuaCode(sendDate)}) -- ${city.toUpperCase()}, ${formatXinhuaShortDate(sendDate)} (${agency}) --`,
                city,
                country,
                sendDate: formatXinhuaLongDate(sendDate),
                eventDate: formatXinhuaLongDate(eventDate),
                usesSameDate,
                credit,
                editorInitials,
                location
            };
        },
        generate(context, photo, narrative) {
            const blocks = this.buildContext(context, photo);
            const cleanNarrative = normalizeNarrative(narrative);
            const narrativeText = blocks.usesSameDate
                ? cleanNarrative
                : buildEventDateNarrative(blocks.eventDate, cleanNarrative);
            const dateClause = blocks.usesSameDate
                ? ` el ${blocks.sendDate}`
                : "";
            const caption = `${blocks.header} ${narrativeText}, ${blocks.location.text}${dateClause}. (${blocks.credit}) (${blocks.editorInitials})`;

            return cleanCaptionString(caption);
        }
    }
};

const getCaptionTemplate = (templateName) => (
    captionTemplates[templateName] || captionTemplates.xinhua
);

const buildCaptionPreview = (photo, narrative) => {
    const coverage = getCoverageCaptionData();
    return getCaptionTemplate(coverage.template).generate(coverage, photo, narrative);
};

const getCurrentLocationValidation = () => {
    const coverage = getCoverageCaptionData();
    const blocks = getCaptionTemplate(coverage.template).buildContext(coverage);
    return blocks.location;
};

const createCaptionRecord = (photo = {}) => ({
    narrative: photo.captionNarrative || "",
    status: captionStatusOptions.includes(photo.captionStatus) ? photo.captionStatus : "Sin editar",
    savedNarrative: photo.captionNarrative || "",
    savedStatus: captionStatusOptions.includes(photo.captionStatus) ? photo.captionStatus : "Sin editar"
});

const getCaptionRecord = (photoId) => {
    if (!captionRecords.has(photoId)) {
        captionRecords.set(photoId, createCaptionRecord(getPhotoById(photoId) || {}));
    }

    return captionRecords.get(photoId);
};

const hasCaptionContent = (photoId) => {
    if (photoId === null || photoId === undefined) {
        return false;
    }

    const record = getCaptionRecord(photoId);
    return Boolean(record.narrative.trim());
};

const setCopyCaptionStatus = (message = "", status = "idle") => {
    if (!copyCaptionStatus) {
        return;
    }

    copyCaptionStatus.textContent = message;
    copyCaptionStatus.dataset.status = status;
};

const getEmptyCaptionTargets = (sourcePhotoId) => (
    selectedPhotos.filter((photo) => photo.id !== sourcePhotoId && !hasCaptionContent(photo.id))
);

const updatePhotoCaptionBadge = (photoId) => {
    if (photoId === null || photoId === undefined) {
        return;
    }

    const card = photoGrid.querySelector(`.photo-grid-item[data-photo-id="${CSS.escape(photoId)}"]`);
    if (!card) {
        return;
    }

    const hasCaption = hasCaptionContent(photoId);
    card.classList.toggle("has-caption", hasCaption);

    const statusPill = card.querySelector(".photo-status-pill");
    if (!statusPill) {
        return;
    }

    statusPill.hidden = !hasCaption;
    statusPill.textContent = hasCaption ? "CAPTION" : "";
    statusPill.dataset.status = hasCaption ? "CAPTION" : "empty";
};

const setSaveStatus = (status) => {
    const labels = {
        dirty: "● Sin guardar",
        saving: "Guardando...",
        saved: "✓ Guardado"
    };
    const label = labels[status] || labels.saved;

    captionSaveStatus.textContent = label;
    captionSaveStatusDetail.textContent = label;
    captionSaveStatus.dataset.status = status;
    captionSaveStatusDetail.dataset.status = status;
};

const setAiStatus = (message = "", status = "idle") => {
    if (!captionAiStatus) {
        return;
    }

    captionAiStatus.textContent = message;
    captionAiStatus.dataset.status = status;
};

const setAiButtonState = (label, disabled = false) => {
    if (!captionAiButton || !captionAiContextButton) {
        return;
    }

    captionAiButton.textContent = label;
    captionAiButton.disabled = disabled;
    captionAiContextButton.disabled = activePhotoId === null;
};

const showAiContext = async () => {
    if (!isAiInterfaceEnabled) {
        return;
    }

    const photo = getActivePhoto();
    if (!photo) {
        return;
    }

    captionAiContextButton.disabled = true;
    captionAiContextJson.textContent = "Cargando contexto IA...";

    try {
        const context = await requestAiContext(photo.id);
        captionAiContextJson.textContent = JSON.stringify(context, null, 2);
    } catch (error) {
        captionAiContextJson.textContent = JSON.stringify({
            ok: false,
            error: "No fue posible cargar el contexto IA."
        }, null, 2);
    } finally {
        captionAiContextButton.disabled = activePhotoId === null;
    }

    if (typeof captionAiContextDialog.showModal === "function") {
        captionAiContextDialog.showModal();
    } else {
        captionAiContextDialog.setAttribute("open", "open");
    }
};

const closeAiContext = () => {
    if (!captionAiContextDialog) {
        return;
    }

    if (typeof captionAiContextDialog.close === "function") {
        captionAiContextDialog.close();
    } else {
        captionAiContextDialog.removeAttribute("open");
    }
};

const hasUnsavedCaption = (record) => (
    record.narrative !== record.savedNarrative || record.status !== record.savedStatus
);

const autosaveCaption = async (photoId = activePhotoId) => {
    if (photoId === null || !captionRecords.has(photoId)) {
        return;
    }

    const record = getCaptionRecord(photoId);
    if (!hasUnsavedCaption(record)) {
        setSaveStatus("saved");
        return;
    }

    if (photoId === activePhotoId) {
        setSaveStatus("saving");
    }

    let payload = null;
    try {
        payload = await persistPhotoCaption(photoId, record);
    } catch (error) {
        if (photoId === activePhotoId) {
            setSaveStatus("dirty");
        }
        return;
    }

    const photo = getPhotoById(photoId);
    if (photo) {
        photo.captionNarrative = record.narrative;
        photo.captionStatus = record.status;
    }

    record.savedNarrative = record.narrative;
    record.savedStatus = record.status;

    if (photoId === activePhotoId) {
        setSaveStatus("saved");
    }
    updateDispatchEntryState(payload);
};

const updateCaptionTextCounters = () => {
    const narrative = captionNarrativeField.value.trim();
    const characterCount = captionNarrativeField.value.length;
    const wordCount = narrative ? narrative.split(/\s+/).length : 0;

    captionCharacterCount.textContent = `${characterCount} caracteres`;
    captionWordCount.textContent = `${wordCount} palabras`;
};

const updateCaptionPhotoNavigation = () => {
    const activeIndex = getPhotoIndex(activePhotoId);
    const hasPhotos = selectedPhotos.length > 0;
    const labelIndex = activeIndex === -1 ? 0 : activeIndex + 1;
    const record = activePhotoId === null ? null : getCaptionRecord(activePhotoId);
    const status = record ? record.status : "Sin editar";

    captionPhotoCounter.textContent = `Foto ${labelIndex} de ${selectedPhotos.length}`;
    captionPhotoStatusIndicator.textContent = status;
    captionPhotoStatusIndicator.dataset.status = status;
    captionFooterStatus.textContent = status;
    updatePhotoCaptionBadge(activePhotoId);
    captionPrevPhotoButton.disabled = !hasPhotos || selectedPhotos.length < 2;
    captionNextPhotoButton.disabled = !hasPhotos || selectedPhotos.length < 2;
};

const renderCaptionPreview = (photo = getActivePhoto()) => {
    const location = getCurrentLocationValidation();

    captionFullPreview.textContent = buildCaptionPreview(photo, captionNarrativeField.value);
    captionLocationWarning.textContent = location.warningText || "";
    captionLocationWarning.hidden = !location.warning;
};

const bindCoverageCaptionMetadataUpdates = () => {
    const editCityField = document.getElementById("edit_city");
    const editCountryField = document.getElementById("edit_country");

    const syncCaptionMetadata = () => {
        if (editCityField) {
            photoWorkspace.dataset.captionCity = editCityField.value;
        }
        if (editCountryField) {
            photoWorkspace.dataset.captionCountry = editCountryField.value;
        }
        renderCaptionPreview();
    };

    editCityField?.addEventListener("input", syncCaptionMetadata);
    editCountryField?.addEventListener("change", syncCaptionMetadata);
};

const confirmAiNarrationReplacement = () => new Promise((resolve) => {
    if (!isAiInterfaceEnabled || !captionAiReplaceDialog) {
        resolve(false);
        return;
    }

    let isResolved = false;
    const cleanup = (shouldReplace) => {
        if (isResolved) {
            return;
        }
        isResolved = true;
        cancelCaptionAiReplaceButton.removeEventListener("click", handleCancel);
        confirmCaptionAiReplaceButton.removeEventListener("click", handleConfirm);
        captionAiReplaceDialog.removeEventListener("close", handleClose);
        resolve(shouldReplace);
    };
    const handleCancel = () => {
        captionAiReplaceDialog.close();
        cleanup(false);
    };
    const handleConfirm = () => {
        captionAiReplaceDialog.close();
        cleanup(true);
    };
    const handleClose = () => cleanup(false);

    if (typeof captionAiReplaceDialog.showModal !== "function") {
        resolve(window.confirm("Esta fotografía ya tiene una narración. ¿Deseas reemplazarla con una nueva propuesta generada por IA?"));
        return;
    }

    cancelCaptionAiReplaceButton.addEventListener("click", handleCancel, { once: true });
    confirmCaptionAiReplaceButton.addEventListener("click", handleConfirm, { once: true });
    captionAiReplaceDialog.addEventListener("close", handleClose, { once: true });
    captionAiReplaceDialog.showModal();
});

const applyAiNarration = async (photoId, narration) => {
    const record = getCaptionRecord(photoId);
    record.narrative = narration;
    record.status = "En edición";

    const photo = getPhotoById(photoId);
    if (photo) {
        photo.captionNarrative = narration;
        photo.captionStatus = "En edición";
    }

    updatePhotoCaptionBadge(photoId);

    if (activePhotoId === photoId) {
        captionNarrativeField.value = narration;
        captionReviewStatusField.value = "En edición";
        updateCaptionTextCounters();
        renderCaptionPreview(photo);
        updateCaptionPhotoNavigation();
        setSaveStatus("dirty");
    }

    await autosaveCaption(photoId);
};

const generateNarrationWithAi = async (options = {}) => {
    if (!isAiInterfaceEnabled) {
        return;
    }

    const photo = getActivePhoto();
    if (!photo || activeAiGenerationPhotoId !== null) {
        return;
    }

    const photoId = photo.id;
    const record = getCaptionRecord(photoId);
    const hasExistingNarration = record.narrative.trim() || captionNarrativeField.value.trim();

    if (hasExistingNarration) {
        const shouldReplace = await confirmAiNarrationReplacement();
        if (!shouldReplace) {
            setAiStatus("Generación cancelada.");
            setAiButtonState("Generar con IA");
            return;
        }
    }

    activeAiGenerationPhotoId = photoId;
    setAiStatus("Analizando fotografía...");
    setAiButtonState("Analizando...", true);

    try {
        await wait(320);
        setAiStatus("Generando narración...");
        setAiButtonState("Generando...", true);
        const payload = await requestAiNarration(photoId, options);
        await applyAiNarration(photoId, payload.narration);
        setAiStatus("Narración generada. Revisa el texto antes de guardar.");
        setAiButtonState("Generar nuevamente");
    } catch (error) {
        setAiStatus("No fue posible generar la narración. Intenta nuevamente.", "error");
        setAiButtonState("Reintentar");
    } finally {
        activeAiGenerationPhotoId = null;
        if (captionAiButton) {
            captionAiButton.disabled = getActivePhoto() === null;
        }
    }
};

const syncCaptionRecordFromFields = () => {
    if (activePhotoId === null) {
        return;
    }

    const record = getCaptionRecord(activePhotoId);
    record.narrative = captionNarrativeField.value;
    record.status = captionReviewStatusField.value;
    updateCaptionPhotoNavigation();
    setSaveStatus(hasUnsavedCaption(record) ? "dirty" : "saved");
};

const renderCaptionEditor = (photo) => {
    const record = getCaptionRecord(photo.id);
    captionNarrativeField.value = record.narrative;
    captionReviewStatusField.value = captionStatusOptions.includes(record.status)
        ? record.status
        : "Sin editar";
    captionNarrativeField.disabled = false;
    captionReviewStatusField.disabled = false;
    setAiStatus("");
    setAiButtonState(
        activeAiGenerationPhotoId === photo.id ? "Generando..." : "Generar con IA",
        Boolean(activeAiGenerationPhotoId)
    );
    updateCaptionTextCounters();
    renderCaptionPreview(photo);
    updateCaptionPhotoNavigation();
    setSaveStatus(hasUnsavedCaption(record) ? "dirty" : "saved");
};

const clearCaptionEditor = () => {
    captionNarrativeField.value = "";
    captionNarrativeField.disabled = true;
    setAiStatus("");
    setAiButtonState("Generar con IA", true);
    captionReviewStatusField.value = "Sin editar";
    captionReviewStatusField.disabled = true;
    captionLocationWarning.hidden = true;
    captionFullPreview.textContent = "";
    updateCaptionTextCounters();
    updateCaptionPhotoNavigation();
    setSaveStatus("saved");
};

const createSkeletonCard = () => {
    const card = document.createElement("div");
    card.className = "photo-grid-skeleton";
    card.setAttribute("aria-hidden", "true");
    card.innerHTML = "<span></span><span></span><span></span>";
    return card;
};

const showSkeletonCards = (count) => {
    photoGrid.innerHTML = "";
    const skeletonCount = Math.min(Math.max(count, 6), 18);
    const fragment = document.createDocumentFragment();

    for (let index = 0; index < skeletonCount; index += 1) {
        fragment.appendChild(createSkeletonCard());
    }

    photoGrid.appendChild(fragment);
};

const createPhotoThumbnailError = () => {
    const errorPlaceholder = document.createElement("span");
    errorPlaceholder.className = "photo-grid-placeholder";
    errorPlaceholder.textContent = "No se pudo cargar la miniatura";
    return errorPlaceholder;
};

const createPhotoCard = (item) => {
    const card = document.createElement("article");
    const isActive = item.id === activePhotoId;

    card.className = "photo-grid-item";
    card.setAttribute("role", "option");
    card.setAttribute("aria-selected", String(isActive));
    card.dataset.photoId = item.id;
    card.classList.toggle("is-active", isActive);

    const selectButton = document.createElement("button");
    selectButton.type = "button";
    selectButton.className = "photo-thumb-select";
    selectButton.setAttribute("aria-label", `Seleccionar ${item.name}`);

    const thumbnailWrap = document.createElement("span");
    thumbnailWrap.className = "photo-grid-thumb-wrap";

    const thumbnailSource = getPhotoThumbnailSource(item);
    const thumbnail = thumbnailSource
        ? document.createElement("img")
        : document.createElement("span");
    thumbnail.className = thumbnailSource
        ? "photo-grid-thumb"
        : "photo-grid-placeholder";

    if (thumbnailSource) {
        thumbnail.src = thumbnailSource;
        thumbnail.alt = `Miniatura de ${item.name}`;
        thumbnail.loading = "lazy";
        thumbnail.addEventListener("error", () => {
            thumbnail.replaceWith(createPhotoThumbnailError());
        }, { once: true });
    } else {
        thumbnail.textContent = item.processingError || "Miniatura no disponible";
    }

    const status = document.createElement("span");
    const hasCaption = hasCaptionContent(item.id);
    card.classList.toggle("has-caption", hasCaption);
    status.className = "photo-status-pill";
    status.textContent = hasCaption ? "CAPTION" : "";
    status.dataset.status = hasCaption ? "CAPTION" : "empty";
    status.hidden = !hasCaption;

    const actions = document.createElement("span");
    actions.className = "photo-thumb-actions";
    actions.append(
        createIconButton("Editar caption", "caption", () => {
            selectPhoto(item.id);
            focusCaptionField();
        }),
        createIconButton("Revisar fotografía", "review", () => {
            openViewer(item.id);
        }),
        createIconButton("Eliminar fotografía", "delete", (button) => {
            openDeleteDialog(item.id, button);
        })
    );

    thumbnailWrap.append(thumbnail, status, actions);

    const name = document.createElement("span");
    name.className = "photo-grid-name";
    name.textContent = item.name;

    const size = document.createElement("span");
    size.className = "photo-grid-size";
    size.textContent = formatSize(item.size);

    selectButton.append(thumbnailWrap, name, size);
    selectButton.addEventListener("click", () => {
        selectPhoto(item.id);
    });

    card.appendChild(selectButton);
    return card;
};

const renderPhotoGridProgressively = () => {
    renderToken += 1;
    const currentToken = renderToken;
    const photos = [...selectedPhotos];
    const batchSize = 8;
    let cursor = 0;

    showSkeletonCards(photos.length);

    const renderBatch = () => {
        if (currentToken !== renderToken) {
            return;
        }

        if (cursor === 0) {
            photoGrid.innerHTML = "";
        }

        const fragment = document.createDocumentFragment();
        const batch = photos.slice(cursor, cursor + batchSize);
        batch.forEach((photo) => {
            fragment.appendChild(createPhotoCard(photo));
        });
        photoGrid.appendChild(fragment);
        scrollActiveThumbnailIntoView();
        cursor += batch.length;

        if (cursor < photos.length) {
            window.requestAnimationFrame(renderBatch);
        }
    };

    if (photos.length === 0) {
        photoGrid.innerHTML = "";
        return;
    }

    renderBatch();
};

const renderWorkspace = () => {
    updateCounters();
    renderSelectionState();
    renderPhotoGridProgressively();
    setCopyCaptionStatus();
    emitPhotoWorkspaceChange();
};

const runCopyCaptionToEmptyPhotos = async () => {
    if (!copyCaptionEmptyButton || activePhotoId === null) {
        setCopyCaptionStatus("Seleccione una fotografía con caption para copiar.", "error");
        return;
    }

    syncCaptionRecordFromFields();
    const sourceRecord = getCaptionRecord(activePhotoId);
    if (!sourceRecord.narrative.trim()) {
        setCopyCaptionStatus("La fotografía seleccionada no tiene caption para copiar.", "error");
        return;
    }

    const targets = getEmptyCaptionTargets(activePhotoId);
    if (targets.length === 0) {
        setCopyCaptionStatus("No hay fotografías sin caption para completar.", "saved");
        return;
    }

    const message = `Se copiará este caption a ${targets.length} fotografía${targets.length === 1 ? "" : "s"} que aún no tienen caption.`;
    copyCaptionConfirmMessage.textContent = message;

    const confirmed = await new Promise((resolve) => {
        const cleanup = () => {
            cancelCopyCaptionButton.removeEventListener("click", cancel);
            confirmCopyCaptionButton.removeEventListener("click", confirm);
            copyCaptionConfirmDialog.removeEventListener("close", close);
        };
        const cancel = () => {
            cleanup();
            if (typeof copyCaptionConfirmDialog.close === "function") {
                copyCaptionConfirmDialog.close();
            } else {
                copyCaptionConfirmDialog.removeAttribute("open");
            }
            resolve(false);
        };
        const confirm = () => {
            cleanup();
            if (typeof copyCaptionConfirmDialog.close === "function") {
                copyCaptionConfirmDialog.close();
            } else {
                copyCaptionConfirmDialog.removeAttribute("open");
            }
            resolve(true);
        };
        const close = () => {
            cleanup();
            resolve(false);
        };

        cancelCopyCaptionButton.addEventListener("click", cancel);
        confirmCopyCaptionButton.addEventListener("click", confirm);
        copyCaptionConfirmDialog.addEventListener("close", close, { once: true });

        if (typeof copyCaptionConfirmDialog.showModal === "function") {
            copyCaptionConfirmDialog.showModal();
        } else {
            copyCaptionConfirmDialog.setAttribute("open", "open");
        }
    });

    if (!confirmed) {
        setCopyCaptionStatus("Copia cancelada.", "idle");
        return;
    }

    copyCaptionEmptyButton.disabled = true;
    setCopyCaptionStatus("Copiando caption...", "saving");

    try {
        await autosaveCaption(activePhotoId);
        const payload = await copyCaptionToEmptyPhotos(activePhotoId, sourceRecord);
        const updatedPhotoIds = payload.updated_photo_ids || [];

        updatedPhotoIds.forEach((photoId) => {
            const record = getCaptionRecord(photoId);
            record.narrative = sourceRecord.narrative;
            record.status = sourceRecord.status;
            record.savedNarrative = sourceRecord.narrative;
            record.savedStatus = sourceRecord.status;

            const photo = getPhotoById(photoId);
            if (photo) {
                photo.captionNarrative = sourceRecord.narrative;
                photo.captionStatus = sourceRecord.status;
            }
            updatePhotoCaptionBadge(photoId);
        });

        setCopyCaptionStatus(`Caption copiado a ${updatedPhotoIds.length} fotografía${updatedPhotoIds.length === 1 ? "" : "s"}.`, "saved");
        emitPhotoWorkspaceChange();
    } catch (error) {
        setCopyCaptionStatus(error.message || "No fue posible copiar el caption.", "error");
    } finally {
        copyCaptionEmptyButton.disabled = false;
    }
};

const focusCaptionField = () => {
    const activePhoto = getActivePhoto();
    if (!activePhoto) {
        return;
    }

    renderPhotoInfo(activePhoto);
    photoCaptionPreview.scrollIntoView({ block: "nearest", behavior: "smooth" });
    captionNarrativeField.focus({ preventScroll: true });
};

const hasDuplicatePhoto = (file) => (
    selectedPhotos.some((photo) => (
        photo.name === file.name
        && photo.size === file.size
        && (
            photo.lastModified === file.lastModified
            || photo.lastModified === null
        )
    ))
);

const buildQueuedPhoto = (file) => {
    const objectUrl = URL.createObjectURL(file);

    return {
        id: generatePhotoId(),
        name: file.name,
        size: file.size,
        type: file.type || "image/jpeg",
        width: null,
        height: null,
        dataUrl: "",
        thumbnailDataUrl: "",
        objectUrl,
        lastModified: file.lastModified,
        sourceFile: file,
        importStatus: "En cola",
        processingError: "",
        captionNarrative: "",
        captionStatus: "Sin editar",
        camera: "",
        photographer: getCoverageCaptionData().photographer || "",
        eventDate: getCoverageCaptionData().eventDate || "",
        receivedAt: "",
        capturedAt: ""
    };
};

const updatePhotoImportStatus = (photo, status, errorMessage = "") => {
    photo.importStatus = status;
    photo.processingError = errorMessage;

    updatePhotoCaptionBadge(photo.id);

    if (activePhotoId === photo.id) {
        renderSelectionState();
    }
};

const refreshImportMessage = () => {
    const pendingCount = queuedPhotoCount + activePhotoProcessingCount;

    if (pendingCount > 0) {
        photoUploadMessage.textContent = `Preparando miniaturas... ${completedPhotoCount} listas · ${pendingCount} en proceso`;
        photoUploadMessage.classList.add("is-visible");
        return;
    }

    if (completedPhotoCount > 0) {
        photoUploadMessage.textContent = `${completedPhotoCount} fotografías listas`;
        photoUploadMessage.classList.add("is-visible");
    }
};

const releasePhotoObjectUrl = (photo) => {
    if (photo.objectUrl) {
        URL.revokeObjectURL(photo.objectUrl);
        photo.objectUrl = null;
    }
};

const processQueuedPhoto = async (photo) => {
    try {
        updatePhotoImportStatus(photo, "Procesando");
        const thumbnail = await createThumbnailDataUrl(photo.sourceFile, photo.objectUrl);
        photo.thumbnailDataUrl = thumbnail.thumbnailDataUrl;
        photo.width = thumbnail.width;
        photo.height = thumbnail.height;
        renderWorkspace();

        updatePhotoImportStatus(photo, "Subiendo");
        photo.dataUrl = await readFileAsDataUrl(photo.sourceFile);
        if (!getPhotoById(photo.id)) {
            releasePhotoObjectUrl(photo);
            return;
        }
        await persistPhoto(photo);
        photo.sourceFile = null;
        releasePhotoObjectUrl(photo);
        updatePhotoImportStatus(photo, "Lista");
        completedPhotoCount += 1;
    } catch (error) {
        updatePhotoImportStatus(photo, "Error", error.message || "No se pudo importar la fotografía.");
    } finally {
        activePhotoProcessingCount = Math.max(activePhotoProcessingCount - 1, 0);
        refreshImportMessage();
        processNextPhotoInQueue();
    }
};

const processNextPhotoInQueue = () => {
    while (
        activePhotoProcessingCount < maxPhotoProcessingConcurrency &&
        photoProcessingQueue.length > 0
    ) {
        const photo = photoProcessingQueue.shift();
        queuedPhotoCount = Math.max(queuedPhotoCount - 1, 0);
        activePhotoProcessingCount += 1;
        refreshImportMessage();
        processQueuedPhoto(photo);
    }
};

const enqueuePhotoProcessing = (photo) => {
    photoProcessingQueue.push(photo);
    queuedPhotoCount += 1;
};

const addFiles = (files) => {
    const incomingFiles = Array.from(files);
    let addedPhotoCount = 0;

    for (const file of incomingFiles) {
        if (!isValidJpeg(file) || hasDuplicatePhoto(file)) {
            continue;
        }

        const photo = buildQueuedPhoto(file);
        selectedPhotos.push(photo);
        getCaptionRecord(photo.id);
        enqueuePhotoProcessing(photo);
        addedPhotoCount += 1;
    }

    if (addedPhotoCount > 0) {
        completedPhotoCount = 0;
        photoUploadMessage.textContent = `${addedPhotoCount} fotografías recibidas · Preparando miniaturas...`;
        photoUploadMessage.classList.add("is-visible");

        if (activePhotoId === null) {
            activePhotoId = selectedPhotos[selectedPhotos.length - addedPhotoCount].id;
        }
    }

    renderWorkspace();
    processNextPhotoInQueue();
};

const setDropZoneDragState = (isDragover) => {
    dropZone.classList.toggle("is-dragover", isDragover);

    if (dropZoneMainText) {
        dropZoneMainText.textContent = isDragover
            ? "Suelta las fotografías para importarlas"
            : defaultDropZoneMainText;
    }
};

const clearDropZoneDragState = () => {
    dropZoneDragDepth = 0;
    setDropZoneDragState(false);
};

const clearSelection = () => {
    autosaveCaption(activePhotoId);
    activePhotoId = null;
    renderSelectionState();
    updateCounters();
    photoGrid.querySelectorAll(".photo-grid-item").forEach((item) => {
        item.classList.remove("is-active");
        item.setAttribute("aria-selected", "false");
    });
};

const openDeleteDialog = (photoId, triggerButton = null) => {
    const photo = getPhotoById(photoId);
    if (!photo) {
        return;
    }

    pendingDeletePhotoId = photoId;
    deleteTriggerButton = triggerButton;
    photoDeleteName.textContent = photo.name;

    if (typeof photoDeleteDialog.showModal === "function") {
        photoDeleteDialog.showModal();
    } else {
        photoDeleteDialog.setAttribute("open", "open");
    }

    cancelPhotoDeleteButton.focus();
};

const closeDeleteDialog = () => {
    if (typeof photoDeleteDialog.close === "function") {
        photoDeleteDialog.close();
    } else {
        photoDeleteDialog.removeAttribute("open");
    }
};

const removePhotoById = async (photoId) => {
    const index = selectedPhotos.findIndex((photo) => photo.id === photoId);
    if (index === -1) {
        if (activePhotoId === photoId) {
            activePhotoId = null;
            renderWorkspace();
        }
        return;
    }

    const photo = selectedPhotos[index];
    const queuedIndex = photoProcessingQueue.findIndex((queuedPhoto) => queuedPhoto.id === photo.id);
    if (queuedIndex !== -1) {
        photoProcessingQueue.splice(queuedIndex, 1);
        queuedPhotoCount = Math.max(queuedPhotoCount - 1, 0);
    }

    if (photo.dataUrl || photo.importStatus === "Lista") {
        try {
            await deletePhotoFromServer(photo.id);
        } catch (error) {
            return;
        }
    }

    if (photo.objectUrl) {
        URL.revokeObjectURL(photo.objectUrl);
    }

    selectedPhotos.splice(index, 1);
    captionRecords.delete(photo.id);

    if (activePhotoId === photo.id) {
        activePhotoId = null;
    }

    if (viewerPhotoId === photo.id) {
        viewerPhotoId = null;
        closeViewer();
    }

    renderWorkspace();
};

const removeActivePhoto = () => {
    if (activePhotoId !== null) {
        openDeleteDialog(activePhotoId, removeSelectedButton);
    }
};

const getViewerPhoto = () => getPhotoById(viewerPhotoId);

const setViewerZoom = (mode) => {
    viewerZoomMode = mode;
    const isActual = mode === "actual";
    photoViewerImage.classList.toggle("is-actual-size", isActual);
    photoViewerZoom.textContent = isActual ? "100%" : "Ajustada";
};

const renderViewerPhoto = () => {
    const photo = getViewerPhoto();
    if (!photo) {
        return;
    }

    const dimensions = photo.width && photo.height
        ? `${photo.width} x ${photo.height} px`
        : "Resolución no disponible";

    photoViewerTitle.textContent = photo.name;
    photoViewerMeta.textContent = dimensions;
    photoViewerImage.src = getPhotoPreviewSource(photo);
    photoViewerImage.alt = `Revisión de ${photo.name}`;
    setViewerZoom(viewerZoomMode);
};

const openViewer = (photoId) => {
    if (!getPhotoById(photoId)) {
        return;
    }

    viewerPhotoId = photoId;
    viewerZoomMode = "fit";
    renderViewerPhoto();

    if (typeof photoViewerDialog.showModal === "function") {
        photoViewerDialog.showModal();
    } else {
        photoViewerDialog.setAttribute("open", "open");
    }

    photoViewerCloseButton.focus();
};

const closeViewer = () => {
    if (typeof photoViewerDialog.close === "function") {
        photoViewerDialog.close();
    } else {
        photoViewerDialog.removeAttribute("open");
    }
};

const moveViewer = (direction) => {
    const currentIndex = getPhotoIndex(viewerPhotoId);
    if (currentIndex === -1 || selectedPhotos.length === 0) {
        return;
    }

    const nextIndex = (currentIndex + direction + selectedPhotos.length) % selectedPhotos.length;
    viewerPhotoId = selectedPhotos[nextIndex].id;
    renderViewerPhoto();
};

const hydrateInitialPhotos = async () => {
    if (!initialPhotosScript) {
        return;
    }

    let initialPhotos = [];

    try {
        initialPhotos = JSON.parse(initialPhotosScript.textContent || "[]");
    } catch (error) {
        initialPhotos = [];
    }

    for (const initialPhoto of initialPhotos) {
        const photo = normalizeInitialPhoto(initialPhoto);

        if ((!photo.width || !photo.height) && photo.dataUrl) {
            const dimensions = await readImageDimensions(photo.dataUrl);
            photo.width = dimensions.width;
            photo.height = dimensions.height;
        }

        selectedPhotos.push(photo);
        getCaptionRecord(photo.id);
    }
};

if (photoWorkspace && dropZone && photoInput && selectPhotosButton) {
    dropZone.addEventListener("dragenter", (event) => {
        event.preventDefault();
        dropZoneDragDepth += 1;
        setDropZoneDragState(true);
    });

    dropZone.addEventListener("dragover", (event) => {
        event.preventDefault();
        setDropZoneDragState(true);
    });

    dropZone.addEventListener("dragleave", (event) => {
        event.preventDefault();
        dropZoneDragDepth = Math.max(dropZoneDragDepth - 1, 0);

        if (dropZoneDragDepth === 0) {
            setDropZoneDragState(false);
        }
    });

    dropZone.addEventListener("drop", (event) => {
        event.preventDefault();
        clearDropZoneDragState();

        if (!event.dataTransfer) {
            return;
        }

        addFiles(event.dataTransfer.files);
    });

    selectPhotosButton.addEventListener("click", () => {
        photoInput.click();
    });

    photoInput.addEventListener("change", () => {
        if (!photoInput.files) {
            return;
        }

        addFiles(photoInput.files);
        photoInput.value = "";
    });

    removeSelectedButton.addEventListener("click", removeActivePhoto);
    clearSelectionButton.addEventListener("click", clearSelection);
    if (copyCaptionEmptyButton) {
        copyCaptionEmptyButton.addEventListener("click", runCopyCaptionToEmptyPhotos);
    }
    captionNarrativeField.addEventListener("input", () => {
        if (activePhotoId === null) {
            return;
        }

        syncCaptionRecordFromFields();
        updatePhotoCaptionBadge(activePhotoId);
        updateCaptionTextCounters();
        renderCaptionPreview();
    });
    if (isAiInterfaceEnabled) {
        captionAiButton.addEventListener("click", (event) => {
            generateNarrationWithAi({ simulateError: event.altKey });
        });
        captionAiContextButton.addEventListener("click", showAiContext);
    }
    captionNarrativeField.addEventListener("blur", () => {
        autosaveCaption(activePhotoId);
    });
    captionReviewStatusField.addEventListener("change", () => {
        if (activePhotoId === null) {
            return;
        }

        syncCaptionRecordFromFields();
        updatePhotoCaptionBadge(activePhotoId);
        autosaveCaption(activePhotoId);
    });
    bindCoverageCaptionMetadataUpdates();
    captionPrevPhotoButton.addEventListener("click", () => moveActivePhoto(-1));
    captionNextPhotoButton.addEventListener("click", () => moveActivePhoto(1));
    cancelPhotoDeleteButton.addEventListener("click", closeDeleteDialog);
    confirmPhotoDeleteButton.addEventListener("click", async () => {
        const photoId = pendingDeletePhotoId;
        closeDeleteDialog();
        pendingDeletePhotoId = null;
        await removePhotoById(photoId);
    });
    if (isAiInterfaceEnabled) {
        closeCaptionAiContextButton.addEventListener("click", closeAiContext);
    }

    photoDeleteDialog.addEventListener("close", () => {
        if (deleteTriggerButton) {
            deleteTriggerButton.focus();
        }
    });

    photoViewerCloseButton.addEventListener("click", closeViewer);
    photoViewerFitButton.addEventListener("click", () => setViewerZoom("fit"));
    photoViewerActualButton.addEventListener("click", () => setViewerZoom("actual"));
    photoViewerPrevButton.addEventListener("click", () => moveViewer(-1));
    photoViewerNextButton.addEventListener("click", () => moveViewer(1));

    photoViewerDialog.addEventListener("click", (event) => {
        if (event.target === photoViewerDialog) {
            closeViewer();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (!photoViewerDialog.open) {
            return;
        }

        if (event.key === "ArrowLeft") {
            event.preventDefault();
            moveViewer(-1);
        }

        if (event.key === "ArrowRight") {
            event.preventDefault();
            moveViewer(1);
        }
    });

    document.addEventListener("keydown", (event) => {
        const isTyping = event.target.matches("input, textarea, select");

        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
            event.preventDefault();
            autosaveCaption(activePhotoId);
            return;
        }

        if (event.key === "Escape" && document.activeElement === captionNarrativeField) {
            event.preventDefault();
            captionNarrativeField.blur();
            return;
        }

        if (photoViewerDialog.open || isTyping || selectedPhotos.length < 2) {
            return;
        }

        if (event.key === "ArrowLeft") {
            event.preventDefault();
            moveActivePhoto(-1);
        }

        if (event.key === "ArrowRight") {
            event.preventDefault();
            moveActivePhoto(1);
        }
    });

    photoGrid.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") {
            return;
        }

        if (event.target.closest(".photo-thumb-action")) {
            return;
        }

        const card = event.target.closest(".photo-grid-item");
        if (!card) {
            return;
        }

        event.preventDefault();
        selectPhoto(card.dataset.photoId);
    });

    window.addEventListener("beforeunload", () => {
        autosaveCaption(activePhotoId);
        captionRecords.forEach((record, photoId) => {
            if (hasUnsavedCaption(record)) {
                persistPhotoCaption(photoId, record, true);
            }
        });
        selectedPhotos.forEach((item) => {
            if (item.objectUrl) {
                URL.revokeObjectURL(item.objectUrl);
            }
        });
    });

    updateCounters();
    showSkeletonCards(8);
    renderSelectionState();
    hydrateInitialPhotos().then(renderWorkspace);
}
