from odoo import fields, models


class BookingPlan(models.Model):
    """Global plan (e.g. Silver / Gold / Platinum). The price is set per product."""
    _name = 'booking.plan'
    _description = 'Booking Plan'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10, help="Plans are shown in this order on the website.")
    description = fields.Text(translate=True, help="Short text shown to the customer with the plan.")
    active = fields.Boolean(default=True)
