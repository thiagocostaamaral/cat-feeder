const statusEl = document.getElementById("status");

function setStatus(text, type) {
    statusEl.textContent = text;
    statusEl.className = "status " + type;
}

async function openMotor() {
    setStatus("Opening...", "loading");
    try {
        await fetch("/motor/open", { method: "POST" });
        setStatus("Opened", "success");
    } catch {
        setStatus("Failed to open", "error");
    }
}

async function closeMotor() {
    setStatus("Closing...", "loading");
    try {
        await fetch("/motor/close", { method: "POST" });
        setStatus("Closed", "success");
    } catch {
        setStatus("Failed to close", "error");
    }
}

async function rotateMotor() {
    const rotation = parseInt(document.getElementById("rotation").value);
    setStatus(`Rotating ${rotation} steps...`, "loading");
    try {
        const response = await fetch("/motor/rotate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ rotation })
        });
        const result = await response.json();
        setStatus(`Moved ${result.rotation} steps`, "success");
    } catch {
        setStatus("Failed to rotate", "error");
    }
}
