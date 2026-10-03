from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBooking(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.silver = cls.env['booking.plan'].create({'name': 'Silver', 'sequence': 1})
        cls.gold = cls.env['booking.plan'].create({'name': 'Gold', 'sequence': 2})
        cls.slot = cls.env['booking.time.slot'].create({'start_time': 10.0, 'end_time': 11.0})
        cls.product = cls.env['product.template'].create({
            'name': 'Movie Show', 'type': 'service', 'is_booking_product': True,
            'sale_ok': True, 'list_price': 1.0, 'booking_max_qty': 5,
            # open every weekday: a weekday without a line is closed
            'booking_day_slot_ids': [
                (0, 0, {'day': str(weekday), 'status': 'open'}) for weekday in range(7)],
            'booking_plan_line_ids': [
                (0, 0, {'plan_id': cls.silver.id, 'price': 90.0}),
                (0, 0, {'plan_id': cls.gold.id, 'price': 135.0}),
            ],
        })
        cls.day = fields.Date.today() + timedelta(days=2)
        cls.partner = cls.env['res.partner'].create({'name': 'Booker'})

    def _order(self, qty, plan=None, day=None):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.product_variant_id.id,
                'product_uom_qty': qty,
                'booking_plan_id': (plan or self.silver).id,
                'booking_date': day or self.day,
                'booking_time_slot_id': self.slot.id,
            })],
        })

    def test_plan_price_used(self):
        self.assertEqual(self._order(1).order_line.price_unit, 90.0)
        self.assertEqual(self._order(1, plan=self.gold).order_line.price_unit, 135.0)

    def test_capacity_is_per_plan(self):
        order = self._order(5)
        order.action_confirm()
        self.assertEqual(len(order.booking_order_ids), 1)
        with self.assertRaises(ValidationError):
            self._order(1)
        # another plan on the same date and slot is not affected
        self._order(5, plan=self.gold).action_confirm()

    def test_cancel_releases_quantity(self):
        order = self._order(5)
        order.action_confirm()
        order.booking_order_ids.action_cancel()
        self._order(5).action_confirm()
        # the cancelled booking cannot be re-confirmed: the quantity is taken
        with self.assertRaises(ValidationError):
            order.booking_order_ids.action_reset()

    def test_availability_left(self):
        self._order(3).action_confirm()
        slots = self.product._get_booking_availability(self.day)
        plans = {p['id']: p['left'] for s in slots if s['id'] == self.slot.id for p in s['plans']}
        self.assertEqual(plans[self.silver.id], 2)
        self.assertEqual(plans[self.gold.id], 5)

    def _day_line(self):
        return self.product.booking_day_slot_ids.filtered(
            lambda l: l.day == str(self.day.weekday()))

    def test_unlisted_weekday_is_closed(self):
        self.assertTrue(self.product._is_booking_date_open(self.day))
        self._day_line().unlink()
        self.assertFalse(self.product._is_booking_date_open(self.day))
        self.assertFalse(
            next(d for d in self.product._get_booking_calendar()
                 if d['date'] == fields.Date.to_string(self.day))['enabled'])
        with self.assertRaises(ValidationError):
            self.product._validate_booking_selection(self.silver, self.day, self.slot, 1)

    def test_closed_weekday(self):
        self._day_line().status = 'closed'
        self.assertFalse(self.product._is_booking_date_open(self.day))

    def test_weekday_time_slots(self):
        other = self.env['booking.time.slot'].create({'start_time': 20.0, 'end_time': 21.0})
        self._day_line().time_slot_ids = other
        slot_ids = [s['id'] for s in self.product._get_booking_availability(self.day)]
        self.assertEqual(slot_ids, other.ids)

    def test_closing_period_and_window(self):
        self.product.booking_closing_period_ids = [(0, 0, {
            'date_from': self.day, 'date_to': self.day})]
        self.assertFalse(self.product._is_booking_date_open(self.day))
        self.product.booking_closing_period_ids = [(5, 0, 0)]
        self.product.write({'booking_limit_advance': True, 'booking_advance_days': 1})
        self.assertFalse(self.product._is_booking_date_open(self.day))
        self.assertTrue(self.product._is_booking_date_open(fields.Date.today() + timedelta(days=1)))

    def test_cannot_book_unlisted_plan(self):
        other_plan = self.env['booking.plan'].create({'name': 'Bronze'})
        with self.assertRaises(ValidationError):
            self._order(1, plan=other_plan)
