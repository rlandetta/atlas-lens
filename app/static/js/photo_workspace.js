const photoWorkspace = document.querySelector(".photo-workspace");
const dropZone = document.getElementById("drop-zone");
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
const photoCaptionPreview = document.getElementById("photo-caption-preview");
const photoCaptionField = document.getElementById("photo-caption-field");
const initialPhotosScript = document.getElementById("coverage-photos-data");
const photoDeleteDialog = document.getElementById("photo-delete-dialog");
const photoDeleteName = document.getElementById("photo-delete-name");
const cancelPhotoDeleteButton = document.getElementById("cancel-photo-delete-button");
const confirmPhotoDeleteButton = document.getElementById("confirm-photo-delete-button");
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

const selectedPhotos = [];
let activePhotoId = null;
let pendingDeletePhotoId = null;
let deleteTriggerButton = null;
let viewerPhotoId = null;
let viewerZoomMode = "fit";
let renderToken = 0;

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

const getPhotoSource = (photo) => photo.objectUrl || photo.dataUrl;

const getActivePhoto = () => (
    selectedPhotos.find((photo) => photo.id === activePhotoId) || null
);

const getPhotoById = (photoId) => (
    selectedPhotos.find((photo) => photo.id === photoId) || null
);

const getPhotoIndex = (photoId) => (
    selectedPhotos.findIndex((photo) => photo.id === photoId)
);

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

const normalizeInitialPhoto = (photo) => ({
    id: photo.id,
    name: photo.name,
    size: Number(photo.size) || 0,
    type: photo.type || "image/jpeg",
    width: photo.width || null,
    height: photo.height || null,
    dataUrl: photo.data_url || photo.dataUrl || "",
    objectUrl: null,
    lastModified: photo.lastModified || null
});

const serializePhotoForServer = (photo) => ({
    id: photo.id,
    name: photo.name,
    size: photo.size,
    type: photo.type || "image/jpeg",
    width: photo.width,
    height: photo.height,
    data_url: photo.dataUrl
});

const buildPhotoDeleteUrl = (photoId) => (
    photoWorkspace.dataset.photoDeleteUrlTemplate.replace("__PHOTO_ID__", encodeURIComponent(photoId))
);

const persistPhoto = async (photo) => {
    const response = await fetch(photoWorkspace.dataset.photosUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(serializePhotoForServer(photo))
    });

    if (!response.ok) {
        throw new Error("Unable to persist photo in coverage memory.");
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

    photoInfoEmpty.hidden = true;
    setElementVisibility(photoInfoDetails, true);
    setElementVisibility(photoCaptionPreview, true);
};

const clearPhotoInfo = () => {
    photoInfoEmpty.hidden = false;
    setElementVisibility(photoInfoDetails, false);
    setElementVisibility(photoCaptionPreview, false);
    photoInfoName.textContent = "";
    photoInfoSize.textContent = "";
    photoInfoType.textContent = "";
    photoInfoDimensions.textContent = "";
};

const renderPreview = (photo) => {
    selectedPhotoPreview.src = getPhotoSource(photo);
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
    activePhotoId = photoId;
    renderSelectionState();
    updateCounters();
    photoGrid.querySelectorAll(".photo-grid-item").forEach((item) => {
        const isActive = item.dataset.photoId === activePhotoId;
        item.classList.toggle("is-active", isActive);
        item.setAttribute("aria-selected", String(isActive));
    });
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

    const thumbnail = document.createElement("img");
    thumbnail.className = "photo-grid-thumb";
    thumbnail.src = getPhotoSource(item);
    thumbnail.alt = `Miniatura de ${item.name}`;
    thumbnail.loading = "lazy";

    const status = document.createElement("span");
    status.className = "photo-status-pill";
    status.textContent = "Preparada";

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
        cursor += batch.length;

        if (cursor < photos.length) {
            window.requestAnimationFrame(renderBatch);
        }
    };

    if (photos.length === 0) {
        photoGrid.innerHTML = "";
        return;
    }

    window.requestAnimationFrame(renderBatch);
};

const renderWorkspace = () => {
    updateCounters();
    renderSelectionState();
    renderPhotoGridProgressively();
};

const focusCaptionField = () => {
    const activePhoto = getActivePhoto();
    if (!activePhoto) {
        return;
    }

    renderPhotoInfo(activePhoto);
    photoCaptionPreview.scrollIntoView({ block: "nearest", behavior: "smooth" });
    photoCaptionField.focus({ preventScroll: true });
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

const buildPhotoFromFile = async (file) => {
    const objectUrl = URL.createObjectURL(file);
    const dataUrl = await readFileAsDataUrl(file);
    const dimensions = await readImageDimensions(objectUrl);

    return {
        id: generatePhotoId(),
        name: file.name,
        size: file.size,
        type: file.type || "image/jpeg",
        width: dimensions.width,
        height: dimensions.height,
        dataUrl,
        objectUrl,
        lastModified: file.lastModified
    };
};

const addFiles = async (files) => {
    const incomingFiles = Array.from(files);
    let addedPhotoCount = 0;

    for (const file of incomingFiles) {
        if (!isValidJpeg(file) || hasDuplicatePhoto(file)) {
            continue;
        }

        const photo = await buildPhotoFromFile(file);

        try {
            await persistPhoto(photo);
        } catch (error) {
            URL.revokeObjectURL(photo.objectUrl);
            continue;
        }

        selectedPhotos.push(photo);
        addedPhotoCount += 1;
    }

    if (addedPhotoCount > 0) {
        photoUploadMessage.classList.add("is-visible");
    }

    renderWorkspace();
};

const toggleDropZone = (isActive) => {
    dropZone.classList.toggle("is-active", isActive);
};

const clearSelection = () => {
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

    try {
        await deletePhotoFromServer(photo.id);
    } catch (error) {
        return;
    }

    if (photo.objectUrl) {
        URL.revokeObjectURL(photo.objectUrl);
    }

    selectedPhotos.splice(index, 1);

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
    photoViewerImage.src = getPhotoSource(photo);
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
    }
};

if (photoWorkspace && dropZone && photoInput && selectPhotosButton) {
    ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            toggleDropZone(true);
        });
    });

    ["dragleave", "dragend"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            toggleDropZone(false);
        });
    });

    dropZone.addEventListener("drop", (event) => {
        event.preventDefault();
        toggleDropZone(false);

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
    cancelPhotoDeleteButton.addEventListener("click", closeDeleteDialog);
    confirmPhotoDeleteButton.addEventListener("click", async () => {
        const photoId = pendingDeletePhotoId;
        closeDeleteDialog();
        pendingDeletePhotoId = null;
        await removePhotoById(photoId);
    });

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
