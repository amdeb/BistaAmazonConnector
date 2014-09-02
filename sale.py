
from osv import osv, fields
import socket
import amazonerp_osv as connection_obj
import time
import datetime
from datetime import date, timedelta
import mx.DateTime as dt
import netsvc
logger = netsvc.Logger()
from tools.translate import _
from datetime import timedelta,datetime
import urllib
import base64
from operator import itemgetter
from itertools import groupby
#import ast

class sale_shop(osv.osv):
    _name = "sale.shop"
    _inherit = "sale.shop"
    def xml_format(self,message_type,merchant_string,message_data):
        str = """
<?xml version="1.0" encoding="utf-8"?>
<AmazonEnvelope xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd">
<Header>
<DocumentVersion>1.01</DocumentVersion>
"""+merchant_string.encode("utf-8") +"""
</Header>
"""+message_type.encode("utf-8")+"""
"""+message_data.encode("utf-8") + """
</AmazonEnvelope>"""
        return str
    def create_product(self,cr,uid,message_id,product_obj,merchant_string,instance_obj,quantity):
        price_string = """<Message>
                            <MessageID>%(message_id)s</MessageID>
                            <Price>
                            <SKU>%(sku)s</SKU>
                            <StandardPrice currency="USD">%(price)s</StandardPrice>
                            </Price>
                            </Message>"""
        price_string = price_string % {
                                    'message_id':message_id,
                                    'sku': product_obj.amazon_sku,
                                    'price':product_obj.list_price,
                                    }
        price_str = """<MessageType>Price</MessageType>"""
        price_data = self.xml_format(price_str,merchant_string,price_string)
        price_submission_id = connection_obj.call(instance_obj, 'POST_PRODUCT_PRICING_DATA',price_data)
        print"price_submission_id",price_submission_id
        time.sleep(40)
#                            if price_submission_id.get('FeedSubmissionId',False):
#                                time.sleep(80)
#                                submission_price_results = connection_obj.call(instance_obj, 'GetFeedSubmissionResult',price_submission_id.get('FeedSubmissionId',False))

        inventory_string = """<Message><MessageID>%(message_id)s</MessageID><Inventory><SKU>%(sku)s</SKU><Quantity>%(qty)s</Quantity></Inventory></Message>"""
        inventory_string = inventory_string % {
                                    'message_id':message_id,
                                    'sku': product_obj.amazon_sku,
                                    'qty':quantity[0]}
        inventory_str = """<MessageType>Inventory</MessageType>"""
        inventory_data = self.xml_format(inventory_str,merchant_string,inventory_string)
        inventory_submission_id = connection_obj.call(instance_obj, 'POST_INVENTORY_AVAILABILITY_DATA',inventory_data)
        time.sleep(40)
        print"inventory_submission_id",inventory_submission_id
        cr.execute("UPDATE product_product SET amazon_prod_status='active',amazon_updated_price='%s' where id=%d"%(product_obj.list_price,product_obj.id,))
        cr.commit()
        return True
    def update_product(self,cr,uid,message_id,product_obj,merchant_string,instance_obj):
        price_string = """<Message>
                            <MessageID>%(message_id)s</MessageID>
                            <Price>
                            <SKU>%(sku)s</SKU>
                            <StandardPrice currency="USD">%(price)s</StandardPrice>
                            </Price>
                            </Message>"""
        price_string = price_string % {
                                    'message_id':message_id,
                                    'sku': product_obj.amazon_sku,
                                    'price':product_obj.list_price,
                                    }
        price_str = """<MessageType>Price</MessageType>"""
        price_data = self.xml_format(price_str,merchant_string,price_string)
        price_submission_id = connection_obj.call(instance_obj, 'POST_PRODUCT_PRICING_DATA',price_data)
        print"price_submission_id",price_submission_id
