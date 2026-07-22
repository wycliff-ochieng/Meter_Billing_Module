from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_metered = fields.Boolean(
        string='Is Metered',
        default=False,
        help="Check if this product is a metered utility (water, electricity, gas, etc.). "
             "When enabled, invoice lines for this product will show meter reading columns.",
    )
