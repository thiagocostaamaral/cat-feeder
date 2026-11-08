const statusEl = document.getElementById("motor-status");
let presenceInterval = null;
let systemInterval = null;
let weightInterval = null;
let historyInterval = null;
let autoInterval = null;
let autoState = null;
let selectedMotor = 1;
let motorRunning = false;

function setStatus(text, type) {
    statusEl.textContent = text;
    statusEl.className = "status " + type;
}

function motorBase(prefix) {
    return selectedMotor === 2 ? prefix.replace("/motor", "/motor2") : prefix;
}

function selectMotor(n) {
    if (motorRunning) return;
    selectedMotor = n;
    document.querySelectorAll(".m-btn").forEach(b => {
        const active = parseInt(b.dataset.motor) === n;
        b.classList.toggle("active", active);
    });
    setStatus(`Motor ${n} · Ready`, "idle");
}

async function openMotor() {
    if (motorRunning) return;
    motorRunning = true;
    setStatus(`Motor ${selectedMotor} · Opening...`, "loading");
    try {
        await fetch(motorBase("/motor/open"), { method: "POST" });
        setStatus(`Motor ${selectedMotor} · Opened`, "success");
    } catch {
        setStatus(`Failed to open motor ${selectedMotor}`, "error");
    } finally {
        motorRunning = false;
    }
}

async function closeMotor() {
    if (motorRunning) return;
    motorRunning = true;
    setStatus(`Motor ${selectedMotor} · Closing...`, "loading");
    try {
        await fetch(motorBase("/motor/close"), { method: "POST" });
        setStatus(`Motor ${selectedMotor} · Closed`, "success");
    } catch {
        setStatus(`Failed to close motor ${selectedMotor}`, "error");
    } finally {
        motorRunning = false;
    }
}

async function rotateMotor() {
    if (motorRunning) return;
    motorRunning = true;
    const rotation = parseInt(document.getElementById("rotation").value);
    setStatus(`Motor ${selectedMotor} · Rotating ${rotation} steps...`, "loading");
    try {
        const response = await fetch(motorBase("/motor/rotate"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ rotation })
        });
        const result = await response.json();
        setStatus(`Motor ${selectedMotor} · Moved ${result.rotation} steps`, "success");
    } catch {
        setStatus(`Failed to rotate motor ${selectedMotor}`, "error");
    } finally {
        motorRunning = false;
    }
}

function switchTab(name) {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

    document.querySelector(`.tab[onclick*="${name}"]`).classList.add("active");
    document.getElementById(`tab-${name}`).classList.add("active");

    stopPresencePolling();
    stopSystemPolling();
    stopWeightPolling();
    stopHistoryPolling();
    stopAutoPolling();

    if (name === "presence") startPresencePolling();
    if (name === "system") startSystemPolling();
    if (name === "weight") {
        startWeightPolling();
        startHistoryPolling();
    }
    if (name === "auto") startAutoPolling();
    if (name === "photos") fetchPhotos();
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

function startAutoPolling() {
    if (autoInterval) return;
    fetchAuto();
    autoInterval = setInterval(fetchAuto, 1000);
}

function stopAutoPolling() {
    if (autoInterval) {
        clearInterval(autoInterval);
        autoInterval = null;
    }
}

async function fetchAuto() {
    try {
        const response = await fetch("/auto");
        autoState = await response.json();
        renderAuto(autoState);
    } catch {}
}

function renderAuto(data) {
    const status = document.getElementById("auto-status");
    const weight = document.getElementById("auto-weight");

    weight.textContent = data.weight.toFixed(1) + " g";

    let text = "Auto · " + data.state;
    if (data.message) text += " · " + data.message;
    if (data.state === "waiting" && data.dwell_left_s > 0) {
        text += " · dwell " + Math.ceil(data.dwell_left_s) + "s";
    } else if (data.state === "waiting" && data.cooldown_left_s > 0) {
        text += " · cooldown " + Math.ceil(data.cooldown_left_s) + "s";
    }
    status.textContent = text;

    const type = data.state === "fault" ? "error"
        : (data.state === "dosing" || data.state === "settling" || data.state === "paused") ? "loading"
        : data.state === "off" ? "idle" : "success";
    status.className = "status " + type;

    document.getElementById("auto-toggle").textContent = data.enabled ? "Disable" : "Enable";

    const lowEl = document.getElementById("auto-low");
    const targetEl = document.getElementById("auto-target");
    if (document.activeElement !== lowEl) lowEl.value = data.low_g;
    if (document.activeElement !== targetEl) targetEl.value = data.target_g;

    document.getElementById("auto-gps").textContent =
        data.grams_per_step.toFixed(3) + " g/step learned · " + data.target_g + " g target";

    renderAutoEvents(data.events || []);
}

function renderAutoEvents(events) {
    const list = document.getElementById("auto-events");
    if (!events.length) {
        list.innerHTML = '<div class="cal-empty">No refills yet</div>';
        return;
    }
    list.innerHTML = events.slice().reverse().map(event => {
        const time = new Date(event.t * 1000).toTimeString().slice(0, 5);
        const after = event.after == null ? "—" : event.after.toFixed(1);
        const ok = event.result === "ok";
        return `
            <div class="event-row${ok ? "" : " event-bad"}">
                <span class="event-time">${time}</span>
                <span class="event-flow">${event.before.toFixed(1)} → ${after} g</span>
                <span class="event-steps">${event.steps} steps</span>
                <span class="event-result">${event.result}</span>
            </div>
        `;
    }).join("");
}

async function toggleAuto() {
    const enabled = !(autoState && autoState.enabled);
    try {
        await fetch("/auto", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled })
        });
    } catch {}
    fetchAuto();
}

