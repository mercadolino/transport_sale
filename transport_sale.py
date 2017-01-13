# -*- coding: utf-8 -*-
# © 2004-2010 Alien Group (<http://www.alien-group.com>).
# © 2015 Apulia Software 
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openerp import models, fields, api, _
from openerp.exceptions import Warning as UserError


class SaleOrderFleetVehicle(models.Model):
    _name = 'sale.order.fleet_vehicle'

    _description = 'All sales order and associated vehicles'

    sale_order_id = fields.Many2one('sale.order', ondelete='cascade')
    sales_date = fields.Date()
    partner_departure_id = fields.Many2one('res.partner', string='From')
    partner_destination_id = fields.Many2one('res.partner', string='To')
    delivery_date = fields.Datetime(help='The date that will start to transport')
    return_date = fields.Datetime(
        help='The expected date to finish all the transport')
    fleet_vehicle_id = fields.Many2one(
        'fleet.vehicle', ondelete='restrict')
    license_plate = fields.Char(size=64)
    internal_number = fields.Integer()
    employee_driver_id = fields.Many2one(
        'hr.employee', required=True, ondelete='restrict')
    employee_helper_id = fields.Many2one('hr.employee', ondelete='restrict')
    fleet_trailer_id = fields.Many2one('fleet.vehicle', ondelete='restrict')
    trailer_license_plate = fields.Char(size=64)
    cargo_ids = fields.One2many(
        'sale.order.cargo', 'sale_order_fleet_id',
        help='All sale order transported cargo')
    transport_complete = fields.Boolean(help="Mark this box if the transport is completed.")

    @api.onchange('fleet_trailer_id')
    def fleet_trailer_id_change(self):
        if not self.fleet_trailer_id:
            return False
        trailer = self.fleet_trailer_id
        if trailer:
            self.trailer_license_plate = trailer.license_plate

    @api.onchange('fleet_vehicle_id')
    def fleet_vehicle_id_change(self):
        if not self.fleet_vehicle_id:
            return False
        vehicle = self.fleet_vehicle_id
        sale_order = self.sale_order_id

        if vehicle:
            self.license_plate = vehicle.license_plate
            self.internal_number = vehicle.internal_number

        if sale_order:
            self.sales_date = sale_order.date_order
            self.partner_departure_id = sale_order.partner_departure_id.id
            self.partner_destination_id = sale_order.partner_shipping_id.id
            self.delivery_date = sale_order.delivery_date
            self.return_date = sale_order.return_date


class SaleOrderCargo(models.Model):
    _name = 'sale.order.cargo'

    _description = 'Transport cargo from a sale order transport service'

    sale_order_fleet_id = fields.Many2one(
        'sale.order.fleet_vehicle', ondelete='cascade', required=True)
    transport_date = fields.Date(
        required=True, help='The day when the product was transported.')
    cargo_product_id = fields.Many2one(
        'product.product',
        help='Associated port document of '
             'the transported product if applicable.')
    cargo_docport = fields.Char(
        help='Associated port document of '
             'the transported product if applicable.')
    brand = fields.Char(help='Brand of the transported product if applicable.')
    model = fields.Char(help='Model of the transported product if applicable.')
    cargo_ident = fields.Char(
        help='Identification of the cargo.Ex:Id,License Plate,Chassi')
    sale_order_id = fields.Many2one('sale.order', required=True)
    transport_from_id = fields.Many2one('res.partner', string='From')
    transport_to_id = fields.Many2one('res.partner', string='To')

    @api.onchange('cargo_product_id')
    def cargo_id_change(self):
        if not self.cargo_product_id:
            return False
        order_id = self.env.context.get('sale_order_id', False)

        if order_id:
            self.sale_order_id = order_id


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    fleet_vehicles_ids = fields.One2many(
        'sale.order.fleet_vehicle', 'sale_order_id')
    partner_departure_id = fields.Many2one('res.partner', required=True)
    delivery_date = fields.Date('Transport Start', required=True,
                                help='Expected Transport start date.')
    return_date = fields.Date('Transport Finish', required=True,
                              help='Expected Transport finish date.')
    cargo_ids = fields.One2many('sale.order.cargo', 'sale_order_id',
                                string='Cargo Manifest',
                                help='All transported cargo manifest.')

    @api.one
    @api.constrains('return_date', 'delivery_date')
    def _validate_data(self):
        for order in self:
            if order.return_date < order.delivery_date:
                raise UserError(_('Error: Invalid return date'))

    @api.one
    @api.constrains('cargo_ids')
    def _validate_cargo_products(self):
        cargo_products_ids = [
            cargo.cargo_product_id.id for cargo in self.cargo_ids]
        line_products_ids = [
            line.product_id.id for line in sale_order.order_line]
        if set(cargo_products_ids) != set(line_products_ids):
            raise UserError(_(
                "Error: There is a cargo product that "
                "doesn't belongs to the sale order line!"))

    @api.one
    @api.constrains('order_line')
    def _validate_cargo_products_qty(self):

        cargo_product_ids = [cargo.cargo_product_id.id for cargo in
                             self.cargo_ids]

        # ---- give all products for order line
        line_product_ids = [line.product_id.id for line in
                            self.order_line]
        line_product_qts = [line.product_uom_qty for line in
                            self.order_line]

        line_product_ids_qts = {}
        line_product_dif_ids = {}

        for idx, prod_id in enumerate(line_product_ids):
            if prod_id in line_product_ids_qts.keys():
                line_product_ids_qts[prod_id] += line_product_qts[idx]
            else:
                line_product_ids_qts[prod_id] = line_product_qts[idx]

        if not cargo_product_ids:
            result = True
        else:
            for cargo_product_id in set(cargo_product_ids):
                line_product_ids_dict = {
                    prod_id: qtd
                    for prod_id, qtd in line_product_ids_qts.iteritems()
                    if prod_id == cargo_product_id and
                    int(line_product_ids_qts[prod_id]) !=
                    cargo_product_ids.count(cargo_product_id)}

                line_product_dif_ids.update(line_product_ids_dict)

            if len(line_product_dif_ids) > 0:
                msg_format = ''
                line_product_names = self.env['product.product'].name_get(
                    line_product_dif_ids.keys())
                cargo_product_qts = [
                    cargo_product_ids.count(cargo_product_id) for
                    cargo_product_id in line_product_dif_ids.keys()]
                for product_name in line_product_names:
                    index = line_product_names.index(product_name)

                    msg_format = _(
                        'Product: {prod}\n\tOrder={order} '
                        'vs Cargo{cargo}'.format(
                            prod=product_name[1],
                            order=int(line_product_dif_ids[product_name[0]]),
                            cargo=cargo_product_qts[index]))

                message = _("The following products quantities in cargo "
                            "don't match\n quantities line:"
                            "\n{msg}".format(msg=msg_format))

                raise UserError(message)
            else:
                result = True
        return result


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    sales_order_ids = fields.One2many(
        'sale.order.fleet_vehicle', 'fleet_vehicle_id', string='Vehicle Sales')
    sales_order_trailer_ids = fields.One2many(
        'sale.order.fleet_vehicle', 'fleet_trailer_id', string='Trailer Sales')
    internal_number = fields.Integer()
    is_trailer = fields.Boolean()


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sales_order_ids = fields.One2many(
        'sale.order.fleet_vehicle', 'employee_driver_id',
        string='Driver Sales')
    sales_order_helper_ids = fields.One2many(
        'sale.order.fleet_vehicle', 'employee_helper_id',
        string='Driver Helper Sales')
    is_driver = fields.Boolean()
