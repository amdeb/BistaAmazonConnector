import hashlib
import hmac
from urllib import urlencode
from datetime import date, timedelta
import xml.dom.minidom
from osv import osv, fields
import time
import datetime
import xmlrpclib
import urllib2
import base64
from tools.translate import _
import httplib, ConfigParser, urlparse
from xml.dom.minidom import parse, parseString
import urllib
import md5
#from elementtree.ElementTree import XML, fromstring, tostring
from lxml import etree as ET

class Session:
    def Initialize(self, access_key, secret_key, merchant_id, marketplace_id):
        self.access_key = access_key
        self.secret_key = secret_key
        self.merchant_id = merchant_id
        self.marketplace_id = marketplace_id
        self.domain = 'mws.amazonaws.com'
        self.version= '2011-01-01'
class Call:
    RequestData = ""  # just a stub
    command = ''
    url_string = ''
    def calc_signature(self, url_params,post_data):
        """Calculate MWS signature to interface with Amazon
        '/Orders/2011-01-01"""
        keys = url_params.keys()
        keys.sort()
        # Get the values in the same order of the sorted keys
        values = map(url_params.get, keys)
        # Reconstruct the URL paramters and encode them
        url_string = urlencode( zip(keys,values) )
        string_to_sign = 'POST\n%s\n%s\n%s' % (self.Session.domain,post_data,url_string)
        signature = hmac.new(self.Session.secret_key.encode('utf-8'),string_to_sign,hashlib.sha256).digest().strip()
        signature = base64.encodestring( signature )
        return signature,url_string
    
    def cal_content_md5(self,request_xml):
        m = md5.new()
        m.update(request_xml)
        value = m.digest()
        hash_string = base64.encodestring(value)
        hash_string = hash_string.replace('\n', '')
        return hash_string
    
    def MakeCall(self,callName):
        print"url_string",self.url_string
        conn = httplib.HTTPSConnection(self.Session.domain)
        if callName.startswith('POST_'):
            content_md5 = self.cal_content_md5(self.RequestData)
            conn.request("POST", self.url_string, self.RequestData, self.GenerateHeaders(len(self.RequestData),content_md5))
        else:
            conn.request("POST", self.url_string, self.RequestData, self.GenerateHeaders('',''))
        response = conn.getresponse()
        data = response.read()
        conn.close()
        responseDOM = parseString(data)
        tag = responseDOM.getElementsByTagName('Error')
        if (tag.count!=0):
            for error in tag:
                print "\n",error.toprettyxml("  ")
        return responseDOM

    def GenerateHeaders(self, length_request, contentmd5):
        headers ={}
        headers = {
                   "Content-type": "text/xml; charset=UTF-8"
                   }
        if length_request and contentmd5:
            headers['Content-Length'] = length_request
            headers['Content-MD5']= contentmd5
        return headers

class ListMatchingProducts:
    Session = Session()
    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def Get(self,product_query,prod_query_contextid):
        print "ListMatchingProducts(get) called"
        api = Call()
        api.Session = self.Session
        command = '/Products/2011-01-01?'
        version = '2011-01-01'
        method = 'ListMatchingProducts'
        url_params ={
                     'Action':method,
                     'SellerId':self.Session.merchant_id,
                     'MarketplaceId':self.Session.marketplace_id,
                     'Query':product_query,
                     'AWSAccessKeyId':self.Session.access_key,
                     'SignatureVersion':'2',
                     'SignatureMethod':'HmacSHA256',
                     'Version':version
                     }
        if prod_query_contextid:
            url_params['QueryContextId'] = prod_query_contextid
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ '.000Z'
        post_data = '/Products/2011-01-01'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData =''
        responseDOM = api.MakeCall('ListMatchingProducts')
        print "responseDOM",responseDOM
        element = ET.XML(responseDOM.toprettyxml())
        mydict = {}
        product_info = []
        flag = False
        for elt in element.getiterator():
            print "=====elt.tag==========",elt.tag
            if (elt.tag[0] == "{") and (elt.text is not None):
                uri, tag = elt.tag[1:].split("}")
                if tag == 'Product':
                    print "aaaccvnfnf======="
                    flag = True      #set flag to true once we find a product tag
                    product_info.append(mydict)
                    mydict = {}
                if flag:
                    mydict[tag] = elt.text.strip()

        product_info.append(mydict)
        product_info.pop(0)
        print "product_info================",product_info
        return product_info

