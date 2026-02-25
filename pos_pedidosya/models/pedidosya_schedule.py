# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PedidosYaSchedule(models.Model):
    _name = 'pedidosya.schedule'
    _description = 'PedidosYa Opening Hours'
    _order = 'day_of_week asc, open_time asc'

    pos_config_id = fields.Many2one(
        'pos.config',
        string='POS Config',
        required=True,
        ondelete='cascade',
    )
    day_of_week = fields.Selection(
        selection=[
            ('0', 'Lunes'),
            ('1', 'Martes'),
            ('2', 'Miércoles'),
            ('3', 'Jueves'),
            ('4', 'Viernes'),
            ('5', 'Sábado'),
            ('6', 'Domingo'),
        ],
        string='Día de inicio',
        required=True,
    )
    open_time = fields.Float(
        string='Hora apertura',
        required=True,
        help='Ej: 20.5 = 20:30',
    )
    close_time = fields.Float(
        string='Hora cierre',
        required=True,
        help='Ej: 1.0 = 01:00 del día siguiente si es menor que la apertura.',
    )
    crosses_midnight = fields.Boolean(
        string='Cruza medianoche',
        compute='_compute_crosses_midnight',
        store=True,
        help='Se activa automáticamente cuando el cierre es menor que la apertura.',
    )
    active = fields.Boolean(default=True)

    @api.depends('open_time', 'close_time')
    def _compute_crosses_midnight(self):
        for r in self:
            r.crosses_midnight = (r.close_time < r.open_time)

    @api.constrains('open_time', 'close_time')
    def _check_times(self):
        for r in self:
            if r.open_time < 0 or r.open_time >= 24:
                raise ValidationError(_('La hora de apertura debe estar entre 0 y 23.99.'))
            if r.close_time <= 0 or r.close_time > 24:
                raise ValidationError(_('La hora de cierre debe estar entre 0.01 y 24.'))
            # Mismo horario exacto no tiene sentido
            if r.open_time == r.close_time:
                raise ValidationError(_('La hora de apertura y cierre no pueden ser iguales.'))

    def name_get(self):
        days = dict(self._fields['day_of_week'].selection)
        result = []
        for r in self:
            h_open  = '%02d:%02d' % (int(r.open_time),  round((r.open_time  % 1) * 60))
            h_close = '%02d:%02d' % (int(r.close_time), round((r.close_time % 1) * 60))
            suffix = ' (+1 día)' if r.crosses_midnight else ''
            result.append((r.id, f"{days.get(r.day_of_week, '')} {h_open}–{h_close}{suffix}"))
        return result

    def is_open_at(self, day_of_week_str, current_time_float):
        """
        Evalúa si este horario está activo en un momento dado.

        Soporta turnos que cruzan medianoche. La lógica es:

        CASO A — Turno normal (ej: 11:30–15:00, 20:30–23:30):
            El turno está activo si: open_time <= current_time < close_time
            Y el día coincide con day_of_week.

        CASO B — Turno que cruza medianoche (ej: 20:30–01:00):
            Se evalúa desde DOS días:
            • Desde el día de inicio: activo si current_time >= open_time
            • Desde el día SIGUIENTE: activo si current_time < close_time

        Recibe:
            day_of_week_str:   día actual como '0'–'6' (0=Lunes)
            current_time_float: hora actual como float (ej: 23.75 = 23:45, 0.5 = 00:30)
        """
        if not self.active:
            return False

        current_day = int(day_of_week_str)

        if not self.crosses_midnight:
            # Caso A — turno simple
            return (
                self.day_of_week == day_of_week_str
                and self.open_time <= current_time_float < self.close_time
            )
        else:
            # Caso B — cruza medianoche
            schedule_day = int(self.day_of_week)
            next_day = (schedule_day + 1) % 7

            # Estamos en el día de inicio y todavía no dimos medianoche
            if current_day == schedule_day and current_time_float >= self.open_time:
                return True

            # Estamos en el día siguiente y el turno todavía no cerró
            if current_day == next_day and current_time_float < self.close_time:
                return True

            return False
