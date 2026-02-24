/** @odoo-module **/

/**
 * PedidosYa POS Frontend
 * Punto de entrada que registra todos los componentes y patches.
 *
 * Carga:
 *  - PedidosYaButton + PedidosYaOrdersDialog (componentes OWL)
 *  - Patch del FloorScreen para inyectar el botón
 */

export { PedidosYaButton, PedidosYaOrdersDialog } from "./pedidosya_orders_widget";
import "./pedidosya_floor_patch";