#                            if price_submission_id.get('FeedSubmissionId',False):
#                                time.sleep(80)
#                                submission_price_results = connection_obj.call(instance_obj, 'GetFeedSubmissionResult',price_submission_id.get('FeedSubmissionId',False))
        cr.execute("UPDATE product_product SET amazon_prod_status='active',amazon_updated_price='%s' where id=%d"%(product_obj.list_price,product_obj.id,))
        cr.commit()
        time.sleep(40)
        return True
    
    def import_orders_amazon(self,cr,uid,ids,context=None):
        instance_obj = self.browse(cr,uid,ids[0]).amazon_instance_id
        last_import_time = self.browse(cr,uid,ids[0]).last_amazon_order_import_date
        if not last_import_time:
            today = datetime.now()
            DD = timedelta(days=30)
            earlier = today - DD
            earlier_str = earlier.strftime("%Y-%m-%dT%H:%M:%S")
            createdAfter = earlier_str+'Z'
            print"createdAfter",createdAfter
            createdBefore =''
        else:
            db_import_time = time.strptime(last_import_time, "%Y-%m-%d %H:%M:%S")
            db_import_time = time.strftime("%Y-%m-%dT%H:%M:%S",db_import_time)
            createdAfter = time.strftime("%Y-%m-%dT%H:%M:%S",time.gmtime(time.mktime(time.strptime(db_import_time,"%Y-%m-%dT%H:%M:%S"))))
            createdAfter = str(createdAfter)+'Z'
            print"createdAfter",createdAfter
            make_time = datetime.utcnow() - timedelta(seconds=120)
            make_time_str = make_time.strftime("%Y-%m-%dT%H:%M:%S")
            createdBefore = make_time_str+'Z'
            print"createdBefore",createdBefore
