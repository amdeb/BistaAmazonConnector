from osv import fields, osv
import base64, urllib
class product_images(osv.osv):
    _inherit = "product.images"
    def write(self,cr,uid,ids,vals,context={}):
       id =  super(product_images, self).write(cr, uid, ids,vals, context)
       amazon_url_location = self.browse(cr,uid,ids[0]).amazon_url_location
       print"amazon_url_location",amazon_url_location
       (filename, header) = urllib.urlretrieve(amazon_url_location)
       f = open(filename , 'rb')
       img_amazon = base64.encodestring(f.read())
       f.close()
       if img_amazon:
            cr.execute("UPDATE product_images SET preview_amazon='%s' where id=%d"%(img_amazon,ids[0],))
            f.close()
       return id

    def create(self,cr,uid,vals,context={}):
       id =  super(product_images, self).create(cr, uid, vals, context)
       amazon_url_location = self.browse(cr,uid,id).amazon_url_location
       (filename, header) = urllib.urlretrieve(amazon_url_location)
       f = open(filename , 'rb')
       img_amazon = base64.encodestring(f.read())
       f.close()
       if img_amazon:
            cr.execute("UPDATE product_images SET preview_amazon='%s' where id=%d"%(img_amazon,id,))
            f.close()
       return id
    _columns = {
        'amazon_url_location':fields.char('Full URL', size=256),
        'preview_amazon':fields.binary('Preview of Amazon Image'),
    }
    _defaults = {
        'link': lambda *a: False,
    }
    
product_images()