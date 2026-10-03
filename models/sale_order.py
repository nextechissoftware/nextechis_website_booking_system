from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date

# First key of the PostgreSQL advisory lock used to serialise bookings of one product.
BOOKING_LOCK_KEY = 190001


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    booking_plan_id = fields.Many2one('booking.plan', string='Booking Plan',
                                      ondelete='restrict', index='btree_not_null', copy=False)
    booking_date = fields.Date(string='Booking Date', index='btree_not_null', copy=False)
    booking_time_slot_id = fields.Many2one('booking.time.slot', string='Booking Time Slot',
                                           ondelete='restrict', index='btree_not_null',
                                           copy=False)

    def _get_booking_price(self):
        self.ensure_one()
        return self.product_id.product_tmpl_id.sudo()._get_booking_plan_price(
            self.booking_plan_id)

    @api.depends('booking_plan_id', 'product_id')
    def _compute_price_unit(self):
        booking_lines = self.filtered('booking_plan_id')
        for line in booking_lines:
            line.price_unit = line._get_booking_price()
            if 'technical_price_unit' in line._fields:
                line.technical_price_unit = line.price_unit
        super(SaleOrderLine, self - booking_lines)._compute_price_unit()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('booking_plan_id') and vals.get('product_id') \
                    and 'price_unit' not in vals:
                product = self.env['product.product'].sudo().browse(vals['product_id'])
                plan = self.env['booking.plan'].sudo().browse(vals['booking_plan_id'])
                vals['price_unit'] = product.product_tmpl_id._get_booking_plan_price(plan)
        return super().create(vals_list)

    @api.constrains('booking_plan_id', 'booking_date', 'booking_time_slot_id', 'product_id')
    def _check_booking_consistency(self):
        for line in self:
            chosen = [line.booking_plan_id, line.booking_date, line.booking_time_slot_id]
            if not any(chosen):
                continue
            if not all(chosen):
                raise ValidationError(_("A booking needs a plan, a date and a time slot."))
            tmpl = line.product_id.product_tmpl_id.sudo()
            if line.booking_plan_id not in tmpl.booking_plan_line_ids.plan_id:
                raise ValidationError(_("The plan does not belong to this product."))

    @api.constrains('booking_plan_id', 'booking_date', 'booking_time_slot_id', 'product_uom_qty')
    def _check_booking_quantities(self):
        orders = self.filtered(
            lambda l: l.booking_time_slot_id and l.order_id.state != 'cancel').order_id
        orders._check_booking_quantities()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    booking_order_ids = fields.One2many('booking.order', 'sale_order_id', string='Bookings')

    def _get_booking_lines(self):
        return self.order_line.filtered(
            lambda l: l.booking_plan_id and l.booking_date and l.booking_time_slot_id)

    def _check_booking_quantities(self, lock=False):
        """Make sure the booked quantities fit the capacity of every plan / date / slot."""
        for order in self.sudo():
            lines = order._get_booking_lines()
            if not lines:
                continue
            if lock:
                # serialise concurrent confirmations on the same products
                for tmpl_id in sorted(set(lines.product_id.product_tmpl_id.ids)):
                    self.env.cr.execute(
                        "SELECT pg_advisory_xact_lock(%s, %s)", [BOOKING_LOCK_KEY, tmpl_id])
            groups = {}
            for line in lines:
                key = (line.product_id.product_tmpl_id, line.booking_date,
                       line.booking_time_slot_id, line.booking_plan_id)
                groups[key] = groups.get(key, 0) + line.product_uom_qty
            sold_maps = {}
            for (tmpl, day, slot, plan), qty in groups.items():
                if (tmpl.id, day) not in sold_maps:
                    sold_maps[(tmpl.id, day)] = tmpl._get_booking_sold_map(
                        day, exclude_order=order)
                sold = sold_maps[(tmpl.id, day)].get((slot.id, plan.id), 0)
                tmpl._validate_booking_quantity(plan, day, slot, qty, sold)

    def _check_booking_lines(self):
        for order in self.sudo().filtered('website_id'):
            for line in order.order_line:
                if line.product_id.is_booking_product and not line.booking_time_slot_id:
                    raise ValidationError(_(
                        "'%s' must be booked with the Book Now button (date, time slot, plan "
                        "and quantity).", line.product_id.display_name))

    def _check_booking_selections(self):
        """Website carts: re-check dates, time slots and capacity just before payment."""
        for order in self.sudo().filtered('website_id'):
            for line in order._get_booking_lines():
                line.product_id.product_tmpl_id._validate_booking_selection(
                    line.booking_plan_id, line.booking_date, line.booking_time_slot_id,
                    line.product_uom_qty)

    def _check_booking_availability(self, lock=False):
        self._check_booking_lines()
        self._check_booking_quantities(lock=lock)

    def _check_cart_is_ready_to_be_paid(self):
        self._check_booking_lines()
        self._check_booking_selections()
        return super()._check_cart_is_ready_to_be_paid()

    def action_confirm(self):
        self._check_booking_availability(lock=True)
        res = super().action_confirm()
        self._create_booking_orders()
        return res

    def _create_booking_orders(self):
        vals_list = []
        for order in self:
            done = order.booking_order_ids.sale_line_id
            for line in order._get_booking_lines() - done:
                vals_list.append({'sale_order_id': order.id, 'sale_line_id': line.id})
        if vals_list:
            self.env['booking.order'].sudo().create(vals_list)
