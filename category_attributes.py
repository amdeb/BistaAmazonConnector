from osv import osv, fields
class amazon_category(osv.osv):
    _name = "amazon.category"
    _columns = {
        'name': fields.char('Category Name', size=64,required=True,help="Ebay Category Name"),
        'amazon_attribute_ids': fields.one2many('amazon.attribute', 'amazon_categ_id', 'Attributes',readonly=True),
    }
amazon_category()

class amazon_attribute(osv.osv):
    _name = "amazon.attribute"
    _columns = {
        'name' : fields.char('Attribute Name', size=64),
        'amazon_categ_id' : fields.many2one('amazon.category', 'Category'),
        'attribute_values' : fields.one2many('amazon.attribute.value','amazon_att_id','Attribute Values'),
    }
amazon_attribute()


class amazon_attribute_value(osv.osv):
    _name = 'amazon.attribute.value'
    _columns = {
        'name':fields.char('Attribute Value', size=64),
        'amazon_att_id':fields.many2one('amazon.attribute','Attribute Master'),
    }
amazon_attribute_value()