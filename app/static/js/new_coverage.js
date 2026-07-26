const dropZone = document.getElementById("drop-zone");
const photoInput = document.getElementById("photo-input");
const selectPhotosButton = document.getElementById("select-photos-button");
const photoPreviewList = document.getElementById("photo-preview-list");
const photoCount = document.getElementById("photo-count");
const uploadPhotosButton = document.getElementById("upload-photos-button");
const photoUploadMessage = document.getElementById("photo-upload-message");

const selectedPhotos = [];

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

const isValidJpeg = (file) => {
    const hasValidExtension = /\.(jpg|jpeg)$/i.test(file.name);
    const hasValidMime = file.type === "image/jpeg" || file.type === "";
    return hasValidExtension && hasValidMime;
};

const updateCounter = () => {
    const total = selectedPhotos.length;
    const label = total === 1 ? "fotografía" : "fotografías";
    photoCount.textContent = `${total} ${label} seleccionadas`;
};

const renderPreviewList = () => {
    photoPreviewList.innerHTML = "";

    selectedPhotos.forEach((item) => {
        const li = document.createElement("li");
        li.className = "photo-preview-item";

        const thumbnail = document.createElement("img");
        thumbnail.className = "photo-thumbnail";
        thumbnail.src = item.previewUrl;
        thumbnail.alt = `Miniatura de ${item.file.name}`;

        const meta = document.createElement("div");
        meta.className = "photo-meta";

        const name = document.createElement("p");
        name.className = "photo-name";
        name.textContent = item.file.name;

        const size = document.createElement("p");
        size.className = "photo-size";
        size.textContent = formatSize(item.file.size);

        meta.append(name, size);

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "remove-photo-button";
        removeButton.textContent = "Quitar";
        removeButton.addEventListener("click", () => {
            const index = selectedPhotos.findIndex((photo) => photo.id === item.id);
            if (index === -1) {
                return;
            }

            URL.revokeObjectURL(selectedPhotos[index].previewUrl);
            selectedPhotos.splice(index, 1);
            updateCounter();
            renderPreviewList();
        });

        li.append(thumbnail, meta, removeButton);
        photoPreviewList.appendChild(li);
    });
};

const addFiles = (files) => {
    const incomingFiles = Array.from(files);

    incomingFiles.forEach((file) => {
        if (!isValidJpeg(file)) {
            return;
        }

        const isDuplicate = selectedPhotos.some((photo) => (
            photo.file.name === file.name
            && photo.file.size === file.size
            && photo.file.lastModified === file.lastModified
        ));

        if (isDuplicate) {
            return;
        }

        selectedPhotos.push({
            id: generatePhotoId(),
            file,
            previewUrl: URL.createObjectURL(file)
        });
    });

    updateCounter();
    renderPreviewList();
};

const toggleDropZone = (isActive) => {
    dropZone.classList.toggle("is-active", isActive);
};

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

uploadPhotosButton.addEventListener("click", () => {
    photoUploadMessage.classList.add("is-visible");
});

window.addEventListener("beforeunload", () => {
    selectedPhotos.forEach((item) => {
        URL.revokeObjectURL(item.previewUrl);
    });
});

updateCounter();
