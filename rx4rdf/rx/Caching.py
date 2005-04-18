"""
    Caching functions used by Raccoon

    Copyright (c) 2003-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    

    Raccoon uses several MRU (most recently used) caches:
    XPath parser cache: This caches XPath expression strings so they don't
    need to be repeatedly parsed.
    
    XPath processing cache: This caches the result of evaluating an
    XPath expression. Certain XPath extension functions have side
    effects or can not be analyzed for dependencies and so any XPath
    expressions that references such a function is not cacheable. You
    can declare addition XPath functions as not cacheable by setting
    the NOT_CACHEABLE_FUNCTIONS config setting.

    Stylesheet parser cache: This caches XSLT and
    RxSLT stylesheets so they don't need to be repeatedly parsed.

    Action cache: This caches the result of executing an Action. For
    an action to be cachable you must assign it a CacheKeyPredicate.
    Raccoon provides cache predicates for caching RxSLT and XSLT
    actions. See the documentation on the Action class for more
    details.

    The Raccoon caching model is a little unusual in that it doesn't rely
    on explicit or proactive cache invalidation. Instead it works on the
    principle that each time we do a cache lookup we can generate a key
    based on the aspects of the current state of the system that uniquely
    determine the cache value. Thus when the relevant system state
    changes, the lookup will fail. For example, for the XPath processing
    cache, the lookup value will be a XPath expression but the key stored
    in the cache will be a tuple consisting of XPath expression, the
    values of any variables referenced by the expression, and a revision
    counter representing the state of the model. When the model is updated
    the revision counter changes and subsequent cache lookups for that
    expression will result in a cache miss, as the lookup key will now
    include the new revision counter. Eventually the old cache entry with
    the old revision counter as part of its key will be flushed out as the
    MRU cache fills up.

    Raccoon's caches have a mechanism for handling side effects that may
    occur when generating a value that will be cached. For example, the
    XPath processing cache and the XSLT/RxSLT processing caches keep track
    of calls to ^^wf:assign-metadata^^ and ^^wf:remove-metadata^^ so that
    the changes they make to the request metadata can be repeated when
    subsequent requests result in the value being retrieved from the
    cache.
"""

from rx.ExtFunctions import *
from rx import MRUCache
from Ft.Xml.Xslt import XSL_NAMESPACE
from xml.dom import Node as _Node
from rx import logging #for python 2.2 compatibility
log = logging.getLogger("raccoon")

##############################################################################################
## The following functions are used to calculate the key for XPath extension
## functions or XSLT extension elements
## 
## They should match this signature: 
## def getKey(node, context, notCacheableDict) where 
## node is either the Ft.Xml.XPath.ParsedExpr.FunctionCall
## or the Ft.Xml.Xslt.XsltElement node representing the function or extension
## element, respectively, context is the XPath context,
## and notCacheableDict is the dictionary of not cacheable functions and elements.
##
## getKey should either return a key (any hashable object)
## or raise MRUCache.NotCacheable.
## Note that the context may not have all its fields set. If the getKey function relies on one, 
## it should check that it's not None and raise MRUCache.NotCacheable if it is.
###############################################################################################

def zeroArgsCheck(field,context, notCacheableXPathFunctions):
    '''
    The function call is not cacheable it has no arguments
    (used by date/time functions that return the current time if no argument is given)
    '''
    if not field._args:
        raise MRUCache.NotCacheable
    return ()

def getHasMetadataCacheKey(field, context, notCacheableXPathFunctions):
    '''
    for the has-metadata() XPath function
    Handles the most common case where the first argument is a literal.
    '''
    if isinstance(field._args[0], XPath.ParsedExpr.ParsedLiteralExpr):
        literal = field._args[0].evaluate(context) #returns field._literal
        varRef = _splitKey(SplitQName(literal), context)#may raise RuntimeException.UNDEFINED_PREFIX
        if not context.node:
            #when getting the key for a stylesheet we don't have
            #the variables available for examination
            #(nor the contextNode and that's easier to test for)
            raise MRUCache.NotCacheable
        return (varRef, context.varBindings.has_key(varRef))
    else:
        raise MRUCache.NotCacheable

def getGetMetadataCacheKey(field, context, notCacheableXPathFunctions):
    '''
    for the get-metadata() XPath function
    Handles the most common case where the first argument is a literal.
    '''
    if isinstance(field._args[0], XPath.ParsedExpr.ParsedLiteralExpr):            
        literal = field._args[0].evaluate(context) #returns field._literal
        varRef =  XPath.ParsedExpr.ParsedVariableReferenceExpr('$'+literal)
        try:
            value = varRef.evaluate(context)
        #except XPath.RuntimeException: if e.code = XPath.RuntimeException.UNDEFINED_VARIABLE:
        except:
            raise MRUCache.NotCacheable
        if isinstance(value, list):
            value = tuple(value)                
        return (varRef, value)
    else:
        raise MRUCache.NotCacheable

