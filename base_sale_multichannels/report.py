# -*- coding: utf-8 -*-
##############################################################################
#
#    Author: Guewen Baconnier
#    Copyright 2012 Camptocamp SA
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

from osv import osv, fields


class external_report_line(osv.osv):

    _inherit = 'external.report.line'

    _columns = {
        'shop_id': fields.many2one('sale.shop', 'Shop', readonly=True),
    }

    def _prepare_log_vals(self, cr, uid, model, action, res_id,
        external_id, referential_id, data_record, context=None):
        if context is None: context = {}
        vals = super(external_report_line, self)._prepare_log_vals(
            cr, uid, model, action, res_id, external_id,
            referential_id, data_record, context=context)

        if context.get('shop_id'):
            vals['shop_id'] = context['shop_id']
        return vals