#        try:
        time.sleep(10)
        results = connection_obj.call(instance_obj, 'ListOrders',createdAfter,createdBefore)
        time.sleep(30)
        if results:
            last_dictionary = results[-1]
            while last_dictionary.get('NextToken',False):
                next_token = last_dictionary.get('NextToken',False)
                del results[-1]
                time.sleep(25)
                results = connection_obj.call(instance_obj, 'ListOrdersByNextToken',next_token)
                results = results + results
                last_dictionary = results[-1]
                if last_dictionary.get('NextToken',False) == False:
                    break
        if results:
             orderid = self.pool.get('amazon.instance').createOrder(cr,uid,instance_obj,ids[0],results,context)
             cr.execute("UPDATE sale_shop SET last_amazon_order_import_date='%s' where id=%d"%(time.strftime('%Y-%m-%d %H:%M:%S'),ids[0]))
        else:
            self.log(cr,uid,ids[0],"No More Orders to Import")
        return True
    
    def export_stock_levels_amazon(self,cr,uid,ids,context=None):
        product_obj = self.pool.get('product.product')
        stock_move_obj = self.pool.get('stock.move')
        instance_obj = self.browse(cr,uid,ids[0]).amazon_instance_id
        product_ids = product_obj.search(cr,uid,[('amazon_export','=','True'),('amazon_prod_status','=','active')])
        last_amazon_inventory_export_date = self.browse(cr,uid,ids[0]).last_amazon_inventory_export_date
        if last_amazon_inventory_export_date:
            recent_move_ids = stock_move_obj.search(cr, uid, [('date', '>', last_amazon_inventory_export_date), ('product_id', 'in', product_ids), ('state', '!=', 'draft'), ('state', '!=', 'cancel')])
        else:
            recent_move_ids = stock_move_obj.search(cr, uid, [('product_id', 'in', product_ids)])
        product_ids = [move.product_id.id for move in stock_move_obj.browse(cr, uid, recent_move_ids) if move.product_id.state != 'obsolete']
        product_ids = [x for x in set(product_ids)]
        merchant_string = ''
        if instance_obj:
            merchant_string ="<MerchantIdentifier>%s</MerchantIdentifier>"%(instance_obj.aws_merchant_id)
            warehouse_id = self.browse(cr,uid,ids[0]).warehouse_id.id
            if warehouse_id:
                location_id = self.pool.get('stock.warehouse').browse(cr,uid,warehouse_id).lot_input_id.id
                message_information = ''
                message_id = 1
                for each_product in product_ids:
                    product_sku = product_obj.browse(cr,uid,each_product).amazon_sku
                    product_id_location = self._my_value(cr, uid,location_id,each_product,context={})
                    product_split = str(product_id_location).split('.')
                    value = product_split[0]
                    message_information += """<Message><MessageID>%s</MessageID><OperationType>Update</OperationType><Inventory><SKU>%s</SKU><Quantity>%s</Quantity></Inventory></Message>""" % (message_id,product_sku,value)
                    message_id = message_id + 1
                if message_information:
                    data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>"""+ merchant_string.encode("utf-8") +"""</Header><MessageType>Inventory</MessageType>""" + message_information.encode("utf-8") + """</AmazonEnvelope>"""
                    if data:
                        results = connection_obj.call(instance_obj, 'POST_INVENTORY_AVAILABILITY_DATA',data)
                        print"results",results
                        if results.get('FeedSubmissionId',False):
                            time.sleep(70)
                            submission_results = connection_obj.call(instance_obj, 'GetFeedSubmissionResult',results.get('FeedSubmissionId',False))
                            if submission_results.get('MessagesWithError',False) == '0':
                                self.log(cr, uid,1, "Inventory Updated Successfully")
                            else:
                                if submission_results.get('ResultDescription',False):
                                    error_message = submission_results.get('ResultDescription',False)
                                    error_message = str(error_message).replace("'"," ")
                                    self.log(cr, uid,1, error_message)
                        self.write(cr,uid,ids[0],{'last_amazon_inventory_export_date':time.strftime('%Y-%m-%d %H:%M:%S')})
        return True
    def _my_value(self, cr, uid, location_id, product_id, context=None):
        cr.execute(
            'select sum(product_qty) '\
            'from stock_move '\
            'where location_id NOT IN  %s '\
            'and location_dest_id = %s '\
            'and product_id  = %s '\
            'and state = %s ',tuple([(location_id,), location_id, product_id, 'done']))
        wh_qty_recieved = cr.fetchone()[0] or 0.0
        #this gets the value which is sold and confirmed
        argumentsnw = [location_id,(location_id,),product_id,( 'done',)]#this will take reservations into account
        cr.execute(
            'select sum(product_qty) '\
            'from stock_move '\
            'where location_id = %s '\
            'and location_dest_id NOT IN %s '\
            'and product_id  = %s '\
            'and state in %s ',tuple(argumentsnw))
        qty_with_reserve = cr.fetchone()[0] or 0.0
        qty_available = wh_qty_recieved - qty_with_reserve
        return qty_available
    def update_amazon_orders(self,cr,uid,ids,context=None):
        message_information = ''
        item_string = ''
        message_id = 1
        saleorder_obj = self.pool.get('sale.order')
        saleorder_ids = []
        last_amazon_update_order_export_date = self.browse(cr,uid,ids[0]).last_amazon_update_order_export_date
        if not last_amazon_update_order_export_date:
            saleorder_ids = saleorder_obj.search(cr,uid,[('state','=','done'),('shop_id','=',ids[0]),('amazon_order_id','!=',False)])
        else:
            saleorder_ids = saleorder_obj.search(cr,uid,[('write_date','>',last_amazon_update_order_export_date),('state','=','done'),('shop_id','=',ids[0]),('amazon_order_id','!=',False)])
        if saleorder_ids:
            for saleorder_id in saleorder_ids:
                picking_ids = saleorder_obj.browse(cr,uid,saleorder_id).picking_ids
                if picking_ids:
                    order_id = saleorder_obj.browse(cr,uid,saleorder_id).amazon_order_id #for getting order_id
                    tracking_id = picking_ids[0].carrier_tracking_ref # for getting tracking_id
                    carrier_id = picking_ids[0].carier_id
                    if carrier_id:
                        carrier_code_split = carrier_id.name.split(' ')
                        carrier_code_split_first = carrier_code_split[0]#for getting shipping method
                    product_info = saleorder_obj.browse(cr,uid,saleorder_id).order_line
                    for each_line in product_info:
                        product_qty = each_line.product_uom_qty
                        product_id = each_line.product_id
                        product_qty_split = str(product_qty).split(".")
                        product_qty_first = product_qty_split[0]
                        product_order_item_id = product_id.product_order_item_id
                        item_string = '''<Item><AmazonOrderItemCode>%s</AmazonOrderItemCode>
                                        <Quantity>%s</Quantity></Item>'''%(product_order_item_id,product_qty_first)
                    fulfillment_date = time.strftime('%Y-%m-%dT%H:%M:%S')
                    fulfillment_date_concat = str(fulfillment_date) + '-00:00'
                    message_information += """<Message><MessageID>%s</MessageID><OperationType>Update</OperationType><OrderFulfillment><AmazonOrderID>%s</AmazonOrderID><FulfillmentDate>%s</FulfillmentDate><FulfillmentData><CarrierName>%s</CarrierName><ShippingMethod>%s</ShippingMethod><ShipperTrackingNumber>%s</ShipperTrackingNumber></FulfillmentData>"""+item_string.encode("utf-8")+"""</OrderFulfillment></Message>""" % (message_id,order_id,fulfillment_date_concat,carrier_code_split_first,carrier_code,tracking_id)
                    message_id = message_id + 1
            data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion><MerchantIdentifier>M_SELLERON_82825133</MerchantIdentifier></Header><MessageType>OrderFulfillment</MessageType>""" + message_information.encode("utf-8") + """</AmazonEnvelope>"""
            if data:
                results = connection_obj.call(instance_obj, 'POST_ORDER_FULFILLMENT_DATA',data)
                print"results",results
                if results.get('FeedSubmissionId',False):
                        time.sleep(70)
                        submission_results = connection_obj.call(instance_obj, 'GetFeedSubmissionResult',results.get('FeedSubmissionId',False))
                        if submission_results.get('MessagesWithError',False) == '0':
                            self.log(cr, uid,1, "Status Updated Successfully")
                        else:
                            if submission_results.get('ResultDescription',False):
                                error_message = submission_results.get('ResultDescription',False)
                                error_message = str(error_message).replace("'"," ")
                                self.log(cr, uid,1, error_message)
