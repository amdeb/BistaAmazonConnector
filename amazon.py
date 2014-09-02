from osv import osv, fields
import time
import datetime
import xmlrpclib
import netsvc
logger = netsvc.Logger()
import urllib2
import base64
from tools.translate import _
import httplib, ConfigParser, urlparse
from xml.dom.minidom import parse, parseString
from lxml import etree
from xml.etree.ElementTree import ElementTree
import amazonerp_osv as connection_obj

class amazon_instance(osv.osv):
    _name = 'amazon.instance'
    def createAccountTax(self, cr, uid, id, value, context={}):
        accounttax_obj = self.pool.get('account.tax')
        accounttax_id = accounttax_obj.create(cr,uid,{'name':'Sales Tax(' + str(value) + '%)','amount':float(value)/100,'type_tax_use':'sale'})
        return accounttax_id
    
    def createAmazonShippingProduct(self, cr, uid, id, context={}):
        prod_obj = self.pool.get('product.product')
        prodcateg_obj = self.pool.get('product.category')
        categ_id = prodcateg_obj.search(cr,uid,[('name','=','Service')])
        if not categ_id:
            categ_id = prodcateg_obj.create(cr,uid,{'name':'Service'})
        else:
            categ_id = categ_id[0]
        prod_id = prod_obj.create(cr,uid,{'type':'service','name':'Shipping and Handling', 'default_code':'SHIP AMAZON','categ_id':categ_id})
        return prod_id
    def import_cat(self,cr,uid,ids,context={}):
        instance = self.browse(cr,uid,ids)[0]
        call = connection_obj.call(instance, 'POST_PRODUCT_DATA','data')

#        parser = etree.XMLParser(remove_blank_text=True)
#        data = etree.parse(open("/home/poonam/AMAZON/Lighting.xsd"),parser)
#        root = data.getroot().findall('schema/element')
#
#        print"root",root
#        fdf
#        for each_iter in root.iter("*"):
#             print"each_iter",each_iter
#             tag = each_iter.tag
#             print"tag",tag
#             if tag.split('}')[-1] =='element':
#                print"this is the element tag"
#             attribute = each_iter.attrib
#             print"attribute",attribute
#             if attribute.get('ref'):
#                find_value = data.find('LightsAndFixtures')
#                print"find_value",find_value

        return True
    def amazon_oe_status(self, cr, uid, order_id, paid=True, context = None, defaults = None):
        saleorder_obj = self.pool.get('sale.order')
        order = saleorder_obj.browse(cr, uid, order_id, context)
        if order.ext_payment_method:
            payment_settings = saleorder_obj.payment_code_to_payment_settings(cr, uid, order.ext_payment_method, context)
            wf_service = netsvc.LocalService("workflow")
            if payment_settings:
                 if payment_settings.order_policy == 'prepaid':
                    cr.execute("UPDATE sale_order SET order_policy='prepaid' where id=%d"%(order_id,))
                    cr.commit()
                    if payment_settings.validate_order:
                        try:
                            wf_service.trg_validate(uid, 'sale.order', order_id, 'order_confirm', cr)
                        except Exception, e:
                            self.log(cr, uid, order_id, "ERROR could not valid order")
                    if payment_settings.validate_invoice:
                        for invoice in order.invoice_ids:
                            wf_service.trg_validate(uid, 'account.invoice', invoice.id, 'invoice_open', cr)
                            if payment_settings.is_auto_reconcile and paid:
                                self.pool.get('account.invoice').invoice_pay_customer(cr, uid, [invoice.id], context=context)
        return True
   
    def updatePartnerAddress(self, cr, uid, id, resultvals, part_id, context={}):
        country_obj = self.pool.get('res.country')
        state_obj = self.pool.get('res.country.state')
        if not part_id:
            return False
        country_id = country_obj.search(cr,uid,[('code','=',resultvals['CountryCode'])])
        state_id = state_obj.search(cr,uid,[('name','=',resultvals['StateOrRegion'])])
        if not country_id:
            country_id = country_obj.create(cr,uid,{'code':resultvals['CountryCode'][:2], 'name':resultvals['CountryCode']})
        else:
            country_id = country_id[0]
        
        if not state_id:
            state_id = state_obj.create(cr,uid,{'country_id':country_id, 'name':resultvals['StateOrRegion'], 'code':resultvals['StateOrRegion'][:3]})
        else:
            state_id = state_id[0]
        if resultvals.has_key('AddressLine1'):
            street = resultvals['AddressLine1']
        else:
            street = ''
        if resultvals.has_key('City'):
            city = resultvals['City']
        else:
            city = ''
        if resultvals.has_key('PostalCode'):
            postalcode = resultvals['PostalCode']
        else:
            postalcode = ''
        address_id = self.pool.get('res.partner').search(cr,uid, [('country_id','=',country_id),('state_id','=',state_id),('city','=',city),('street','=',street),('zip','=',postalcode)])
