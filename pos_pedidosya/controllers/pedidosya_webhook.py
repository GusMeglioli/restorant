# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging
import base64

_logger = logging.getLogger(__name__)


class PedidosYaWebhook(http.Controller):

    @http.route(
        '/pedidosya/webhook/order/<string:remote_id>',
        type='jsonrpc',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def order_dispatch(self, remote_id, **kwargs):
        """
        Recibe Order Dispatch webhook de PedidosYa.
        Crea únicamente un pedidosya.order (sin tocar pos.order).
        El frontend del POS mostrará el pedido al mozo para que lo procese.
        """
        try:
            payload = request.get_json_data()
        except Exception as e:
            _logger.error('PedidosYa webhook: JSON inválido. %s', str(e))
            return {'status': 'error', 'message': 'Invalid JSON'}, 400

        order_data = payload.get('order', payload)
        order_id = str(order_data.get('id', ''))

        _logger.info(
            'PedidosYa Order Dispatch recibido: remote_id=%s | order_id=%s',
            remote_id, order_id,
        )

        # Buscar la configuración del POS por remote_id
        pos_config = request.env['pos.config'].sudo().search([
            ('pedidosya_remote_id', '=', remote_id),
            ('pedidosya_enabled', '=', True),
        ], limit=1)

        if not pos_config:
            _logger.warning('No se encontró POS config para remote_id=%s', remote_id)
            return {'status': 'error', 'message': 'Vendor not found'}, 404

        # Validar autenticación Basic Auth
        if pos_config.pedidosya_plugin_username and pos_config.pedidosya_plugin_password:
            if not self._validate_auth(request, pos_config):
                _logger.warning('Autenticación fallida para remote_id=%s', remote_id)
                return {'status': 'error', 'message': 'Unauthorized'}, 401

        if not order_id:
            return {'status': 'error', 'message': 'Missing order ID'}, 400

        # Evitar duplicados
        existing = request.env['pedidosya.order'].sudo().search([
            ('pedidosya_order_id', '=', order_id)
        ], limit=1)
        if existing:
            _logger.warning('Pedido %s ya existe. Ignorando duplicado.', order_id)
            return {'status': 'ok', 'odoo_order_id': existing.id, 'state': existing.state}

        # Extraer datos del cliente
        customer_data = order_data.get('customer', {})
        delivery_address_data = customer_data.get('deliveryAddress', {})
        address_str = self._format_address(delivery_address_data)

        # Soporte para 'products' (spec oficial) o 'items' (payload simplificado)
        raw_items = order_data.get('products') or order_data.get('items', [])

        try:
            pedidosya_order = request.env['pedidosya.order'].sudo().create({
                'pedidosya_order_id': order_id,
                'platform_order_id': str(order_data.get('displayId', '')),
                'pedidosya_vendor_id': pos_config.pedidosya_vendor_id,
                'pos_config_id': pos_config.id,
                'state': 'received',
                'customer_name': customer_data.get('name', ''),
                'customer_phone': customer_data.get('phone', ''),
                'delivery_address': address_str,
                'order_total': float(order_data.get('totalAmount', 0.0)),
                'is_preorder': order_data.get('preorder', False),
                'raw_payload': json.dumps(payload),
            })

            # Crear líneas del pedido
            for item in raw_items:
                remote_code = str(item.get('remoteCode') or item.get('id', ''))
                product = request.env['product.product'].sudo().search([
                    ('default_code', '=', remote_code),
                    ('available_in_pos', '=', True),
                ], limit=1)
                request.env['pedidosya.order.line'].sudo().create({
                    'order_id': pedidosya_order.id,
                    'product_id': product.id if product else False,
                    'remote_code': remote_code,
                    'product_name': item.get('name', ''),
                    'quantity': float(item.get('quantity', 1)),
                    'unit_price': float(item.get('unitPrice', 0.0)),
                    'notes': item.get('comment', ''),
                })

            _logger.info('PedidosYa order %s creado con ID %s', order_id, pedidosya_order.id)

            # Auto-aceptar si está configurado
            if pos_config.pedidosya_auto_accept:
                try:
                    pedidosya_order.action_accept()
                except Exception as e:
                    _logger.error('Auto-accept fallido para %s: %s', order_id, str(e))

            return {
                'status': 'ok',
                'odoo_order_id': pedidosya_order.id,
                'state': pedidosya_order.state,
            }

        except Exception as e:
            _logger.exception('Error creando pedidosya.order para %s: %s', order_id, str(e))
            return {'status': 'error', 'message': 'Internal error'}, 500

    @http.route(
        '/pedidosya/webhook/status/<string:remote_id>',
        type='jsonrpc',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def order_status_update(self, remote_id, **kwargs):
        """
        Recibe actualizaciones de estado de PedidosYa (cancelaciones, etc).
        """
        try:
            payload = request.get_json_data()
        except Exception as e:
            _logger.error('PedidosYa status webhook: JSON inválido. %s', str(e))
            return {'status': 'error', 'message': 'Invalid JSON'}, 400

        order_id = str(payload.get('orderId', '') or payload.get('order', {}).get('id', ''))
        new_status = payload.get('status', '')

        _logger.info(
            'PedidosYa Status Update: order=%s status=%s remote_id=%s',
            order_id, new_status, remote_id,
        )

        if not order_id or not new_status:
            return {'status': 'error', 'message': 'Missing orderId or status'}, 400

        pedidosya_order = request.env['pedidosya.order'].sudo().search([
            ('pedidosya_order_id', '=', order_id),
        ], limit=1)

        if not pedidosya_order:
            _logger.warning('Pedido %s no encontrado en Odoo.', order_id)
            return {'status': 'ok'}  # 200 para evitar reintentos

        if new_status == 'CANCELED':
            from odoo import fields as odoo_fields
            pedidosya_order.write({
                'state': 'canceled',
                'canceled_at': odoo_fields.Datetime.now(),
            })
            _logger.info('Pedido %s marcado como cancelado.', order_id)

        return {'status': 'ok'}

    @http.route(
        '/pedidosya/webhook/ping',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def ping(self, **kwargs):
        """Health check endpoint para PedidosYa."""
        return request.make_response(
            json.dumps({'status': 'ok', 'service': 'PedidosYa POS Connector'}),
            headers=[('Content-Type', 'application/json')],
        )

    def _validate_auth(self, request, pos_config):
        """Valida Basic Auth del webhook de PedidosYa."""
        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Basic '):
            return False
        try:
            credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
            username, password = credentials.split(':', 1)
            return (
                username == pos_config.pedidosya_plugin_username
                and password == pos_config.pedidosya_plugin_password
            )
        except Exception:
            return False

    def _format_address(self, address_data):
        """Convierte dict de dirección a string legible."""
        if not address_data:
            return ''
        parts = [
            address_data.get('street', ''),
            address_data.get('number', ''),
            address_data.get('complement', ''),
            address_data.get('neighborhood', ''),
            address_data.get('city', ''),
            address_data.get('state', ''),
            address_data.get('country', ''),
        ]
        return ', '.join(p for p in parts if p)
