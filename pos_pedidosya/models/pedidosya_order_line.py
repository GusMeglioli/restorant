# -*- coding: utf-8 -*-
from odoo import models, fields, api

class PedidosYaOrderLine(models.Model):
    _name = 'pedidosya.order.line'
    _description = 'PedidosYa Order Line'

    order_id = fields.Many2one(
        'pedidosya.order',
        string='Order',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
    )
    remote_code = fields.Char(
        string='Remote Code',
        help='Código del producto en PedidosYa (remoteCode)',
    )
    product_name = fields.Char(string='Product Name')
    quantity = fields.Float(string='Quantity', default=1.0)
    unit_price = fields.Float(string='Unit Price')
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
    )
    notes = fields.Char(string='Notes')

    @api.depends('quantity', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.unit_price
