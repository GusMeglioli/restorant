# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # ── Configuración PedidosYa ──────────────────────────────────────────────
    pedidosya_enabled = fields.Boolean(
        string='Enable PedidosYa Integration',
        default=False,
    )
    pedidosya_vendor_id = fields.Char(
        string='PedidosYa Vendor ID',
        help='Vendor code provided by PedidosYa (Platform Vendor ID)',
    )
    pedidosya_remote_id = fields.Char(
        string='Remote ID',
        help='Unique identifier of this POS on your PedidosYa plugin',
    )
    pedidosya_integration_type = fields.Selection(
        selection=[
            ('direct', 'Direct Integration'),
            ('indirect', 'Indirect Integration'),
        ],
        string='Integration Type',
        default='direct',
        help=(
            'Direct: orders managed entirely from Odoo POS.\n'
            'Indirect: orders accepted first on PedidosYa device, '
            'then forwarded to POS.'
        ),
    )
    pedidosya_auto_accept = fields.Boolean(
        string='Auto-accept Orders',
        default=False,
        help='Automatically accept incoming PedidosYa orders without manual confirmation.',
    )
    pedidosya_plugin_username = fields.Char(
        string='Plugin Username',
        help='Username credential for incoming webhook authentication from PedidosYa.',
    )
    pedidosya_plugin_password = fields.Char(
        string='Plugin Password',
        help='Password credential for incoming webhook authentication from PedidosYa.',
    )
    pedidosya_middleware_url = fields.Char(
        string='Middleware Base URL',
        default='https://integration-middleware.restaurant-partners.com',
        help='PedidosYa Integration Middleware API base URL.',
    )
    pedidosya_access_token = fields.Char(
        string='Access Token',
        help='Token obtained from PedidosYa Login API. Refreshed automatically.',
    )
    pedidosya_token_expiry = fields.Datetime(
        string='Token Expiry',
    )
    pedidosya_country = fields.Selection(
        selection=[
            ('AR', 'Argentina'),
            ('UY', 'Uruguay'),
            ('CL', 'Chile'),
            ('PY', 'Paraguay'),
            ('BO', 'Bolivia'),
            ('PE', 'Peru'),
            ('EC', 'Ecuador'),
            ('DO', 'Dominican Republic'),
            ('PA', 'Panama'),
            ('CR', 'Costa Rica'),
            ('HN', 'Honduras'),
            ('GT', 'Guatemala'),
            ('SV', 'El Salvador'),
            ('NI', 'Nicaragua'),
            ('VE', 'Venezuela'),
        ],
        string='Country',
        default='AR',
    )

    @api.constrains('pedidosya_enabled', 'pedidosya_vendor_id', 'pedidosya_remote_id')
    def _check_pedidosya_config(self):
        for record in self:
            if record.pedidosya_enabled:
                if not record.pedidosya_vendor_id:
                    raise ValidationError(_(
                        'PedidosYa Vendor ID is required when integration is enabled.'
                    ))
                if not record.pedidosya_remote_id:
                    raise ValidationError(_(
                        'Remote ID is required when integration is enabled.'
                    ))

    def get_pedidosya_webhook_url(self):
        """Returns the full webhook URL to register in PedidosYa portal."""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/pedidosya/webhook/order/{self.pedidosya_remote_id}"
