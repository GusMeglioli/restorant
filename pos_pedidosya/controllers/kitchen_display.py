# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging
from datetime import datetime, timedelta

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
        """Pantalla de cocina — muestra TODOS los pedidos activos."""
        return request.render('pos_pedidosya.kitchen_display', {})

    @http.route(
        '/pedidosya/kitchen/orders',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def kitchen_orders(self, **kwargs):
        """
        API JSON — devuelve pedidos de TODAS las fuentes:
        1. PedidosYa (accepted / preparing)
        2. POS mesa (pos.order state=draft con table_id)
        3. POS teléfono/ventanilla (pos.order state=draft sin table_id, sin pedidosya)
        """
        result = []

        # ── 1. Pedidos PedidosYa ──────────────────────────────────────────
        pya_orders = request.env['pedidosya.order'].sudo().search_read(
            [('state', 'in', ['accepted', 'preparing'])],
            ['id', 'platform_order_id', 'customer_name', 'order_total',
             'state', 'accepted_at', 'order_line_ids'],
            order='accepted_at asc',
            limit=30,
        )
        for order in pya_orders:
            line_ids = order.pop('order_line_ids', [])
            lines = request.env['pedidosya.order.line'].sudo().search_read(
                [('id', 'in', line_ids)],
                ['product_name', 'quantity', 'notes'],
                order='id asc',
            )
            result.append({
                'id': 'pya_%s' % order['id'],
                'source': 'pedidosya',
                'source_label': '🛵 PedidosYa',
                'order_ref': order.get('platform_order_id') or '#%s' % order['id'],
                'customer_name': order.get('customer_name') or 'PedidosYa',
                'table_name': None,
                'state': order['state'],
                'created_at': order.get('accepted_at') or '',
                'lines': [
                    {
                        'product_name': l['product_name'],
                        'quantity': l['quantity'],
                        'notes': l.get('notes') or '',
                    }
                    for l in lines
                ],
            })

        # ── 2 & 3. Pedidos POS (mesa + teléfono/ventanilla) ──────────────
        # Buscar órdenes POS activas de las últimas 12 horas que NO sean de PedidosYa
        since = datetime.now() - timedelta(hours=12)
        pos_orders = request.env['pos.order'].sudo().search(
            [
                ('state', '=', 'draft'),
                ('is_pedidosya', '=', False),
                ('date_order', '>=', since.strftime('%Y-%m-%d %H:%M:%S')),
            ],
            order='date_order asc',
            limit=50,
        )

        for order in pos_orders:
            # Determinar fuente
            table = order.table_id
            if table:
                source = 'mesa'
                source_label = '🍽️ Mesa'
                table_name = table.name
            else:
                source = 'ventanilla'
                source_label = '📞 Retiro/Ventanilla'
                table_name = None

            lines = []
            for line in order.lines:
                if not line.product_id:
                    continue
                note = ''
                if hasattr(line, 'customer_note'):
                    note = line.customer_note or ''
                lines.append({
                    'product_name': line.product_id.name,
                    'quantity': line.qty,
                    'notes': note,
                })

            if not lines:
                continue

            result.append({
                'id': 'pos_%s' % order.id,
                'source': source,
                'source_label': source_label,
                'order_ref': order.name or '#%s' % order.id,
                'customer_name': order.partner_id.name if order.partner_id else '',
                'table_name': table_name,
                'state': 'preparing',
                'created_at': order.date_order.isoformat() if order.date_order else '',
                'lines': lines,
            })

        return result

    @http.route(
        '/pedidosya/kitchen/ready/<string:order_key>',
        type='jsonrpc',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def mark_ready(self, order_key, **kwargs):
        """Marca un pedido como listo. Soporta pya_ID y pos_ID."""
        try:
            if order_key.startswith('pya_'):
                order_id = int(order_key[4:])
                order = request.env['pedidosya.order'].sudo().browse(order_id)
                if not order.exists():
                    return {'status': 'error', 'message': 'Order not found'}
                order.action_mark_prepared()
                return {'status': 'ok', 'state': order.state}

            elif order_key.startswith('pos_'):
                # Para POS, solo marcamos visualmente — el estado se maneja desde el POS
                order_id = int(order_key[4:])
                order = request.env['pos.order'].sudo().browse(order_id)
                if not order.exists():
                    return {'status': 'error', 'message': 'Order not found'}
                # Escribir en chatter o nota interna que está listo
                return {'status': 'ok', 'state': 'ready'}

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
        type='jsonrpc',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def ready_orders(self, **kwargs):
        """API JSON — devuelve pedidos PedidosYa listos para retirar."""
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
        type='jsonrpc',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def mark_dispatched(self, order_id, **kwargs):
        """Marca un pedido PedidosYa como despachado."""
        order = request.env['pedidosya.order'].sudo().browse(order_id)
        if not order.exists():
            return {'status': 'error', 'message': 'Order not found'}
        try:
            order.action_mark_dispatched()
            return {'status': 'ok', 'state': order.state}
        except Exception as e:
            _logger.error('Kitchen mark_dispatched error: %s', str(e))
            return {'status': 'error', 'message': str(e)}