class ListOrders:
    Session = Session()
    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)
        
    def getErrors(self, node):
        info = {}
        for node in node:
            for cNode in node.childNodes:
                if cNode.nodeName == 'Message':
                     info['Error'] = cNode.childNodes[0].data
        return info
    def getOrderdetails(self, nodelist):
        transDetails = []
        for node in nodelist:
            info = {}
            for cNode in node.childNodes:
                if cNode.nodeName == 'ShippingAddress':
                    if cNode.childNodes[0].childNodes:
                        for gcNode in cNode.childNodes:
                            if gcNode.nodeName == 'Name':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'AddressLine1':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'City':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'StateOrRegion':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'PostalCode':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'Phone':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'CountryCode':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                elif cNode.nodeName == 'AmazonOrderId':
                    info[cNode.nodeName] = cNode.childNodes[0].data
                elif cNode.nodeName == 'PurchaseDate':
                    info[cNode.nodeName] = cNode.childNodes[0].data
                elif cNode.nodeName == 'NumberOfItemsShipped':
                    info[cNode.nodeName] = cNode.childNodes[0].data
                elif cNode.nodeName == 'OrderStatus':
                    info[cNode.nodeName] = cNode.childNodes[0].data
            transDetails.append(info)
        return transDetails

    def Get(self,timefrom,timeto):
        api = Call()
        api.Session = self.Session
        version = '2011-01-01'
        method= 'ListOrders'
        command = '/Orders/2011-01-01?'
#        url_'''params ={
#                     'Action':method,
#                     'SellerId':self.Session.merchant_id,
#                     'MarketplaceId.Id.1':self.Session.marketplace_id,
#                     'OrderStatus.Status.1':'Unshipped',
#                     'OrderStatus.Status.2':'PartiallyShipped',
#                     'AWSAccessKeyId':self.Session.access_key,
#                     'SignatureVersion':'2',
#                     'SignatureMethod':'HmacSHA256',
#                     'Version':version
#                     }'''
        url_params ={
                     'Action':method,
                     'SellerId':self.Session.merchant_id,
                     'MarketplaceId.Id.1':self.Session.marketplace_id,
                     'OrderStatus.Status.1':'Shipped',
                     'AWSAccessKeyId':self.Session.access_key,
                     'SignatureVersion':'2',
                     'SignatureMethod':'HmacSHA256',
                     'Version':version
                     }
        url_params['CreatedAfter'] = timefrom
        if timeto:
            url_params['CreatedBefore'] = timeto
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        post_data = '/Orders/2011-01-01'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData =''
        responseDOM = api.MakeCall('ListOrders')
        print"responseDom",responseDOM.toprettyxml()
        getOrderdetails = {}
        getErrordetails = {}
        getOrderdetails = self.getOrderdetails(responseDOM.getElementsByTagName('Order'))
        print "getOrderdetails++++++++++++++++",getOrderdetails
        getErrordetails = self.getErrors(responseDOM.getElementsByTagName('Error'))
        print "getErrordetails++++++++++++++++",getErrordetails
        if getErrordetails.get('Error',False):
            raise osv.except_osv(_('Error!'), _((getErrordetails.get('Error',False))))
        if responseDOM.getElementsByTagName('NextToken'):
            print "getOrderdetails--------",getOrderdetails
            print "aaaaaaa---------------",getOrderdetails + [{'NextToken':responseDOM.getElementsByTagName('NextToken')[0].childNodes[0].data}]
            getOrderdetails = getOrderdetails + [{'NextToken':responseDOM.getElementsByTagName('NextToken')[0].childNodes[0].data}]
            print "getOrderdetails--------",getOrderdetails
        return getOrderdetails

