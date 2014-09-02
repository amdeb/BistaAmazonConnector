from osv import fields, osv
from tools.translate import _
class create_amazon_shop(osv.osv_memory):
    _name = "create.amazon.shop"
    _description = "Create Amazon Shop"
    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(create_amazon_shop, self).view_init(cr, uid, fields_list, context=context)
        active_ids = context.get('active_ids',[])
        if active_ids:
            search_shop = self.pool.get('sale.shop').search(cr,uid,[('amazon_instance_id','=',active_ids[0])])
            if search_shop:
                raise osv.except_osv(_('Warning !'), _('Shop Is Already Created'))
        return res
    def create_amazon_shop_action(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        print"::::::::::create_amazon_shop_action called::::::::"
#        print"data_amazon_shop",data_amazon_shop
        data_amazon_shop = self.read(cr, uid, ids, context=context)[0]
        shop_vals = {
            'name' : data_amazon_shop.get('name',False),
            'warehouse_id' : data_amazon_shop.get('warehouse_id',False)[0],
            'cust_address' : data_amazon_shop.get('cust_address',False)[0],
            'company_id' : data_amazon_shop.get('company_id',False)[0],
            'amazon_picking_policy' : data_amazon_shop.get('picking_policy',False),
            'amazon_order_policy' : data_amazon_shop.get('order_policy',False),
            'amazon_invoice_quantity' : data_amazon_shop.get('invoice_quantity',False),
            'amazon_instance_id' : context.get('active_id') and context['active_id'] or False,
            'amazon_shop' : True,
        }
        print"shop_vals",shop_vals
        amazon_shop_id = self.pool.get('sale.shop').create(cr,uid,shop_vals,context)
        if amazon_shop_id:
            message = _('%s Shop Successfully Created!')%(data_amazon_shop['name'])
            self.pool.get('sale.shop').log(cr, uid, amazon_shop_id, message)
            return {'type': 'ir.actions.act_window_close'}
        else:
            message = _('Error creating amazon shop')
            self.log(cr, uid, ids[0], message)
            return False
    _columns = {
        'name': fields.char('Shop Name', size=64, required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse',required=True),
        'cust_address': fields.many2one('res.partner', 'Address', required=True),
#        'cust_address': fields.many2one('res.partner.address', 'Address', required=True),
        'company_id': fields.many2one('res.company', 'Company', required=False),
        'picking_policy': fields.selection([('direct', 'Partial Delivery'), ('one', 'Complete Delivery')],
                                           'Packing Policy', help="""If you don't have enough stock available to deliver all at once, do you accept partial shipments or not?""",required=True),
        'order_policy': fields.selection([
            ('prepaid', 'Payment Before Delivery'),
            ('manual', 'Shipping & Manual Invoice'),
            ('postpaid', 'Invoice on Order After Delivery'),
            ('picking', 'Invoice from the Packing'),
        ], 'Shipping Policy', help="""The Shipping Policy is used to synchronise invoice and delivery operations.
  - The 'Pay before delivery' choice will first generate the invoice and then generate the packing order after the payment of this invoice.
  - The 'Shipping & Manual Invoice' will create the packing order directly and wait for the user to manually click on the 'Invoice' button to generate the draft invoice.
  - The 'Invoice on Order After Delivery' choice will generate the draft invoice based on sale order after all packing lists have been finished.
  - The 'Invoice from the packing' choice is used to create an invoice during the packing process.""",required=True),
        'invoice_quantity': fields.selection([('order', 'Ordered Quantities'), ('procurement', 'Shipped Quantities')], 'Invoice on', help="The sale order will automatically create the invoice proposition (draft invoice). Ordered and delivered quantities may not be the same. You have to choose if you invoice based on ordered or shipped quantities. If the product is a service, shipped quantities means hours spent on the associated tasks.",required=True),
    }
    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'sale.shop', context=c),
    }
create_amazon_shop()