/** @odoo-module **/

/**
 * PedidosYa POS Button - Implementación en HTML/JS puro.
 * Sin dependencia de OWL App independiente ni templates externos.
 * Se inyecta directamente en el DOM cuando el POS carga.
 */

const POLL_INTERVAL = 15000;

let pollingTimer = null;
let lastKnownIds = new Set();
let audioCtx = null;

// ── RPC via fetch nativo ───────────────────────────────────────────────────

async function rpc(model, method, args = [], kwargs = {}) {
    const response = await fetch("/web/dataset/call_kw", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: { model, method, args, kwargs },
        }),
    });
    const data = await response.json();
    if (data.error) throw new Error(data.error.data?.message || "RPC Error");
    return data.result;
}

// ── Sonido de alerta ───────────────────────────────────────────────────────

function playAlert() {
    try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const notes = [880, 1100, 880, 1100];
        let time = audioCtx.currentTime;
        for (const freq of notes) {
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.type = "sine";
            osc.frequency.value = freq;
            gain.gain.setValueAtTime(0.3, time);
            gain.gain.exponentialRampToValueAtTime(0.001, time + 0.18);
            osc.start(time);
            osc.stop(time + 0.18);
            time += 0.2;
        }
    } catch {}
}

// ── Render del diálogo ────────────────────────────────────────────────────

