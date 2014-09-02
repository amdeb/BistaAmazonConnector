
from osv import fields, osv
from tools.translate import _
import ast

class amazon_product_lookup(osv.osv_memory):
    _name = "amazon.product.lookup"
    _description = "Details of Amazon product found in Item Search"

    _columns = {
        'name' : fields.char('Product Name', size=64,readonly=True),
        'product_asin' : fields.char('ASIN',size=10,readonly=True),
        'product_category' : fields.char('Category', size=64,readonly=True),
        'product_id' : fields.many2one('product.product', 'Product'),
        'product_attributes' : fields.many2many('amazon.products.attributes.master', 'amz_lookup_amzprodatt_rel', 'lookup_id','attribute_id','Amazon Product Attributes',readonly=True),
    }

    def assign_asin_to_product(self, cr, uid, ids, context=None):
        product_asin = self.browse(cr,uid,ids[0]).product_asin
        product_id = self.browse(cr,uid,ids[0]).product_id
        cr.execute("UPDATE product_product SET amz_type='ASIN',amz_type_value='%s' where id=%d"%(product_asin,product_id.id))

#        self.pool.get('product.product').write(cr,uid,product_id.id,{'amazon_asin':product_asin})
        return {'type': 'ir.actions.act_window_close'}

    def default_get(self, cr, uid, fields, context=None):
        """
        This function gets default values
        """
        
        if context is None:
            context = {}

        defaults = super(amazon_product_lookup, self).default_get(cr, uid, fields, context=context)
        active_id = context.get('active_ids')
        if not active_id:
            return defaults

        amazon_product = self.pool.get('amazon.products.master').browse(cr, uid, active_id[0], context=context)

        amazon_product_attributes = ast.literal_eval(amazon_product.amazon_product_attributes)

        amazon_prod_attr_ids =[]
        for key in amazon_product_attributes.keys():
               attributeVals = {
                    'attribute_name' : key,
                    'attribute_value' : amazon_product_attributes[key],
#                    'attribute_id' : active_id[0],
               }
               amazon_prod_attributes_master_obj = self.pool.get('amazon.products.attributes.master')
               amazon_prod_master_id  = amazon_prod_attributes_master_obj.create(cr,uid,attributeVals)
               amazon_prod_attr_ids.append(amazon_prod_master_id)

        defaults = {'name' :  amazon_product.name,
               'product_asin' : amazon_product.product_asin,
               'product_category' : amazon_product.product_category,
               'product_id' : amazon_product.product_id.id,
               'product_attributes': amazon_prod_attr_ids,
              }
        return defaults
amazon_product_lookup()


class amazon_products_attributes_master(osv.osv_memory):
    _name = "amazon.products.attributes.master"
    _rec_name = 'attribute_name'
    _columns = {
        'attribute_name' : fields.char('Attribute Name', size=64),
        'attribute_value' : fields.char('Attribute Value', size=64),
        #'attribute_id' : fields.many2one('amazon.products.lookup', 'Attributes'),
    }
amazon_products_attributes_master()