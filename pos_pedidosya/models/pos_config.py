# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    # ── Configuración PedidosYa ──────────────────────────────────────────────
    pedidosya_enabled = fields.Boolean(
        string='Enable PedidosYa Integration',
        default=False,
    )
    pedidosya_vendor_id = fields.Char(
        string='PedidosYa Vendor ID',
        help='Vendor code provided by PedidosYa (Platform Vendor ID)',
    )
    pedidosya_remote_id = fields.Char(
        string='Remote ID',
        help='Unique identifier of this POS on your PedidosYa plugin',
    )
    pedidosya_integration_type = fields.Selection(
        selection=[
            ('direct', 'Direct Integration'),
            ('indirect', 'Indirect Integration'),
        ],
        string='Integration Type',
        default='direct',
        help=(
            'Direct: orders managed entirely from Odoo POS.\n'
            'Indirect: orders accepted first on PedidosYa device, '
            'then forwarded to POS.'
        ),
    )
    pedidosya_auto_accept = fields.Boolean(
        string='Auto-accept Orders',
        default=False,
        help='Automatically accept incoming PedidosYa orders without manual confirmation.',
    )
    pedidosya_plugin_username = fields.Char(
        string='Plugin Username',
        help='Username credential for incoming webhook authentication from PedidosYa.',
    )
    pedidosya_plugin_password = fields.Char(
        string='Plugin Password',
        help='Password credential for incoming webhook authentication from PedidosYa.',
    )
    pedidosya_middleware_url = fields.Char(
        string='Middleware Base URL',
        default='https://integration-middleware.restaurant-partners.com',
        help='PedidosYa Integration Middleware API base URL.',
    )
    pedidosya_access_token = fields.Char(
        string='Access Token',
        help='Token obtained from PedidosYa Login API. Refreshed automatically.',
    )
    pedidosya_token_expiry = fields.Datetime(
        string='Token Expiry',
    )
    pedidosya_country = fields.Selection(
        selection=[
            ('AR', 'Argentina'),
            ('UY', 'Uruguay'),
            ('CL', 'Chile'),
            ('PY', 'Paraguay'),
            ('BO', 'Bolivia'),
            ('PE', 'Peru'),
            ('EC', 'Ecuador'),
            ('DO', 'Dominican Republic'),
            ('PA', 'Panama'),
            ('CR', 'Costa Rica'),
            ('HN', 'Honduras'),
            ('GT', 'Guatemala'),
            ('SV', 'El Salvador'),
            ('NI', 'Nicaragua'),
            ('VE', 'Venezuela'),
        ],
        string='Country',
        default='AR',
    )

    @api.constrains('pedidosya_enabled', 'pedidosya_vendor_id', 'pedidosya_remote_id')
    def _check_pedidosya_config(self):
        for record in self:
            if record.pedidosya_enabled:
                if not record.pedidosya_vendor_id:
                    raise ValidationError(_(
                        'PedidosYa Vendor ID is required when integration is enabled.'
                    ))
                if not record.pedidosya_remote_id:
                    raise ValidationError(_(
                        'Remote ID is required when integration is enabled.'
                    ))

    def get_pedidosya_webhook_url(self):
        """Returns the full webhook URL to register in PedidosYa portal."""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/pedidosya/webhook/order/{self.pedidosya_remote_id}"

    # ── Estado apertura PedidosYa ────────────────────────────────────────────
    pedidosya_is_open = fields.Boolean(
        string='PedidosYa Abierto',
        default=False,
        help='Estado actual del local en PedidosYa.',
    )
    pedidosya_manual_override = fields.Boolean(
        string='Control Manual Activo',
        default=False,
        help='Si está activo, los horarios automáticos no sobreescriben el estado.',
    )
    pedidosya_close_until = fields.Datetime(
        string='Cerrado hasta',
        help='El local reabre automáticamente en esta fecha/hora.',
    )
    pedidosya_schedule_ids = fields.One2many(
        comodel_name='pedidosya.schedule',
        inverse_name='pos_config_id',
        string='Horarios de apertura',
    )

    # ── Acciones manuales ────────────────────────────────────────────────────

    def action_pedidosya_open(self):
        """Abre el local en PedidosYa manualmente."""
        self.ensure_one()
        try:
            self.env['pedidosya.sync'].update_vendor_availability(self, True)
        except Exception:
            pass  # non-blocking
        self.write({
            'pedidosya_is_open': True,
            'pedidosya_manual_override': True,
            'pedidosya_close_until': False,
        })
        return True

    def action_pedidosya_close(self, close_until=None):
        """Cierra el local en PedidosYa manualmente."""
        self.ensure_one()
        try:
            self.env['pedidosya.sync'].update_vendor_availability(
                self, False, close_until=close_until
            )
        except Exception:
            pass  # non-blocking
        self.write({
            'pedidosya_is_open': False,
            'pedidosya_manual_override': True,
            'pedidosya_close_until': close_until,
        })
        return True

    def action_pedidosya_toggle(self):
        """Toggle desde el back office."""
        self.ensure_one()
        if self.pedidosya_is_open:
            self.action_pedidosya_close()
        else:
            self.action_pedidosya_open()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'PedidosYa ' + ('abierto ✅' if self.pedidosya_is_open else 'cerrado 🔴'),
                'type': 'success' if self.pedidosya_is_open else 'warning',
                'sticky': False,
            },
        }

    # ── Cron: aplicar horarios automáticos ──────────────────────────────────

    def cron_pedidosya_schedule_check(self):
        """
        Se ejecuta cada 15 minutos.
        Aplica horarios automáticos a todos los POS con PedidosYa activo.
        Solo actúa si no hay override manual activo.
        """
        from datetime import datetime
        import pytz

        configs = self.search([
            ('pedidosya_enabled', '=', True),
            ('pedidosya_vendor_id', '!=', False),
        ])
        for config in configs:
            config._apply_schedule()

    def _apply_schedule(self):
        """
        Evalúa si hay que abrir o cerrar según los horarios configurados.
        Soporta turnos que cruzan medianoche (ej: 20:30 → 01:00 del día siguiente).
        """
        import pytz
        from datetime import datetime

        # Si hay override manual, verificar si expiró el close_until
        if self.pedidosya_manual_override:
            if self.pedidosya_close_until:
                if fields.Datetime.now() >= self.pedidosya_close_until:
                    # Expiró — quitar override y seguir con la evaluación del horario
                    self.write({
                        'pedidosya_manual_override': False,
                        'pedidosya_close_until': False,
                    })
                else:
                    return  # Cierre temporal vigente, no tocar nada
            else:
                return  # Override indefinido, el dueño manda

        if not self.pedidosya_schedule_ids:
            return  # Sin horarios configurados, nada que hacer

        # Hora local del usuario (fallback: Argentina)
        tz_name = self.env.user.tz or 'America/Argentina/Buenos_Aires'
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = pytz.timezone('America/Argentina/Buenos_Aires')

        now_local   = datetime.now(tz)
        current_day  = str(now_local.weekday())       # '0'=Lunes … '6'=Domingo
        current_time = now_local.hour + now_local.minute / 60.0

        # Evaluar TODOS los horarios usando is_open_at()
        # Esto cubre tanto turnos normales como los que cruzan medianoche
        should_be_open = any(
            s.is_open_at(current_day, current_time)
            for s in self.pedidosya_schedule_ids
        )

        # Solo actuar si hay un cambio real de estado
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
