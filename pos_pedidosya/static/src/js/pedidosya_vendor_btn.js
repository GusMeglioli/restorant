/** @odoo-module **/
const VENDOR_POLL_MS = 30000;
let vendorTimer = null;

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

function formatCloseUntil(closeUntilStr) {
    if (!closeUntilStr) return '';
    const d = new Date(closeUntilStr.replace(' ', 'T') + 'Z');
    return d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

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

function renderVendorDialog(status) {
    document.getElementById('pya-vendor-dialog')?.remove();
    const pendingWarn = status.pending_orders > 0
        ? `<div class="pya-vendor-warn">⚠️ Hay <strong>${status.pending_orders}</strong> pedido(s) activo(s). Al cerrar no se cancelarán automáticamente.</div>`
        : '';
    const closeOpts = `<div class="pya-vendor-close-opts"><p class="pya-vendor-subtitle">¿Cuánto tiempo cerrar?</p><div class="pya-vendor-opt-grid"><button class="pya-vendor-opt" data-min="30">30 min</button><button class="pya-vendor-opt" data-min="60">1 hora</button><button class="pya-vendor-opt" data-min="120">2 horas</button><button class="pya-vendor-opt" data-min="0">Indefinido</button></div></div>`;
    const openOpts = `<div class="pya-vendor-open-opts"><p class="pya-vendor-subtitle">¿Confirmar reapertura?</p><button class="pya-vendor-confirm-open">✅ Abrir ahora</button></div>`;
    const dialog = document.createElement('div');
    dialog.id = 'pya-vendor-dialog';
    dialog.innerHTML = `<div class="pya-vendor-backdrop" id="pya-vendor-backdrop"><div class="pya-vendor-modal"><div class="pya-vendor-modal-header"><span>${status.is_open ? '🟢 Local abierto' : '🔴 Local cerrado'}</span><button class="pya-vendor-x" id="pya-vendor-x">✕</button></div>${pendingWarn}${status.is_open ? closeOpts : openOpts}</div></div>`;
    document.body.appendChild(dialog);
    document.getElementById('pya-vendor-x')?.addEventListener('click', () => document.getElementById('pya-vendor-dialog')?.remove());
    document.getElementById('pya-vendor-backdrop')?.addEventListener('click', e => { if (e.target.id === 'pya-vendor-backdrop') document.getElementById('pya-vendor-dialog')?.remove(); });
    dialog.querySelectorAll('.pya-vendor-opt').forEach(b => b.addEventListener('click', async () => {
        b.disabled = true; b.textContent = '...';
        try { await vendorRpc('/pedidosya/vendor/close', { close_minutes: parseInt(b.dataset.min) || null }); await checkVendorStatus(); document.getElementById('pya-vendor-dialog')?.remove(); } catch (e) { b.disabled = false; }
    }));
    dialog.querySelector('.pya-vendor-confirm-open')?.addEventListener('click', async () => {
        try { await vendorRpc('/pedidosya/vendor/open', {}); await checkVendorStatus(); document.getElementById('pya-vendor-dialog')?.remove(); } catch (e) { }
    });
}

async function checkVendorStatus() {
    try { const s = await vendorRpc('/pedidosya/vendor/status', {}); updateVendorBtn(s); return s; }
    catch (e) { return null; }
}

function injectVendorStyles() {
    if (document.getElementById('pya-vendor-styles')) return;
    const s = document.createElement('style');
    s.id = 'pya-vendor-styles';
    s.textContent = `.pya-vendor-btn{\n        position:fixed;top:14px;right:170px;z-index:9998;border:none;\n        border-radius:20px;padding:8px 16px;font-size:0.88rem;font-weight:700;\n        cursor:pointer;display:flex;align-items:center;gap:6px;\n        box-shadow:0 2px 8px rgba(0,0,0,0.25);transition:opacity 0.2s;\n        font-family:inherit;\n}.pya-vendor-open{background:#22c55e;color:#fff}\n.pya-vendor-closed{background:#ef4444;color:#fff}\n#pya-vendor-dialog{position:fixed;inset:0;z-index:99999}\n.pya-vendor-backdrop{position:absolute;inset:0;background:rgba(0,0,0,0.55);display:flex;align-items:center;justify-content:center}\n.pya-vendor-modal{background:#1e293b;border-radius:16px;padding:24px;min-width:320px;max-width:400px;width:90%;color:#f1f5f9;box-shadow:0 8px 30px rgba(0,0,0,0.4)}\n.pya-vendor-modal-header{display:flex;justify-content:space-between;align-items:center;font-size:1.05rem;font-weight:700;margin-bottom:16px}\n.pya-vendor-x{background:transparent;border:none;color:#94a3b8;font-size:1.1rem;cursor:pointer}\n.pya-vendor-warn{\nbackground:rgba(251,191,36,0.15);border:1px solid rgba(251,191,36,0.4);border-radius:10px;padding:10px 14px;color:#fbbf24;font-size:0.9rem;margin-bottom:16px}\n.pya-vendor-opt-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}\n.pya-vendor-opt{background:#ef4444;color:#fff;border:none;border-radius:10px;padding:12px;font-size:1rem;font-weight:700;cursor:pointer}\n.pya-vendor-confirm-open{background:#22c55e;color:#fff;border:none;border-radius:10px;padding:14px;font-size:1rem;font-weight:700;cursor:pointer;width:100%}`;
    document.head.appendChild(s);
}

function injectVendorButton() {
    if (document.getElementById('pya-vendor-btn')) return;
    injectVendorStyles();
    const btn = document.createElement('button');
    btn.id = 'pya-vendor-btn';
    btn.className = 'pya-vendor-btn pya-vendor-closed';
    btn.innerHTML = '🔴 <span>Cerrado</span>';
    btn.addEventListener('click', async () => {
        const s = await checkVendorStatus();
        if (s) renderVendorDialog(s);
    });
    document.body.appendChild(btn);
    if (vendorTimer) clearInterval(vendorTimer);
    checkVendorStatus();
    vendorTimer = setInterval(checkVendorStatus, VENDOR_POLL_MS);
}

function startVendorObserver() {
    if (!document.body) { setTimeout(startVendorObserver, 50); return; }
    const obs = new MutationObserver(() => {
        if (document.querySelector('.floor-screen, .pos-content') && document.getElementById('pya-floor-btn')) {
            obs.disconnect();
            setTimeout(injectVendorButton, 300);
        }
    });
    obs.observe(document.body, { childList: true, subtree: true });
}

startVendorObserver();
