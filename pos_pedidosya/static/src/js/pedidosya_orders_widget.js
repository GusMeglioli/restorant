/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";

/**
 * Diálogo que muestra los pedidos PedidosYa pendientes.
 * Se instancia desde PedidosYaButton.openDialog().
 */
export class PedidosYaOrdersDialog extends Component {
    static template = "pos_pedidosya.PedidosYaOrdersDialog";
    static props = {
        orders: { type: Array },
        onAccept: { type: Function },
        onReject: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.state = useState({
            orders: this.props.orders,
            loading: {},
        });
    }

    close() {
        this.props.onClose();
    }

    async acceptOrder(orderId) {
        this.state.loading[orderId] = true;
        await this.props.onAccept(orderId);
        this.state.loading[orderId] = false;
    }

    async rejectOrder(orderId) {
        this.state.loading[orderId] = true;
        await this.props.onReject(orderId);
        this.state.loading[orderId] = false;
    }
}


/**
 * Botón flotante que se inyecta en el FloorScreen.
 * Hace polling cada 15 segundos y muestra badge con pedidos pendientes.
 * Al hacer clic abre PedidosYaOrdersDialog.
 */
export class PedidosYaButton extends Component {
    static template = "pos_pedidosya.PedidosYaButton";
    static components = { PedidosYaOrdersDialog };
    static props = {};

    setup() {
        this.state = useState({
            pendingCount: 0,
            hasNew: false,
            orders: [],
            dialogOpen: false,
        });

        this._pollingTimer = null;
        this._lastKnownIds = new Set();
        this._audioCtx = null;

        onMounted(() => this._startPolling());
        onWillUnmount(() => this._stopPolling());
    }

    // ── Llamada RPC vía fetch nativo (sin depender del env del POS) ─────────

    async _rpc(model, method, args = [], kwargs = {}) {
        const response = await fetch("/web/dataset/call_kw", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: {
                    model,
                    method,
                    args,
                    kwargs,
                },
            }),
        });
        const data = await response.json();
        if (data.error) throw new Error(data.error.data?.message || data.error.message);
        return data.result;
    }

    // ── Polling ────────────────────────────────────────────────────────────

    _startPolling() {
        this._checkOrders();
        this._pollingTimer = setInterval(() => this._checkOrders(), 15000);
    }

    _stopPolling() {
        if (this._pollingTimer) {
            clearInterval(this._pollingTimer);
            this._pollingTimer = null;
        }
    }

    async _checkOrders() {
        try {
            const result = await this._rpc("pedidosya.order", "search_read", [
                [["state", "=", "received"]],
                ["id", "pedidosya_order_id", "platform_order_id", "customer_name", "order_total", "create_date"],
            ], { limit: 20, order: "create_date asc" });

            const orders = result || [];
            const currentIds = new Set(orders.map((o) => o.id));
            const hasNew = [...currentIds].some((id) => !this._lastKnownIds.has(id));

            if (hasNew && orders.length > 0) {
                this._playAlert();
            }

            this._lastKnownIds = currentIds;
            const enriched = await this._loadOrderLines(orders);

            this.state.orders = enriched;
            this.state.pendingCount = orders.length;
            this.state.hasNew = hasNew && orders.length > 0;
        } catch (error) {
            console.error("PedidosYa: error al verificar pedidos", error);
        }
    }

    async _loadOrderLines(orders) {
        if (!orders.length) return orders;
        try {
            const orderIds = orders.map((o) => o.id);
            const lines = await this._rpc("pedidosya.order.line", "search_read", [
                [["order_id", "in", orderIds]],
                ["order_id", "product_name", "quantity", "unit_price", "notes"],
            ], { limit: 200 });

            const linesByOrder = {};
            for (const line of lines || []) {
                const oid = line.order_id[0];
                if (!linesByOrder[oid]) linesByOrder[oid] = [];
                linesByOrder[oid].push(line);
            }
            return orders.map((o) => ({ ...o, lines: linesByOrder[o.id] || [] }));
        } catch {
            return orders.map((o) => ({ ...o, lines: [] }));
        }
    }

    // ── Sonido de alerta ───────────────────────────────────────────────────

    _playAlert() {
        try {
            if (!this._audioCtx) {
                this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
            const ctx = this._audioCtx;
            const notes = [880, 1100, 880, 1100];
            let time = ctx.currentTime;
            for (const freq of notes) {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = "sine";
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.3, time);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 0.18);
                osc.start(time);
                osc.stop(time + 0.18);
                time += 0.2;
            }
        } catch {
            // Sin audio — no crítico
        }
    }

    // ── Acciones del diálogo ───────────────────────────────────────────────

    openDialog() {
        this.state.hasNew = false;
        this.state.dialogOpen = true;
    }

    closeDialog() {
        this.state.dialogOpen = false;
    }

    async acceptOrder(orderId) {
        try {
            await this._rpc("pedidosya.order", "action_accept", [[orderId]]);
            await this._checkOrders();
        } catch {
            console.error("PedidosYa: error al aceptar pedido");
        }
    }

    async rejectOrder(orderId) {
        try {
            await this._rpc("pedidosya.order", "action_reject", [[orderId], "technical_problem"]);
            await this._checkOrders();
        } catch {
            console.error("PedidosYa: error al rechazar pedido");
        }
    }
}