def evaluateKey(paramNums, field, context, notCacheableXPathFunctions):
    '''
    Used for functions that dynamically evaluate XPath expressions.
    Handles the most common case where the arguments that are XPath expressions
    are literals.
    '''
    from rx import raccoon
    key = []
    notCacheableXPathFunctions = dict(notCacheableXPathFunctions) #copy dict
    #too complicated to deal with sideeffects now so mark uncacheable
    notCacheableXPathFunctions[(RXWIKI_XPATH_EXT_NS, 'remove-metadata')] = 0
    notCacheableXPathFunctions[(RXWIKI_XPATH_EXT_NS, 'assign-metadata')] = 0

    for arg in xrange(len(field._args)):
        if arg in paramNums:
            if isinstance(field._args[arg], XPath.ParsedExpr.ParsedLiteralExpr):
                literal = field._args[arg].evaluate(context) #returns field._literal                    
                try:
                    compExpr = raccoon.RequestProcessor.expCache.getValue(literal)
                    key.append( getKeyFromXPathExp(compExpr, context,
                                        notCacheableXPathFunctions) )
                #except XPath.RuntimeException: if e.code = XPath.RuntimeException.UNDEFINED_VARIABLE:
                except:
                    raise MRUCache.NotCacheable
            else:
                raise MRUCache.NotCacheable
    return tuple(key)

DefaultNotCacheableFunctions = dict([(x, None) for x in [                                    
        (FT_EXT_NAMESPACE, 'iso-time'),        
        (RXWIKI_XPATH_EXT_NS, 'current-time'),            
        ('http://exslt.org/dates-and-times', 'date-time'),            
        (RXWIKI_XPATH_EXT_NS, 'generate-bnode'),
        (FT_EXT_NAMESPACE, 'generate-uuid'),
        (FT_EXT_NAMESPACE, 'random'),
        ("http://exslt.org/math", 'random'),
        (RXWIKI_XPATH_EXT_NS, 'error'),
        #xslt extension elements:
        (FT_EXT_NAMESPACE, 'chain-to'),
        ('http://exslt.org/common', 'document'), #this element is banned actually
        ]])

DefaultNotCacheableFunctions[(RXWIKI_XPATH_EXT_NS, 'get-metadata')] = getGetMetadataCacheKey
DefaultNotCacheableFunctions[(RXWIKI_XPATH_EXT_NS, 'has-metadata')] = getHasMetadataCacheKey
#note: assign/remove-metadata are handle by the side-effect capturing functions
#functions that dynamically evaluate expressions: 
DefaultNotCacheableFunctions[(RXWIKI_XPATH_EXT_NS, 'if')] = lambda *args: evaluateKey( (1,2), *args)
DefaultNotCacheableFunctions[(RXWIKI_XPATH_EXT_NS, 'sort')] = lambda *args: evaluateKey( (1,), *args)
DefaultNotCacheableFunctions[(RXWIKI_XPATH_EXT_NS, 'evaluate')] = lambda *args: evaluateKey( (0,), *args)
DefaultNotCacheableFunctions[(FT_EXT_NAMESPACE, 'evaluate')] = lambda *args: evaluateKey( (0,), *args)
DefaultNotCacheableFunctions[('http://exslt.org/dynamic', 'evaluate')] = lambda *args: evaluateKey( (0,), *args)
DefaultNotCacheableFunctions[(RXWIKI_XPATH_EXT_NS, 'map')] = lambda *args: evaluateKey( (1,), *args)    
DefaultNotCacheableFunctions[(RXWIKI_XPATH_EXT_NS, 'format-pytime')] = zeroArgsCheck
for functionName in ['date','time', 'year', 'leap-year', 'month-in-year',
        'month-name','month-abbreviation','week-in-year', 'day-in-year',
        'day-in-month','day-of-week-in-month', 'day-in-week','day-name',
        'day-abbreviation', 'hour-in-day', 'minute-in-hour', 'second-in-minute']:
    DefaultNotCacheableFunctions[('http://exslt.org/dates-and-times', functionName)] = zeroArgsCheck              

