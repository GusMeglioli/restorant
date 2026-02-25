# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class KitchenDisplay(http.Controller):

    @http.route(
        '/pedidosya/kitchen',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
    )
    def kitchen_view(self, **kwargs):
        """Pantalla de cocina — muestra pedidos PedidosYa aceptados."""
        return request.render('pos_pedidosya.kitchen_display', {})

    @http.route(
        '/pedidosya/kitchen/orders',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def kitchen_orders(self, **kwargs):
        """API JSON — devuelve pedidos en estado accepted/preparing."""
        orders = request.env['pedidosya.order'].sudo().search_read(
            [('state', 'in', ['accepted', 'preparing'])],
            ['id', 'platform_order_id', 'customer_name', 'order_total',
             'state', 'accepted_at', 'order_line_ids'],
            order='accepted_at asc',
            limit=30,
        )
        # Enriquecer con líneas
        for order in orders:
            line_ids = order.pop('order_line_ids', [])
            lines = request.env['pedidosya.order.line'].sudo().search_read(
                [('id', 'in', line_ids)],
                ['product_name', 'quantity', 'notes'],
                order='id asc',
            )
            order['lines'] = lines
        return orders

    @http.route(
        '/pedidosya/kitchen/ready/<int:order_id>',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def mark_ready(self, order_id, **kwargs):
        """Marca un pedido como listo para retirar."""
        order = request.env['pedidosya.order'].sudo().browse(order_id)
        if not order.exists():
            return {'status': 'error', 'message': 'Order not found'}
        try:
            order.action_mark_prepared()
            return {'status': 'ok', 'state': order.state}
        except Exception as e:
            _logger.error('Kitchen mark_ready error: %s', str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route(
        '/pedidosya/ready',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
    )
    def ready_view(self, **kwargs):
        """Pantalla de mozo — muestra pedidos listos para retirar."""
        return request.render('pos_pedidosya.ready_display', {})

    @http.route(
        '/pedidosya/ready/orders',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def ready_orders(self, **kwargs):
        """API JSON — devuelve pedidos listos para retirar."""
        orders = request.env['pedidosya.order'].sudo().search_read(
            [('state', '=', 'ready')],
            ['id', 'platform_order_id', 'customer_name', 'order_total',
             'state', 'prepared_at', 'order_line_ids'],
            order='prepared_at asc',
            limit=30,
        )
        for order in orders:
            line_ids = order.pop('order_line_ids', [])
            lines = request.env['pedidosya.order.line'].sudo().search_read(
                [('id', 'in', line_ids)],
                ['product_name', 'quantity'],
                order='id asc',
            )
            order['lines'] = lines
        return orders

    @http.route(
        '/pedidosya/ready/dispatched/<int:order_id>',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def mark_dispatched(self, order_id, **kwargs):
        """Marca un pedido como despachado (rider lo retiró)."""
        order = request.env['pedidosya.order'].sudo().browse(order_id)
        if not order.exists():
            return {'status': 'error', 'message': 'Order not found'}
        try:
            order.action_mark_dispatched()
            return {'status': 'ok', 'state': order.state}
        except Exception as e:
            _logger.error('Kitchen mark_dispatched error: %s', str(e))
            return {'status': 'error', 'message': str(e)}
