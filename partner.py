from osv import fields, osv

class res_partner(osv.osv):
    _name = "res.partner"
    _inherit = "res.partner"
    _columns = {
        'amazon_access_key' : fields.char('Amazon Access Key',size=256),
        'amazon_shop_ids' : fields.many2many('sale.shop','partner_shop_id','partner_id','shop_id','Amazon Shops',readonly=True)
    }
res_partner()



