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

import netsvc
import pooler
import logging
from osv import osv, fields

_logger = logging.getLogger('auto.workflow.job')


class reconcile_job(osv.osv):
    """
    Deprecated model, replace by auto.workflow.job

    Pool of invoices to auto-reconcile
    Workaround for bug:https://bugs.launchpad.net/openobject-server/+bug/961919
    As we cannot reconcile within action_invoice_create
    We have to postpone the reconcilation
    """

    _name = 'base.sale.auto.reconcile.job'

    _columns = {
        'invoice_id': fields.many2one('account.invoice',
                                      string='Invoice',
                                      select=True,
                                      required=True)
    }

    def create(self, cr, uid, vals, context=None):
        """
        Deprecated, create an auto.workflow.job instead
        """
        _logger.debug(
            "Deprecated: use auto.workflow.job instead of "
            "base.sale.auto.reconcile.job")
        return self.pool.get('auto.workflow.job').create(
            cr, uid,
            {'res_model': 'account.invoice',
             'res_id': vals.get('invoice_id'),
             'action': 'auto_wkf_reconcile'},
            context=context)

    def run(self, cr, uid, ids=None, context=None):
        _logger.debug(
            "Deprecated: use auto.workflow.job instead of "
            "base.sale.auto.reconcile.job")
        return self.pool.get('auto.workflow.job').run(
            cr, uid, ids, context=context)

reconcile_job()


class auto_workflow_job(osv.osv):
    """ Previously the automatic workflows (validate invoice, picking,
    reconcile, ...) where all implemented in a method oe_status().

    This was not working because all the operations were done in the same time,
    provoking workflows / concurrency errors.

    This model aims to delay each automatic workflow actions using jobs.
    So a job is represented by :
     - a model
     - an id
     - an action (auto_wkf_validate, auto_wkf_reconcile, ...)

    Jobs should be called by a cron, but they can also be called once at a time
    if necessary.

    By convention, automatic workflow methods should begin with auto_wkf on
    models and their signature should be:
    auto_wkf_something(self, cr, uid, browse_record, context=None)

    They must return True if the operation is done or has already be done, so
    the job can be deleted. They must return False if the job still needs to be
    done
    """

    _name = 'auto.workflow.job'

    _columns = {
        'res_model': fields.char(
            'Resource Object', size=64, required=True, readonly=True),
        'res_id': fields.integer('Resource ID', required=True, readonly=True),
        'action': fields.char('Action', size=32),
    }

    def init(self, cr):
        """ Migration from base.sale.auto.reconcile.job"""
        cr.execute("""
        INSERT INTO auto_workflow_job (res_model, res_id, action)
          SELECT 'account.invoice', invoice_id, 'auto_wkf_reconcile'
          FROM base_sale_auto_reconcile_job
          EXCEPT
          SELECT res_model, res_id, action from auto_workflow_job
        """)
        cr.execute("DELETE FROM base_sale_auto_reconcile_job")

    def _call_action(self, cr, uid, job, context=None):
        """ Call the action of a job on the res_model model

        :param browse_record job: browse record instance of an
            auto.workflow.job
        :return: the return of the actions
        """
        model = self.pool.get(job.res_model)

        action_meth = getattr(model, job.action)
        record = model.browse(cr, uid, job.res_id, context=context)
        # the record could have been deleted meanwhile
        if not record:
            self.unlink(cr, uid, job.id, context=context)
            return False
        return action_meth(cr, uid, record, context=context)

    def run(self, cr, uid, ids=None, context=None):
        """ Call the actions of each job and commit after each job

        :param list/int/long ids: id of workflow jobs to process, if None
            they will all be processed
        :return: True
        """
        if ids is None:
            ids = self.search(cr, uid, [], context=context)
        elif isinstance(ids, (int, long)):
            ids = [ids]

        for job in self.browse(cr, uid, ids, context=context):
            local_cr = pooler.get_db(cr.dbname).cursor()
            try:
                if self._call_action(local_cr, uid, job, context=context):
                    self.unlink(local_cr, uid, job.id, context=context)
            except Exception:
                local_cr.rollback()
                _logger.exception(
                    "Failed to execute automatic workflow job %s"
                    "on %s with id %s", job.action, job.res_model, job.res_id)
            else:
                local_cr.commit()
            finally:
                local_cr.close()
        return True

