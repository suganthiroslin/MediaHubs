const videoUrl = document.getElementById("videoUrl");
const urlFormat = document.getElementById("urlFormat");
const convertUrlBtn = document.getElementById("convertUrlBtn");
const urlStatus = document.getElementById("urlStatus");

const mediaFile = document.getElementById("mediaFile");
const fileName = document.getElementById("fileName");
const processBtn = document.getElementById("processBtn");
const trimBtn = document.getElementById("trimBtn");
const editorStatus = document.getElementById("editorStatus");
const startTime = document.getElementById("startTime");
const endTime = document.getElementById("endTime");

const optionButtons = document.querySelectorAll(".option-btn");
let selectedOperation = "mp3";

const MAX_FILE_SIZE = 300 * 1024 * 1024;

function showStatus(element, message, isError = false) {
    element.className = isError ? "status error" : "status";
    element.textContent = message;
}

function showDownload(element, message, downloadPath) {
    element.className = "status";
    element.replaceChildren();

    const text = document.createElement("p");
    text.textContent = message;

    const link = document.createElement("a");
    link.href = downloadPath;
    link.textContent = "Download your file";
    link.setAttribute("download", "");

    element.append(text, link);
}

async function readResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
        throw new Error("The server returned an unexpected response. Check that Flask is running.");
    }

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || "The request could not be completed.");
    }
    return data;
}

// Show the selected file name and validate its size before sending it.
mediaFile.addEventListener("change", function () {
    const file = mediaFile.files[0];

    if (!file) {
        fileName.textContent = "No file selected";
        return;
    }

    if (file.size > MAX_FILE_SIZE) {
        mediaFile.value = "";
        fileName.textContent = "No file selected";
        showStatus(editorStatus, "The selected file is larger than 300 MB.", true);
        return;
    }

    fileName.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(2)} MB)`;
    showStatus(editorStatus, "File selected. Choose an operation or trim the file.");
});

// URL to MP4 / MP3.
convertUrlBtn.addEventListener("click", async function () {
    const url = videoUrl.value.trim();
    const format = urlFormat.value;

    if (!url) {
        showStatus(urlStatus, "Please enter a video URL.", true);
        return;
    }

    try {
        const parsedUrl = new URL(url);
        if (parsedUrl.protocol !== "https:") {
            showStatus(urlStatus, "Please enter a valid HTTPS URL.", true);
            return;
        }
    } catch {
        showStatus(urlStatus, "Please enter a valid URL.", true);
        return;
    }

    convertUrlBtn.disabled = true;
    convertUrlBtn.textContent = "Converting...";
    showStatus(urlStatus, "Please wait. Your media is being processed.");

    try {
        const response = await fetch("/url-convert", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url, operation: format })
        });

        const data = await readResponse(response);
        showDownload(urlStatus, data.message || "Conversion completed!", data.download);
    } catch (error) {
        showStatus(urlStatus, error.message, true);
    } finally {
        convertUrlBtn.disabled = false;
        convertUrlBtn.textContent = "Convert Media";
    }
});

// Select the media editing operation.
optionButtons.forEach(function (button) {
    button.addEventListener("click", function () {
        optionButtons.forEach(item => item.classList.remove("active"));
        button.classList.add("active");
        selectedOperation = button.dataset.operation;
    });
});

// Upload the selected file directly with the processing request.
// FormData sends the actual file bytes to Flask in request.files["file"].
processBtn.addEventListener("click", async function () {
    const file = mediaFile.files[0];

    if (!file) {
        showStatus(editorStatus, "Please select an audio or video file first.", true);
        return;
    }

    if (file.size > MAX_FILE_SIZE) {
        showStatus(editorStatus, "The selected file is larger than 300 MB.", true);
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("operation", selectedOperation);

    processBtn.disabled = true;
    processBtn.textContent = "Processing...";
    showStatus(editorStatus, "Uploading and processing your media. Please wait.");

    try {
        const response = await fetch("/convert", {
            method: "POST",
            body: formData
        });

        const data = await readResponse(response);
        showDownload(editorStatus, data.message || "Processing completed!", data.download);
    } catch (error) {
        showStatus(editorStatus, error.message, true);
    } finally {
        processBtn.disabled = false;
        processBtn.textContent = "Process Media";
    }
});

// Trim audio or video. The same selected file is uploaded to Flask here too.
trimBtn.addEventListener("click", async function () {
    const file = mediaFile.files[0];
    const start = Number(startTime.value);
    const end = Number(endTime.value);

    if (!file) {
        showStatus(editorStatus, "Please select a media file first.", true);
        return;
    }

    if (
        startTime.value === "" ||
        endTime.value === "" ||
        !Number.isFinite(start) ||
        !Number.isFinite(end) ||
        start < 0 ||
        end <= start
    ) {
        showStatus(
            editorStatus,
            "Enter a valid start time and an end time greater than the start time.",
            true
        );
        return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("start", String(start));
    formData.append("end", String(end));

    trimBtn.disabled = true;
    trimBtn.textContent = "Trimming...";
    showStatus(editorStatus, "Uploading and trimming your media. Please wait.");

    try {
        const response = await fetch("/trim", {
            method: "POST",
            body: formData
        });

        const data = await readResponse(response);
        showDownload(editorStatus, data.message || "Your trimmed file is ready!", data.download);
    } catch (error) {
        showStatus(editorStatus, error.message, true);
    } finally {
        trimBtn.disabled = false;
        trimBtn.textContent = "Trim Media";
    }
});
