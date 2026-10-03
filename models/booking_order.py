from odoo import api, fields, models


class BookingOrder(models.Model):
    _name = 'booking.order'
    _description = 'Booking Order'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True,
                                    ondelete='cascade', index=True, readonly=True)
    sale_line_id = fields.Many2one('sale.order.line', required=True, ondelete='cascade',
                                   readonly=True)
    partner_id = fields.Many2one(related='sale_order_id.partner_id', store=True, index=True)
    company_id = fields.Many2one(related='sale_order_id.company_id', store=True, index=True)
    currency_id = fields.Many2one(related='sale_order_id.currency_id')
    product_tmpl_id = fields.Many2one(
        related='sale_line_id.product_id.product_tmpl_id', store=True, string='Product',
        index=True)
    plan_id = fields.Many2one(related='sale_line_id.booking_plan_id', store=True, string='Plan')
    booking_date = fields.Date(related='sale_line_id.booking_date', store=True, string='Date',
                               index=True)
    time_slot_id = fields.Many2one(related='sale_line_id.booking_time_slot_id', store=True,
                                   string='Time Slot')
    quantity = fields.Float(related='sale_line_id.product_uom_qty', store=True, digits=(16, 0))
    amount = fields.Monetary(related='sale_line_id.price_total', store=True,
                             currency_field='currency_id', string='Amount')
    sale_state = fields.Selection(related='sale_order_id.state', string='Order Status')
    state = fields.Selection(
        [('confirmed', 'Confirmed'), ('done', 'Done'), ('cancelled', 'Cancelled')],
        default='confirmed', required=True, tracking=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('booking.order') or 'New'
        return super().create(vals_list)

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        """Cancelling a booking releases its quantity on the date / time slot."""
        self.write({'state': 'cancelled'})

    def action_reset(self):
        """Re-confirm a cancelled booking, only if the quantity is still free."""
        self.mapped('sale_order_id')._check_booking_quantities(lock=True)
        self.write({'state': 'confirmed'})

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
        }
