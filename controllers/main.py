from datetime import datetime
from urllib.parse import urlencode

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.tools.misc import format_date


class WebsiteBooking(http.Controller):

    def _get_products(self):
        return request.env['product.template'].sudo().search([
            ('is_booking_product', '=', True),
            ('sale_ok', '=', True),
            ('website_published', '=', True),
        ])

    @staticmethod
    def _parse_date(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    @http.route('/booking', type='http', auth='public', website=True, sitemap=True)
    def booking_list(self, error=None, **kw):
        products = self._get_products().filtered(lambda p: p._is_booking_available())
        return request.render('nextechis_website_booking_system.booking_page', {
            'products': products,
            'error': error,
        })

    @http.route('/booking/availability', type='http', auth='public', methods=['GET'],
                website=True, sitemap=False)
    def booking_availability(self, product_tmpl_id=None, date=None, **kw):
        """Time slots (with plans and quantity left) of one product on one date."""
        day = self._parse_date(date)
        try:
            product_id = int(product_tmpl_id)
        except (TypeError, ValueError):
            product_id = 0
        product = request.env['product.template'].sudo().browse(product_id).exists()
        slots = []
        if day and product and product.is_booking_product and product.sale_ok \
                and product.website_published:
            slots = product._get_booking_availability(day)
        return request.make_json_response(
            {'date': date, 'slots': slots}, headers=[('Cache-Control', 'no-store')])

    @http.route('/booking/add', type='http', auth='public', methods=['POST'],
                website=True, sitemap=False)
    def booking_add(self, product_tmpl_id=None, plan_id=None, slot_id=None, date=None,
                    qty=1, **kw):
        env = request.env

        def _back(msg, product=None):
            url = product.website_url if product else '/booking'
            sep = '&' if '?' in url else '?'
            return request.redirect(url + sep + urlencode({'error': msg}))

        day = self._parse_date(date)
        try:
            product_id, plan_id, slot_id, qty = (
                int(product_tmpl_id), int(plan_id), int(slot_id), int(qty))
        except (TypeError, ValueError):
            return request.redirect('/booking')
        if not day:
            return request.redirect('/booking')

        product = env['product.template'].sudo().browse(product_id).exists()
        plan = env['booking.plan'].sudo().browse(plan_id).exists()
        slot = env['booking.time.slot'].sudo().browse(slot_id).exists()
        if not (product and plan and slot) or not product.is_booking_product \
                or not product.sale_ok or not product.website_published:
            return _back("This booking is no longer available.")

        # Odoo 19+: the cart lives on ``request.cart``
        order = request.cart
        order = order.sudo() if order else order

        def _same_booking(line):
            return line.booking_plan_id == plan and line.booking_date == day \
                and line.booking_time_slot_id == slot

        line = order.order_line.filtered(_same_booking)[:1] if order else env['sale.order.line']
        try:
            product._validate_booking_selection(
                plan, day, slot, qty + (line.product_uom_qty if line else 0))
        except ValidationError as e:
            return _back(e.args[0], product)

        if not order:
            order = request.website._create_cart().sudo()

        try:
            with env.cr.savepoint():
                if line:
                    line.product_uom_qty += qty
                else:
                    env['sale.order.line'].sudo().create({
                        'order_id': order.id,
                        'product_id': product.product_variant_id.id,
                        'product_uom_qty': qty,
                        'booking_plan_id': plan.id,
                        'booking_date': day,
                        'booking_time_slot_id': slot.id,
                        'name': "%s - %s\n%s %s" % (
                            product.name, plan.name, format_date(env, day), slot.display_name),
                    })
        except ValidationError as e:
            return _back(e.args[0], product)
        return request.redirect('/shop/cart')