async function saveAutoField() {
    const low = parseFloat(document.getElementById("auto-low").value);
    const target = parseFloat(document.getElementById("auto-target").value);
    if (isNaN(low) || isNaN(target)) return;
    try {
        await fetch("/auto", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ low_g: low, target_g: target })
        });
    } catch {}
    fetchAuto();
}

async function doseOnce() {
    try {
        await fetch("/auto/dose", { method: "POST" });
    } catch {}
    fetchAuto();
}

async function stopAuto() {
    try {
        await fetch("/auto/stop", { method: "POST" });
    } catch {}
    fetchAuto();
}

async function fetchPhotos() {
    try {
        const response = await fetch("/photos");
        renderPhotos(await response.json());
    } catch {}
}

function renderPhotos(photos) {
    const grid = document.getElementById("photos-grid");
    if (!photos.length) {
        grid.innerHTML = '<div class="stat-row"><span style="color:rgba(255,255,255,0.3);font-size:14px;width:100%;text-align:center">No photos yet</span></div>';
        return;
    }
    grid.innerHTML = photos.map(p => {
        const displayName = p.name.replace(".jpg", "").replace(/_/g, ":");
        const timeLabel = displayName.slice(9, 11) + ":" + displayName.slice(11, 13) + ":" + displayName.slice(13, 15);
        return `
            <div class="photo-card">
                <img src="${p.url}" loading="lazy">
                <span class="photo-time">${timeLabel}</span>
                <button class="photo-del" onclick="removePhoto('${p.name}')">✕</button>
            </div>
        `;
    }).join("");
}

async function removePhoto(name) {
    try {
        await fetch(`/photos/${name}`, { method: "DELETE" });
        fetchPhotos();
    } catch {}
}

function startWeightPolling() {
    if (weightInterval) return;
    fetchWeight();
    weightInterval = setInterval(fetchWeight, 1000);
}

function stopWeightPolling() {
    if (weightInterval) {
        clearInterval(weightInterval);
        weightInterval = null;
    }
}

function setWeightStatus(text, type) {
    const el = document.getElementById("weight-status");
    el.textContent = text;
    el.className = "status " + type;
}

async function fetchWeight() {
    try {
        const response = await fetch("/weight");
        updateWeightUI(await response.json());
    } catch {}
}

