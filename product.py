from osv import fields, osv
from tools.translate import _
import amazonerp_osv as connection_obj
class amazon_products_master(osv.osv):
    _name = "amazon.products.master"
    def action_process_amazon_details(self, cr, uid, ids, context=None):
        if context is None: context = {}
        return {
            'name':_("Amazon Product"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'amazon.product.lookup',
#            'res_id': ids,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': dict(context, active_ids=ids)
        }

    _columns = {
        'name' : fields.char('Product Name', size=64),
        'product_asin' : fields.char('ASIN',size=10),
        'product_category' : fields.char('Category', size=64),
        'product_id' : fields.many2one('product.product', 'Product'),
        'amazon_product_attributes' : fields.text('Extra Product Details'),
#        'product_attributes' : fields.one2many('amazon.products.attributes.master', 'attribute_id','Amazon Product Attributes'),
    }
amazon_products_master()

class product_product(osv.osv):
    _inherit = 'product.product'
    def onchange_amz_type(self,cr,uid,ids,amz_type,context={}):
        if not amz_type:
            res= {}
            res['amz_type_value']=''
            print"res",res
            return {'value':res}

    def _amazon_browse_node_get(self, cr, uid, context=None):
        amazon_browse_node_obj = self.pool.get('amazon.browse.node')
        amazon_browse_node_ids = amazon_browse_node_obj.search(cr, uid, [], order='browse_node_name')
        amazon_browse_node = amazon_browse_node_obj.read(cr, uid, amazon_browse_node_ids, ['id','browse_node_name'], context=context)
        return [(node['browse_node_name'],node['browse_node_name']) for node in amazon_browse_node]
    def _amazon_instance_get(self, cr, uid, context=None):
        amazon_instance_obj = self.pool.get('amazon.instance')
        amazon_instance_ids = amazon_instance_obj.search(cr, uid, [], order='name')
        amazon_instances = amazon_instance_obj.read(cr, uid, amazon_instance_ids, ['id','name'], context=context)
        return [(instance['id'],instance['name']) for instance in amazon_instances]

    ''' Assign by default one instance id to selection field on amazon instance '''
    def _assign_default_amazon_instance(self, cr, uid, context=None):
        amazon_instance_obj = self.pool.get('amazon.instance')
        amazon_instance_ids = amazon_instance_obj.search(cr, uid, [], order='name')
        amazon_instances = amazon_instance_obj.read(cr, uid, amazon_instance_ids, ['id','name'], context=context)
        if amazon_instances:
            return amazon_instances[0]['id']
        else:
            return False
    def amazon_product_lookup(self, cr, uid, ids, context=None):
        """
        Function to search product on amazon based on ListMatchingProduct Operation
        """
        amazon_instance_id  = self.browse(cr,uid,ids[0]).amazon_instance_id
        if not amazon_instance_id:
            raise osv.except_osv('Warning !','Please select Amazon Instance and try again.')
        amazon_instance_obj = self.pool.get('amazon.instance').browse(cr,uid,int(amazon_instance_id))
        product_query = self.browse(cr,uid,ids[0]).prod_query
        if not product_query:
            raise osv.except_osv('Warning !','Please enter Product Search Query and try again')
        product_query = product_query.strip().replace(' ','%')
        prod_query_contextid = self.browse(cr,uid,ids[0]).prod_query_contextid
        productData = False
        try:
            productData = connection_obj.call(amazon_instance_obj, 'ListMatchingProducts',product_query,prod_query_contextid)
            print'productData===--==-',productData
        except Exception, e:
            raise osv.except_osv(_('Error !'),e)
        if productData:
            ### Flushing amazon.products.master data to show new search data ###
            delete_all_prods = cr.execute('delete from amazon_products_master where product_id=%s',(ids[0],))
            for data in productData:
                keys_val = data.keys()
                prod_category = ''
                if 'Binding' in keys_val:
                    prod_category = data['Binding']
                prodvals = {
                        'name' : data['Title'],
                        'product_asin' : data['ASIN'],
                        'product_category' : prod_category,
                        'product_id' : ids[0],
                        'amazon_product_attributes' : data
                    }
                amazon_prod_master_obj = self.pool.get('amazon.products.master')
                amazon_prod_master_id  = amazon_prod_master_obj.create(cr,uid,prodvals)
        else:
                 raise osv.except_osv(_('Warning !'),'No products found on Amazon as per your search query. Please try again')
        return True
    _columns = {
        'amazon_sku': fields.char('Amazon SKU', size=126),
        'amazon_asin': fields.char('ASIN', size=16,readonly=True),
        'orderitemid': fields.char('Orderitemid', size=16),
        'product_order_item_id': fields.char('Order_item_id', size=256),
        'amazon_export':fields.boolean('Exported to Amazon'),
        'amazon_category':fields.many2one('amazon.category','Amazon Category'),
        'amz_type': fields.selection([('',''),('IBSN','IBSN'),('UPC','UPC'),('EAN','EAN'),('ASIN','ASIN')],'Type'),
        'amz_type_value': fields.char('Amazon Type Value', size=126),
        'amzn_condtn': fields.selection([('',''),('New','New'),('UsedLikeNew','Used Like New'),('UsedVeryGood','Used Very Good'),('UsedGood','UsedGood')
        ,('UsedAcceptable','Used Acceptable'),('CollectibleLikeNew','Collectible Like New'),('CollectibleVeryGood','Collectible Very Good'),('CollectibleGood','Collectible Good')
        ,('CollectibleAcceptable','Collectible Acceptable'),('Refurbished','Refurbished'),('Club','Club')],'Amazon Condition'),
        'prod_query': fields.char('Product Search Query', size=200, help="A search string with the same support as that is provided on Amazon marketplace websites."),
        'prod_query_contextid': fields.selection(_amazon_browse_node_get,'Query ContextId', help="An identifier for the context within which the given search will be performed."),
        'amazon_instance_id': fields.selection(_amazon_instance_get,'Amazon Instance', help="Select the Amazon instance where you want to perform search."),
        'amazon_products_ids': fields.one2many('amazon.products.master', 'product_id', 'Amazon Searched Products'),
        'amazon_prod_status':  fields.selection([('active','Active'),('fail','Failure')],'Status',readonly="True"),
        'operation_performed': fields.char('Operation Performed', size=126),
        'submit_feed_result' : fields.text('Submit Feed Result',readonly=True),
        'amazon_updated_price':fields.float('Amazon Updated Price',digits=(16,2)),
        'condition_note' : fields.text('Condition Note'),
    }
    _defaults = {
        'amzn_condtn':'',
        'amazon_instance_id': _assign_default_amazon_instance
    }
product_product()
