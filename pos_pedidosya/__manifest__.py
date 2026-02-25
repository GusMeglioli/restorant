{
    'name': 'PedidosYa POS Connector',
    'version': '19.0.1.1.0',
    'summary': 'Recibí pedidos de PedidosYa directo en tu POS Restaurante',
    'description': """
Integración completa de PedidosYa con Odoo POS Restaurant.
Recibe pedidos automáticamente via webhook con botón en pantalla de mesas.

Funcionalidades:
- Recepción automática de pedidos via webhook
- Botón flotante en pantalla de mesas con badge de pedidos pendientes
- Alerta sonora al llegar pedidos nuevos
- Aceptar / Rechazar pedidos desde el POS sin salir
- Auto-aceptar configurable por POS
- Soporte multi-local
- Ciclo completo: recibido → aceptado → entregado / cancelado
    """,
    'author': 'GM Multiservicios',
    'website': '',
    'license': 'OPL-1',
    'category': 'Point of Sale',
    'depends': [
        'point_of_sale',
        'pos_restaurant',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/pedidosya_cron.xml',
        'views/pedidosya_order_views.xml',
        'views/pos_config_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            # CSS
            'pos_pedidosya/static/src/css/pedidosya_pos.css',
            # JavaScript puro - sin dependencias OWL externas
            'pos_pedidosya/static/src/js/pedidosya_floor_patch.js',
            'pos_pedidosya/static/src/js/pedidosya_notification.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
