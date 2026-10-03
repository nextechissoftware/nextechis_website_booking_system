from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date

# Without an end date / advance limit, customers can book this many days ahead.
BOOKING_MAX_WINDOW_DAYS = 90


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_booking_product = fields.Boolean(
        string='Available for Booking', copy=False,
        help="Customers book this product from the website by date, time slot and plan.")
    booking_start_date = fields.Date(
        string='Start Date', help="First date on which the product can be booked.")
    booking_end_date = fields.Date(
        string='End Date', help="Last date on which the product can be booked.")
    booking_limit_advance = fields.Boolean(
        string='Limit Advance Booking',
        help="Only allow bookings a limited number of days ahead.")
    booking_advance_days = fields.Integer(
        string='Allowed Booking Period', default=7,
        help="How many days ahead (counting from today) a customer can book.")
    booking_closing_period_ids = fields.Many2many(
        'booking.closing.period', 'product_template_booking_closing_rel',
        'product_tmpl_id', 'period_id', string='Closing Periods',
        help="Date ranges on which the product cannot be booked.")
    booking_day_slot_ids = fields.One2many(
        'booking.day.slot', 'product_tmpl_id', string='Day Slots')
    booking_plan_line_ids = fields.One2many(
        'booking.product.plan', 'product_tmpl_id', string='Plans & Prices')
    booking_max_qty = fields.Integer(
        string='Max Booking Qty', default=5,
        help="Maximum quantity that can be booked for each plan, date and time slot.")

    @api.constrains('is_booking_product', 'booking_max_qty', 'booking_start_date',
                    'booking_end_date', 'booking_limit_advance', 'booking_advance_days')
    def _check_booking_config(self):
        for product in self.filtered('is_booking_product'):
            if product.booking_max_qty < 1:
                raise ValidationError(_("Max Booking Qty must be at least 1."))
            if (product.booking_start_date and product.booking_end_date
                    and product.booking_end_date < product.booking_start_date):
                raise ValidationError(_("The booking end date must be after the start date."))
            if product.booking_limit_advance and product.booking_advance_days < 1:
                raise ValidationError(_("The allowed booking period must be at least 1 day."))

    # ------------------------------------------------------------------
    # Calendar rules
    # ------------------------------------------------------------------
    def _booking_now(self):
        """Current datetime in the user / website timezone."""
        return fields.Datetime.context_timestamp(self, fields.Datetime.now())

    def _get_booking_window(self):
        """Return (first, last) bookable dates, or (None, None) when nothing is open."""
        self.ensure_one()
        today = self._booking_now().date()
        first = max(today, self.booking_start_date) if self.booking_start_date else today
        last = first + timedelta(days=BOOKING_MAX_WINDOW_DAYS - 1)
        if self.booking_end_date:
            last = min(last, self.booking_end_date)
        if self.booking_limit_advance:
            last = min(last, today + timedelta(days=self.booking_advance_days))
        return (first, last) if first <= last else (None, None)

    def _get_booking_time_slots(self, day):
        """Time slots offered on ``day`` according to the weekday configuration.

        Only weekdays with an *Open* line are bookable; a weekday without a line is closed.
        An open line without time slots offers all the active time slots.
        """
        self.ensure_one()
        line = self.booking_day_slot_ids.filtered(lambda l: l.day == str(day.weekday()))[:1]
        if not line or line.status != 'open':
            return self.env['booking.time.slot']
        if line.time_slot_ids:
            return line.time_slot_ids
        return self.env['booking.time.slot'].sudo().search([])

    def _is_booking_date_open(self, day, window=None):
        self.ensure_one()
        first, last = window or self._get_booking_window()
        if not first or not (first <= day <= last):
            return False
        if any(p.date_from <= day <= p.date_to for p in self.booking_closing_period_ids):
            return False
        return bool(self._get_booking_time_slots(day))

    def _is_booking_slot_past(self, day, slot, now=None):
        now = now or self._booking_now()
        return day == now.date() and slot.start_time <= now.hour + now.minute / 60.0

    def _get_booking_active_plan_lines(self):
        self.ensure_one()
        return self.booking_plan_line_ids.filtered(lambda l: l.plan_id.active)

    def _get_booking_prices(self):
        self.ensure_one()
        return [line.price for line in self._get_booking_active_plan_lines()]

    def _get_booking_plan_price(self, plan):
        self.ensure_one()
        return self.booking_plan_line_ids.filtered(lambda l: l.plan_id == plan)[:1].price

    def _is_booking_available(self):
        """True when the product can be booked on at least one date."""
        self.ensure_one()
        if not (self.is_booking_product and self._get_booking_active_plan_lines()):
            return False
        window = self._get_booking_window()
        if not window[0]:
            return False
        for offset in range((window[1] - window[0]).days + 1):
            if self._is_booking_date_open(window[0] + timedelta(days=offset), window):
                return True
        return False

    def _get_booking_calendar(self):
        """Dates of the bookable window, for the date strip of the website popup."""
        self.ensure_one()
        window = self._get_booking_window()
        if not window[0]:
            return []
        days = []
        for offset in range((window[1] - window[0]).days + 1):
            day = window[0] + timedelta(days=offset)
            days.append({
                'date': fields.Date.to_string(day),
                'weekday': format_date(self.env, day, date_format='EEE'),
                'day': format_date(self.env, day, date_format='d'),
                'month': format_date(self.env, day, date_format='MMM'),
                'enabled': self._is_booking_date_open(day, window),
            })
        return days

    # ------------------------------------------------------------------
    # Capacity
    # ------------------------------------------------------------------
    def _get_booking_sold_map(self, day, exclude_order=None):
        """Quantity already booked on ``day``: {(time_slot_id, plan_id): qty}."""
        self.ensure_one()
        domain = [
            ('product_tmpl_id', '=', self.id),
            ('booking_date', '=', day),
            ('state', 'in', ('confirmed', 'done')),
            ('sale_order_id.state', '=', 'sale'),
        ]
        if exclude_order:
            domain.append(('sale_order_id', '!=', exclude_order.id))
        groups = self.env['booking.order'].sudo()._read_group(
            domain, ['time_slot_id', 'plan_id'], ['quantity:sum'])
        return {(slot.id, plan.id): int(qty) for slot, plan, qty in groups}

    def _get_booking_availability(self, day):
        """Time slots of ``day`` with, for each, the plans and the quantity left."""
        self.ensure_one()
        window = self._get_booking_window()
        if not self._is_booking_date_open(day, window):
            return []
        now = self._booking_now()
        sold = self._get_booking_sold_map(day)
        plan_lines = self._get_booking_active_plan_lines()
        result = []
        for slot in self._get_booking_time_slots(day):
            if self._is_booking_slot_past(day, slot, now):
                continue
            plans = []
            for line in plan_lines:
                left = max(0, self.booking_max_qty - sold.get((slot.id, line.plan_id.id), 0))
                plans.append({
                    'id': line.plan_id.id,
                    'name': line.plan_id.name,
                    'description': line.plan_id.description or '',
                    'price': line.price,
                    'left': left,
                })
            result.append({'id': slot.id, 'name': slot.display_name, 'plans': plans})
        return result

    def _validate_booking_quantity(self, plan, day, slot, qty, sold):
        """Raise when ``qty`` does not fit in what is left after ``sold`` bookings."""
        self.ensure_one()
        left = self.booking_max_qty - sold
        if qty > left:
            raise ValidationError(_(
                "Only %(left)s left for '%(product)s' - %(plan)s on %(date)s (%(slot)s).",
                left=max(left, 0), product=self.display_name, plan=plan.display_name,
                date=format_date(self.env, day), slot=slot.display_name))

    def _validate_booking_selection(self, plan, day, slot, qty):
        """Full check of a customer's choice (calendar rules + capacity)."""
        self.ensure_one()
        if not self.is_booking_product or plan not in self._get_booking_active_plan_lines().plan_id:
            raise ValidationError(_("This plan is not available for '%s'.", self.display_name))
        if qty < 1:
            raise ValidationError(_("Please choose at least one."))
        window = self._get_booking_window()
        if not self._is_booking_date_open(day, window) \
                or slot not in self._get_booking_time_slots(day) \
                or self._is_booking_slot_past(day, slot):
            raise ValidationError(_("This date or time slot is no longer available."))
        sold = self._get_booking_sold_map(day).get((slot.id, plan.id), 0)
        self._validate_booking_quantity(plan, day, slot, qty, sold)

    def action_check_booking_quantity(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Booking Quantity: %s", self.display_name),
            'res_model': 'booking.order',
            'view_mode': 'pivot,list',
            'domain': [('product_tmpl_id', '=', self.id), ('state', '!=', 'cancelled')],
            'context': {'create': False},
        }