#                self.write(cr,uid,ids[0],{'last_ebay_update_order_export_date':time.strftime('%Y-%m-%d %H:%M:%S')})
                cr.execute("UPDATE sale_shop SET last_ebay_update_order_export_date='%s' where id=%d"%(time.strftime('%Y-%m-%d %H:%M:%S'),ids[0]))
        return True
    
    def _get_amazon_exportable_product_ids(self, cr, uid, ids, name, args, context=None):
        res = {}
        product_obj = self.pool.get("product.product")
        last_amazon_catalog_export_date = self.browse(cr,uid,ids[0]).last_amazon_catalog_export_date
        for shop in self.browse(cr, uid, ids, context=context):
            if last_amazon_catalog_export_date:
                product_ids = product_obj.search(cr, uid, [('amazon_export', '=', True),('write_date','>',last_amazon_catalog_export_date )])
            else:
                product_ids = product_obj.search(cr, uid, [('amazon_export', '=', True)])
            res[shop.id] = product_ids
        return res

    def export_catalog_amazon(self,cr,uid,ids,context={}):
        instance_obj = self.browse(cr,uid,ids[0]).amazon_instance_id
        merchant_string = ''
        standard_product_string = ''
        category_info = ''
        final_condition_string = ''
        condition_string = ''
        desc = ''
        log_id = 0
        warehouse_id = self.browse(cr,uid,ids[0]).warehouse_id.id
        location_id = self.pool.get('stock.warehouse').browse(cr,uid,warehouse_id).lot_stock_id.id
        release_date = datetime.utcnow()
        release_date = release_date.strftime("%Y-%m-%dT%H:%M:%S")
        date_string = """<LaunchDate>%s</LaunchDate>
                         <ReleaseDate>%s</ReleaseDate>"""%(release_date,release_date)
        if instance_obj:
            merchant_string ="<MerchantIdentifier>%s</MerchantIdentifier>"%(instance_obj.aws_merchant_id)
            amazon_exportable_product_ids = self.browse(cr,uid,ids[0]).amazon_exportable_product_ids    
            message_information = ''
            message_id = 1
            for each_product in amazon_exportable_product_ids:
                product_nm = each_product.name_template
                product_sku = each_product.amazon_sku
                function_call = self._my_value(cr, uid,location_id,each_product.id,context={})
                quantity = str(function_call).split('.')
                condition = each_product.amzn_condtn
                condition_note = each_product.condition_note
                if condition:
                    condition_string += """<ConditionType>%s</ConditionType>"""%(condition)
                if condition and condition_note:
                    condition_string += """<ConditionNote>%s</ConditionNote>"""%(condition_note)
                final_condition_string = "<Condition>"+ condition_string.encode('utf-8') + "</Condition>"
                title = each_product.name_template
                sale_description = each_product.description_sale
                if sale_description:
                    desc = "<Description>%s</Description>"%(sale_description)
