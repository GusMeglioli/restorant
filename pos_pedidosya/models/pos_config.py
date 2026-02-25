# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    pedidosya_enabled = fields.Boolean(string='Enable PedidosYa Integration', default=False)
    pedidosya_vendor_id = fields.Char(string='PedidosYa Vendor ID')
    pedidosya_remote_id = fields.Char(string='Remote ID')
    pedidosya_integration_type = fields.Selection(
        selection=[('direct', 'Direct Integration'), ('indirect', 'Indirect Integration')],
        string='Integration Type', default='direct')
    pedidosya_auto_accept = fields.Boolean(string='Auto-accept Orders', default=False)
    pedidosya_plugin_username = fields.Char(string='Plugin Username')
    pedidosya_plugin_password = fields.Char(string='Plugin Password')
    pedidosya_middleware_url = fields.Char(
        string='Middleware Base URL',
        default='https://integration-middleware.restaurant-partners.com')
    pedidosya_access_token = fields.Char(string='Access Token')
    pedidosya_token_expiry = fields.Datetime(string='Token Expiry')
    pedidosya_country = fields.Selection(
        selection=[('AR', 'Argentina'), ('UY', 'Uruguay'), ('CL', 'Chile'),
                    ('PY', 'Paraguay'), ('BO', 'Bolivia'), ('PE', 'Peru')],
        string='Country', default='AR')

    # Vendor availability
    pedidosya_is_open = fields.Boolean(string='PedidosYa Abierto', default=False)
    pedidosya_manual_override = fields.Boolean(string='Control Manual Activo', default=False)
    pedidosya_close_until = fields.Datetime(string='Cerrado hasta')
    pedidosya_schedule_ids = fields.One2many(
        comodel_name='pedidosya.schedule',
        inverse_name='pos_config_id',
        string='Horarios de apertura')

    @api.constrains('pedidosya_enabled', 'pedidosya_vendor_id', 'pedidosya_remote_id')
    def _check_pedidosya_config(self):
        for record in self:
            if record.pedidosya_enabled:
                if not record.pedidosya_vendor_id:
                    raise ValidationError(_('PedidosYa Vendor ID is required when integration is enabled.'))
                if not record.pedidosya_remote_id:
                    raise ValidationError(_('Remote ID is required when integration is enabled.'))

    def get_pedidosya_webhook_url(self):
        self.ensure_one()
        base_url = self.env['ir.config.parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/pedidosya/webhook/order/{self.pedidosya_remote_id}"

    def action_pedidosya_open(self):
        self.ensure_one()
        try:
            self.env['pedidosya.sync'].update_vendor_availability(self, True)
        except Exception:
            pass
        self.write({'pedidosya_is_open': True, 'pedidosya_manual_override': True, 'pedidosya_close_until': False})
        return True

    def action_pedidosya_close(self, close_until=None):
        self.ensure_one()
        try:
            self.env['pedidosya.sync'].update_vendor_availability(self, False, close_until=close_until)
        except Exception:
            pass
        self.write({'pedidosya_is_open': False, 'pedidosya_manual_override': True, 'pedidosya_close_until': close_until})
        return True

    def action_pedidosya_toggle(self):
        self.ensure_one()
        if self.pedidosya_is_open:
            self.action_pedidosya_close()
        else:
            self.action_pedidosya_open()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'message': 'PedidosYa ' + ('abierto ✅' if self.pedidosya_is_open else 'cerrado 🔴'), 'type': 'success' if self.pedidosya_is_open else 'warning', 'sticky': False}}

    def cron_pedidosya_schedule_check(self):
        configs = self.search([('pedidosya_enabled', '=', True), ('pedidosya_vendor_id', '!=', False)])
        for config in configs:
            config._apply_schedule()

    def _apply_schedule(self):
        import pytz
        from datetime import datetime
        if self.pedidosya_manual_override:
            if self.pedidosya_close_until:
                if fields.Datetime.now() >= self.pedidosya_close_until:
                    self.write({'pedidosya_manual_override': False, 'pedidosya_close_until': False})
                else:
                    return
            else:
                return
        if not self.pedidosya_schedule_ids:
            return
        tz_name = self.env.user.tz or 'America/Argentina/Buenos_Aires'
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone('America/Argentina/Buenos_Aires')
        now_local = datetime.now(tz)
        current_day = str(now_local.weekday())
        current_time = now_local.hour + now_local.minute / 60.0
        should_be_open = any(
            s.is_open_at(current_day, current_time)
            for s in self.pedidosya_schedule_ids
        )
        if should_be_open and not self.pedidosya_is_open:
            try:
                self.env['pedidosya.sync'].update_vendor_availability(self, True)
            except Exception:
                pass
            self.write({'pedidosya_is_open': True})
        elif not should_be_open and self.pedidosya_is_open:
            try:
                self.env['pedidosya.sync'].update_vendor_availability(self, False)
            except Exception:
                pass
            self.write({'pedidosya_is_open': False})
