# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging
import hmac
import hashlib

_logger = logging.getLogger(__name__)


class PedidosYaWebhook(http.Controller):

    @http.route(
        '/pedidosya/webhook/order/<string:remote_id>',
        type='json',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def order_dispatch(self, remote_id, **kwargs):
        """
        Receives Order Dispatch webhook from PedidosYa Integration Middleware.
        PedidosYa sends a POST with the full order payload when a new order arrives.
        """
        try:
            payload = request.get_json_data()
        except Exception as e:
            _logger.error('PedidosYa webhook: invalid JSON payload. %s', str(e))
            return {'status': 'error', 'message': 'Invalid JSON'}, 400

        _logger.info(
            'PedidosYa Order Dispatch received for remote_id=%s | order_id=%s',
            remote_id,
            payload.get('order', {}).get('id', 'unknown'),
        )

        # Buscar la configuración del POS por remote_id
        pos_config = request.env['pos.config'].sudo().search([
            ('pedidosya_remote_id', '=', remote_id),
            ('pedidosya_enabled', '=', True),
        ], limit=1)

        if not pos_config:
            _logger.warning(
                'PedidosYa webhook: no POS config found for remote_id=%s',
                remote_id,
            )
            return {'status': 'error', 'message': 'Vendor not found'}, 404

        # Validar autenticación básica si está configurada
        if pos_config.pedidosya_plugin_username and pos_config.pedidosya_plugin_password:
            if not self._validate_auth(request, pos_config):
                _logger.warning(
                    'PedidosYa webhook: unauthorized request for remote_id=%s',
                    remote_id,
                )
                return {'status': 'error', 'message': 'Unauthorized'}, 401

        # Crear el pedido en Odoo
        try:
            pedidosya_order = request.env['pos.order'].sudo().create_from_pedidosya(
                payload, pos_config
            )
            if pedidosya_order:
                return {
                    'status': 'ok',
                    'odoo_order_id': pedidosya_order.id,
                    'state': pedidosya_order.state,
                }
            return {'status': 'error', 'message': 'Failed to create order'}, 500
        except Exception as e:
            _logger.exception(
                'PedidosYa webhook: unhandled error creating order. %s', str(e)
            )
            return {'status': 'error', 'message': 'Internal error'}, 500

    @http.route(
        '/pedidosya/webhook/status/<string:remote_id>',
        type='json',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def order_status_update(self, remote_id, **kwargs):
        """
        Receives Order Status Update webhook from PedidosYa.
        Used to receive cancellation notifications (required for Direct Integration).
        """
        try:
            payload = request.get_json_data()
        except Exception as e:
            _logger.error('PedidosYa status webhook: invalid JSON. %s', str(e))
            return {'status': 'error', 'message': 'Invalid JSON'}, 400

        order_id = str(payload.get('orderId', '') or payload.get('order', {}).get('id', ''))
        new_status = payload.get('status', '')

        _logger.info(
            'PedidosYa Order Status Update: order=%s status=%s remote_id=%s',
            order_id, new_status, remote_id,
        )

        if not order_id or not new_status:
            return {'status': 'error', 'message': 'Missing orderId or status'}, 400

        pedidosya_order = request.env['pedidosya.order'].sudo().search([
            ('pedidosya_order_id', '=', order_id),
        ], limit=1)

        if not pedidosya_order:
            _logger.warning(
                'PedidosYa status webhook: order %s not found in Odoo.', order_id
            )
            return {'status': 'ok'}  # Responder 200 para evitar reintentos

        # Procesar cancelación
        if new_status == 'CANCELED':
            pedidosya_order.sudo().write({
                'state': 'canceled',
                'canceled_at': request.env['pedidosya.order']._fields[
                    'canceled_at'
                ].default(pedidosya_order) if False else __import__(
                    'odoo'
                ).fields.Datetime.now(),
            })
            _logger.info('PedidosYa order %s marked as canceled.', order_id)

        return {'status': 'ok'}

    @http.route(
        '/pedidosya/webhook/ping',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
    )
    def ping(self, **kwargs):
        """
        Health check endpoint.
        PedidosYa may use this to validate the plugin URL is reachable.
        """
        return request.make_response(
            json.dumps({'status': 'ok', 'service': 'PedidosYa POS Connector'}),
            headers=[('Content-Type', 'application/json')],
        )

    def _validate_auth(self, request, pos_config):
        """Validate Basic Auth credentials from PedidosYa webhook request."""
        import base64
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
