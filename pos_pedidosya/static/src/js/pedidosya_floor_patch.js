/** @odoo-module **/

/**
 * Inyecta PedidosYaButton en el FloorScreen de Odoo 19 POS.
 *
 * En Odoo 19 el nombre del template del FloorScreen cambió y la herencia XML
 * no es confiable. En su lugar patcheamos el componente en JS puro:
 * montamos PedidosYaButton como una OWL App independiente sobre un div
 * que insertamos en el body cuando el FloorScreen está activo.
 */

import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount, App } from "@odoo/owl";
import { FloorScreen } from "@point_of_sale/app/screens/floor_screen/floor_screen";
import { PedidosYaButton } from "./pedidosya_orders_widget";
import { getTemplate } from "@web/core/templates";

patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);

        this._pedidosyaContainer = null;
        this._pedidosyaApp = null;

        onMounted(() => this._mountPedidosYaButton());
        onWillUnmount(() => this._destroyPedidosYaButton());
    },

    _mountPedidosYaButton() {
        try {
            this._pedidosyaContainer = document.createElement("div");
            this._pedidosyaContainer.id = "pedidosya-btn-root";
            document.body.appendChild(this._pedidosyaContainer);

            this._pedidosyaApp = new App(PedidosYaButton, {
                templates: getTemplate,
                env: this.env,
                props: {},
            });
            this._pedidosyaApp.mount(this._pedidosyaContainer);
        } catch (e) {
            console.error("PedidosYa: error al montar botón en FloorScreen", e);
        }
    },

    _destroyPedidosYaButton() {
        try {
            if (this._pedidosyaApp) {
                this._pedidosyaApp.destroy();
                this._pedidosyaApp = null;
            }
            if (this._pedidosyaContainer && this._pedidosyaContainer.parentNode) {
                this._pedidosyaContainer.parentNode.removeChild(this._pedidosyaContainer);
                this._pedidosyaContainer = null;
            }
        } catch (e) {
            console.error("PedidosYa: error al desmontar botón", e);
        }
    },
});
