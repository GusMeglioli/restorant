{
    'name': 'GM Multiservicios - Branding',
    'version': '19.0.1.0.0',
    'summary': 'Identidad visual corporativa GM Multiservicios',
    'author': 'GM Multiservicios',
    'license': 'OPL-1',
    'category': 'Theme',
    'depends': ['web', 'base_setup'],
    'data': [
        'data/company_branding.xml',
    ],
    'assets': {
        # Bundle principal de Odoo 19 (genera light + dark)
        'web.assets_web': [
            'gm_branding/static/src/css/gm_branding.css',
        ],
        # POS tiene su propio bundle
        'point_of_sale._assets_pos': [
            'gm_branding/static/src/css/gm_branding.css',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}
