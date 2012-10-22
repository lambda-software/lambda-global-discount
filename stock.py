# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _columns = {
        'global_discount_ids':fields.many2many('sale.global.discount','stock_picking_global_discounts_rel','picking_id','discount_id','Descuentos globales', readonly=True, states={'draft': [('readonly', False)]}),
    }

    def _prepare_invoice(self, cr, uid, picking, partner, inv_type, journal_id, context=None):
        res = super(stock_picking, self)._prepare_invoice(cr, uid, picking, partner, inv_type, journal_id, context)
        discounts = []
        for discount in picking.global_discount_ids: discounts.append(discount.id)
        res.update({'global_discount_ids':[(6, 0, discounts)]})
        return res

stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