#                product_category = each_product.amazon_category
                amz_type = each_product.amz_type
                amz_type_value = each_product.amz_type_value
                product_asin = each_product.amazon_asin
                if amz_type and amz_type_value:
                    standard_product_string = """
                    <StandardProductID>
                    <Type>%s</Type>
                    <Value>%s</Value>
                    </StandardProductID>
                    """%(amz_type,amz_type_value)
                if not standard_product_string:
                    category_info = """<ProductData>
<CE>
<ProductType>
<ConsumerElectronics>
<VariationData></VariationData>
<Color>Color</Color>
<DigitalMediaFormat>4_mm_tape</DigitalMediaFormat>
</KindleAccessories>
</ProductType>
</CE>
</ProductData>"""
                    standard_product_string = """
                    <StandardProductID>
                    <Type>ASIN</Type>
                    <Value>%s</Value>
                    </StandardProductID>
                    """%(product_asin)
                message_information = """<Message>
                                            <MessageID>%(message_id)s</MessageID>
                                            <Product>
                                            <SKU>%(sku)s</SKU>
                                            """ +standard_product_string.encode('utf-8')+"""
                                            """+ date_string.encode('utf-8') + """
                                            """+ final_condition_string.encode('utf-8') +"""
                                            <DescriptionData>
                                            <Title>%(title)s</Title>
                                           """ + desc.encode("utf-8") + """
                                            </DescriptionData>
                                            </Product>
                                            </Message>"""
                message_information = message_information % { 'sku': product_sku,
                                              'condition': condition,
                                              'title': title,
                                              'message_id':message_id}
                product_str = """<MessageType>Product</MessageType>"""
                product_data = self.xml_format(product_str,merchant_string,message_information)
                print"data",product_data
                if product_data:
                    product_submission_id = connection_obj.call(instance_obj, 'POST_PRODUCT_DATA',product_data)
                    if product_submission_id.get('FeedSubmissionId',False):
                        time.sleep(80)
                        submission_results = connection_obj.call(instance_obj, 'GetFeedSubmissionResult',product_submission_id.get('FeedSubmissionId',False))
                        if submission_results.get('MessagesWithError',False) == '0':
                            amazon_status = each_product.amazon_prod_status
                            if amazon_status == 'active':
                                if each_product.list_price != each_product.amazon_updated_price:
                                    print"price UnMatches"
                                    self.update_product(cr,uid,message_id,each_product,merchant_string,instance_obj)
                                product_long_message = ('%s: Updated Successfully on Amazon') % (product_nm)
                                self.log(cr, uid,log_id, product_long_message)
                                log_id += 1
                            else:
                                self.create_product(cr,uid,message_id,each_product,merchant_string,instance_obj,quantity)
                            product_long_message = ('%s: Created Successfully on Amazon') % (product_nm)
                            self.log(cr, uid,log_id, product_long_message)
                            log_id += 1
                            #code for Updating Price###