auto_workflow_job()


class sale_order(osv.osv):

    _inherit = 'sale.order'

    def auto_wkf_validate(self, cr, uid, order, context=None):
        payment_settings = order.base_payment_type_id

        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(
                uid, 'sale.order', order.id, 'order_confirm', cr)

        self.init_auto_wkf_picking(cr, uid, order, context=context)

        # TODO put in a glue module
        cr.execute('select * from ir_module_module where name=%s and state=%s', ('mrp','installed'))
        if payment_settings.validate_manufactoring_order and cr.fetchone(): #if mrp module is installed
            self.pool.get('stock.picking').validate_manufactoring_order(cr, uid, order.name, context)

        if order.order_policy == 'prepaid':
            for invoice in order.invoice_ids:
                self.init_auto_wkf_invoice(cr, uid, order, invoice.id, context=context)

        elif order.order_policy == 'manual':
            self.init_auto_wkf_manual(cr, uid, order, context=context)

        # IF postpaid DO NOTHING
        # automatic worflows are handled in
        # action_invoice_create()

        elif order.order_policy == 'picking':
            self.init_auto_wkf_picking(cr, uid, order, context=context)
        return True

    def auto_wkf_cancel(self, cr, uid, order, context=None):
        """Interface method for the automatic worflow.
        Cancel an order

        :param browse_record order: the order to cancel
        :return: True if the order have been canceled, False if not
        """
        if order.state == 'cancel':
            return True
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'sale.order', order.id, 'cancel', cr)
        return True

    def auto_wkf_manual_invoice(self, cr, uid, order, context=None):
        """Interface method for the automatic worflow.
        Generate the invoice on an order

        :param browse_record order: the order
        :return: True if the invoice have been generated , False if not
        """
        if order.state not in ('draft', 'manual'):
            return True
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'sale.order', order.id, 'manual_invoice', cr)
        order.refresh()
        for invoice in order.invoice_ids:
            self.init_auto_wkf_invoice(cr, uid, order, invoice.id, context=context)
        return True

    def init_auto_wkf_validate(self, cr, uid, order, context=None):
        payment_settings = order.base_payment_type_id
        if payment_settings and payment_settings.validate_order:
            auto_wkf_obj = self.pool.get('auto.workflow.job')
            auto_wkf_obj.create(
                cr, uid,
                {'res_model': 'sale.order',
                 'res_id': order.id,
                 'action': 'auto_wkf_validate'},
                context=context)
        return True

    def init_auto_wkf_manual(self, cr, uid, order, context=None):
        payment_settings = order.base_payment_type_id
        if payment_settings and payment_settings.create_invoice:
            auto_wkf_obj = self.pool.get('auto.workflow.job')
            auto_wkf_obj.create(
                cr, uid,
                {'res_model': 'sale.order',
                 'res_id': order.id,
                 'action': 'auto_wkf_manual_invoice'},
                context=context)
        return True

    def init_auto_wkf_cancel(self, cr, uid, order, context=None):
        """Initialize the automatic workflow action to cancel an order

        :param browse_record order: order to cancel
        :return: True
        """
        auto_wkf_obj = self.pool.get('auto.workflow.job')
        auto_wkf_obj.create(
            cr, uid,
            {'res_model': 'sale.order',
             'res_id': order.id,
             'action': 'auto_wkf_cancel'},
            context=context)
        return True

    def init_auto_wkf_invoice(self, cr, uid, order, invoice_id, context=None):
        """Initialize the automatic workflow action to validate
        and reconcile the invoices based on payment settings

        :param browse_record order: order with invoices to validate
        :param int invoice_id: id of the invoice to validate
            must be provided because it is not necessarily
            linked with sale order (invoice on delivery)
        :return: True
        """
        payment_settings = order.base_payment_type_id
        if payment_settings and payment_settings.validate_invoice:
            auto_wkf_obj = self.pool.get('auto.workflow.job')
            auto_wkf_obj.create(
                cr, uid,
                {'res_model': 'account.invoice',
                 'res_id': invoice_id,
                 'action': 'auto_wkf_validate'},
                context=context)
            if payment_settings.is_auto_reconcile:
                auto_wkf_obj.create(
                    cr, uid,
                    {'res_model': 'account.invoice',
                     'res_id': invoice_id,
                     'action': 'auto_wkf_reconcile'},
                    context=context)
        return True

    def init_auto_wkf_picking(self, cr, uid, order, context=None):
        """Initialize the automatic workflow action to validate
        the order based on payment settings

        :param browse_record order: order with pickings to validate
        :return: True
        """
        payment_settings = order.base_payment_type_id
        if payment_settings and payment_settings.validate_picking:
            auto_wkf_obj = self.pool.get('auto.workflow.job')
            for picking in order.picking_ids:
                auto_wkf_obj.create(
                    cr, uid,
                    {'res_model': 'stock.picking',
                     'res_id': picking.id,
                     'action': 'auto_wkf_validate'},
                    context=context)
        return True

    def init_auto_wkf_picking_invoice(self, cr, uid, order, context=None):
        """Initialize the automatic workflow action when the invoices should
        be created from picking.

        :param browse_record order: order with pickings for which we generate
            invoices
        :return: True
        """
        payment_settings = order.base_payment_type_id
        if payment_settings and payment_settings.create_invoice:
            auto_wkf_obj = self.pool.get('auto.workflow.job')
            for picking in order.picking_ids:
                auto_wkf_obj.create(
                    cr, uid,
                    {'res_model': 'stock.picking',
                     'res_id': picking.id,
                     'action': 'auto_wkf_invoice'},
                    context=context)
        return True


