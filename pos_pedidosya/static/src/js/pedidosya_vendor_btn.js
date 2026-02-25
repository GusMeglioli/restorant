/** @odoo-module **/
/**
 * PedidosYa — Botón Abrir/Cerrar Local
 * Se inyecta en el DOM del POS junto al botón de pedidos.
 * Patrón idéntico al de pedidosya_floor_patch.js
 */

const VENDOR_POLL_MS = 30000;
let vendorTimer = null;

// ── RPC helper ──────────────────────────────────────────────────────────────
async function vendorRpc(route, params = {}) {
    const resp = await fetch(route, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params }),
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error.data?.message || 'RPC Error');
    return data.result;
}

// ── Formatear "cerrado hasta" ───────────────────────────────────────────────
function formatCloseUntil(closeUntilStr) {
    if (!closeUntilStr) return '';
    const d = new Date(closeUntilStr.replace(' ', 'T') + 'Z');
    return d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

// ── Actualizar apariencia del botón ────────────────────────────────────────
function updateVendorBtn(status) {
    const btn = document.getElementById('pya-vendor-btn');
    if (!btn) return;
    if (status.is_open) {
        btn.className = 'pya-vendor-btn pya-vendor-open';
        btn.innerHTML = '🟢 <span>Abierto</span>';
    } else {
        const until = status.close_until ? formatCloseUntil(status.close_until) : '';
        btn.className = 'pya-vendor-btn pya-vendor-closed';
        btn.innerHTML = `🔴 <span>Cerrado${until ? ' hasta ' + until : ''}</span>`;
    }
}

// ── Diálogo de apertura/cierre ──────────────────────────────────────────────
function renderVendorDialog(status) {
    document.getElementById('pya-vendor-dialog')?.remove();

    const pendingWarn = status.pending_orders > 0
        ? `<div class="pya-vendor-warn">
             ⚠️ Hay <strong>${status.pending_orders}</strong> pedido(s) activo(s).
             Al cerrar no se cancelarán automáticamente.
           </div>`
        : '';

    const closeOptions = `
        <div class="pya-vendor-close-opts">
            <p class="pya-vendor-subtitle">¿Cuánto tiempo cerrar?</p>
            <div class="pya-vendor-opt-grid">
                <button class="pya-vendor-opt" data-min="30">30 min</button>
                <button class="pya-vendor-opt" data-min="60">1 hora</button>
                <button class="pya-vendor-opt" data-min="120">2 horas</button>
                <button class="pya-vendor-opt" data-min="0">Indefinido</button>
            </div>
        </div>`;

    const openOptions = `
        <div class="pya-vendor-open-opts">
            <p class="pya-vendor-subtitle">¿Confirmar reapertura en PedidosYa?</p>
            <button class="pya-vendor-confirm-open">✅ Abrir ahora</button>
        </div>`;

    const dialog = document.createElement('div');
    dialog.id = 'pya-vendor-dialog';
    dialog.innerHTML = `
        <div class="pya-vendor-backdrop" id="pya-vendor-backdrop">
            <div class="pya-vendor-modal">
                <div class="pya-vendor-modal-header">
                    <span>${status.is_open ? '🟢 Local abierto en PedidosYa' : '🔴 Local cerrado en PedidosYa'}</span>
                    <button class="pya-vendor-x" id="pya-vendor-x">✕</button>
                </div>
                ${pendingWarn}
                ${status.is_open ? closeOptions : openOptions}
            </div>
        </div>`;
    document.body.appendChild(dialog);

    // Cerrar backdrop
    document.getElementById('pya-vendor-x')?.addEventListener('click', closeVendorDialog);
    document.getElementById('pya-vendor-backdrop')?.addEventListener('click', (e) => {
        if (e.target.id === 'pya-vendor-backdrop') closeVendorDialog();
    });

    // Opciones de cierre
    dialog.querySelectorAll('.pya-vendor-opt').forEach(btn => {
        btn.addEventListener('click', async () => {
            const min = parseInt(btn.dataset.min);
            try {
                btn.disabled = true;
                btn.textContent = '...';
                await vendorRpc('/pedidosya/vendor/close', { close_minutes: min || null });
                await checkVendorStatus();
                closeVendorDialog();
            } catch (e) {
                btn.disabled = false;
                btn.textContent = btn.dataset.label || btn.textContent;
            }
        });
    });

    // Botón abrir
    dialog.querySelector('.pya-vendor-confirm-open')?.addEventListener('click', async () => {
        try {
            await vendorRpc('/pedidosya/vendor/open', {});
            await checkVendorStatus();
            closeVendorDialog();
        } catch (e) {
            console.error('PedidosYa: error al abrir', e);
        }
    });
}

function closeVendorDialog() {
    document.getElementById('pya-vendor-dialog')?.remove();
}

// ── Poll del estado ─────────────────────────────────────────────────────────
async function checkVendorStatus() {
    try {
        const status = await vendorRpc('/pedidosya/vendor/status', {});
        updateVendorBtn(status);
        return status;
    } catch (e) {
        console.error('PedidosYa: error al obtener estado del vendor', e);
        return null;
    }
}

// ── CSS del botón y diálogo ─────────────────────────────────────────────────
function injectVendorStyles() {
    if (document.getElementById('pya-vendor-styles')) return;
    const style = document.createElement('style');
    style.id = 'pya-vendor-styles';
    style.textContent = `
        .pya-vendor-btn {
            border: none;
            border-radius: 20px;
            padding: 7px 14px;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.25);
            transition: opacity 0.2s, transform 0.1s;
            font-family: inherit;
            white-space: nowrap;
            flex-shrink: 0;
        }
        .pya-vendor-btn:hover { opacity: 0.88; transform: scale(1.03); }
        .pya-vendor-open  { background: #22c55e; color: #fff; }
        .pya-vendor-closed { background: #ef4444; color: #fff; }

        /* Diálogo */
        #pya-vendor-dialog { position: fixed; inset: 0; z-index: 99999; }
        .pya-vendor-backdrop {
            position: absolute; inset: 0;
            background: rgba(0,0,0,0.55);
            display: flex; align-items: center; justify-content: center;
        }
        .pya-vendor-modal {
            background: #1e293b;
            border-radius: 16px;
            padding: 24px;
            min-width: 320px;
            max-width: 400px;
            width: 90%;
            color: #f1f5f9;
            box-shadow: 0 8px 30px rgba(0,0,0,0.4);
        }
        .pya-vendor-modal-header {
            display: flex; justify-content: space-between; align-items: center;
            font-size: 1.05rem; font-weight: 700; margin-bottom: 16px;
        }
        .pya-vendor-x {
            background: transparent; border: none; color: #94a3b8;
            font-size: 1.1rem; cursor: pointer;
        }
        .pya-vendor-warn {
            background: rgba(251,191,36,0.15);
            border: 1px solid rgba(251,191,36,0.4);
            border-radius: 10px;
            padding: 10px 14px;
            color: #fbbf24;
            font-size: 0.9rem;
            margin-bottom: 16px;
        }
        .pya-vendor-subtitle {
            color: #94a3b8; font-size: 0.9rem; margin-bottom: 12px;
        }
        .pya-vendor-opt-grid {
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .pya-vendor-opt {
            background: #ef4444; color: #fff; border: none;
            border-radius: 10px; padding: 12px;
            font-size: 1rem; font-weight: 700; cursor: pointer;
            transition: background 0.15s;
        }
        .pya-vendor-opt:hover { background: #dc2626; }
        .pya-vendor-opt:disabled { opacity: 0.5; }
        .pya-vendor-confirm-open {
            background: #22c55e; color: #fff; border: none;
            border-radius: 10px; padding: 14px;
            font-size: 1rem; font-weight: 700; cursor: pointer;
            width: 100%; transition: background 0.15s;
        }
        .pya-vendor-confirm-open:hover { background: #16a34a; }
    `;
    document.head.appendChild(style);
}

// ── Inyección del botón ─────────────────────────────────────────────────────
function injectVendorButton() {
    if (document.getElementById('pya-vendor-btn')) return;

    injectVendorStyles();

    const btn = document.createElement('button');
    btn.id = 'pya-vendor-btn';
    btn.className = 'pya-vendor-btn pya-vendor-closed';
    btn.innerHTML = '🔴 <span>Cerrado</span>';
    btn.addEventListener('click', async () => {
        const status = await checkVendorStatus();
        if (status) renderVendorDialog(status);
    });
    // Inyectar en el grupo de la barra de pisos (junto al botón de pedidos)
    let group = document.getElementById('pya-toolbar-group');
    if (!group) {
        const floorBar = document.querySelector('.d-flex.flex-row.justify-content-between.border-bottom');
        if (!floorBar) { document.body.appendChild(btn); return; }
        group = document.createElement('div');
        group.id = 'pya-toolbar-group';
        floorBar.appendChild(group);
    }
    group.appendChild(btn);

    // Polling
    if (vendorTimer) clearInterval(vendorTimer);
    checkVendorStatus();
    vendorTimer = setInterval(checkVendorStatus, VENDOR_POLL_MS);

    console.log('PedidosYa: botón vendor inyectado');
}

// ── Observer para esperar que el POS esté listo ─────────────────────────────
function startVendorObserver() {
    if (!document.body) { setTimeout(startVendorObserver, 50); return; }
    const observer = new MutationObserver(() => {
        const floorBar = document.querySelector('.d-flex.flex-row.justify-content-between.border-bottom');
        if (floorBar) {
            observer.disconnect();
            setTimeout(injectVendorButton, 400);
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
}

startVendorObserver();