#                            price_string = """<Message>
#                                                <MessageID>%(message_id)s</MessageID>
#                                                <Price>
#                                                <SKU>%(sku)s</SKU>
#                                                <StandardPrice currency="USD">%(price)s</StandardPrice>
#                                                </Price>
#                                                </Message>"""
#                            price_string = price_string % {
#                                                        'message_id':message_id,
#                                                        'sku': product_sku,
#                                                        'price':list_price,
#                                                        }
#                            price_str = """<MessageType>Price</MessageType>"""
#                            price_data = self.xml_format(price_str,merchant_string,price_string)
#                            price_submission_id = connection_obj.call(instance_obj, 'POST_PRODUCT_PRICING_DATA',price_data)
#                            print"price_submission_id",price_submission_id
##                            if price_submission_id.get('FeedSubmissionId',False):
##                                time.sleep(80)
##                                submission_price_results = connection_obj.call(instance_obj, 'GetFeedSubmissionResult',price_submission_id.get('FeedSubmissionId',False))
#
#                            inventory_string = """<Message><MessageID>%(message_id)s</MessageID><Inventory><SKU>%(sku)s</SKU><Quantity>%(qty)s</Quantity></Inventory></Message>"""
#                            inventory_string = inventory_string % {
#                                                        'message_id':message_id,
#                                                        'sku': product_sku,
#                                                        'qty':quantity[0]}
#                            inventory_str = """<MessageType>Inventory</MessageType>"""
#                            inventory_data = self.xml_format(inventory_str,merchant_string,inventory_string)
#                            inventory_submission_id = connection_obj.call(instance_obj, 'POST_INVENTORY_AVAILABILITY_DATA',inventory_data)
#                            print"inventory_submission_id",inventory_submission_id
#                            cr.execute("UPDATE product_product SET prod_status='active' where id=%d"%(each_product.id,))
#                            cr.commit()
#                            if inventory_submission_id.get('FeedSubmissionId',False):
#                                time.sleep(80)
#                                submission_inventory_results = connection_obj.call(instance_obj, 'GetFeedSubmissionResult',inventory_submission_id.get('FeedSubmissionId',False))
                        else:
                            if submission_results.get('ResultDescription',False):
                                error_message = submission_results.get('ResultDescription',False)
                                error_message = str(error_message).replace("'"," ")
                                cr.execute("UPDATE product_product SET submit_feed_result='%s' where id=%d"%(error_message,each_product.id,))
                                cr.commit()
                                product_long_message = ('Error : %s:') % (product_nm)+ ' ' + error_message
                                self.log(cr, uid,log_id, product_long_message)
                                log_id += 1
        cr.execute("UPDATE sale_shop SET last_amazon_catalog_export_date='%s' where id=%d"%(time.strftime('%Y-%m-%d %H:%M:%S'),ids[0]))
        return True

    def export_images_amazon(self,cr,uid,ids,context={}):
        product_image_obj = self.pool.get('product.images')
        instance_obj = self.browse(cr,uid,ids[0]).amazon_instance_id
        product_obj = self.pool.get("product.product")
        product_ids = product_obj.search(cr,uid,[('amazon_export','=','True'),('amazon_prod_status','=','active')])
        last_amazon_image_export_date = self.browse(cr,uid,ids[0]).last_amazon_image_export_date
        if last_amazon_image_export_date:
            recent_image_ids = product_image_obj.search(cr, uid, [('write_date', '>', last_amazon_image_export_date), ('product_id', 'in', product_ids)])
        else:
            recent_image_ids = product_image_obj.search(cr, uid, [('product_id', 'in', product_ids)])
        merchant_string = ''
        if instance_obj:
            merchant_string ="<MerchantIdentifier>%s</MerchantIdentifier>"%(instance_obj.aws_merchant_id)
            message_information = ''
            message_id = 1
            for each_image_id in recent_image_ids:
                product_id = product_image_obj.browse(cr,uid,each_image_id).product_id
                product_sku =  product_id.amazon_sku
                image_url = product_image_obj.browse(cr,uid,each_image_id).amazon_url_location
                message_information += """<Message><MessageID>%s</MessageID><OperationType>Update</OperationType><ProductImage><SKU>%s</SKU><ImageType>Main</ImageType><ImageLocation>%s</ImageLocation></ProductImage></Message>""" % (message_id,product_sku,image_url)
                message_id = message_id + 1
            if message_information:
                data = """<?xml version="1.0" encoding="utf-8"?><AmazonEnvelope xmlns:xsi="https://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="amzn-envelope.xsd"><Header><DocumentVersion>1.01</DocumentVersion>"""+ merchant_string.encode("utf-8") +"""</Header><MessageType>ProductImage</MessageType>""" + message_information.encode("utf-8") + """</AmazonEnvelope>"""
                if data:
                    results = connection_obj.call(instance_obj, 'POST_PRODUCT_IMAGE_DATA',data)
                    print"results",results
                    if results.get('FeedSubmissionId',False):
                        time.sleep(80)
                        submission_results = connection_obj.call(instance_obj, 'GetFeedSubmissionResult',results.get('FeedSubmissionId',False))
                        if submission_results.get('MessagesWithError',False) == '0':
                            self.log(cr,uid,1,'Images Updated Successfully')
                        else:
                            if submission_results.get('ResultDescription',False):
                                error_message = submission_results.get('ResultDescription',False)
                                error_message = str(error_message).replace("'"," ")
                                self.log(cr, uid,log_id, product_long_message)
                    cr.execute("UPDATE sale_shop SET last_amazon_image_export_date='%s' where id=%d"%(time.strftime('%Y-%m-%d %H:%M:%S'),ids[0]))
        return True
    _columns = {
        'amazon_instance_id' : fields.many2one('amazon.instance','Instance',readonly=True),
        'last_amazon_inventory_export_date': fields.datetime('Last Inventory Export Time'),
        'last_amazon_catalog_export_date': fields.datetime('Last Inventory Export Time'),
        'last_amazon_image_export_date': fields.datetime('Last Image Export Time'),
        'last_amazon_order_import_date' : fields.datetime('Last Order Import  Time'),
        'last_amazon_update_order_export_date' : fields.datetime('Last Order Update  Time'),
#        #TODO all the following settings are deprecated and replaced by the finer grained base.sale.payment.type settings!
        'amazon_picking_policy': fields.selection([('direct', 'Partial Delivery'), ('one', 'Complete Delivery')],
                                           'Packing Policy', help="""If you don't have enough stock available to deliver all at once, do you accept partial shipments or not?"""),
        'amazon_order_policy': fields.selection([
            ('prepaid', 'Payment Before Delivery'),
            ('manual', 'Shipping & Manual Invoice'),
            ('postpaid', 'Invoice on Order After Delivery'),
            ('picking', 'Invoice from the Packing'),
        ], 'Shipping Policy', help="""The Shipping Policy is used to synchronise invoice and delivery operations.
  - The 'Pay before delivery' choice will first generate the invoice and then generate the packing order after the payment of this invoice.
  - The 'Shipping & Manual Invoice' will create the packing order directly and wait for the user to manually click on the 'Invoice' button to generate the draft invoice.
  - The 'Invoice on Order After Delivery' choice will generate the draft invoice based on sale order after all packing lists have been finished.
  - The 'Invoice from the packing' choice is used to create an invoice during the packing process."""),
        'amazon_invoice_quantity': fields.selection([('order', 'Ordered Quantities'), ('procurement', 'Shipped Quantities')], 'Invoice on', help="The sale order will automatically create the invoice proposition (draft invoice). Ordered and delivered quantities may not be the same. You have to choose if you invoice based on ordered or shipped quantities. If the product is a service, shipped quantities means hours spent on the associated tasks."),
        'amazon_shop' : fields.boolean('Amazon Shop',readonly=True),
        'auto_import_amazon' : fields.boolean('Auto Import'),
        'partner_id': fields.many2one('res.partner','Customer'),
        'amazon_exportable_product_ids': fields.function(_get_amazon_exportable_product_ids, method=True, type='one2many', relation="product.product", string='Exportable Products'),
    }
sale_shop()

class sale_order(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'
    def _default_journal(self, cr, uid, context={}):
        accountjournal_obj = self.pool.get('account.journal')
        accountjournal_ids = accountjournal_obj.search(cr,uid,[('name','=','Sales Journal')])
        if accountjournal_ids:
            return accountjournal_ids[0]
        else:
#            raise wizard.except_wizard(_('Error !'), _('Sales journal not defined.'))
            return False
    _columns = {
        'amazon_order_id' : fields.char('Order ID', size=256),
        'journal_id': fields.many2one('account.journal', 'Journal',readonly=True),
    }
    _defaults = {
        'journal_id': _default_journal,
    }
sale_order()
