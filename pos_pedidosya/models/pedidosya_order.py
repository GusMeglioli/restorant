# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PedidosYaOrder(models.Model):
    _name = 'pedidosya.order'
    _description = 'PedidosYa Order'
    _order = 'create_date desc'
    _rec_name = 'pedidosya_order_id'

    # ── Identificadores ──────────────────────────────────────────────────────
    pedidosya_order_id = fields.Char(
        string='PedidosYa Order ID',
        required=True,
        index=True,
    )
    pedidosya_vendor_id = fields.Char(
        string='Vendor ID',
    )
    platform_order_id = fields.Char(
        string='Platform Order ID',
    )

    # ── Estado ───────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('received', 'Received'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('preparing', 'Preparing'),
            ('ready', 'Ready for Pickup'),
            ('dispatched', 'Dispatched'),
            ('canceled', 'Canceled'),
            ('error', 'Error'),
        ],
        string='State',
        default='received',
        index=True,
    )
    reject_reason = fields.Selection(
        selection=[
            ('restaurant_closed', 'Restaurant Closed'),
            ('product_unavailable', 'Product Unavailable'),
            ('too_many_orders', 'Too Many Orders'),
            ('technical_problem', 'Technical Problem'),
            ('other', 'Other'),
        ],
        string='Reject Reason',
    )
    error_message = fields.Text(string='Error Message')

    # ── Relación con POS ─────────────────────────────────────────────────────
    pos_config_id = fields.Many2one(
        comodel_name='pos.config',
        string='POS Configuration',
        ondelete='restrict',
    )
    pos_order_id = fields.Many2one(
        comodel_name='pos.order',
        string='POS Order',
        ondelete='set null',
    )

    # ── Datos del pedido ─────────────────────────────────────────────────────
    raw_payload = fields.Text(
        string='Raw Payload',
        help='Original JSON payload received from PedidosYa webhook.',
    )
    customer_name = fields.Char(string='Customer Name')
    customer_phone = fields.Char(string='Customer Phone')
    delivery_address = fields.Text(string='Delivery Address')
    order_total = fields.Float(string='Order Total')
    estimated_pickup_time = fields.Datetime(string='Estimated Pickup Time')
    is_preorder = fields.Boolean(string='Is Preorder', default=False)

    # ── Auditoría ─────────────────────────────────────────────────────────────
    accepted_at = fields.Datetime(string='Accepted At')
    prepared_at = fields.Datetime(string='Prepared At')
    dispatched_at = fields.Datetime(string='Dispatched At')
    canceled_at = fields.Datetime(string='Canceled At')

    _sql_constraints = [
        (
            'unique_pedidosya_order_id',
            'UNIQUE(pedidosya_order_id)',
            'A PedidosYa order with this ID already exists.',
        )
    ]

    def action_accept(self):
        """Accept order and notify PedidosYa."""
        self.ensure_one()
        if self.state != 'received':
            raise UserError(_('Only orders in Received state can be accepted.'))
        sync = self.env['pedidosya.sync']
        result = sync.update_order_status(self, 'order_accepted')
        if result:
            self.write({
                'state': 'accepted',
                'accepted_at': fields.Datetime.now(),
            })
        return result

    def action_reject(self, reason='technical_problem'):
        """Reject order and notify PedidosYa."""
        self.ensure_one()
        sync = self.env['pedidosya.sync']
        result = sync.update_order_status(self, 'order_rejected', reason=reason)
        if result:
            self.write({
                'state': 'rejected',
                'reject_reason': reason,
            })
        return result

    def action_mark_prepared(self):
        """Mark order as ready for pickup."""
        self.ensure_one()
        if self.state not in ('accepted', 'preparing'):
            raise UserError(_('Order must be accepted before marking as prepared.'))
        sync = self.env['pedidosya.sync']
        result = sync.mark_order_prepared(self)
        if result:
            self.write({
                'state': 'ready',
                'prepared_at': fields.Datetime.now(),
            })
        return result

    def action_mark_dispatched(self):
        """Mark order as picked up by rider."""
        self.ensure_one()
        if self.state != 'ready':
            raise UserError(_('Order must be ready for pickup before dispatching.'))
        sync = self.env['pedidosya.sync']
        result = sync.update_order_status(self, 'order_picked_up')
        if result:
            self.write({
                'state': 'dispatched',
                'dispatched_at': fields.Datetime.now(),
            })
        return result

    def action_view_pos_order(self):
        """Open related POS order."""
        self.ensure_one()
        if not self.pos_order_id:
            raise UserError(_('No POS order linked to this PedidosYa order.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'res_id': self.pos_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
