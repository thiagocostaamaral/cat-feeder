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
    if (name === "schedule") fetchSchedules();
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

    document.getElementById("time-text").textContent = data.time;

    document.getElementById("uptime-text").textContent = data.uptime;
}

async function fetchSchedules() {
    try {
        const response = await fetch("/schedule");
        renderSchedules(await response.json());
    } catch {}
}

function renderSchedules(schedules) {
    const list = document.getElementById("schedule-list");
    if (!schedules.length) {
        list.innerHTML = '<div class="stat-row"><span style="color:rgba(255,255,255,0.3);font-size:14px;width:100%;text-align:center">No schedules</span></div>';
        return;
    }
    list.innerHTML = schedules.map(s => `
        <div class="schedule-item">
            <span class="schedule-time">${s.time}</span>
            <span class="schedule-rot">${s.rotation} steps</span>
            <button class="btn-del" onclick="removeSchedule('${s.id}')">✕</button>
        </div>
    `).join("");
}

async function addSchedule() {
    const time = document.getElementById("schedule-time").value;
    const rotation = parseInt(document.getElementById("schedule-rotation").value);
    if (!time) return;
    try {
        await fetch("/schedule", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ time, rotation })
        });
        fetchSchedules();
    } catch {}
}

async function removeSchedule(id) {
    try {
        await fetch(`/schedule/${id}`, { method: "DELETE" });
        fetchSchedules();
    } catch {}
}