#        address_id = self.pool.get('res.partner.address').search(cr,uid, [('country_id','=',country_id),('state_id','=',state_id),('city','=',city),('street','=',street),('zip','=',postalcode)])
        if address_id:
            address_id = address_id
        if not address_id:
            addressvals = {
                'name' : resultvals['Name'],
                'street' : street,
                'city' : city,
                'country_id' : country_id,
                'phone' : resultvals.get('Phone',False) and resultvals['Phone'] or False,
                'zip' : postalcode,
                'state_id' : state_id,
#                'partner_id' : part_id,
                'type' : 'default',
            }
            address_id = self.pool.get('res.partner').create(cr,uid,addressvals)
#            address_id = self.pool.get('res.partner.address').create(cr,uid,addressvals)
        return address_id

    def updatePartner(self, cr, uid, id, shop_id, resultvals, part_id=0, context={}):
        partner_id = False
        partner_obj = self.pool.get('res.partner')
        partnervals = {
            'customer' : True,
            'name' : resultvals['Name'],
            'amazon_shop_ids' : [(6,0,[shop_id])]
        }
        if part_id == 0:
            partner_id = partner_obj.create(cr,uid, partnervals)
        else:
            partner_obj.write(cr,uid, part_id, partnervals)
            partner_id = part_id
        return partner_id

    def createProduct(self, cr, uid, id, shop_id, product_details, result=False, context={}):
        prodtemp_obj = self.pool.get('product.template')
        prod_obj = self.pool.get('product.product')
        quantity_ordered = product_details.get('QuantityOrdered',False)
        item_price = product_details.get('Amount',False)
        list_price = float(item_price) / float(quantity_ordered)
        template_vals = {
            'list_price' : list_price,
            'purchase_ok' : 'TRUE',
            'sale_ok' : 'TRUE',
            'name' : product_details.get('Title',False),
            'type' : 'product',
            'procure_method' : 'make_to_stock',
            'cost_method' : 'standard',
        }
        template_id = prodtemp_obj.create(cr,uid,template_vals)
        product_vals = {
            'product_tmpl_id' : template_id,
            'amazon_sku': product_details.get('SellerSKU',False),
            'amazon_asin' : product_details.get('ASIN',False),
            'amazon_prod_status' : 'active',
            'amazon_export' : 'True',
            'product_order_item_id' : product_details.get('OrderItemId',False),
        }
        prod_id = prod_obj.create(cr,uid,product_vals)
        return prod_id
    
    def createOrder(self, cr, uid, id, shop_id, resultvals, context={}):
        saleorderid = False
        saleorder_obj = self.pool.get('sale.order')
        for resultval in resultvals:
            if resultval != {} and resultval.has_key('Name') :
                partner_obj = self.pool.get('res.partner')
                saleorderid = saleorder_obj.search(cr,uid,[('amazon_order_id','=',resultval.get('AmazonOrderId',False))])
                if not saleorderid:
                    partner_id = partner_obj.search(cr, uid, [('name','=',resultval['Name'])]) or [0]
                    partner_id_update = self.updatePartner(cr,uid,id,shop_id,resultval,partner_id[0])
                    partneraddress_id = self.updatePartnerAddress(cr,uid,id,resultval,partner_id_update)
                    partner_order_id = partner_obj.address_get(cr,uid,[partner_id_update], ['contact' or 'default'])
                    partner_invoice_id = partner_obj.address_get(cr,uid,[partner_id_update], ['invoice' or 'default'])
                    partner_shipping_id = partner_obj.address_get(cr,uid,[partner_id_update], ['delivery' or 'default'])
                    pricelist_id = partner_obj.browse(cr,uid,partner_id_update)['property_product_pricelist'].id
                    shop_obj = self.pool.get('sale.shop').browse(cr,uid,shop_id)
                    ordervals = {
                        'name' : 'Amazon_' + resultval.get('AmazonOrderId',False),
                        'picking_policy' : shop_obj.amazon_picking_policy,
                        'order_policy' : shop_obj.amazon_order_policy,
                        'partner_order_id' : partner_order_id['contact' or 'default'],
                        'partner_invoice_id' : partner_invoice_id['invoice' or 'default'],
                        'date_order' : resultval.get('PurchaseDate',False),
                        'shop_id' : shop_id,
                        'partner_id' : partner_id_update,
                        'partner_shipping_id' : partner_shipping_id['delivery'],
                        'state' : 'draft',
                        'invoice_quantity' : shop_obj.amazon_invoice_quantity,
                        'pricelist_id' : pricelist_id,
                        'ext_payment_method' : 'ccsave',
                        'amazon_order_id': resultval.get('AmazonOrderId',False),
                    }
                    product_obj = self.pool.get('product.product')
                    results = connection_obj.call(id,'ListOrderItems',resultval['AmazonOrderId'])
                    if results:
                        last_dictionary = results[-1]
                        while last_dictionary.get('NextToken',False):
                            next_token = last_dictionary.get('NextToken',False)
                            del results[-1]
                            results = results + results
                            results = connection_obj.call(id,'ListOrderItemsByNextToken',next_token)
                            if last_dictionary.get('NextToken',False) == False:
                                break
                    if results:
                        saleorderid = saleorder_obj.create(cr,uid,ordervals)
                        for each_result in results:
                            amazon_sku = each_result.get('SellerSKU',False)
                            product_search = product_obj.search(cr,uid,[('amazon_sku','=',amazon_sku)])
                            if not product_search:
                                product_id = self.createProduct(cr,uid,id,shop_id,each_result,context)
                            else:
                                product_id =product_search[0]
                            product_amount = product_obj.browse(cr,uid,product_id).list_price
                            tax_id = []
                            if each_result.get('ItemTax',False) > 0.0:
                                amount = float(each_result.get('ItemTax',False)) / 100
                                acctax_id = self.pool.get('account.tax').search(cr,uid,[('type_tax_use', '=', 'sale'), ('amount', '=', amount)])
                                if not acctax_id:
                                    acctax_id = self.createAccountTax(cr,uid,id,each_result.get('ItemTax',False), context)
                                    tax_id = [(6, 0, [acctax_id])]
                                else:
                                    tax_id = [(6, 0, acctax_id)]
                            orderlinevals = {
                            'order_id' : saleorderid,
                            'product_uom_qty' : each_result.get('QuantityOrdered',False),
                            'product_uom' : product_obj.browse(cr,uid,product_id).product_tmpl_id.uom_id.id,
                            'name' : product_obj.browse(cr,uid,product_id).product_tmpl_id.name,
                            'price_unit' : product_amount,
                            'delay' : product_obj.browse(cr,uid,product_id).product_tmpl_id.sale_delay,
                            'invoiced' : False,
                            'state' : 'confirmed',
                            'product_id' : product_id,
                            'tax_id' : tax_id
                                }
                            sale_order_line_obj = self.pool.get('sale.order.line')
                            saleorderlineid = sale_order_line_obj.create(cr,uid,orderlinevals)
                            if saleorderlineid:
                                prod_shipping_id = product_obj.search(cr,uid,[('default_code','=','SHIP AMAZON')])
                                if not prod_shipping_id:
                                    prod_shipping_id = self.createAmazonShippingProduct(cr,uid,id,context)
                                else:
                                    prod_shipping_id = prod_shipping_id[0]
                                if each_result.get('ShippingPrice',False):
                                    shiporderlinevals = {
                                        'order_id' : saleorderid,
                                        'product_uom_qty' : 1,
                                        'product_uom' : product_obj.browse(cr,uid,prod_shipping_id).product_tmpl_id.uom_id.id,
                                        'name' : product_obj.browse(cr,uid,prod_shipping_id).product_tmpl_id.name,
                                        'price_unit' : each_result.get('ShippingPrice',False),
                                        'delay' : product_obj.browse(cr,uid,prod_shipping_id).product_tmpl_id.sale_delay,
                                        'invoiced' : False,
                                        'state' : 'confirmed',
                                        'product_id' : prod_shipping_id,
                                    }
                                    shiplineid = sale_order_line_obj.create(cr,uid,shiporderlinevals)
                        company_id = self.pool.get('res.users').browse(cr,uid,uid).company_id.id
                        defaults = {'company_id':company_id}
                        paid = True
                        amazon_oe_status = self.amazon_oe_status(cr, uid, saleorderid, paid, context, defaults)
            else:
                print"No data is available"
        return True
    
    _columns = {
        'name' : fields.char('Name',size=64, required=True),
        'aws_access_key_id' : fields.char('Access Key',size=64,required=True),
        'aws_secret_access_key' : fields.char('Secret Key',size=64,required=True),
        'aws_market_place_id' : fields.char('Market Place ID',size=64,required=True),
        'aws_merchant_id' : fields.char('Merchant ID',size=64,required=True),
        }
amazon_instance()

class amazon_browse_node(osv.osv):
    _name = 'amazon.browse.node'
    _columns = {
        'browse_node_name' : fields.char('Name',size=64, required=True),
        'browse_node_country' : fields.many2many('res.country','browse_node_country_rel','browse_node_id','country_id','Browse Node Country')
        }
amazon_browse_node()