function updateWeightUI(data) {
    const gramsEl = document.getElementById("weight-grams");

    if (!data.available) {
        gramsEl.textContent = "—";
        setWeightStatus("Scale · not connected", "error");
        return;
    }

    if (data.error) {
        gramsEl.textContent = "—";
        setWeightStatus("Scale · " + data.error, "error");
        return;
    }

    if (!data.calibrated) {
        gramsEl.textContent = "—";
        setWeightStatus("Scale · not configured", "loading");
        return;
    }

    gramsEl.textContent = data.grams == null ? "—" : data.grams.toFixed(1);
    setWeightStatus(data.stable ? "Scale · stable" : "Scale · settling",
        data.stable ? "success" : "idle");
}

async function tareScale() {
    setWeightStatus("Scale · taring...", "loading");
    try {
        const result = await (await fetch("/weight/tare", { method: "POST" })).json();
        if (result.status === "ok") {
            setWeightStatus("Scale · tared", "success");
        } else {
            setWeightStatus("Scale · " + (result.error || "tare failed"), "error");
        }
    } catch {
        setWeightStatus("Scale · tare failed", "error");
    }
    fetchWeight();
}

function startHistoryPolling() {
    if (historyInterval) return;
    fetchHistory();
    historyInterval = setInterval(fetchHistory, 5000);
}

function stopHistoryPolling() {
    if (historyInterval) {
        clearInterval(historyInterval);
        historyInterval = null;
    }
}

async function fetchHistory() {
    try {
        const response = await fetch("/weight/history");
        updateHistory(await response.json());
    } catch {}
}

function updateHistory(data) {
    const samples = data.samples || [];
    const range = document.getElementById("history-range");

    if (!samples.length) {
        range.textContent = "no samples yet";
    } else {
        const age = Date.now() / 1000 - samples[0].t;
        range.textContent = samples.length + " samples · oldest " + formatAge(age);
    }

    drawHistory(samples, data.presence);
}

function formatAge(seconds) {
    if (seconds < 90) return Math.round(seconds) + "s ago";
    if (seconds < 5400) return Math.round(seconds / 60) + "m ago";
    return (seconds / 3600).toFixed(1) + "h ago";
}

function drawHistory(samples, presence) {
    const canvas = document.getElementById("weight-history");
    const width = canvas.parentElement.clientWidth - 16;
    const height = 120;

    canvas.width = width * devicePixelRatio;
    canvas.height = height * devicePixelRatio;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";

    const ctx = canvas.getContext("2d");
    ctx.scale(devicePixelRatio, devicePixelRatio);
    ctx.clearRect(0, 0, width, height);

    if (!samples || samples.length < 2) return;

    const times = samples.map(s => s.t);
    const grams = samples.map(s => s.g);

    let tMin = Math.min(...times);
    let tMax = Math.max(...times);
    let gMin = Math.min(...grams);
    let gMax = Math.max(...grams);

    if (tMin === tMax) {
        tMin -= 1;
        tMax += 1;
    }
    if (gMin === gMax) {
        gMin -= 1;
        gMax += 1;
    }

    const pad = (gMax - gMin) * 0.15;
    gMin -= pad;
    gMax += pad;

    const x = t => 4 + (t - tMin) / (tMax - tMin) * (width - 8);
    const y = g => height - 6 - (g - gMin) / (gMax - gMin) * (height - 12);

    ctx.beginPath();
    ctx.moveTo(x(tMin), height - 6);
    samples.forEach(s => ctx.lineTo(x(s.t), y(s.g)));
    ctx.lineTo(x(tMax), height - 6);
    ctx.closePath();
    ctx.fillStyle = "rgba(249, 115, 22, 0.15)";
    ctx.fill();

    ctx.beginPath();
    samples.forEach((s, i) => {
        i === 0 ? ctx.moveTo(x(s.t), y(s.g)) : ctx.lineTo(x(s.t), y(s.g));
    });
    ctx.strokeStyle = "#f97316";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "rgba(255, 255, 255, 0.35)";
    ctx.font = "10px 'Segoe UI', system-ui, sans-serif";
    ctx.fillText(gMax.toFixed(1) + " g", 6, 12);
    ctx.fillText(gMin.toFixed(1) + " g", 6, height - 2);

    if (presence) {
        ctx.fillStyle = "rgba(74, 222, 128, 0.75)";
        ctx.beginPath();
        ctx.arc(width - 8, 8, 3, 0, Math.PI * 2);
        ctx.fill();
    }
}
