from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def float_to_time_str(value):
    hours, minutes = divmod(int(round(value * 60)), 60)
    return "%02d:%02d" % (hours, minutes)


class BookingTimeSlot(models.Model):
    """Global time slot (e.g. 09:00 - 11:00) that products can be booked on."""
    _name = 'booking.time.slot'
    _description = 'Booking Time Slot'
    _order = 'sequence, start_time, id'

    name = fields.Char(compute='_compute_name', store=True)
    sequence = fields.Integer(default=10)
    start_time = fields.Float(string='Start Time', required=True, default=9.0)
    end_time = fields.Float(string='End Time', required=True, default=10.0)
    active = fields.Boolean(default=True)

    @api.depends('start_time', 'end_time')
    def _compute_name(self):
        for slot in self:
            slot.name = "%s - %s" % (
                float_to_time_str(slot.start_time), float_to_time_str(slot.end_time))

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for slot in self:
            if not (0.0 <= slot.start_time < slot.end_time <= 24.0):
                raise ValidationError(_("The end time must be after the start time (same day)."))