#EnvironmentDependentFunctions contains functions that are not cacheable if there's a 
#chance the local files they depend on might change while the cache is being used
EnvironmentDependentFunctions = dict([(x, None) for x in [
    (None, 'document'),
    (RXWIKI_XPATH_EXT_NS, 'openurl'),
    (RXWIKI_XPATH_EXT_NS, 'file-exists') ]])

###################################################################################
## The following functions are used for extracting the key from an XPath expression
## which uniquely identify the result of the XPath expression's evaluation.
## Here's how these functions are used by Raccoon:
##    queryCache = MRUCache.MRUCache(self.XPATH_CACHE_SIZE,
##          lambda compExpr, context: compExpr.evaluate(context),
##          lambda compExpr, context: getKeyFromXPathExp(compExpr, context, self.NOT_CACHEABLE_FUNCTIONS),
##          _processXPathExpSideEffects, _calcXPathSideEffects)
###################################################################################

def _splitKey(key, context):
    (prefix, local) = key
    if prefix:
        try:
            expanded = (context.processorNss[prefix], local)
        except:
            raise RuntimeException(RuntimeException.UNDEFINED_PREFIX, prefix)
    else:
        expanded = key
    return expanded

def _getKeyFromValue(value):
    assert not isinstance(value, _Node) #this shouldn't happen
    if isinstance(value, list): #its a nodeset
        newValue = []
        for node in value:
            #treat free floating text nodes as strings
            if not node.parentNode and node.nodeType == _Node.TEXT_NODE:
                newValue.append(node.nodeValue)
            else:
                getKey = getattr(node.ownerDocument, 'getKey', None)
                if getKey:
                    newValue.append( getKey( node )  )
                else:
                    newValue.append( id(node) )
        value = tuple(newValue)                    
    return value        
    
def getKeyFromXPathExp(compExpr, context, notCacheableXPathFunctions):
    '''
    Returns the key uniquely representing the result of evaluating an expression given a context.
    The key consists of:
        expr, context.node, (var1, value1), (var2, value2), etc.
          for each variable referenced in the expression
    '''
    key = [ repr(compExpr) ]
    DomDependent = False
    for field in compExpr:
        if context.node and isinstance(field, XPath.ParsedExpr.ParsedVariableReferenceExpr):
            #when getting the key for a stylesheet we don't have
            #the variables available for examination                
            #(nor the context.node and that's easier to test for)
            #and in this case we don't want them in the key since we add the stylesheet's params instead
            value = field.evaluate(context) #may raise RuntimeException.UNDEFINED_VARIABLE
            expanded = _splitKey(field._key, context)
            if isinstance(value, list): #its a nodeset
                value = tuple(value)    
                DomDependent = True     #todo: but it could come from another DOM
            elif isinstance(value, _Node): #this shouldn't happen
                DomDependent = True                
            key.append( (expanded, value) )
        elif isinstance(field, XPath.ParsedExpr.FunctionCall):
            DomDependent = True #todo: we could check if its a 'static' function that doesn't access the dom
            expandedKey = _splitKey(field._key, context)
            if expandedKey in notCacheableXPathFunctions:
                keyfunc = notCacheableXPathFunctions[expandedKey]
                if keyfunc:
                   key += keyfunc(field, context, notCacheableXPathFunctions)
                else:
                   raise MRUCache.NotCacheable
            #else: log.debug("%s cacheable! not in %s" % (str(expandedKey), str(notCacheableXPathFunctions) ) )
        elif not isinstance(field, XPath.ParsedExpr.ParsedLiteralExpr):            
            DomDependent = True
    if DomDependent and context.node:
        key += [id(context.node), id(context.node.ownerDocument), getattr(context.node.ownerDocument, 'revision', None)]
    #print 'returning key', tuple(key)
    return tuple(key)

def calcXPathSideEffects(result, compExpr, context):
    '''
    Returns a list of calls to assign-metadata and remove-metadata
    so they can be invoked by processXPathExpSideEffects()
    '''
    def hasSideEffect(field):
        if isinstance(field, XPath.ParsedExpr.FunctionCall):            
            expandedKey = _splitKey(field._key, context)
            if expandedKey in [(RXWIKI_XPATH_EXT_NS, 'remove-metadata'),
                               (RXWIKI_XPATH_EXT_NS, 'assign-metadata')]:
                log.debug("recording side effect for %s" % str(expandedKey) )
                return field
    #figure out sideeffect
    callList = [node for node in compExpr if hasSideEffect(node)]
    return callList

