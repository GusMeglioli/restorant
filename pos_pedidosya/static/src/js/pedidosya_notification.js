/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

/**
 * PedidosYa Order Notification Component
 * Shows incoming PedidosYa orders in the POS interface
 */
export class PedidosYaNotification extends Component {
    static template = "pos_pedidosya.PedidosYaNotification";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            pendingOrders: [],
            isVisible: false,
        });
        this.pollingInterval = null;
        onMounted(() => this.startPolling());
        onWillUnmount(() => this.stopPolling());
    }

    startPolling() {
        // Poll for new PedidosYa orders every 15 seconds
        this.pollingInterval = setInterval(() => {
            this.checkPendingOrders();
        }, 15000);
        // Initial check
        this.checkPendingOrders();
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
        }
    }

    async checkPendingOrders() {
        try {
            const orders = await this.orm.searchRead(
                "pedidosya.order",
                [["state", "=", "received"]],
                ["id", "pedidosya_order_id", "platform_order_id", "customer_name", "order_total", "create_date"],
                { limit: 10, order: "create_date asc" }
            );
            this.state.pendingOrders = orders;
            this.state.isVisible = orders.length > 0;

            if (orders.length > 0) {
                this.notification.add(
                    `${orders.length} PedidosYa order(s) pending`,
                    { type: "warning", sticky: false }
                );
            }
        } catch (error) {
            console.error("PedidosYa: Error checking pending orders", error);
        }
    }

    async acceptOrder(orderId) {
        try {
            await this.orm.call("pedidosya.order", "action_accept", [[orderId]]);
            await this.checkPendingOrders();
            this.notification.add("Order accepted", { type: "success" });
        } catch (error) {
            this.notification.add("Error accepting order", { type: "danger" });
        }
    }

    async rejectOrder(orderId) {
        try {
            await this.orm.call("pedidosya.order", "action_reject", [[orderId], "technical_problem"]);
            await this.checkPendingOrders();
            this.notification.add("Order rejected", { type: "info" });
        } catch (error) {
            this.notification.add("Error rejecting order", { type: "danger" });
        }
    }
}
