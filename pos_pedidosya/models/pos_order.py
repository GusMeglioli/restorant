# -*- coding: utf-8 -*-
from odoo import models, fields

# Este archivo solo agrega los campos de relación a pos.order.
# La creación de pedidos PedidosYa se maneja directamente
# en el webhook controller (pedidosya_webhook.py) sobre el modelo
# pedidosya.order — sin tocar pos.order desde el backend.


class PosOrder(models.Model):
    _inherit = 'pos.order'

    pedidosya_order_id = fields.Many2one(
        comodel_name='pedidosya.order',
        string='PedidosYa Order',
        ondelete='set null',
        readonly=True,
    )
    is_pedidosya = fields.Boolean(
        string='From PedidosYa',
        default=False,
        readonly=True,
    )