class ListOrderItems:
    Session = Session()

    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

###############################for getting products price###################################
    def getItemPrice(self, node):
        info = {}
        for cNode in node.childNodes:
            if cNode.nodeName == 'Amount':
                 return cNode.childNodes[0].data

    def getShippingPrice(self, node):
        info = {}
        for cNode in node.childNodes:
            if cNode.nodeName == 'Amount':
                 return cNode.childNodes[0].data
    def getItemTax(self, node):
        info = {}
        for cNode in node.childNodes:
            if cNode.nodeName == 'Amount':
                 return cNode.childNodes[0].data
#############################for getting product details######################################
    def getProductdetails(self, nodelist):
        productDetails = []
        for node in nodelist:
            info = {}
            for cNode in node.childNodes:
                if cNode.nodeName == 'OrderItem':
                    if cNode.childNodes[0].childNodes:
                        for gcNode in cNode.childNodes:
                            if gcNode.nodeName == 'ASIN':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'Title':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'SellerSKU':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'OrderItemId':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'ItemPrice':
                                info['Amount'] = self.getItemPrice(gcNode)
                            elif gcNode.nodeName == 'ShippingPrice':
                                info['ShippingPrice'] = self.getShippingPrice(gcNode)
                            elif gcNode.nodeName == 'ItemTax':
                                info['ItemTax'] = self.getItemTax(gcNode)
                            elif gcNode.nodeName == 'QuantityOrdered':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
            productDetails.append(info)
        return productDetails
    
    def Get(self,order_id):
        api = Call()
        api.Session = self.Session
        version = '2011-01-01'
        method= 'ListOrderItems'
        command = '/Orders/2011-01-01?'
        url_params = {'Action':method,'SellerId':self.Session.merchant_id,'AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['AmazonOrderId'] = order_id
        post_data = '/Orders/2011-01-01'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData =''
        responseDOM = api.MakeCall('ListOrderItems')
        print"responseDom",responseDOM.toprettyxml()
        getproductinfo = {}
        getproductinfo = self.getProductdetails(responseDOM.getElementsByTagName('OrderItems'))
        if responseDOM.getElementsByTagName('NextToken'):
            getproductinfo = getOrderdetails + [{'NextToken':responseDOM.getElementsByTagName('NextToken')[0].childNodes[0].data}]
        return getproductinfo

class ListOrdersByNextToken:
    Session = Session()
    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def getOrderdetails(self, nodelist):
        transDetails = []
        for node in nodelist:
            info = {}
            for cNode in node.childNodes:
                if cNode.nodeName == 'ShippingAddress':
                    if cNode.childNodes[0].childNodes:
                        for gcNode in cNode.childNodes:
                            if gcNode.nodeName == 'Name':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'AddressLine1':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'City':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'StateOrRegion':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'PostalCode':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'Phone':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                            elif gcNode.nodeName == 'CountryCode':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
                elif cNode.nodeName == 'AmazonOrderId':
                    info[cNode.nodeName] = cNode.childNodes[0].data
                elif cNode.nodeName == 'PurchaseDate':
                    info[cNode.nodeName] = cNode.childNodes[0].data
                elif cNode.nodeName == 'NumberOfItemsShipped':
                    info[cNode.nodeName] = cNode.childNodes[0].data
                elif cNode.nodeName == 'OrderStatus':
                    info[cNode.nodeName] = cNode.childNodes[0].data
            transDetails.append(info)
        return transDetails
    def Get(self,next_token):
        api = Call()
        api.Session = self.Session
        version = '2011-01-01'
        method= 'ListOrdersByNextToken'
        command = '/Orders/2011-01-01?'
        url_params = {'Action':method,'SellerId':self.Session.merchant_id,'AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['NextToken'] = next_token
        post_data = '/Orders/2011-01-01'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData =''
        responseDoM = api.MakeCall('ListOrdersByNextToken')
        print"responseDom",responseDoM.toprettyxml()
        getOrderdetails = {}
        getOrderdetails = self.getOrderdetails(responseDoM.getElementsByTagName('Order'))
        if responseDoM.getElementsByTagName('NextToken'):
            print"Next token",responseDoM.getElementsByTagName('NextToken')
            getOrderdetails = getOrderdetails + [{'NextToken':responseDoM.getElementsByTagName('NextToken')[0].childNodes[0].data}]
        return getOrderdetails

class ListOrderItemsByNextToken:
    Session = Session()
    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def Get(self,next_token):
        api = Call()
        api.Session = self.Session
        version = '2011-01-01'
        method= 'ListOrderItemsByNextToken'
        command = '/Orders/2011-01-01?'
        url_params = {'Action':method,'SellerId':self.Session.merchant_id,'MarketplaceId.Id.1':self.Session.marketplace_id,'AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['NextToken'] = next_token
        post_data = '/Orders/2011-01-01'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData =''
        responseDoM = api.MakeCall('ListOrderItemsByNextToken')
        print"responseDom",responseDoM.toprettyxml()

class GetFeedSubmissionResult:
    Session = Session()

    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def submitfeedresult(self, nodelist):
        for node in nodelist:
            info = {}
            for cNode in node.childNodes:
                if cNode.nodeName == 'ProcessingReport':
                        if cNode.childNodes:
                            for gcNode in cNode.childNodes:
#                                if gcNode.nodeName == 'Summary':
#                                    for gcNode in gcNode.childNodes:
                                        if gcNode.nodeName == 'ProcessingSummary':
                                            for gccNode in gcNode.childNodes:
                                                if gccNode.nodeName == 'MessagesWithError':
                                                    info[gccNode.nodeName] = gccNode.childNodes[0].data
                                                elif gccNode.nodeName == 'MessagesWithWarning':
                                                    info[gccNode.nodeName] = gccNode.childNodes[0].data
#                                elif gcNode.nodeName == 'Result':
#                                        for gccNode in gcNode.childNodes:
#                                            if gccNode.nodeName == 'ResultDescription':
#                                                info[gccNode.nodeName] = gccNode.childNodes[0].data
        return info
    def Get(self,FeedSubmissionId):
        api = Call()
        api.Session = self.Session
        version = '2009-01-01'
        method= 'GetFeedSubmissionResult'
        command = '/?'
        url_params = {'Action':method,'Merchant':self.Session.merchant_id,'AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['FeedSubmissionId'] = FeedSubmissionId
        post_data = '/'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData =''
        responseDoM = api.MakeCall('GetFeedSubmissionResult')
        print"responseDom",responseDoM.toprettyxml()
        getsubmitfeedresult = {}
        getsubmitfeedresult = self.submitfeedresult(responseDoM.getElementsByTagName('Message'))
        print"getsubmitfeedresult",getsubmitfeedresult
        return getsubmitfeedresult
        

class POST_INVENTORY_AVAILABILITY_DATA:
    Session = Session()
    def submitresult(self, nodelist):
        info = {}
        for node in nodelist:
            
            for cNode in node.childNodes:
                if cNode.nodeName == 'FeedSubmissionInfo':
                    if cNode.childNodes[0].childNodes:
                        for gcNode in cNode.childNodes:
                            if gcNode.nodeName == 'FeedSubmissionId':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
        return info

    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def Get(self,requestData):
        requestData = requestData.strip()
        print"requestData In INVENTORY",requestData
        api = Call()
        api.Session = self.Session
        version = '2009-01-01'
        method = 'SubmitFeed'
        command = '/?'
        url_params = {'Action':method,'Merchant':self.Session.merchant_id,'FeedType':'_POST_INVENTORY_AVAILABILITY_DATA_','AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['PurgeAndReplace'] = 'false'
        post_data = '/'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData = requestData
        responseDoM = api.MakeCall('POST_INVENTORY_AVAILABILITY_DATA')
        print"responseDom",responseDoM.toprettyxml()
        getsubmitfeed = {}
        getsubmitfeed = self.submitresult(responseDoM.getElementsByTagName('SubmitFeedResult'))
        return getsubmitfeed

class POST_ORDER_FULFILLMENT_DATA:
    Session = Session()
    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def submitresult(self, nodelist):
        for node in nodelist:
            info = {}
            for cNode in node.childNodes:
                if cNode.nodeName == 'FeedSubmissionInfo':
                    if cNode.childNodes[0].childNodes:
                        for gcNode in cNode.childNodes:
                            if gcNode.nodeName == 'FeedSubmissionId':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
        return info
    def Get(self,requestData):
        requestData = requestData.strip()
        print"requestdata",requestData
        api = Call()
        api.Session = self.Session
        version = '2009-01-01'
        method = 'SubmitFeed'
        command = '/?'
        url_params = {'Action':method,'Merchant':self.Session.merchant_id,'FeedType':'_POST_INVENTORY_AVAILABILITY_DATA_','AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['PurgeAndReplace'] = 'false'
        post_data = '/'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData = requestData
        responseDoM = api.MakeCall('POST_ORDER_FULFILLMENT_DATA')
        print"responseDom",responseDoM.toprettyxml()
        getsubmitfeed = {}
        getsubmitfeed = self.submitresult(responseDoM.getElementsByTagName('SubmitFeedResult'))
        print"getsubmitfee",getsubmitfeed
        return getsubmitfeed

class POST_PRODUCT_PRICING_DATA:
    Session = Session()
    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def submitresult(self, nodelist):
        info = {}
        for node in nodelist:
            for cNode in node.childNodes:
                if cNode.nodeName == 'FeedSubmissionInfo':
                    if cNode.childNodes[0].childNodes:
                        for gcNode in cNode.childNodes:
                            if gcNode.nodeName == 'FeedSubmissionId':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
        return info
    def Get(self,requestData):
        requestData = requestData.strip()
        api = Call()
        api.Session = self.Session
        version = '2009-01-01'
        method = 'SubmitFeed'
        command = '/?'
        url_params = {'Action':method,'Merchant':self.Session.merchant_id,'FeedType':'_POST_PRODUCT_PRICING_DATA_','AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['PurgeAndReplace'] = 'false'
        post_data = '/'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData = requestData
        responseDoM = api.MakeCall('POST_PRODUCT_PRICING_DATA')
        print"responseDom pricing Update",responseDoM.toprettyxml()
        getsubmitfeed = {}
        getsubmitfeed = self.submitresult(responseDoM.getElementsByTagName('SubmitFeedResult'))
        print"getsubmitfee",getsubmitfeed
        return getsubmitfeed

class POST_PRODUCT_DATA:
    Session = Session()
    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def submitresult(self, nodelist):
        info = {}
        for node in nodelist:
            for cNode in node.childNodes:
                if cNode.nodeName == 'FeedSubmissionInfo':
                    if cNode.childNodes[0].childNodes:
                        for gcNode in cNode.childNodes:
                            if gcNode.nodeName == 'FeedSubmissionId':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
        return info
    def Get(self,requestData):
        requestData = requestData.strip()
        api = Call()
        api.Session = self.Session
        version = '2009-01-01'
        method = 'SubmitFeed'
        command = '/?'
        url_params = {'Action':method,'Merchant':self.Session.merchant_id,'FeedType':'_POST_PRODUCT_DATA_','AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['PurgeAndReplace'] = 'false'
        post_data = '/'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData = requestData
        responseDoM = api.MakeCall('POST_PRODUCT_DATA')
        print"responseDom",responseDoM.toprettyxml()
        getsubmitfeed = {}
        getsubmitfeed = self.submitresult(responseDoM.getElementsByTagName('SubmitFeedResult'))
        print"getsubmitfee",getsubmitfeed
        return getsubmitfeed


class POST_PRODUCT_IMAGE_DATA:
    Session = Session()
    def __init__(self, access_key, secret_key, merchant_id, marketplace_id):
        self.Session.Initialize(access_key, secret_key, merchant_id, marketplace_id)

    def submitresult(self, nodelist):
        info = {}
        for node in nodelist:
            for cNode in node.childNodes:
                if cNode.nodeName == 'FeedSubmissionInfo':
                    if cNode.childNodes[0].childNodes:
                        for gcNode in cNode.childNodes:
                            if gcNode.nodeName == 'FeedSubmissionId':
                                info[gcNode.nodeName] = gcNode.childNodes[0].data
        return info
    def Get(self,requestData):
        requestData = requestData.strip()
        print"requestdata",requestData
        api = Call()
        api.Session = self.Session
        version = '2009-01-01'
        method = 'SubmitFeed'
        command = '/?'
        url_params = {'Action':method,'Merchant':self.Session.merchant_id,'FeedType':'_POST_PRODUCT_IMAGE_DATA_','AWSAccessKeyId':self.Session.access_key,'SignatureVersion':'2','SignatureMethod':'HmacSHA256','Version':version}
        url_params['Timestamp'] = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())+ 'Z'
        url_params['PurgeAndReplace'] = 'false'
        post_data = '/'
        url_params['Signature'] = api.calc_signature(url_params,post_data)[0]
        url_string = api.calc_signature(url_params,post_data)[1].replace('%0A','')
        api.url_string  = str(command) + url_string
        api.RequestData = requestData
        responseDoM = api.MakeCall('POST_PRODUCT_IMAGE_DATA')
        print"responseDom",responseDoM.toprettyxml()
        getsubmitfeed = {}
        getsubmitfeed = self.submitresult(responseDoM.getElementsByTagName('SubmitFeedResult'))
        print"getsubmitfee",getsubmitfeed
        return getsubmitfeed

def call(amazon_instance, method, *arguments):
        if method == 'ListOrders':
            lo = ListOrders(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = lo.Get(arguments[0],arguments[1])
            return result
        elif method == 'ListOrderItems':
            lo = ListOrderItems(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = lo.Get(arguments[0])
            return result
        elif method == 'ListOrdersByNextToken':
            lo = ListOrdersByNextToken(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = lo.Get(arguments[0])
            return result
        elif method == 'ListOrderItemsByNextToken':
            lo = ListOrderItemsByNextToken(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = lo.Get(arguments[0],arguments[1])
            return result
        elif method == 'POST_INVENTORY_AVAILABILITY_DATA':
            pi = POST_INVENTORY_AVAILABILITY_DATA(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = pi.Get(arguments[0])
            return result
        elif method == 'POST_ORDER_FULFILLMENT_DATA':
            po = POST_ORDER_FULFILLMENT_DATA(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = po.Get(arguments[0])
            return result
        elif method == 'POST_PRODUCT_PRICING_DATA':
            po = POST_PRODUCT_PRICING_DATA(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = po.Get(arguments[0])
            return result
        elif method == 'POST_PRODUCT_DATA':
            pp = POST_PRODUCT_DATA(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = pp.Get(arguments[0])
            return result
        elif method == 'POST_PRODUCT_IMAGE_DATA':
            pi = POST_PRODUCT_IMAGE_DATA(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = pi.Get(arguments[0])
            return result
        elif method == 'GetFeedSubmissionResult':
            gfs = GetFeedSubmissionResult(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = gfs.Get(arguments[0])
            return result
        elif method == 'ListMatchingProducts':
            lmp = ListMatchingProducts(amazon_instance.aws_access_key_id, amazon_instance.aws_secret_access_key, amazon_instance.aws_merchant_id, amazon_instance.aws_market_place_id)
            result = lmp.Get(arguments[0],arguments[1])
            return result
