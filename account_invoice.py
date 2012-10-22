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

import time
from osv import fields, osv
import decimal_precision as dp

class account_invoice(osv.osv):
    _inherit='account.invoice'

    def _amount_all(self, cr, uid, ids, name, args, context=None):
        res = {}
        for invoice in self.browse(cr, uid, ids, context=context):
            res[invoice.id] = {
                'amount_untaxed': 0.0,
                'amount_tax': 0.0,
                'amount_total': 0.0,
                'amount_subtotal': 0.0,
            }
            for line in invoice.invoice_line:
                res[invoice.id]['amount_subtotal'] += line.price_line_subtotal
            for line in invoice.invoice_line:
                res[invoice.id]['amount_untaxed'] += line.price_subtotal
            for line in invoice.tax_line:
                res[invoice.id]['amount_tax'] += line.amount
            res[invoice.id]['amount_total'] = res[invoice.id]['amount_tax'] + res[invoice.id]['amount_untaxed']
        return res

    def _get_invoice_line(self, cr, uid, ids, context=None):
        result = {}
        for line in self.pool.get('account.invoice.line').browse(cr, uid, ids, context=context):
            result[line.invoice_id.id] = True
        return result.keys()

    def _get_invoice_tax(self, cr, uid, ids, context=None):
        result = {}
        for tax in self.pool.get('account.invoice.tax').browse(cr, uid, ids, context=context):
            result[tax.invoice_id.id] = True
        return result.keys()

    _columns={
        'global_discount_ids':fields.many2many('sale.global.discount','account_invoice_global_discounts_rel','invoice_id','discount_id','Global Discounts', readonly=True, states={'draft': [('readonly', False)]}),
        'amount_untaxed': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Untaxed Amount',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line','global_discount_ids'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
            },
            multi='all', help="Total with discounts and without taxes."),
        'amount_tax': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Taxes',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line','global_discount_ids'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
            },
            multi='all'),
        'amount_total': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Total',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line','global_discount_ids'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
            },
            multi='all'),
        'amount_subtotal': fields.function(_amount_all, digits_compute=dp.get_precision('Account'), string='Amount Subtotal',
            store={
                'account.invoice': (lambda self, cr, uid, ids, c={}: ids, ['invoice_line','global_discount_ids'], 20),
                'account.invoice.tax': (_get_invoice_tax, None, 20),
                'account.invoice.line': (_get_invoice_line, ['price_unit','invoice_line_tax_id','quantity','discount','invoice_id'], 20),
            },
            multi='all', help="Total amount without global discounts."),
    }

    def onchange_discounts(self, cr, uid, ids, discounts,context=None):
        for invoice in self.browse(cr, uid, ids, context):    
            for line in invoice.invoice_line:
                self.pool.get('account.invoice.line').write(cr, uid, line.id, {}, context=context)
        return {}

account_invoice()