function renderDialog(orders) {
    // Eliminar diálogo previo si existe
    document.getElementById("pedidosya-dialog")?.remove();

    const linesHTML = (order) => {
        if (!order.lines || !order.lines.length) return "";
        return order.lines.map(l => `
            <div class="pya-line">
                <span class="pya-line-qty">${l.quantity}x</span>
                <span class="pya-line-name">${l.product_name}</span>
                ${l.notes ? `<span class="pya-line-notes">(${l.notes})</span>` : ""}
            </div>
        `).join("");
    };

    const cardsHTML = orders.length === 0
        ? `<div class="pya-empty">✅ No hay pedidos pendientes</div>`
        : orders.map(o => `
            <div class="pya-card" data-id="${o.id}">
                <div class="pya-card-header">
                    <span class="pya-card-id"># ${o.platform_order_id || o.pedidosya_order_id}</span>
                    <span class="pya-card-customer">👤 ${o.customer_name || "Sin nombre"}</span>
                    <span class="pya-card-total">$ ${o.order_total}</span>
                </div>
                <div class="pya-card-lines">${linesHTML(o)}</div>
                <div class="pya-card-actions">
                    <button class="pya-btn pya-accept" data-id="${o.id}">✓ Aceptar</button>
                    <button class="pya-btn pya-reject" data-id="${o.id}">✗ Rechazar</button>
                </div>
            </div>
        `).join("");

    const dialog = document.createElement("div");
    dialog.id = "pedidosya-dialog";
    dialog.innerHTML = `
        <div class="pya-backdrop" id="pya-backdrop">
            <div class="pya-modal">
                <div class="pya-modal-header">
                    <h3>🛵 PedidosYa
                        ${orders.length > 0 ? `<span class="pya-count">${orders.length} pendiente(s)</span>` : ""}
                    </h3>
                    <button class="pya-close" id="pya-close">✕</button>
                </div>
                <div class="pya-modal-body">${cardsHTML}</div>
                <div class="pya-modal-footer">
                    <button class="pya-btn pya-secondary" id="pya-close-btn">Cerrar</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(dialog);

    // Eventos
    document.getElementById("pya-close")?.addEventListener("click", closeDialog);
    document.getElementById("pya-close-btn")?.addEventListener("click", closeDialog);
    document.getElementById("pya-backdrop")?.addEventListener("click", (e) => {
        if (e.target.id === "pya-backdrop") closeDialog();
    });

    dialog.querySelectorAll(".pya-accept").forEach(btn => {
        btn.addEventListener("click", async () => {
            const id = parseInt(btn.dataset.id);
            btn.disabled = true;
            btn.textContent = "...";
            try {
                await rpc("pedidosya.order", "action_accept", [[id]]);
                await refreshDialog();
            } catch {
                btn.disabled = false;
                btn.textContent = "✓ Aceptar";
            }
        });
    });

    dialog.querySelectorAll(".pya-reject").forEach(btn => {
        btn.addEventListener("click", async () => {
            const id = parseInt(btn.dataset.id);
            btn.disabled = true;
            btn.textContent = "...";
            try {
                await rpc("pedidosya.order", "action_reject", [[id], "technical_problem"]);
                await refreshDialog();
            } catch {
                btn.disabled = false;
                btn.textContent = "✗ Rechazar";
            }
        });
    });
}

function closeDialog() {
    document.getElementById("pedidosya-dialog")?.remove();
}

async function refreshDialog() {
    const orders = await fetchOrders();
    renderDialog(orders);
}

// ── Fetch de pedidos ───────────────────────────────────────────────────────

async function fetchOrders() {
    try {
        const orders = await rpc(
            "pedidosya.order",
            "search_read",
            [[["state", "=", "received"]]],
            {
                fields: ["id", "pedidosya_order_id", "platform_order_id", "customer_name", "order_total"],
                limit: 20,
                order: "create_date asc",
            }
        ) || [];

        if (!orders.length) return orders;

        const orderIds = orders.map(o => o.id);
        const lines = await rpc(
            "pedidosya.order.line",
            "search_read",
            [[["order_id", "in", orderIds]]],
            { fields: ["order_id", "product_name", "quantity", "notes"], limit: 200 }
        ) || [];

        const linesByOrder = {};
        for (const l of lines) {
            const oid = l.order_id[0];
            if (!linesByOrder[oid]) linesByOrder[oid] = [];
            linesByOrder[oid].push(l);
        }
        return orders.map(o => ({ ...o, lines: linesByOrder[o.id] || [] }));
    } catch (e) {
        console.error("PedidosYa: error al obtener pedidos", e);
        return [];
    }
}

// ── Polling y actualización del badge ─────────────────────────────────────

async function checkOrders() {
    const orders = await fetchOrders();
    const currentIds = new Set(orders.map(o => o.id));
    const hasNew = [...currentIds].some(id => !lastKnownIds.has(id));

    if (hasNew && orders.length > 0) playAlert();
    lastKnownIds = currentIds;

    const btn = document.getElementById("pya-floor-btn");
    if (!btn) return;

    const badge = btn.querySelector(".pya-badge");
    if (orders.length > 0) {
        btn.classList.add("pya-pulse");
        badge.textContent = orders.length;
        badge.style.display = "inline-flex";
    } else {
        btn.classList.remove("pya-pulse");
        badge.style.display = "none";
    }

    // Actualizar diálogo si está abierto
    if (document.getElementById("pedidosya-dialog")) {
        renderDialog(orders);
    }
}

// ── Inyección del botón en el DOM ─────────────────────────────────────────

function injectButton() {
    if (document.getElementById("pya-floor-btn")) return; // Ya existe

    const btn = document.createElement("button");
    btn.id = "pya-floor-btn";
    btn.innerHTML = `🛵 PedidosYa <span class="pya-badge" style="display:none">0</span>`;
    btn.addEventListener("click", async () => {
        const orders = await fetchOrders();
        renderDialog(orders);
    });
    document.body.appendChild(btn);

    // Iniciar polling
    if (pollingTimer) clearInterval(pollingTimer);
    checkOrders();
    pollingTimer = setInterval(checkOrders, POLL_INTERVAL);

    console.log("PedidosYa: botón inyectado correctamente");
}

// ── Punto de entrada ───────────────────────────────────────────────────────

// Observar el DOM hasta que el POS esté montado y luego inyectar el botón
const observer = new MutationObserver(() => {
    const posReady = document.querySelector(".floor-screen, .pos-content, .pos-topleft-buttons");
    if (posReady) {
        observer.disconnect();
        setTimeout(injectButton, 500);
    }
});

observer.observe(document.body, { childList: true, subtree: true });

