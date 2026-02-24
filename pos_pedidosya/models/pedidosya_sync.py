# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

MIDDLEWARE_STAGING = 'https://integration-middleware.stg.restaurant-partners.com'
MIDDLEWARE_PRODUCTION = 'https://integration-middleware.restaurant-partners.com'


class PedidosYaSync(models.AbstractModel):
    _name = 'pedidosya.sync'
    _description = 'PedidosYa API Synchronization'

    # ── Autenticación ────────────────────────────────────────────────────────

    def _get_access_token(self, pos_config):
        """
        Get a valid access token for the PedidosYa API.
        Refreshes automatically if expired.
        """
        now = fields.Datetime.now()
        if (
            pos_config.pedidosya_access_token
            and pos_config.pedidosya_token_expiry
            and pos_config.pedidosya_token_expiry > now + timedelta(minutes=5)
        ):
            return pos_config.pedidosya_access_token

        return self._refresh_token(pos_config)

    def _refresh_token(self, pos_config):
        """Call PedidosYa Login API to get a fresh access token."""
        url = f"{pos_config.pedidosya_middleware_url}/api/v1/login"
        payload = {
            'username': pos_config.pedidosya_plugin_username,
            'password': pos_config.pedidosya_plugin_password,
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            token = data.get('accessToken') or data.get('access_token')
            if not token:
                raise UserError(_('PedidosYa: No access token received from Login API.'))

            pos_config.sudo().write({
                'pedidosya_access_token': token,
                'pedidosya_token_expiry': fields.Datetime.now() + timedelta(hours=1),
            })
            return token
        except requests.exceptions.RequestException as e:
            _logger.error('PedidosYa login failed: %s', str(e))
            raise UserError(_('PedidosYa: Authentication failed. Check credentials.\n%s') % str(e))

    def _get_headers(self, pos_config):
        token = self._get_access_token(pos_config)
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        }

    # ── Gestión de órdenes ───────────────────────────────────────────────────

    def update_order_status(self, pedidosya_order, status, reason=None, pickup_time=None):
        """
        POST Update Order Status to PedidosYa Integration Middleware.
        status: 'order_accepted' | 'order_rejected' | 'order_picked_up'
        """
        pos_config = pedidosya_order.pos_config_id
        url = (
            f"{pos_config.pedidosya_middleware_url}"
            f"/api/v1/orders/{pedidosya_order.pedidosya_order_id}/status"
        )
        payload = {'status': status}

        if status == 'order_accepted' and pickup_time:
            payload['estimatedPickupTime'] = pickup_time.strftime('%Y-%m-%dT%H:%M:%SZ')

        if status == 'order_rejected' and reason:
            payload['rejectReason'] = reason

        try:
            response = requests.post(
                url,
                headers=self._get_headers(pos_config),
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            _logger.info(
                'PedidosYa order %s status updated to %s',
                pedidosya_order.pedidosya_order_id,
                status,
            )
            return True
        except requests.exceptions.RequestException as e:
            _logger.error(
                'PedidosYa update_order_status failed for order %s: %s',
                pedidosya_order.pedidosya_order_id,
                str(e),
            )
            pedidosya_order.write({
                'state': 'error',
                'error_message': str(e),
            })
            return False

    def mark_order_prepared(self, pedidosya_order):
        """
        POST Mark Order as Prepared — notifies PedidosYa that
        the order is ready for rider pickup.
        """
        pos_config = pedidosya_order.pos_config_id
        url = (
            f"{pos_config.pedidosya_middleware_url}"
            f"/api/v1/orders/{pedidosya_order.pedidosya_order_id}/prepared"
        )
        try:
            response = requests.post(
                url,
                headers=self._get_headers(pos_config),
                timeout=10,
            )
            response.raise_for_status()
            _logger.info(
                'PedidosYa order %s marked as prepared.',
                pedidosya_order.pedidosya_order_id,
            )
            return True
        except requests.exceptions.RequestException as e:
            _logger.error(
                'PedidosYa mark_order_prepared failed for order %s: %s',
                pedidosya_order.pedidosya_order_id,
                str(e),
            )
            return False

    # ── Disponibilidad del local ─────────────────────────────────────────────

    def update_vendor_availability(self, pos_config, is_open, close_until=None):
        """
        POST Update Vendor Availability — open or close the restaurant on PedidosYa.
        """
        url = (
            f"{pos_config.pedidosya_middleware_url}"
            f"/api/v1/vendors/{pos_config.pedidosya_vendor_id}/availability"
        )
        payload = {'available': is_open}
        if not is_open and close_until:
            payload['closeUntil'] = close_until.strftime('%Y-%m-%dT%H:%M:%SZ')

        try:
            response = requests.post(
                url,
                headers=self._get_headers(pos_config),
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            _logger.info(
                'PedidosYa vendor %s availability set to %s',
                pos_config.pedidosya_vendor_id,
                'open' if is_open else 'closed',
            )
            return True
        except requests.exceptions.RequestException as e:
            _logger.error('PedidosYa update_vendor_availability failed: %s', str(e))
            return False

    def get_vendor_availability(self, pos_config):
        """
        GET Vendor Availability — check current open/close status on PedidosYa.
        """
        url = (
            f"{pos_config.pedidosya_middleware_url}"
            f"/api/v1/vendors/{pos_config.pedidosya_vendor_id}/availability"
        )
        try:
            response = requests.get(
                url,
                headers=self._get_headers(pos_config),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error('PedidosYa get_vendor_availability failed: %s', str(e))
            return None

    # ── Reconciliación diaria ────────────────────────────────────────────────

    def reconcile_orders(self):
        """
        Cron job: reconcile orders from PedidosYa Order Report Service.
        Retrieves order IDs from last 24 hours and checks consistency with Odoo.
        """
        configs = self.env['pos.config'].search([
            ('pedidosya_enabled', '=', True),
            ('pedidosya_vendor_id', '!=', False),
        ])
        for config in configs:
            self._reconcile_vendor_orders(config)

    def _reconcile_vendor_orders(self, pos_config):
        url = (
            f"{pos_config.pedidosya_middleware_url}"
            f"/api/v1/orders/report/{pos_config.pedidosya_vendor_id}"
        )
        try:
            response = requests.get(
                url,
                headers=self._get_headers(pos_config),
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            order_ids = data.get('orderIds', [])
            _logger.info(
                'PedidosYa reconciliation for vendor %s: %d orders found in last 24h.',
                pos_config.pedidosya_vendor_id,
                len(order_ids),
            )
            for order_id in order_ids:
                existing = self.env['pedidosya.order'].search([
                    ('pedidosya_order_id', '=', str(order_id))
                ], limit=1)
                if not existing:
                    _logger.warning(
                        'PedidosYa order %s not found in Odoo — possible missed webhook.',
                        order_id,
                    )
        except requests.exceptions.RequestException as e:
            _logger.error(
                'PedidosYa reconciliation failed for vendor %s: %s',
                pos_config.pedidosya_vendor_id,
                str(e),
            )
