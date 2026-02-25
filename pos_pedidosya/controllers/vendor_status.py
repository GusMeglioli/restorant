# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)


class VendorStatusController(http.Controller):

    def _get_pos_config(self):
        return request.env['pos.config'].sudo().search(
            [('pedidosya_enabled', '=', True)], limit=1
        )

    @http.route('/pedidosya/vendor/status', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def get_status(self, **kwargs):
        config = self._get_pos_config()
        if not config:
            return {'error': 'No PedidosYa config found'}
        pending = request.env['pedidosya.order'].sudo().search_count(
            [('state', 'in', ['received', 'accepted'])]
        )
        close_until = None
        if config.pedidosya_close_until:
            close_until = fields.Datetime.to_string(config.pedidosya_close_until)
        return {
            'is_open': config.pedidosya_is_open,
            'manual_override': config.pedidosya_manual_override,
            'close_until': close_until,
            'pending_orders': pending,
        }

    @http.route('/pedidosya/vendor/open', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def open_vendor(self, **kwargs):
        config = self._get_pos_config()
        if not config:
            return {'status': 'error', 'message': 'No config'}
        try:
            config.action_pedidosya_open()
            return {'status': 'ok', 'is_open': True}
        except Exception as e:
            _logger.error('Vendor open error: %s', str(e))
            return {'status': 'error', 'message': str(e)}

    @http.route('/pedidosya/vendor/close', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def close_vendor(self, close_minutes=None, **kwargs):
        config = self._get_pos_config()
        if not config:
            return {'status': 'error', 'message': 'No config'}
        try:
            close_until = None
            if close_minutes and int(close_minutes) > 0:
                close_until = fields.Datetime.now() + timedelta(minutes=int(close_minutes))
            config.action_pedidosya_close(close_until=close_until)
            return {'status': 'ok', 'is_open': False, 'close_until': fields.Datetime.to_string(close_until) if close_until else None}
        except Exception as e:
            _logger.error('Vendor close error: %s', str(e))
            return {'status': 'error', 'message': str(e)}