def processXPathExpSideEffects(cacheValue, callList, compExpr, context):
    '''
    Re-assign or remove metadata using the list created by calcXPathSideEffects()
    '''
    for function in callList:
        log.debug("performing side effect for %s with args %s" % (function._name, str(function._args) ) )
        function.evaluate(context) #invoke the function with a side effect
    return cacheValue

#this is not used right now since we monkey patch FunctionCall evaluate
def _resetFunctions(compiledExp, *ignoreArgs):
    '''because the function map is not part of the key for the
       expression cache we need to clear out _func field after retrieving
       the expression from the cache, thus forcing _func to be recalculated
       in order to guard against the function map values changing.
    '''
    for field in compiledExp:
        if isinstance(field, XPath.ParsedExpr.FunctionCall):                
            field._func = None

###########################################################################################
## The following functions and classes are used by the XSLT stylesheet parsing cache
## If the stylesheet has dependencies on external files, then parsing will not be cacheable
## Sample usage:    MRUCache.MRUCache(STYLESHEET_CACHE_SIZE, styleSheetValueCalc,
##                            isValueCacheableCalc = isStyleSheetCacheable)
## If you are not worried about the dependent files changing, don't set isValueCacheableCalc
##########################################################################################
import Ft.Xml.Xslt.StylesheetReader 
class StylesheetReader(Ft.Xml.Xslt.StylesheetReader.StylesheetReader):
    '''
    Subclass StylesheetReader so we can tell if the stylesheet had dependencies on external resources
    '''
    standAlone = True
    
    def externalEntityRef(self, context, base, sysid, pubid):
        self.standAlone = False
        return Ft.Xml.Xslt.StylesheetReader.StylesheetReader.externalEntityRef(self, context, base, sysid, pubid)
        
    def _handle_xinclude(self, attribs):
        self.standAlone = False
        return Ft.Xml.Xslt.StylesheetReader.StylesheetReader._handle_xinclude(self, attribs)
        
    def _combine_stylesheet(self, href, is_import):
        self.standAlone = False
        return Ft.Xml.Xslt.StylesheetReader.StylesheetReader._combine_stylesheet(self, href, is_import)
        
def styleSheetValueCalc(source, uri):
    '''
    Return the stylesheet given the stylesheet source.
    '''
    if type(source) == type(u''):
        source = source.encode('utf8')
    iSrc = InputSource.DefaultFactory.fromString(source, uri)      
    _styReader = StylesheetReader()
    stylesheetElement = _styReader.fromSrc(iSrc) #todo: support extElements=self.extElements
    stylesheetElement.standAlone = _styReader.standAlone
    return stylesheetElement

def isStyleSheetCacheable(key, styleSheet, source, uri):
    return styleSheet.standAlone

        
###################################################################
## caching functions used by the XSLT and RxSLT content processors
## to cache the results of processing the stylesheet
###################################################################
              
def getXsltCacheKeyPredicate(styleSheetCache, styleSheetNotCacheableFunctions,
                                    styleSheetContents, sourceContents, kw,
                                    contextNode, styleSheetUri='path:'):
    '''
    Returns a key that uniquely identifies the result of processing this stylesheet
    considering the input source and referenced parameters.
    '''
    revision = getattr(contextNode.ownerDocument, 'revision', None)            
    key = [styleSheetContents, styleSheetUri, sourceContents, contextNode,
         id(contextNode.ownerDocument), revision]

    styleSheet = styleSheetCache.getValue(styleSheetContents, styleSheetUri)                  
    try:
        #we might have associated whether this stylesheet is cacheable or not
        #(or additional keys)
        styleSheetKeys = styleSheet.isCacheable
    except AttributeError:
        #no we didn't, calculate that now
        styleSheetKeys = styleSheet.isCacheable = getStylesheetCacheKey(
            styleSheet.children, styleSheetNotCacheableFunctions)
      
    if isinstance(styleSheetKeys, MRUCache.NotCacheable):
        raise styleSheetKeys #not cacheable
    else:
        key.extend(styleSheetKeys)

    #the top level xsl:param element determines the parameters of the stylesheet: extract them          
    topLevelParams = [child for child in styleSheet.children 
        if child.expandedName[0] == XSL_NAMESPACE and child.expandedName[1] == 'param']
       
    for var in topLevelParams:
        #note: we don't really need the contextNode     
        #var._name is (ns, local)
        if var._name[0]:
            processorNss = { 'x' : var._name[0]}
            qname = 'x:'+ var._name[1]
        else:
            processorNss = { }
            qname = var._name[1]
         
        context = XPath.Context.Context(contextNode, processorNss = processorNss)
        if HasMetaData(kw, context, qname): 
            value = GetMetaData(kw, context, qname)
            if type(value) is type([]):
                value = tuple(value)
            key.append( ( var._name ,value) )
        else:
            key.append( var._name )
    return tuple(key)

