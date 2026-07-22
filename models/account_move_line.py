from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    meter_previous = fields.Float(
        string='Previous',
        compute='_compute_meter_previous',
        store=True,
        help="Previous meter reading from the last posted invoice for the same partner and product.",
    )
    meter_new = fields.Float(
        string='New',
        default=0.0,
        help="Current meter reading captured for this billing cycle.",
    )
    meter_actual = fields.Float(
        string='Actual',
        compute='_compute_meter_actual',
        store=True,
        help="Net consumption: New reading minus Previous reading.",
    )
    meter_serial = fields.Char(
        string='Meter Serial / Ref',
        help="Serial number or reference of the physical meter associated with this reading.",
    )
    product_is_metered = fields.Boolean(
        related='product_id.is_metered',
        string='Is Metered',
    )

    @api.depends('product_id', 'move_id.partner_id', 'move_id.state')
    def _compute_meter_previous(self):
        for line in self:
            if not line.product_id or not line.move_id.partner_id:
                line.meter_previous = 0.0
                continue

            domain = [
                ('product_id', '=', line.product_id.id),
                ('move_id.partner_id', '=', line.move_id.partner_id.id),
                ('move_id.state', '=', 'posted'),
                ('meter_new', '>', 0),
            ]
            if line.move_id.move_type:
                domain.append(('move_id.move_type', '=', line.move_id.move_type))
            if line.id:
                domain.append(('id', '!=', line.id))

            last_line = self.search(
                domain,
                order='id desc',
                limit=1,
            )
            line.meter_previous = last_line.meter_new if last_line else 0.0

    @api.depends('meter_new', 'meter_previous')
    def _compute_meter_actual(self):
        for line in self:
            actual = max(line.meter_new - line.meter_previous, 0.0)
            line.meter_actual = actual
            line.quantity = actual

    @api.constrains('meter_new', 'meter_previous')
    def _check_meter_readings(self):
        for line in self:
            if line.meter_previous and line.meter_new < line.meter_previous:
                raise ValidationError(
                    f"For product '{line.product_id.name}', the New reading ({line.meter_new}) "
                    f"cannot be less than the Previous reading ({line.meter_previous})."
                )
