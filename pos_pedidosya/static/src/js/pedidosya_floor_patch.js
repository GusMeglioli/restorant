/** @odoo-module **/

/**
 * Monta PedidosYaButton en el POS sin depender del FloorScreen.
 *
 * Estrategia: esperar que el DOM del POS esté listo y montar
 * el botón como una App OWL independiente fijada al body.
 * Así evitamos cualquier dependencia de rutas internas del POS
 * que pueden cambiar entre versiones de Odoo.
 */

import { App, whenReady } from "@odoo/owl";
import { PedidosYaButton } from "./pedidosya_orders_widget";
import { templates } from "@web/core/assets";
import { makeEnv, startServices } from "@web/env";

// Montar el botón una vez que el DOM esté listo
whenReady(() => {
    // Esperar un tick para que el POS termine de inicializar
    setTimeout(() => {
        try {
            const container = document.createElement("div");
            container.id = "pedidosya-btn-root";
            document.body.appendChild(container);

            const app = new App(PedidosYaButton, {
                templates,
                props: {},
            });
            app.mount(container);
            console.log("PedidosYa: botón montado correctamente");
        } catch (e) {
            console.error("PedidosYa: error al montar botón", e);
        }
    }, 2000);
});
