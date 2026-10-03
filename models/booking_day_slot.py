from odoo import fields, models

WEEKDAYS = [
    ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), ('3', 'Thursday'),
    ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
]


class BookingDaySlot(models.Model):
    """Weekly configuration of a product: which weekdays are open, and on which time slots.

    A weekday without a line is closed. An open line without time slots offers every
    active time slot.
    """
    _name = 'booking.day.slot'
    _description = 'Booking Day Configuration'
    _order = 'product_tmpl_id, day'

    product_tmpl_id = fields.Many2one('product.template', required=True, ondelete='cascade',
                                      index=True)
    day = fields.Selection(WEEKDAYS, required=True)
    status = fields.Selection([('open', 'Open'), ('closed', 'Closed')], string='Status',
                              default='open', required=True)
    time_slot_ids = fields.Many2many(
        'booking.time.slot', string='Time Slots',
        help="Time slots offered on this weekday. Leave empty to offer all time slots.")

    _day_unique = models.Constraint(
        'UNIQUE(product_tmpl_id, day)',
        'Each weekday can only be configured once per product.')