def xsltSideEffectsCalc(cacheValue, resultNodeset, kw, contextNode, retVal):
    '''
    Calculate a value that represents the side effects that occurred while processing this.    
    '''
    #assign-metadata and remove-metadata record the changes they made in _metadatachanges
    return kw.get('_metadatachanges', [])

def xsltSideEffectsFunc(cacheValue, sideEffects, resultNodeset, kw, contextNode, retVal):
    '''
    This called when retrieving a value from the cache and we want to
    re-play any side effects that occurred when calculating the value.
    '''
    for change in sideEffects:
        nssMap = change[0]
        change = change[1]
        #note: we don't really need the contextNode
        context = XPath.Context.Context(contextNode, processorNss = nssMap)
        if isinstance(change, tuple):
            AssignMetaData(kw, context, change[0],change[1])
        else:        
            RemoveMetaData(kw, context, change)
    return cacheValue
                
def _addXPathExprCacheKey(compExpr, nsMap, key, notCacheableXPathFunctions):
    '''
    Check if the XPath expression is cacheable and return a key representing the expression.
    This is similar to getKeyFromXPathExp except it doesn't add variable references to key.
    '''
    #note: we don't know the contextNode now, keyfunc must be prepared to handle that
    context = XPath.Context.Context(None, processorNss = nsMap)    
    for field in compExpr:
        if isinstance(field, XPath.ParsedExpr.FunctionCall):
          (prefix, local) = field._key
          if prefix:
              expanded = (nsMap[prefix], local)
          else:
              expanded = field._key
          if expanded in notCacheableXPathFunctions:
               keyfunc = notCacheableXPathFunctions[expanded]
               if keyfunc:
                   key.append( keyfunc(field, context, notCacheableXPathFunctions) ) #may raise MRUCache.NotCacheable
               else:
                   raise MRUCache.NotCacheable    

def getStylesheetCacheKey(nodes, styleSheetNotCacheableFunctions, key = None):
    '''
    Walk through the elements in the stylesheet looking for
    elements that reference XPath expressions; then iterate through each 
    expression looking for functions that aren't cacheable.
    Also checks for uncacheable extension elements.
    '''
    from Ft.Xml.Xslt import AttributeInfo, AttributeValueTemplate    
    key = key or []
    try:
        for node in nodes:
            #is this element cachable?
            if node.expandedName in styleSheetNotCacheableFunctions:                
                keyfunc = notCacheableXPathFunctions[expandedKey]
                if keyfunc:
                   context = XPath.Context.Context(None, processorNss = nsMap)    
                   key.extend( keyfunc(node, context, notCacheableXPathFunctions) )
                else:
                   #stylesheet uses an uncacheable extension element
                   raise MRUCache.NotCacheable                    
            attrDict = getattr(node, 'legalAttrs', None)
            if attrDict is not None:
                for name, value in attrDict.items():
                    if isinstance(value, (AttributeInfo.Expression, AttributeInfo.Avt)):
                        #this attribute may have an expression in it
                        attributeName = '_' + SplitQName(name)[1].replace('-', '_') #see Ft.Xml.Xslt.StylesheetHandler
                        attributeValue = getattr(node, attributeName, None)
                        if isinstance(attributeValue, AttributeInfo.ExpressionWrapper):
                            _addXPathExprCacheKey(attributeValue.expression,
                                node.namespaces, key, styleSheetNotCacheableFunctions)                                
                        elif isinstance(attributeValue, AttributeValueTemplate.AttributeValueTemplate):
                            for expr in attributeValue._parsedParts:
                                _addXPathExprCacheKey(expr, node.namespaces,
                                                key, styleSheetNotCacheableFunctions)
            #handle LiteralElements
            outputAttrs = getattr(node, '_output_attrs', None) 
            if outputAttrs is not None:
                for (qname, namespace, value) in outputAttrs:
                    if isinstance(value, AttributeValueTemplate.AttributeValueTemplate):                           
                        for expr in value._parsedParts:
                            _addXPathExprCacheKey(expr, node.namespaces,
                                             key, styleSheetNotCacheableFunctions)                

            if node.children is not None:
                key = getStylesheetCacheKey(node.children, styleSheetNotCacheableFunctions, key)
                if isinstance(key, MRUCache.NotCacheable):
                    return key
    except MRUCache.NotCacheable, e:
      return e
    
    return key