from odoo import api, fields, models


class BookingProductPlan(models.Model):
    """A plan offered on a product, with the price of that plan for that product."""
    _name = 'booking.product.plan'
    _description = 'Booking Plan Price'
    _order = 'product_tmpl_id, sequence, id'

    product_tmpl_id = fields.Many2one('product.template', required=True, ondelete='cascade',
                                      index=True)
    plan_id = fields.Many2one('booking.plan', string='Plan', required=True, ondelete='cascade',
                              index=True)
    sequence = fields.Integer(related='plan_id.sequence', store=True)
    currency_id = fields.Many2one(related='product_tmpl_id.currency_id')
    price = fields.Monetary(currency_field='currency_id', required=True, default=0.0)

    _plan_unique = models.Constraint(
        'UNIQUE(product_tmpl_id, plan_id)', 'A plan can only be added once per product.')
    _price_positive = models.Constraint('CHECK(price >= 0)', 'The price cannot be negative.')

    @api.depends('plan_id')
    def _compute_display_name(self):
        for line in self:
            line.display_name = line.plan_id.display_name or ''
