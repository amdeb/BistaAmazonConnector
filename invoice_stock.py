
from osv import osv, fields

import time
import pytz,datetime
from pytz import timezone
from datetime import date, timedelta
from time import gmtime, strftime
from datetime import datetime
import netsvc
logger = netsvc.Logger()
from tools.translate import _
##############account invoice###################
class account_invoice(osv.osv):
    _inherit = "account.invoice"
    def create(self, cr, uid, vals, context=None):
        inv_id = super(account_invoice, self).create(cr, uid, vals, context)
        if vals.get('type',False) and vals['type'] == 'in_invoice':
            self.button_compute(cr,uid,[inv_id],context,set_total=True)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'account.invoice', inv_id, 'invoice_open', cr)
        return inv_id

    def invoice_pay_customer(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        accountinvoice_link = self.browse(cr,uid,ids[0])
        saleorder_obj = self.pool.get('sale.order')
        currentTime = time.strftime("%Y-%m-%d")
        period_id = self.pool.get('account.period').search(cr,uid,[('date_start','<=',currentTime),('date_stop','>=',currentTime)])
        if not period_id:
            raise wizard.except_wizard(_('Error !'), _('Period is not defined.'))
        else:
            period_id = period_id[0]

        if self.browse(cr,uid,ids[0]).type == 'out_invoice':
            cr.execute("SELECT invoice_id, order_id FROM sale_order_invoice_rel WHERE invoice_id =%d" % (ids[0],))
            saleorder_res = dict(cr.fetchall())
            saleorder_id = saleorder_res[ids[0]]
            saleorder_link = saleorder_obj.browse(cr,uid,saleorder_id)
            journal = self.pool.get('account.journal').browse(cr,uid,saleorder_link.journal_id.id)
            acc_id = journal.default_credit_account_id and journal.default_credit_account_id.id
            if not acc_id:
                raise wizard.except_wizard(_('Error !'), _('Your journal must have a default credit and debit account.'))
            paid = True
            company_id = self.pool.get('res.users').browse(cr,uid,uid).company_id.id
            voucher_id = saleorder_obj.generate_payment_with_pay_code(cr,uid,saleorder_link.ext_payment_method,saleorder_link.partner_id.id,saleorder_link.amount_total,accountinvoice_link.reference,accountinvoice_link.origin,currentTime,paid,context)
            invpay_return = self.pay_and_reconcile(cr, uid, ids, saleorder_link.amount_total, acc_id, period_id, saleorder_link.journal_id.id, False, period_id, False)
            wf_service.trg_write(uid, 'account.invoice', ids[0], cr)
            wf_service.trg_write(uid, 'sale.order', saleorder_id, cr)

        elif self.browse(cr,uid,ids[0]).type == 'in_invoice':
            cr.execute("SELECT invoice_id, purchase_id FROM purchase_invoice_rel WHERE invoice_id =%d" % (ids[0],))
            purchase_res = dict(cr.fetchall())
            purchase_id = purchase_res[ids[0]]
            purchase_obj = self.pool.get('purchase.order')
            purchase_link = purchase_obj.browse(cr,uid,purchase_id)
            journal = self.pool.get('account.journal').browse(cr,uid,purchase_link.journal_id.id)
            acc_id = journal.default_credit_account_id and journal.default_credit_account_id.id
            if not acc_id:
                raise wizard.except_wizard(_('Error !'), _('Your journal must have a default credit and debit account.'))
            paid = True
            voucher_id = saleorder_obj.generate_payment_with_journal(cr,uid,purchase_link.journal_id.id,purchase_link.partner_id.id,purchase_link.amount_total,accountinvoice_link.reference,accountinvoice_link.origin,currentTime,paid,context)
            picking_ids = purchase_link.picking_ids
            if picking_ids:
                for picking_id in picking_ids:
                    stockpicking_obj = self.pool.get('stock.picking')
                    stockpicking_obj.write(cr,uid,picking_id.id,{'invoice_state':'invoiced'})
                    if picking_id.state == 'done':
                        purchase_obj.write(cr,uid,purchase_id,{'state':'done'})
                    else:
                        purchase_obj.write(cr,uid,purchase_id,{'state':'invoiced'})
            else:
                purchase_obj.write(cr,uid,purchase_id,{'state':'invoiced'})
            invpay_return = self.pay_and_reconcile(cr, uid, ids, purchase_link.amount_total, acc_id, period_id, purchase_link.journal_id.id, False, period_id, False)
            wf_service.trg_write(uid, 'account.invoice', ids[0], cr)
            wf_service.trg_write(uid, 'purchase.order', purchase_id, cr)
        return True

    def confirm_paid(self, cr, uid, ids, context=None):
        res = super(account_invoice, self).confirm_paid(cr, uid, ids, context=None)
        type_chk = self.browse(cr,uid,ids[0]).type
        if type_chk == 'out_invoice':
            cr.execute("SELECT invoice_id, order_id FROM sale_order_invoice_rel WHERE invoice_id =%d" % (ids[0],))
            saleorder_res = dict(cr.fetchall())
            saleorder_id = saleorder_res[ids[0]]
            saleorder_obj = self.pool.get('sale.order')
            order_policy = saleorder_obj.browse(cr,uid,saleorder_id).order_policy
            if order_policy == 'prepaid':
                saleorder_obj.write(cr,uid,saleorder_id,{'state':'progress'})
            else:
                saleorder_obj.write(cr,uid,saleorder_id,{'state':'done'})
                picking_ids = saleorder_obj.browse(cr,uid,saleorder_id).picking_ids
                for picking_id in picking_ids:
                    self.pool.get('stock.picking').write(cr,uid,picking_id.id,{'invoice_state':'invoiced'})
        return res

account_invoice()



class stock_partial_picking(osv.osv_memory):
    _inherit = 'stock.partial.picking'
    
    def get_picking_type(self, cr, uid, picking, context=None):
        picking_type = picking.type
        for move in picking.move_lines:
            if picking.type == 'in' and move.product_id.cost_method == 'average':
                picking_type = 'in'
                break
            else:
                picking_type = 'out'
        return picking_type
    
    def do_partial(self, cr, uid, ids, context=None):
        """ Makes partial moves and pickings done.
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param fields: List of fields for which we want default values
        @param context: A standard dictionary
        @return: A dictionary which of fields with values.
        """
        pick_obj = self.pool.get('stock.picking')
        picking_ids = context.get('active_ids', False)
        partial = self.browse(cr, uid, ids[0], context=context)
        partial_datas = {
            'delivery_date' : partial.date
        }
        sale_id= pick_obj.browse(cr,uid,picking_ids[0]).sale_id.id
        sale_order_obj=self.pool.get('sale.order')
        sale_order_obj.write(cr,uid,sale_id,{'state':'done'})
        sale_order_obj.write(cr,uid,sale_id,{'shipped':True})
        for pick in pick_obj.browse(cr, uid, picking_ids, context=context):
            picking_type = self.get_picking_type(cr, uid, pick, context=context)
            moves_list = picking_type == 'in' and partial.product_moves_in or partial.product_moves_out
            for move in moves_list:
                partial_datas['move%s' % (move.move_id.id)] = {
                    'product_id': move.id,
                    'product_qty': move.quantity,
                    'product_uom': move.product_uom.id,
                    'prodlot_id': move.prodlot_id.id,
                }
                if (picking_type == 'in') and (move.product_id.cost_method == 'average'):
                    partial_datas['move%s' % (move.move_id.id)].update({
                                                    'product_price' : move.cost,
                                                    'product_currency': move.currency.id,
                                                    })
        pick_obj.do_partial(cr, uid, picking_ids, partial_datas, context=context)
        return {'type': 'ir.actions.act_window_close'}
stock_partial_picking()