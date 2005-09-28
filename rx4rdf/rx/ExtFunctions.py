"""
    XPath Extension functions used by Raccoon

    Copyright (c) 2003-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

import os, os.path, time, sys, base64, traceback, urllib, re
from Ft.Xml.XPath.Conversions import StringValue, NumberValue
from Ft.Xml import SplitQName, XPath, InputSource, EMPTY_NAMESPACE
from Ft.Xml.XPath import RuntimeException,FT_EXT_NAMESPACE
from rx import utils, RxPath

from RxPath import XFalse, XTrue, Xbool
from Ft.Lib import Uri, number, Time

#xpath variable namespaces:
RXIKI_HTTP_REQUEST_HEADER_NS = 'http://rx4rdf.sf.net/ns/raccoon/http-request-header#'
RXIKI_HTTP_RESPONSE_HEADER_NS = 'http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
RXIKI_REQUEST_COOKIES_NS = 'http://rx4rdf.sf.net/ns/raccoon/request-cookie#'
RXIKI_RESPONSE_COOKIES_NS = 'http://rx4rdf.sf.net/ns/raccoon/response-cookie#'
RXIKI_SESSION_NS = 'http://rx4rdf.sf.net/ns/raccoon/session#'
RXIKI_PREV_NS = 'http://rx4rdf.sf.net/ns/raccoon/previous#'
RXIKI_ERROR_NS = 'http://rx4rdf.sf.net/ns/raccoon/error#'
#XPath extension functions:
RXWIKI_XPATH_EXT_NS = 'http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'

############################################################
##XPath extension functions
##(can be used with both RxPath/RxSLT/XUpdate and XPath/XSLT
############################################################
#first delete insecure functions from FT's built-in extensions
from Ft.Xml.XPath import BuiltInExtFunctions
from Ft.Xml.Xslt import XsltFunctions, XsltContext, Exslt

extFuncDicts = [BuiltInExtFunctions.ExtFunctions, XPath.Context.Context.functions,
                         XsltContext.XsltContext.functions]

if BuiltInExtFunctions.ExtFunctions.has_key((FT_EXT_NAMESPACE, 'spawnv')):
    for functionDict in extFuncDicts:
        del functionDict[(FT_EXT_NAMESPACE, 'spawnv')]
        del functionDict[(FT_EXT_NAMESPACE, 'system')]
        del functionDict[(FT_EXT_NAMESPACE, 'env-var')]

#1.0a4 version of 4Suite deleted deprecated functions, so re-add the ones we still use
if not BuiltInExtFunctions.ExtFunctions.has_key((FT_EXT_NAMESPACE, 'escape-url')):
    for functionDict in extFuncDicts:
        #4Suite 1.0a4's pytime-to-exslt is broken, reimplement it:
        functionDict[(FT_EXT_NAMESPACE, 'pytime-to-exslt')] = lambda context, t=None:\
            t and unicode(Time.FromPythonTime(NumberValue(t))) or unicode(Time.FromPythonTime())
        #todo: we should stop using this and use exslt:string's encode-uri
        functionDict[(FT_EXT_NAMESPACE, 'escape-url')] = lambda context, uri: urllib.quote(StringValue(uri))

if Exslt.ExtElements.has_key(("http://exslt.org/common", 'document')):
    #document only can write to the local files system and does use our secure URI resolver
    del Exslt.ExtElements[("http://exslt.org/common", 'document')]
             
def SystemProperty(context, qname):
    '''
    disable the 'http://xmlns.4suite.org/xslt/env-system-property'
    namespace (it is a security hole), otherwise call
    Ft.Xml.Xslt.XsltFunctions.SystemProperty
    '''
    qname = StringValue(qname)
    if qname:
        (uri, local) = context.expandQName(qname)
        if uri == 'http://xmlns.4suite.org/xslt/env-system-property':
            return u''
    return XsltFunctions.SystemProperty(context, qname)
XsltFunctions.CoreFunctions[(EMPTY_NAMESPACE, 'system-property')] = SystemProperty
XsltContext.XsltContext.functions[(EMPTY_NAMESPACE, 'system-property')] = SystemProperty

def Max(context, nodeset, nanvalue = number.nan):
    """ Like math:max function except it returns the optional nanvalue argument
    (default: NaN) if nodeset is empty or any of its values are NaN."""
    
    def f(a, b):
        if number.isnan(b):
            return b
        elif a > b:
            return a
        else:
            return b
    if not isinstance(nodeset, list):
        nodset = [ nodeset ]
    return reduce(f, map(NumberValue, nodeset), nanvalue)

def Min(context, nodeset, nanvalue = number.nan):
    """ Like math:min function except it returns the optional nanvalue argument
    (default: NaN) if nodeset is empty or any of its values are NaN."""
    
    def f(a, b):
        if number.isnan(b):
            return b
        elif a < b:
            return a
        else:
            return b
    if not isinstance(nodeset, list):
        nodset = [ nodeset ]
    return reduce(f, map(NumberValue, nodeset), nanvalue)

def DocumentAsText(context, url):
    '''
    Return the contents of url as a string or an empty nodeset
    if url is an zero length string. If the url resolves to a file
    thCat contains bytes sequences that are not ascii or utf-8
    (e.g. a binary file) this function can not be used in contexts
    such as xsl:value-of however, an raw xpath expression will
    return a non-unicode string and thus will work in those
    contexts.
    '''

    urlString = StringValue( url )
    if not urlString:
        return [] #return an empty nodeset    
    #file = urllib2.urlopen(urlString) #use InputSource instead so our SiteUriResolver get used
    #print "urlstring", urlString
    #todo: set baseURI = this current context's $_path, have site resolver use this as the docbase
    file = InputSource.DefaultFactory.fromUri(urlString)
    bytes = file.read()
    #print bytes[0:100]
    #print 'bytes', bytes
    return bytes

def String2NodeSet(context, string):
    '''Ft.Xml.Xslt.Exslt.Common.NodeSet is not implemented correctly -- this behavior should be part of it'''
    #if its already a nodeset just return that
    #(this enables us to use function to treat strings and text nodeset interchangable
    if isinstance(string, list):
        return string 
    assert isinstance(string, (str, unicode))
    return [context.node.ownerDocument.createTextNode(string)]

def Split(context, string, pattern=u' '):
    '''
    Similar to Ft.Xml.Xslt.Exslt.String.Split but doesn't depend
    on a XSLT processor -- any XPath context will do.    
    '''
    string = StringValue(string)
    pattern = StringValue(pattern)        
    nodeset = []    

    frag = context.node.ownerDocument.createDocumentFragment()
    def addToNodeset(token):
        text = context.node.ownerDocument.createTextNode(token)        
        nodeset.append( text )
        return
        #the following causes a seg fault in cdomlette the second time around
        elem = context.node.ownerDocument.createElementNS(None, 'token')
        frag.appendChild(elem)
        text = context.node.ownerDocument.createTextNode(token)
        elem.appendChild(text)
        nodeset.append( elem )
        
    if pattern:
        if string:
            if pattern == ' ':
                pattern = None #python normalizes whitespace if pattern is None
            #addToNodeset(string.split(pattern)[0])
            for token in string.split(pattern):
                addToNodeset(token)
    else:
        for ch in string:
            addToNodeset(token)
    return nodeset

def GenerateBnode(context, name=None):
    if name is not None:
        name = StringValue(name)
    return utils.generateBnode(name)

def FileExists(context, uri):
    path = StringValue(uri)
    if path.startswith('file:'):
        path = Uri.UriToOsPath(path) #todo: security hole
        return Xbool(os.path.exists(path))
    else:
        if path.startswith('path:'):
            path = path[len('path:'):]
        for prefix in InputSource.DefaultFactory.resolver.path:
            if os.path.exists(os.path.join(prefix.strip(), path) ):
                return XTrue
        return XFalse                    
    
def CurrentTime(context):
    '''
    This returns the current time in epoch seconds with the precision truncated to 3 digits.
    '''
    #i just want a number i can accurately compare, not obvious how to do that with all the exslt date-time functions
    return "%.3f" % time.time() #limit precision

def ParseDateToPyTime(context, date, format=''):
    """
    Inverse of CurrentTime
    """
    import calendar
    date = StringValue(date)
    format = StringValue(format) or "%Y-%m-%dT%H:%M:%S"
    time_tuple = time.strptime(date, format)
    return "%.3f" % calendar.timegm(time_tuple) 

def FormatPyTime(context, t, format='%Y-%m-%dT%H:%M:%S'):
    """
    Given a Python timestamp number return a formatted date string.
        t - a time stamp number, as from Python's time.time()
            if omitted, use the current time
        format - Python date format
    """
    if t:
        t = NumberValue(t)
        t = time.gmtime(t)
    else:
        t = time.gmtime()
    return time.strftime(StringValue(format),t)
    
class DummyExpression:
    def __init__(self, nodeset):
        self.nodeset = nodeset
        
    def evaluate(self, context):
        return self.nodeset
    
def Sort(context, nodeset, key='string(.)', dataType='text', order='ascending',
         lang=None, caseOrder=None):
    from Ft.Xml import Xslt, XPath    
    import Ft.Xml.Xslt.XPathExtensions
    import Ft.Xml.Xslt.SortElement
    from rx import raccoon
    
    se = Xslt.SortElement.SortElement(None, '','','')
    se._select = raccoon.RequestProcessor.expCache.getValue(key)
    se._comparer = se.makeComparer(order,dataType, caseOrder)
    sortednodeset = Xslt.XPathExtensions.SortedExpression(
        DummyExpression(nodeset), [se]).evaluate(context)
    return sortednodeset

def If(context, cond, v1, v2=None):
    """
    just like Ft.Xml.XPath.BuiltInExtFunctions.If
    but the then and else parameters are strings that evaluated dynamically 
    thus supporting the short circuit logic you expect from if expressions
    """
    from Ft.Xml.XPath import Conversions
    from rx import raccoon
    queryCache=getattr(context.node.ownerDocument, 'queryCache', None)
    if Conversions.BooleanValue(cond):            
        compExpr = raccoon.RequestProcessor.expCache.getValue(Conversions.StringValue(v1))
        if queryCache:
            return queryCache.getValue(compExpr, context)         
        else:
            return compExpr.evaluate(context)    
    elif v2 is None:
        return []
    else:
        compExpr = raccoon.RequestProcessor.expCache.getValue(Conversions.StringValue(v2))
        if queryCache:
            return queryCache.getValue(compExpr, context)         
        else:
            return compExpr.evaluate(context)    

def Map(context, nodeset, string):
    if type(nodeset) != type([]):
        raise RuntimeException(RuntimeException.WRONG_ARGUMENTS, 'map', "expected node set argument")
    from Ft.Xml.XPath import parser
    from Ft.Lib import Set
    from rx import raccoon
    mapContext = context.clone()
    mapContext.size = len(nodeset)
    mapContext.position = 1
    #note: exslt-dyn:map implies that parse exception should be caught and an empty nodeset returned
    exp = raccoon.RequestProcessor.expCache.getValue(StringValue(string))
    queryCache=getattr(context.node.ownerDocument, 'queryCache', None)

    def eval(l, node):
        mapContext.node = node
        mapContext.position += 1
        mapContext.varBindings[(RXWIKI_XPATH_EXT_NS, 'current')] = node
        if queryCache:
            result = queryCache.getValue(exp, mapContext)         
        else:
            result = exp.evaluate(mapContext)            
        if type(result) != type([]):
            if not isinstance(result, unicode):
                result = unicode(str(result), 'utf8')                
            result = String2NodeSet(mapContext, result)
        l.extend( result  )
        return l
    nodeset = reduce(eval, nodeset, [])        
    return Set.Unique(nodeset)
    
def GetRDFXML(context, resultset = None):
  '''Returns a nodeset containing a RDF/XML representation of the
  RxPathDOM nodes contained in resultset parameter. If
  resultset is None, it will be set to the context node '''
  if resultset is None:
        resultset = [ context.node ]
  from Ft.Rdf.Serializers.Dom import Serializer as DomSerializer
  serializer = DomSerializer()
  stmts = []
  for n in resultset:
      stmts.extend(n.getModelStatements())
  if resultset:
      nsMap=resultset[0].ownerDocument.nsRevMap
  else:
      nsMap = None
  outdoc = serializer.serialize(None, stmts = stmts, nsMap = nsMap)
  return [outdoc]
  #prettyOutput = StringIO.StringIO()
  #from Ft.Xml.Lib.Print import PrettyPrint
  #PrettyPrint(outdoc, stream=prettyOutput)
  #return prettyOutput.getvalue()    

import Ft
class XPathUserError(XPath.RuntimeException):
    def __init__(self, message, errorCode, *args):
        messages = { errorCode : message }
        Ft.FtException.__init__(self, errorCode, messages, args)

def Error(context, message, code=0):
    raise XPathUserError(message, code)

def HasMetaData(kw, context, name):
    def _test(local, dict):
        if dict and dict.has_key(local):
            return XTrue
        else:
            return XFalse
    return _onMetaData(kw, context, name, _test, 'has')

def GetMetaData(kw, context, name, default=XFalse):
    '''
    The advantage of using this instead of a variable reference is
    that it just returns 0 if the name doesn't exist, not an error
    '''
    def _get(local, dict):
        if dict and dict.has_key(local):
            return dict[local]
        else:
            return default
    return _onMetaData(kw, context, name, _get, 'get')

def AssignMetaData(kw, context, name, val, recordChange = None, authorize=True):
    '''
    Note: new variable and values don't affect corresponding xpath variable 
    '''
    def _assign(local, dict):
        #oldval = dict.get(local, None)
        if dict is not None:
            dict[local] = val
        return val
    #print >>sys.stderr,'AssignMetaData ', name, ' ' , val    
    retVal = _onMetaData(kw, context, name, _assign, 'assign', val, authorize)
    if recordChange:
        kw.setdefault(recordChange, []).append( (context.processorNss, (name, val)) )
    return retVal

def RemoveMetaData(kw, context, name, recordChange = None, authorize=True):
    def _delete(local, dict):
        if dict and dict.has_key(local):
            del dict[local]
            return XTrue
        else:
            return XFalse
    retVal = _onMetaData(kw, context, name, _delete, 'remove',authorize=authorize)
    if retVal and recordChange:
        kw.setdefault(recordChange, []).append( (context.processorNss, name) )
    return retVal

def _onMetaData(kw, context, name, func, opname, value=None, authorize=True):
    from rx import raccoon
    (prefix, local) = SplitQName(name)
    if prefix:
        try:
            namespace = context.processorNss[prefix]
        except KeyError:
            raise RuntimeException(RuntimeException.UNDEFINED_PREFIX,
                                   prefix)
    else:
        namespace = None
    local = str(local) #function argument keyword dict can't be unicode
    if authorize and not kw['__server__'].authorizeMetadata(opname, namespace, local, value, kw):
        if value is None:
            value = ''        
        raise raccoon.NotAuthorized('%s-metadata with %s:%s %s' % (opname, namespace, name, value))

    dict = None
    kwdicts = kw['__server__'].kw2varsMap
    if not namespace:
        dict = kw
    elif kwdicts.get(namespace):
        dictname, attrib, filter = kwdicts[namespace]
        dict = kw.get(dictname)
        if dict and attrib:
            dict = getattr(dict, attrib, None)        
    else:
        raise raccoon.UnusableNamespaceError( '%s uses unusable namespace: %s' % (local, namespace) )
    #if dict is None:
    #    log.debug('calling %s-metadata on an unavailable namespace %s' % (opname, namespace) )

    return func(local, dict)

def instanceof(context, test, cmptype):
    '''sort of like the "instance of" operator in XPath 2.0'''
    #todo: do we really need this when there is exsl:object-type 
    cmptype = StringValue(cmptype)    
    if cmptype == 'number':
       result = isinstance(test, (int, float)) #float
    elif cmptype == 'string':
       result = isinstance(test, (unicode, str)) #string
    elif cmptype == 'node-set':
       result = isinstance(test, list ) #node-set
    elif cmptype == 'boolean':
       #result = isinstance(test, (bool, XPath.boolean.BooleanType)) #boolean
       result = test == 1 or test == 0
    elif cmptype == 'object':
       #true if any thing is not one of the above types
       result = not isinstance(test, (int, float, unicode, str, list,
                     bool, XPath.boolean.BooleanType)) #boolean       
    else:
       raise RuntimeError('unknown type specified %s' % cmptype)
    return Xbool(result)

DefaultExtFunctions = {
    (RXWIKI_XPATH_EXT_NS, 'string-to-nodeset'): String2NodeSet,
    (RXWIKI_XPATH_EXT_NS, 'openurl'): DocumentAsText,
    (RXWIKI_XPATH_EXT_NS, 'generate-bnode'): GenerateBnode,
    (RXWIKI_XPATH_EXT_NS, 'current-time'): CurrentTime,
    (RXWIKI_XPATH_EXT_NS, 'parse-date-to-pytime'): ParseDateToPyTime,
    (RXWIKI_XPATH_EXT_NS, 'format-pytime'): FormatPyTime,
    (RXWIKI_XPATH_EXT_NS, 'file-exists'):  FileExists,
    (RXWIKI_XPATH_EXT_NS, 'if'): If,
    (RXWIKI_XPATH_EXT_NS, 'map'): Map,
    (RXWIKI_XPATH_EXT_NS, 'sort'): Sort,
    (RXWIKI_XPATH_EXT_NS, 'split'): Split,
    (RXWIKI_XPATH_EXT_NS, 'min'): Min,
    (RXWIKI_XPATH_EXT_NS, 'max'): Max,
    (RXWIKI_XPATH_EXT_NS, 'get-rdf-as-xml'): GetRDFXML,
    (RXWIKI_XPATH_EXT_NS, 'instance-of'): instanceof,
    (RXWIKI_XPATH_EXT_NS, 'error'): Error,
}