class account_invoice(osv.osv):

    _inherit = 'account.invoice'

    def auto_wkf_validate(self, cr, uid, invoice, context=None):
        """Interface method for the automatic worflow.
        Validate an invoice in draft state.

        :param browse_record invoice: the invoice to validate
        :return: True if the invoice have been opened, False if not
        """
        if invoice.state in ('cancel', 'open', 'paid'):
            return True
        if invoice.state == 'draft':
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(
                uid, 'account.invoice', invoice.id, 'invoice_open', cr)
            return True
        return False

    def auto_wkf_reconcile(self, cr, uid, invoice, context=None):
        """Interface method for the automatic worflow.
        Auto-reconcile an invoice in open state.

        :param browse_record invoice: the invoice to reconcile
        :return: True if the invoice have been reconciled, False if not
        """
        if invoice.state in ('paid', 'cancel'):
            return True
        if invoice.state == 'open':
            return self.auto_reconcile_single(
                cr, uid, invoice.id, context=context)
        return False

class stock_picking(osv.osv):

    _inherit = 'stock.picking'

    def auto_wkf_validate(self, cr, uid, picking, context=None):
        """Interface method for the automatic worflow.
        Validate a picking in draft, confirmed or assigned state.

        :param browse_record picking: the picking to validate
        :return: True if the picking have been confirmed, False if not
        """
        if picking.state in ('cancel', 'done'):
            return True
        if picking.state in ('draft', 'confirmed', 'assigned'):
            self.validate_picking(cr, uid, [picking.id], context=context)
            return True
        return False

    def auto_wkf_invoice(self, cr, uid, picking, context=None):
        """Interface method for the automatic worflow.
        Create invoice from packing.

        :param browse_record picking: the picking to validate
        :return: True if the picking have been confirmed, False if not
        """
        if picking.state == '2binvoiced':
            invoice_ids = self.action_invoice_create(
                cr, uid, [picking.id], context=context)
            # if not linked to an order, we don't know if the invoice has to be
            # validated (no payment settings)
            if not picking.sale_id:
                return True
            for invoice_id in invoice_ids.itervalues():
                self.init_auto_wkf_invoice(cr, uid, picking.sale_id, invoice_id, context=context)
        # already invoiced or not applicable so we have to delete the job anyway
        return True

stock_picking()

