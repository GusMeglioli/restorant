/** @odoo-module **/

/**
 * Integración del botón PedidosYa en el FloorScreen (pantalla de mesas).
 *
 * En Odoo 19 POS, el FloorScreen es un componente OWL ubicado en:
 * @point_of_sale/app/screens/floor_screen/floor_screen
 *
 * Lo patcheamos para agregar PedidosYaButton como componente hijo
 * visible en la pantalla principal de mesas.
 */

import { patch } from "@web/core/utils/patch";
import { FloorScreen } from "@point_of_sale/app/screens/floor_screen/floor_screen";
import { PedidosYaButton } from "./pedidosya_orders_widget";

// Registrar el sub-componente en el FloorScreen
patch(FloorScreen, {
    components: {
        ...FloorScreen.components,
        PedidosYaButton,
    },
});
