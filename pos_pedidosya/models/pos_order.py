# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


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

    @api.model
    def create_from_pedidosya(self, payload, pos_config):
        """
        Creates a pos.order from a PedidosYa webhook Order Dispatch payload.

        payload structure (PedidosYa Integration Middleware):
        {
            "order": {
                "id": "PYA-123456",
                "displayId": "ABC-123",
                "platform": {...},
                "orderTime": "2024-01-15T12:00:00Z",
                "estimatedPickupTime": "2024-01-15T12:30:00Z",
                "preorder": false,
                "customer": {
                    "name": "John Doe",
                    "phone": "+5491112345678",
                    "deliveryAddress": {...}
                },
                "products": [
                    {
                        "id": "PROD-001",
                        "name": "Burger",
                        "quantity": 2,
                        "unitPrice": 1500.0,
                        "totalPrice": 3000.0,
                        "variants": [...],
                        "comment": "No onions"
                    }
                ],
                "totalAmount": 3500.0,
                "deliveryFee": 500.0,
                "payment": {
                    "online": true,
                    "method": "ONLINE"
                }
            }
        }
        """
        order_data = payload.get('order', payload)
        order_id = str(order_data.get('id', ''))

        if not order_id:
            _logger.error('PedidosYa webhook: missing order ID in payload.')
            return False

        # Verificar si ya existe para evitar duplicados
        existing = self.env['pedidosya.order'].search([
            ('pedidosya_order_id', '=', order_id)
        ], limit=1)
        if existing:
            _logger.warning('PedidosYa order %s already exists. Skipping.', order_id)
            return existing

        # Obtener la sesión activa del POS
        pos_session = self.env['pos.session'].search([
            ('config_id', '=', pos_config.id),
            ('state', '=', 'opened'),
        ], limit=1)

        if not pos_session:
            _logger.error(
                'No open POS session found for config %s. Cannot create order.',
                pos_config.name,
            )
            # Registrar el pedido con error para no perderlo
            pedidosya_order = self.env['pedidosya.order'].create({
                'pedidosya_order_id': order_id,
                'pedidosya_vendor_id': pos_config.pedidosya_vendor_id,
                'pos_config_id': pos_config.id,
                'state': 'error',
                'error_message': 'No open POS session found.',
                'raw_payload': json.dumps(payload),
            })
            return pedidosya_order

        # Extraer datos del cliente
        customer_data = order_data.get('customer', {})
        delivery_address = customer_data.get('deliveryAddress', {})
        address_str = self._format_delivery_address(delivery_address)

        # Construir líneas de pedido
        # Soportar tanto 'products' (spec PedidosYa) como 'items' (payload simplificado)
        raw_products = order_data.get('products') or order_data.get('items', [])
        order_lines = self._build_order_lines(raw_products, pos_session)

        if not order_lines:
            _logger.error('PedidosYa order %s: no valid products found.', order_id)
            pedidosya_order = self.env['pedidosya.order'].create({
                'pedidosya_order_id': order_id,
                'pedidosya_vendor_id': pos_config.pedidosya_vendor_id,
                'pos_config_id': pos_config.id,
                'state': 'error',
                'error_message': 'No valid products found in order.',
                'raw_payload': json.dumps(payload),
            })
            return pedidosya_order

        # Crear el pos.order
        pos_order_vals = {
            'session_id': pos_session.id,
            'partner_id': False,
            'is_pedidosya': True,
            'lines': order_lines,
            'note': f"PedidosYa Order #{order_data.get('displayId', order_id)}",
        }

        pos_order = self.create(pos_order_vals)

        # Crear el pedidosya.order vinculado
        import datetime
        estimated_pickup = order_data.get('estimatedPickupTime')
        pickup_dt = None
        if estimated_pickup:
            try:
                pickup_dt = fields.Datetime.from_string(
                    estimated_pickup.replace('T', ' ').replace('Z', '')
                )
            except Exception:
                pass

        pedidosya_order = self.env['pedidosya.order'].create({
            'pedidosya_order_id': order_id,
            'platform_order_id': str(order_data.get('displayId', '')),
            'pedidosya_vendor_id': pos_config.pedidosya_vendor_id,
            'pos_config_id': pos_config.id,
            'pos_order_id': pos_order.id,
            'state': 'received',
            'customer_name': customer_data.get('name', ''),
            'customer_phone': customer_data.get('phone', ''),
            'delivery_address': address_str,
            'order_total': float(order_data.get('totalAmount', 0.0)),
            'estimated_pickup_time': pickup_dt,
            'is_preorder': order_data.get('preorder', False),
            'raw_payload': json.dumps(payload),
        })

        pos_order.write({'pedidosya_order_id': pedidosya_order.id})

        # ── Crear líneas en pedidosya.order.line ─────────────────────────
        for product_data in raw_products:
            remote_code = str(
                product_data.get('remoteCode') or product_data.get('id', '')
            )
            product = self.env['product.product'].search([
                ('default_code', '=', remote_code),
                ('available_in_pos', '=', True),
            ], limit=1)
            self.env['pedidosya.order.line'].create({
                'order_id': pedidosya_order.id,
                'product_id': product.id if product else False,
                'remote_code': remote_code,
                'product_name': product_data.get('name', ''),
                'quantity': float(product_data.get('quantity', 1)),
                'unit_price': float(product_data.get('unitPrice', 0.0)),
                'notes': product_data.get('comment', ''),
            })
        # ─────────────────────────────────────────────────────────────────

        _logger.info(
            'PedidosYa order %s created as POS order %s.',
            order_id,
            pos_order.name,
        )

        # Auto-aceptar si está configurado
        if pos_config.pedidosya_auto_accept:
            try:
                pedidosya_order.action_accept()
            except Exception as e:
                _logger.error(
                    'PedidosYa auto-accept failed for order %s: %s',
                    order_id,
                    str(e),
                )

        return pedidosya_order

    def _build_order_lines(self, products, pos_session):
        """
        Convert PedidosYa product list to Odoo POS order lines format.
        Matches products by internal reference (default_code) = remoteCode.
        Soporta tanto el campo 'remoteCode' como 'id' para el código del producto.
        """
        lines = []
        for product_data in products:
            # remoteCode es el campo oficial de PedidosYa; 'id' como fallback
            remote_code = str(
                product_data.get('remoteCode') or product_data.get('id', '')
            )
            product = self.env['product.product'].search([
                ('default_code', '=', remote_code),
                ('available_in_pos', '=', True),
            ], limit=1)

            if not product:
                _logger.warning(
                    'PedidosYa product with remoteCode %s not found in Odoo POS.',
                    remote_code,
                )
                continue

            qty = float(product_data.get('quantity', 1))
            unit_price = float(product_data.get('unitPrice', product.lst_price))
            note = product_data.get('comment', '')

            # Línea principal del producto
            line_vals = (0, 0, {
                'product_id': product.id,
                'qty': qty,
                'price_unit': unit_price,
                'customer_note': note,
            })
            lines.append(line_vals)

            # Variantes / modificadores como notas adicionales
            variants = product_data.get('variants', [])
            for variant in variants:
                variant_name = variant.get('name', '')
                variant_options = variant.get('options', [])
                for option in variant_options:
                    option_name = option.get('name', '')
                    option_code = str(option.get('id', ''))
                    option_product = self.env['product.product'].search([
                        ('default_code', '=', option_code),
                        ('available_in_pos', '=', True),
                    ], limit=1)
                    if option_product:
                        option_qty = float(option.get('quantity', 1))
                        option_price = float(option.get('price', 0.0))
                        lines.append((0, 0, {
                            'product_id': option_product.id,
                            'qty': option_qty * qty,
                            'price_unit': option_price,
                            'customer_note': f"[{variant_name}] {option_name}",
                        }))

        return lines

    def _format_delivery_address(self, address_data):
        """Format delivery address dict into readable string."""
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
