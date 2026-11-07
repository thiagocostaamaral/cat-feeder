let points = [];
let loaded = false;
let liveRaw = null;

async function fetchState() {
    try {
        const data = await (await fetch("/weight")).json();
        updateLive(data);
        if (!loaded) {
            points = (data.points || []).map(p => ({ grams: p.grams, raw: p.raw }));
            loaded = true;
            renderPoints();
        }
        drawGraph();
    } catch {}
}

function updateLive(data) {
    liveRaw = data.raw;
    document.getElementById("live-raw").textContent = data.raw + " · " + data.raw_hex;

    const grams = data.grams;
    document.getElementById("live-grams").textContent =
        grams == null ? "—" : grams.toFixed(1) + " g";

    const status = document.getElementById("live-status");
    if (!data.available) {
        status.textContent = "Scale · not connected";
        status.className = "status error";
    } else if (data.error) {
        status.textContent = "Scale · " + data.error;
        status.className = "status error";
    } else if (data.warning) {
        status.textContent = "Scale · " + data.warning;
        status.className = "status loading";
    } else if (!data.calibrated) {
        status.textContent = "Scale · needs 2 captured points";
        status.className = "status loading";
    } else {
        status.textContent = "Scale · calibrated";
        status.className = "status success";
    }
}

function renderPoints() {
    const list = document.getElementById("points-list");
    if (!points.length) {
        list.innerHTML = '<div class="cal-empty">No points yet, add one below</div>';
        return;
    }
    list.innerHTML = points.map((point, index) => `
        <div class="cal-row">
            <input class="cal-weight" type="number" min="0" step="1" value="${point.grams}"
                   oninput="setWeight(${index}, this.value)">
            <span class="cal-unit">g</span>
            <span class="cal-raw">${point.raw === null ? "not captured" : point.raw}</span>
            <button class="cal-btn" onclick="capturePoint(${index})">Capture</button>
            <button class="cal-del" onclick="removePoint(${index})">✕</button>
        </div>
    `).join("");
}

function setWeight(index, value) {
    points[index].grams = parseFloat(value) || 0;
    drawGraph();
}

function addPoint() {
    const input = document.getElementById("new-weight");
    points.push({ grams: parseFloat(input.value) || 0, raw: null });
    renderPoints();
    drawGraph();
}

function removePoint(index) {
    points.splice(index, 1);
    renderPoints();
    drawGraph();
}

async function capturePoint(index) {
    setSaveStatus("Capturing...", "loading");
    try {
        const response = await fetch("/weight/capture", { method: "POST" });
        const result = await response.json();
        if (result.raw === undefined) {
            setSaveStatus(result.error || "capture failed", "error");
            return;
        }
        points[index].raw = result.raw;
        renderPoints();
        drawGraph();
        setSaveStatus("Captured " + result.raw, "success");
    } catch {
        setSaveStatus("capture failed", "error");
    }
}

async function savePoints() {
    const clean = points
        .filter(point => point.raw !== null)
        .map(point => ({ grams: point.grams, raw: point.raw }));

    if (clean.length < 2) {
        setSaveStatus("Capture at least 2 points", "error");
        return;
    }

    setSaveStatus("Saving...", "loading");
    try {
        const response = await fetch("/calibration", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ points: clean })
        });
        const result = await response.json();
        if (result.status === "error") {
            setSaveStatus(result.error || "save failed", "error");
            return;
        }
        points = (result.points || []).map(p => ({ grams: p.grams, raw: p.raw }));
        renderPoints();
        drawGraph();
        setSaveStatus("Saved", "success");
    } catch {
        setSaveStatus("save failed", "error");
    }
}

function setSaveStatus(text, type) {
    const el = document.getElementById("save-status");
    el.textContent = text;
    el.className = "status " + type;
}

function drawGraph() {
    const canvas = document.getElementById("cal-graph");
    const width = canvas.parentElement.clientWidth - 16;
    const height = 180;

    canvas.width = width * devicePixelRatio;
    canvas.height = height * devicePixelRatio;
    canvas.style.width = width + "px";
    canvas.style.height = height + "px";

    const ctx = canvas.getContext("2d");
    ctx.scale(devicePixelRatio, devicePixelRatio);
    ctx.clearRect(0, 0, width, height);

    const usable = points
        .filter(point => point.raw !== null)
        .slice()
        .sort((a, b) => a.raw - b.raw);

    if (!usable.length) {
        document.getElementById("graph-x-min").textContent = "raw";
        document.getElementById("graph-x-max").textContent = "raw";
        return;
    }

    let rawMin = Math.min(...usable.map(p => p.raw));
    let rawMax = Math.max(...usable.map(p => p.raw));
    let gramMin = Math.min(...usable.map(p => p.grams));
    let gramMax = Math.max(...usable.map(p => p.grams));

    if (rawMin === rawMax) {
        rawMin -= 1;
        rawMax += 1;
    }
    if (gramMin === gramMax) {
        gramMin -= 1;
        gramMax += 1;
    }

    const rawPad = (rawMax - rawMin) * 0.08;
    const gramPad = (gramMax - gramMin) * 0.15;
    rawMin -= rawPad;
    rawMax += rawPad;
    gramMin -= gramPad;
    gramMax += gramPad;

    const padX = 8;
    const padY = 8;
    const x = raw => padX + (raw - rawMin) / (rawMax - rawMin) * (width - padX * 2);
    const y = grams => height - padY - (grams - gramMin) / (gramMax - gramMin) * (height - padY * 2);

    ctx.strokeStyle = "rgba(255,255,255,0.12)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padX, height - padY);
    ctx.lineTo(width - padX, height - padY);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(padX, padY);
    ctx.lineTo(padX, height - padY);
    ctx.stroke();

    if (usable.length > 1) {
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 2;
        ctx.beginPath();
        usable.forEach((point, index) => {
            index === 0
                ? ctx.moveTo(x(point.raw), y(point.grams))
                : ctx.lineTo(x(point.raw), y(point.grams));
        });
        ctx.stroke();
    }

    ctx.fillStyle = "#4ade80";
    usable.forEach(point => {
        ctx.beginPath();
        ctx.arc(x(point.raw), y(point.grams), 3.5, 0, Math.PI * 2);
        ctx.fill();
    });

    if (liveRaw !== null && liveRaw >= rawMin && liveRaw <= rawMax) {
        ctx.strokeStyle = "rgba(139,92,246,0.85)";
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x(liveRaw), padY);
        ctx.lineTo(x(liveRaw), height - padY);
        ctx.stroke();
        ctx.setLineDash([]);
    }

    document.getElementById("graph-x-min").textContent = Math.round(rawMin) + " raw";
    document.getElementById("graph-x-max").textContent = Math.round(rawMax) + " raw";
}

fetchState();
setInterval(fetchState, 1000);
window.addEventListener("resize", drawGraph);
