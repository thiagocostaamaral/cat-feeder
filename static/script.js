const statusEl = document.getElementById("motor-status");
let presenceInterval = null;
let systemInterval = null;

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

function switchTab(name) {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

    document.querySelector(`.tab[onclick*="${name}"]`).classList.add("active");
    document.getElementById(`tab-${name}`).classList.add("active");

    stopPresencePolling();
    stopSystemPolling();

    if (name === "presence") startPresencePolling();
    if (name === "system") startSystemPolling();
}

function startPresencePolling() {
    if (presenceInterval) return;
    fetchPresence();
    presenceInterval = setInterval(fetchPresence, 1000);
}

function stopPresencePolling() {
    if (presenceInterval) {
        clearInterval(presenceInterval);
        presenceInterval = null;
    }
}

async function fetchPresence() {
    try {
        const response = await fetch("/presence");
        updatePresenceUI(await response.json());
    } catch {}
}

function updatePresenceUI(data) {
    const dot = document.getElementById("presence-dot");
    const label = document.getElementById("presence-label");

    if (data.current) {
        dot.classList.add("active");
        label.textContent = "Presence detected";
    } else {
        dot.classList.remove("active");
        label.textContent = "No presence";
    }

    drawGraph(data.samples);
}

function drawGraph(samples) {
    const canvas = document.getElementById("presence-graph");
    const container = canvas.parentElement;
    const w = container.clientWidth - 16;
    const h = 100;

    canvas.width = w * devicePixelRatio;
    canvas.height = h * devicePixelRatio;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";

    const ctx = canvas.getContext("2d");
    ctx.scale(devicePixelRatio, devicePixelRatio);

    ctx.clearRect(0, 0, w, h);

    if (!samples || samples.length === 0) return;

    const barW = w / samples.length;

    for (let i = 0; i < samples.length; i++) {
        const x = i * barW;
        const barH = samples[i] ? h * 0.85 : 4;
        const y = h - barH;

        ctx.fillStyle = samples[i] ? "#4ade80" : "rgba(255,255,255,0.08)";
        ctx.fillRect(x + 1, y, barW - 2, barH);
    }
}

function startSystemPolling() {
    if (systemInterval) return;
    fetchSystem();
    systemInterval = setInterval(fetchSystem, 2000);
}

function stopSystemPolling() {
    if (systemInterval) {
        clearInterval(systemInterval);
        systemInterval = null;
    }
}

async function fetchSystem() {
    try {
        const response = await fetch("/status");
        updateSystemUI(await response.json());
    } catch {}
}

function updateSystemUI(data) {
    const cpuPercent = data.cpu_percent;
    document.getElementById("cpu-bar").style.width = Math.min(cpuPercent, 100) + "%";
    document.getElementById("cpu-text").textContent = cpuPercent + "%";

    const ram = data.ram;
    document.getElementById("ram-bar").style.width = Math.min(ram.percent, 100) + "%";
    document.getElementById("ram-text").textContent = ram.used_mb + " / " + ram.total_mb + " MB";

    const temp = data.temperature_c;
    document.getElementById("temp-text").textContent = temp != null ? temp + "°C" : "—";

    document.getElementById("uptime-text").textContent = data.uptime;
}