class account_invoice_line(osv.osv):
    _inherit='account.invoice.line'

    def _amount_line(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            res[line.id] = {
                'price_line_subtotal': 0.0,
                'price_subtotal': 0.0,
            }
            price = line.price_unit * (1-(line.discount or 0.0)/100.0)
            taxes = tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price, line.quantity, product=line.product_id, address_id=line.invoice_id.address_invoice_id, partner=line.invoice_id.partner_id)
            if line.invoice_id:
                discounts = line.invoice_id.global_discount_ids
            else:
                order_ids = self.pool.get('sale.order').search(cr, uid, [('name','=',line.origin)], context=context)
                order = self.pool.get('sale.order').browse(cr, uid, order_ids, context=context)
                if order!=[]: discounts = order[0].global_discount_ids
                else: discounts=[]
            for discount in discounts:
                price -= (price*discount.value/100.0)
            taxes_disc = tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price, line.quantity, product=line.product_id, address_id=line.invoice_id.address_invoice_id, partner=line.invoice_id.partner_id)
            if line.invoice_id:
                cur = line.invoice_id.currency_id
                res[line.id]['price_subtotal'] = taxes_disc['total']
                res[line.id]['price_line_subtotal']= taxes['total']
        return res

    def _price_unit_default(self, cr, uid, context=None):
        if context is None:
            context = {}
        if context.get('check_total', False):
            t = context['check_total']
            for l in context.get('invoice_line', {}):
                if isinstance(l, (list, tuple)) and len(l) >= 3 and l[2]:
                    tax_obj = self.pool.get('account.tax')
                    p = l[2].get('price_unit', 0) * (1-l[2].get('discount', 0)/100.0)
                    for discount in l[2].get('invoice_id').global_discount_ids:
                        p -= (p*discount.value/100.0)
                    t = t - (p * l[2].get('quantity'))
                    taxes = l[2].get('invoice_line_tax_id')
                    if len(taxes[0]) >= 3 and taxes[0][2]:
                        taxes = tax_obj.browse(cr, uid, list(taxes[0][2]))
                        for tax in tax_obj.compute_all(cr, uid, taxes, p,l[2].get('quantity'), context.get('address_invoice_id', False), l[2].get('product_id', False), context.get('partner_id', False))['taxes']:
                            t = t - tax['amount']
            return t
        return 0

    _columns = {
        'price_subtotal': fields.function(_amount_line, string='Global Subtotal', type="float", digits_compute= dp.get_precision('Account'), store=True, multi="sums"),
        'price_line_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account'), multi="sums"),
    }

    def move_line_get(self, cr, uid, invoice_id, context=None):
        res = []
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        if context is None:
            context = {}
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
        company_currency = inv.company_id.currency_id.id

        for line in inv.invoice_line:
            mres = self.move_line_get_item(cr, uid, line, context)
            if not mres:
                continue
            res.append(mres)
            tax_code_found= False
            #AddStart
            price = (line.price_unit * (1.0 - (line['discount'] or 0.0) / 100.0))
            if line.invoice_id:
                discounts = line.invoice_id.global_discount_ids
            else:
                order_ids = self.pool.get('sale.order').search(cr, uid, [('name','=',line.origin)], context=context)
                order = self.pool.get('sale.order').browse(cr, uid, order_ids, context=context)[0]
                discounts = order.global_discount_ids
            for discount in discounts:
                price -= (price*discount.value/100.0)
            #AddEnd
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price,
                    line.quantity, inv.address_invoice_id.id, line.product_id, inv.partner_id)['taxes']:

                if inv.type in ('out_invoice', 'in_invoice'):
                    tax_code_id = tax['base_code_id']
                    tax_amount = line.price_subtotal * tax['base_sign']
                else:
                    tax_code_id = tax['ref_base_code_id']
                    tax_amount = line.price_subtotal * tax['ref_base_sign']

                if tax_code_found:
                    if not tax_code_id:
                        continue
                    res.append(self.move_line_get_item(cr, uid, line, context))
                    res[-1]['price'] = 0.0
                    res[-1]['account_analytic_id'] = False
                elif not tax_code_id:
                    continue
                tax_code_found = True

                res[-1]['tax_code_id'] = tax_code_id
                res[-1]['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, tax_amount, context={'date': inv.date_invoice})
        return res


account_invoice_line()

class account_invoice_tax(osv.osv):
    _inherit = 'account.invoice.tax'

    def compute(self, cr, uid, invoice_id, context=None):
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id, context=context)
        cur = inv.currency_id
        company_currency = inv.company_id.currency_id.id
        for line in inv.invoice_line:
            #AddStart
            price = line.price_unit* (1-(line.discount or 0.0)/100.0)    
            if line.invoice_id:
                discounts = line.invoice_id.global_discount_ids
            else:
                order_ids = self.pool.get('sale.order').search(cr, uid, [('name','=',line.origin)], context=context)
                order = self.pool.get('sale.order').browse(cr, uid, order_ids, context=context)[0]
                discounts = order.global_discount_ids
            for discount in discounts:
                price -= (price*discount.value/100.0)
            #AddEnd
            for tax in tax_obj.compute_all(cr, uid, line.invoice_line_tax_id, price, line.quantity, inv.address_invoice_id.id, line.product_id, inv.partner_id)['taxes']:
                #tax['price_unit'] = cur_obj.round(cr, uid, cur, tax['price_unit'])
                val={}
                val['invoice_id'] = inv.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = tax['price_unit'] * line['quantity']
                if inv.type in ('out_invoice','in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_collected_id'] or line.account_id.id
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['ref_base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['ref_tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_paid_id'] or line.account_id.id

                key = (val['tax_code_id'], val['base_code_id'], val['account_id'])
                if not key in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']
        '''
        for t in tax_grouped.values():
            t['base'] = cur_obj.round(cr, uid, cur, t['base'])
            t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
            t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
            t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])'''
        return tax_grouped

account_invoice_tax()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
