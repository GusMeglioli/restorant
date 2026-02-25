{
    'name': 'PedidosYa POS Connector',
    'version': '19.0.1.0.0',
    'summary': 'Integrate PedidosYa orders directly into Odoo POS Restaurant',
    'description': """
        Receive PedidosYa orders automatically in Odoo Point of Sale.
        Full integration with PedidosYa Integration Middleware API (Delivery Hero).
        Supports direct and indirect order flow, kitchen display,
        vendor availability management and daily order reconciliation.

        Features:
        - Automatic order reception via webhook
        - Auto-accept configurable per POS
        - Kitchen Display System (KDS) integration
        - Vendor open/close from POS interface
        - Product catalog sync with PedidosYa
        - Daily order reconciliation (cron)
        - Multi-vendor support
        - Full order lifecycle management
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
        'views/kitchen_display_templates.xml',
        'views/pedidosya_schedule_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_pedidosya/static/src/js/**/*',
            'pos_pedidosya/static/src/xml/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
