# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 Lambda Software (http://www.lambdasoftware.net)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields, osv
import decimal_precision as dp

class global_discount(osv.osv):
    _name='sale.global.discount'
    _order = 'sequence ASC'
    _columns={
        'name' : fields.char('Reason', size=128, help='Reason of discount.'),
        'value': fields.float('Discount (%)', digits=(16, 2)),
        'sequence': fields.integer('Sequence', help='The sequence order to apply discounts.'),
        'default':fields.boolean('Default Discount', help='If checked this discount will be applied by default.')
    }
global_discount()    

class sale_order(osv.osv):
    _inherit='sale.order'

    def _amount_line_tax(self, cr, uid, line, context=None):
        val = 0.0
        precio_descuento = line.price_unit * (1-(line.discount or 0.0)/100.0)
        for discount in line.order_id.global_discount_ids:
            precio_descuento = precio_descuento * (1-(discount.value or 0.0) /100.0)
        for c in self.pool.get('account.tax').compute_all(cr, uid, line.tax_id, precio_descuento, line.product_uom_qty, line.order_id.partner_invoice_id.id, line.product_id, line.order_id.partner_id)['taxes']:
            val += c.get('amount', 0.0)
        return val

    def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
                'amount_subtotal':0.0,
            }
            val = val1 = val2 = 0.0
            cur = order.pricelist_id.currency_id
            for line in order.order_line:
                val2 += line.price_line_subtotal
                val1 += line.price_subtotal
                val += self._amount_line_tax(cr, uid, line, context=context)
            res[order.id]['amount_tax'] = val
            res[order.id]['amount_untaxed'] = val1
            res[order.id]['amount_subtotal'] = val2
            res[order.id]['amount_total'] = res[order.id]['amount_untaxed'] + res[order.id]['amount_tax']
        return res

    def _get_order(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('sale.order.line').browse(cr, uid, ids, context=context):
            result[line.order_id.id] = True
        return result.keys()

    def get_default_discounts(self, cr, uid, context={}):
        discount_ids = self.pool.get('sale.global.discount').search(cr, uid, [('default','=', True)])
        if discount_ids!=[]: return [[6,0,discount_ids]]
        else: return []

    _columns={
        'global_discount_ids':fields.many2many('sale.global.discount','sale_order_global_discounts_rel','order_id','discount_id','Descuentos globales', readonly=True, states={'draft': [('readonly', False)]}),
        'amount_untaxed': fields.function(_amount_all, digits_compute= dp.get_precision('Sale Price'), string='Untaxed Amount',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line','global_discount_ids'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="Total with discounts and without taxes."),
        'amount_tax': fields.function(_amount_all, digits_compute= dp.get_precision('Sale Price'), string='Taxes',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line','global_discount_ids'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="The tax amount."),
        'amount_total': fields.function(_amount_all, digits_compute= dp.get_precision('Sale Price'), string='Total',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line','global_discount_ids'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="The total amount."),
        'amount_subtotal': fields.function(_amount_all, digits_compute= dp.get_precision('Sale Price'), string='Amount Subtotal',
            store = {
                'sale.order': (lambda self, cr, uid, ids, c={}: ids, ['order_line','global_discount_ids'], 10),
                'sale.order.line': (_get_order, ['price_unit', 'tax_id', 'discount', 'product_uom_qty'], 10),
            },
            multi='sums', help="Total amount without global discounts."),

    }
    _defaults={
        'global_discount_ids': lambda self, cr, uid, context: self.get_default_discounts(cr, uid, context),
    }

    def _prepare_order_picking(self, cr, uid, order, context=None):
        res = super(sale_order, self)._prepare_order_picking(cr, uid, order, context)
        discounts=[]
        for discount in order.global_discount_ids: discounts.append(discount.id)
        res.update({'global_discount_ids': [(6, 0, discounts)]})
        return res

    def _prepare_invoice(self, cr, uid, order, lines, context=None):
        invoice_vals = super(sale_order,self)._prepare_invoice(cr, uid, order, lines, context)
        discounts = []
        for discount in order.global_discount_ids:
            if discount.id not in discounts: discounts.append(discount.id)
        invoice_vals.update({'global_discount_ids': [(6, 0, discounts)]})
        return invoice_vals

    def onchange_discounts(self, cr, uid, ids, discounts,context=None):
        for order in self.browse(cr, uid, ids, context):    
            for line in order.order_line:
                self.pool.get('sale.order.line').write(cr, uid, line.id, {}, context=context)
        return {}



sale_order()

class sale_order_line(osv.osv):
    _inherit='sale.order.line'

    def _amount_line(self, cr, uid, ids, field_name, arg, context=None):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = {}
        if context is None:
            context = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {
                'price_line_subtotal': 0.0,
                'price_subtotal': 0.0,
            }
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = tax_obj.compute_all(cr, uid, line.tax_id, price, line.product_uom_qty, line.order_id.partner_invoice_id.id, line.product_id, line.order_id.partner_id)
            for discount in line.order_id.global_discount_ids:
                price -= price * discount.value / 100.0
            taxes_disc = tax_obj.compute_all(cr, uid, line.tax_id, price, line.product_uom_qty, line.order_id.partner_invoice_id.id, line.product_id, line.order_id.partner_id)
            cur = line.order_id.pricelist_id.currency_id
            res[line.id]['price_line_subtotal'] = taxes['total']
            res[line.id]['price_subtotal'] = taxes_disc['total']
        return res

    _columns= {
        'price_subtotal': fields.function(_amount_line, string='Global Subtotal', digits_compute= dp.get_precision('Sale Price'), multi="sums"),
        'price_line_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Sale Price'), multi="sums"),
    }
sale_order_line()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
