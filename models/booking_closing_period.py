from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BookingClosingPeriod(models.Model):
    """Date range during which a product cannot be booked (holidays, maintenance...)."""
    _name = 'booking.closing.period'
    _description = 'Booking Closing Period'
    _order = 'date_from desc, id'

    name = fields.Char(compute='_compute_name', store=True)
    date_from = fields.Date(string='From', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='To', required=True, default=fields.Date.context_today)

    @api.depends('date_from', 'date_to')
    def _compute_name(self):
        for period in self:
            period.name = "(%s - %s)" % (period.date_from or '', period.date_to or '')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for period in self:
            if period.date_to < period.date_from:
                raise ValidationError(_("The closing period must end on or after its start date."))
