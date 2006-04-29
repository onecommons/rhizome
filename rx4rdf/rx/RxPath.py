'''
    An implementation of RxPath.
    Loads and saves the DOM to a RDF model.

    See RxPathDOM.py for more notes and todos.

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
'''
from __future__ import generators

from Ft.Lib.boolean import false as XFalse, true as XTrue, bool as Xbool

from Ft.Xml.XPath.Conversions import StringValue, NumberValue
from Ft.Xml import XPath, InputSource, SplitQName, EMPTY_NAMESPACE

from rx import utils
from rx.RxPathUtils import *
from rx.RxPathModel import *
from rx.RxPathSchema import *

import os.path, sys, traceback

from rx import logging #for python 2.2 compatibility
log = logging.getLogger("RxPath")

useQueryEngine = 1

def createDOM(model, nsRevMap = None, modelUri=None,
        schemaClass = defaultSchemaClass, graphManager=None):
    from rx import RxPathDom
    return RxPathDom.Document(model, nsRevMap,modelUri,schemaClass,
                              graphManager=graphManager)




##########################################################################
## public utility functions
##########################################################################
    
def splitUri(uri):
    '''
    Split an URI into a (namespaceURI, name) pair suitable for creating a QName with
    Returns (uri, '') if it can't
    '''
    if uri.startswith(BNODE_BASE):  
        index = BNODE_BASE_LEN-1
    else:
        index = uri.rfind('#')
    if index == -1:        
        index = uri.rfind('/')
        if index == -1:
            index = uri.rfind(':')
            if index == -1:
                return (uri, '') #no ':'? what kind of URI is this?
    local = uri[index+1:]
    if not local or (not local[0].isalpha() and local[0] != '_'):
       return (uri, '')  #local name doesn't start with a namechar or _  
    if not local.replace('_', '0').replace('.', '0').replace('-', '0').isalnum():
       return (uri, '')  #local name has invalid characters  
    if local and not local.lstrip('_'): #if all '_'s
        local += '_' #add one more
    return (uri[:index+1], local)

def elementNamesFromURI(uri, nsMap):    
    predNs, predLocal  = splitUri(uri)
    if not predLocal: # no "#" or nothing after the "#" 
        predLocal = u'_'
    if nsMap.has_key(predNs):
        prefix = nsMap[predNs]
    else:        
        prefix = u'ns' + str(len(nsMap.keys()))
        nsMap[predNs] = prefix
    return prefix+':'+predLocal, predNs, prefix, predLocal

def getURIFromElementName(elem):
    u = elem.namespaceURI
    local = elem.localName 
    return u + getURIFragmentFromLocal(local)

def getURIFragmentFromLocal(local):
    if local[-1:] == '_' and not local.lstrip('_'): #must be all '_'s
        return local[:-1] #strip last '_'
    else:
        return local

##########################################################################
## public user functions
##########################################################################                
from Ft.Xml.Xslt.Processor import Processor
class RxSLTProcessor(Processor, object): #derive from object so super() works
    def _stripElements(self, node):
        '''RxSLT DOMs don't need StripElements called'''#huge optimization!
        return

def applyXslt(rdfDom, xslStylesheet, topLevelParams = None, extFunctionMap = None,
              baseUri='file:', styleSheetCache = None, processor = None):
    if extFunctionMap is None: extFunctionMap = {}
    #ExtFunctions = { (FT_EXT_NAMESPACE, 'base-uri'): BaseUri,
    #processor.registerExtensionModules( [__name__] )
    #or processor.registerExtensionFunction(namespace, localName, function) #function just need context as first arg
    if extFunctionMap:
        extFunctionMap.update(BuiltInExtFunctions)
    else:
        extFunctionMap = BuiltInExtFunctions

    if processor is None:
        processor = RxSLTProcessor()

    if styleSheetCache:
        styleSheet = styleSheetCache.getValue(xslStylesheet, baseUri)
        processor.appendStylesheetInstance( styleSheet, baseUri ) 
    else:
        processor.appendStylesheet( InputSource.DefaultFactory.fromString(xslStylesheet, baseUri)) #todo: fix this
        
    for (k, v) in extFunctionMap.items():
        namespace, localName = k
        processor.registerExtensionFunction(namespace, localName, v)
        
    oldVal = rdfDom.globalRecurseCheck #todo make globalRecurseCheck a thread local property
    rdfDom.globalRecurseCheck=True #todo remove this when we implement RxSLT
    try:
        return processor.runNode(rdfDom, None, 0, topLevelParams) 
    finally:
        rdfDom.globalRecurseCheck=oldVal

def applyXUpdate(rdfdom, xup = None, vars = None, extFunctionMap = None, uri='file:', msgOutput=None):
    """
    Executes the XUpdate script on the given RxPathDOM.  The XUpdate document is either
    contained as a string in the xup parameter or as an URL specified in the uri parameter.
    """
    #from Ft.Xml import XUpdate #buggy -- use our patched version
    from rx import XUpdate
    from Ft.Xml import Domlette
    xureader = Domlette.NonvalidatingReader    
    processor = XUpdate.Processor()
    if msgOutput is not None:
        processor.messageControl(msgOutput)
    if xup is None:
        xupInput = InputSource.DefaultFactory.fromUri(uri)
    else:
        xupInput = InputSource.DefaultFactory.fromString(xup, uri)
    xupdate = xureader.parse(xupInput)
    if extFunctionMap:
        extFunctionMap.update(BuiltInExtFunctions)
    else:
        extFunctionMap = BuiltInExtFunctions    
    processor.execute(rdfdom, xupdate, vars, extFunctionMap = extFunctionMap)

def _compileXPath(xpath, context, expCache=None, useEngine=None):
    if expCache:
        compExpr = expCache.getValue(xpath)#, context)
        #todo support the caching of ReplaceRxPathSubExpr
        #e.g. def cacheKey():
        #  if (useEngine and context and context.node is rxpath: extract context.vars
        #todo: nsMap should be part of the key -- until then clear the cache if you change that!
    else:
        compExpr = XPath.Compile(xpath)

    #so we can change useQueryEngine anytime    
    useEngine = useEngine is None and useQueryEngine or useEngine 
    
    origCompExpr = compExpr
    if useEngine and getattr(compExpr, 'fromCache', False):
        #if skipQuery is set, its a regular XPath expr
        if getattr(compExpr, 'skipQuery', False):
            useEngine = False
        else:
            #don't modify the compExpr saved in the cache
            compExpr = XPath.Compile(xpath)
    
    if useEngine:
        import RxPathQuery
        transform = RxPathQuery.ReplaceRxPathSubExpr(context, compExpr)
        if transform.changed:
            compExpr = transform.resultExpr
        else:
            origCompExpr.skipQuery = True

    return compExpr    

cumTime = 0
cumAnaTime = 0 

_saveStats = 0
if _saveStats:
    evalRunOut = file('evalRun.txt', 'w')

def evalXPath(xpath, context, expCache=None, queryCache=None, useEngine=None):
    context.functions.update(BuiltInExtFunctions)

    from time import time as timer
    start = timer() 
    
    compExpr =_compileXPath(xpath, context, expCache, useEngine)
    
    analyzeTime = timer() - start
        
    if queryCache:
        res = queryCache.getValue(compExpr, context)         
    else:
        res = compExpr.evaluate(context)
    
    xpathClock = timer() - start
    global cumTime, cumAnaTime
    cumTime += xpathClock
    cumAnaTime += analyzeTime
    if _saveStats:
        print >> evalRunOut, '%08.3f %07.4f' % (cumTime, xpathClock), xpath.replace('\n',' ') #cumAnaTime, analyzeTime
    return res

##########################################################################
## RxPath extension functions
##########################################################################                
#todo: return true if all in nodeset?
#isSubject is a little murky.. why would use it
##def isSubject(context, nodeset=None):
##    if nodeset is None:
##        nodeset = [ context.node ]
##    return nodeset[0].nodeType == Node.ELEMENT_NODE and nodeset[0].parentNode == nodeset[0].ownerDocument 
##
##def isObject(context, nodeset=None):
##    if nodeset is None:
##        nodeset = [ context.node ]
##    return nodeset[0].parentNode and isPredicate(context, nodeset[0].parentNode)

def isPredicate(context, nodeset=None):
    '''
    return true if the nodeset is not empty and all the nodes in the nodeset
    are predicate nodes, otherwise return false.
    '''
    if nodeset is None:
        nodeset = [ context.node ]
        
    if nodeset and nodeset[0].nodeType == Node.ELEMENT_NODE and nodeset[0].parentNode\
       and isResource(context, [nodeset[0].parentNode]):
        if len(nodeset)>1:
            return isPredicate(context, nodeset[1:])
        else:
            return XTrue #we made it to the end 
    else:
        return XFalse

def isResource(context, nodeset=None):
    '''
    return true if the nodeset is not empty and all the nodes in the nodeset
    are resource nodes, otherwise return false.
    '''
    if nodeset is None:
        nodeset = [ context.node ]
        
    if nodeset and nodeset[0].nodeType == Node.ELEMENT_NODE\
       and nodeset[0].getAttributeNS(RDF_MS_BASE, 'about'):#or instead use: and not isPredicate(context, nodeset[0])
        if len(nodeset) > 1:
            return isResource(context, nodeset[1:])
        else:
            return XTrue #we made it to the end 
    else:
        return XFalse

def getResource(context, nodeset=None):
    '''
    map each node in the nodeset to its "nearest resource":
    if we're a resource return '.'
    if we're a predicate return '..'
    if we're a literal return '../..'
    otherwise empty nodeset
    '''    
    if nodeset is None:
        nodeset = [ context.node ]
        
    def getResourceFromNode(node):
        if node.nodeType == Node.ATTRIBUTE_NODE:
            node = node.ownerElement
        if isResource(context, [node]):
            return node
        else:
            return getResourceFromNode(node.parentNode)
    return [getResourceFromNode(node) for node in nodeset \
        if node.nodeType in [Node.ELEMENT_NODE, Node.TEXT_NODE, Node.ATTRIBUTE_NODE] ]
        
def isInstanceOf(context, candidate, test):
    '''
    This function returns true if the resource specified in the first
    argument is an instance of the class resource specified in the
    second argument, where each string is treated as the URI reference
    of a resource.
    '''
    #design note: follow equality semantics for nodesets
    if not isinstance(test, list):
        test = [ test ]
    if not isinstance(candidate, list):
        candidate = [ candidate ]
    for node in test:
        classResource = StringValue(node)
        for candidateNode in candidate:
            resource = context.node.ownerDocument.findSubject(
                                     StringValue(candidateNode))
            if resource and resource.matchName(classResource, ''):
                return XTrue
    return XFalse
               
def isProperty(context, candidate, test):
    '''    
    This function returns true if the property specified in the first
    argument is a subproperty of the property specified in the second
    argument, where each string is treated as the URI reference of a
    property resource.
    '''
    #design note: follow equality semantics for nodesets
    if not isinstance(test, list):
        test = [ test ]
    if not isinstance(candidate, list):
        candidate = [ candidate ]
    for node in test:
        propertyURI = StringValue(node)
        for candidateNode in candidate:
            if context.node.ownerDocument.schema.isCompatibleProperty(
                            StringValue(candidateNode), propertyURI):
                return XTrue
    return XFalse

def isType(context, candidate, test):
    '''    
    This function returns true if the class specified in the first
    argument is a subtype of the class specified in the second
    argument, where each string is treated as the URI reference of a
    class resource.
    '''
    #design note: follow equality semantics for nodesets
    if not isinstance(test, list):
        test = [ test ]
    if not isinstance(candidate, list):
        candidate = [ candidate ]
    for node in test:
        classURI = StringValue(node)
        for candidateNode in candidate:
            if context.node.ownerDocument.schema.isCompatibleType(
                            StringValue(candidateNode), classURI):
                return XTrue
    return XFalse

def getQNameFromURI(context, uri=None):
    return _getNamesFromURI(context, uri)[0]

def getNamespaceURIFromURI(context, uri=None):
    return _getNamesFromURI(context, uri)[1]

def getPrefixFromURI(context, uri=None):
    return _getNamesFromURI(context, uri)[2]

def getLocalNameFromURI(context, uri=None):
    return _getNamesFromURI(context, uri)[3]

def _getNamesFromURI(context, uri=None):    
    if uri is None:
        uri = context.node
    uri = StringValue(uri)
    qname, namespaceURI, prefix, localName = \
        elementNamesFromURI(uri, context.node.ownerDocument.nsRevMap)
    return qname, namespaceURI, prefix, localName 

def getURIFromElement(context, nodeset=None):
    string = None
    if nodeset is None:
        node = context.node
    elif type(nodeset) == type([]):
        if nodeset:
            node = nodeset[0]
            if node.nodeType != Node.ELEMENT_NODE:
               string = node
        else:
            return u''
    else:
        string = nodeset
        
    if string is not None:
       qname = StringValue(string)
       (prefix, local) = SplitQName(qname)
       if prefix:
        try:
            namespace = context.processorNss[prefix]
        except KeyError:
            raise XPath.RuntimeException(XPath.RuntimeException.UNDEFINED_PREFIX,
                                   prefix)       
        return namespace + getURIFragmentFromLocal(local)
    else:
        return getURIFromElementName(node)

def getReified(context, nodeset):
    reifications = []
    for node in nodeset:
        if hasattr(node,'stmt'):
            reifiedURIs=node.ownerDocument.model.findStatementIDs(node.stmt)
            reifications.extend([node.ownerDocument.findSubject(uri)
                                 for uri in reifiedURIs])
    return reifications

def getGraphPredicates(context, uri):
    uri = StringValue(uri)
    predicates = []
    doc = context.node.ownerDocument
    if doc.graphManager:
        statements = doc.graphManager.getStatementsInGraph(uri)
    else:
        statements = doc.model.getStatements(context=uri)
    for stmt in statements:        
        assert stmt.scope == uri
        subjectNode = doc.findSubject(stmt.subject)
        assert subjectNode
        predNode = subjectNode.findPredicate(stmt)
        assert predNode
        predicates.append(predNode)
    return predicates

def findGraphURIs(context, nodeset):
    scopes = {}
    for node in nodeset:
        if hasattr(node,'stmt'):
            if stmt.scope:
                scopeRes = node.ownerDocument.findSubject(stmt.scope)
                assert scopeRes
                scopes[stmt.scope]= scopeRes
    return scopes.values()

def rdfDocument(context, object,type='unknown', nodeset=None):
    '''Equivalent to XSLT's document() function except it parses RDF
    and returns RxPath Document nodes instead of XML Document nodes.
    The first and third arguments are equivalent to document()'s first
    and second arguments, respectively, and the second argument is
    converted to a string that names the format of the RDF being
    parsed. The format names recognized are the same as the ones used
    by parseRDFFromString(). ParseException will be raised if the RDF
    can not be parsed.

    Note: this is only available in the context of an XSLT processor.
    '''
    
    type = StringValue(type)
    oldDocReader = context.processor._docReader
    class RDFDocReader:
        def __init__(self, uri2prefixMap, type, schemaClass):
            self.uri2prefixMap = uri2prefixMap
            self.type = type
            self.schemaClass = schemaClass
            
        def parse(self, isrc): 
            contents = isrc.stream.read()
            isrc.stream.close()
            stmts = parseRDFFromString(contents, isrc.uri, self.type)            
            return RxPathDOMFromStatements(stmts, self.uri2prefixMap, isrc.uri,
                                           self.schemaClass)

    nsRevMap = getattr(context.node.ownerDocument, 'nsRevMap', None)
    schemaClass = getattr(context.node.ownerDocument, 'schemaClass',
                                                      defaultSchemaClass)
    context.processor._docReader = RDFDocReader(nsRevMap, type,defaultSchemaClass)
    from Ft.Xml.Xslt import XsltFunctions
    result = XsltFunctions.Document(context, object, nodeset)
    context.processor._docReader = oldDocReader
    return result

#def XML2RDF(context, nodeset, uri,type=None):
#    uri = StringValue(uri)
#    assert len(nodeset) == 1, 'only one root node in nodeset supported'
#    nsRevMap = getattr(context.node.ownerDocument, 'nsRevMap', None)
#    return RxPathDOMFromStatements(parseRDFFromDOM(nodeset[0]), nsRevMap, uri)

def getContextDoc(context, nodeset):
    contexturis = [n.uri for n in nodeset if isResource([n])]
    if not contexturis:
        return []
    return [ RxPathDom.ContextDoc(nodeset[0].rootNode,contexturis) ]        
            
RXPATH_EXT_NS = None #todo: put these in an extension namespace?
BuiltInExtFunctions = {
(RXPATH_EXT_NS, 'is-predicate'): isPredicate,
(RXPATH_EXT_NS, 'is-resource'): isResource,
(RXPATH_EXT_NS, 'resource'): getResource,

(RXPATH_EXT_NS, 'is-instance-of'): isInstanceOf,
(RXPATH_EXT_NS, 'is-subproperty-of'): isProperty,
(RXPATH_EXT_NS, 'is-subclass-of'): isType,

(RXPATH_EXT_NS, 'name-from-uri'): getQNameFromURI,
(RXPATH_EXT_NS, 'prefix-from-uri'): getPrefixFromURI,
(RXPATH_EXT_NS, 'local-name-from-uri'): getLocalNameFromURI,
(RXPATH_EXT_NS, 'namespace-uri-from-uri'): getNamespaceURIFromURI,
(RXPATH_EXT_NS, 'uri'): getURIFromElement,

(RXPATH_EXT_NS, 'get-statement-uris'): getReified,
(RXPATH_EXT_NS, 'get-graph-predicates'): getGraphPredicates,
(RXPATH_EXT_NS, 'rdfdocument'): rdfDocument,
}
from Ft.Xml.Xslt import XsltContext
XsltContext.XsltContext.functions[(RXPATH_EXT_NS, 'rdfdocument')] = rdfDocument
##########################################################################
## "monkey patches" to Ft.XPath
##########################################################################

#4suite 1.0a3 disables this function but we really need it 
#as a "compromise" we only execute this function if getElementById is there
#also there's a bug in 4Suite's id() in that nodeset can contain duplicates
from Ft.Xml.Xslt import XsltFunctions, XsltContext
from Ft.Lib import Set
def Id(context, object):
    """Function: <node-set> id(<object>)"""
    id_list = []
    if type(object) != type([]):
        st = StringValue(object)
        id_list = st.split()
    else:
        for n in object:
            id_list.append(StringValue(n))

    doc = context.node.rootNode
    getElementById = getattr(doc, 'getElementById', None)
    if not getElementById:
       #this is from 4suite 1.0a3's version of id():
       import warnings
       warnings.warn("id() function not supported")
       #We do not (cannot, really) support the id() function
       return []
           
    nodeset = []
    for id in id_list:
        element = getElementById(id)
        if element:
           nodeset.append(element)
    return Set.Unique(nodeset)

XPath.CoreFunctions.CoreFunctions[(EMPTY_NAMESPACE, 'id')] = Id
XPath.Context.Context.functions[(EMPTY_NAMESPACE, 'id')] = Id
XsltContext.XsltContext.functions[(EMPTY_NAMESPACE, 'id')] = Id

from xml.dom import Node

preNodeSorting4Suite = hasattr(XPath.Util, 'SortDocOrder') #4Suite versions prior to 1.0b1
if preNodeSorting4Suite: 
    def SortDocOrder(context, nodeset):
        return XPath.Util.SortDocOrder(context, nodeset)
else:
    def SortDocOrder(context, nodeset):
        nodeset.sort()
        return nodeset

def descendants(self, context, nodeTest, node, nodeSet, startNode=None):
    """Select all of the descendants from the context node"""
    startNode = startNode or context.node
    if context.node.nodeType != Node.ATTRIBUTE_NODE:
        childNodeFunc = getattr(node, 'getSafeChildNodes', None)
        if childNodeFunc:
            childNodes = childNodeFunc(startNode)
        else:
            childNodes = node.childNodes
        for child in childNodes:
            childNodeFunc = getattr(child, 'getSafeChildNodes', None)
            if childNodeFunc:
                if isPredicate(context, [child]):
                    if nodeTest(context, child, self.principalType):
                        nodeSet.append(child)
                    else:
                        continue#we're a RxPath dom and the nodetest didn't match, don't examine the node's descendants
            elif nodeTest(context, child, self.principalType):
                nodeSet.append(child)
             
            if childNodeFunc:
                childNodes = childNodeFunc(startNode)
            else:
                childNodes = child.childNodes                
            if childNodes:
                self.descendants(context, nodeTest, child, nodeSet, startNode)
    return (nodeSet, 0)
XPath.ParsedAxisSpecifier.AxisSpecifier.descendants = descendants

def findNextStep(parsed):
    #currently only works in the context of a ParsedAbbreviatedAbsoluteLocationPath
    if isinstance(parsed, (XPath.ParsedStep.ParsedStep, XPath.ParsedStep.ParsedAbbreviatedStep)):
        return parsed
    elif isinstance(parsed, (XPath.ParsedRelativeLocationPath.ParsedRelativeLocationPath,
                XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath)):
        return findNextStep(parsed._left)
    else:
        return None

def isChildAxisSpecifier(step):    
    axis = getattr(step, '_axis', None)
    if isinstance(axis, XPath.ParsedAxisSpecifier.ParsedChildAxisSpecifier):
        return True
    else:
        return False

def _descendants(self, context, nodeset, nextStepAttr, startNode=None):
    startNode = startNode or context.node
    childNodeFunc = getattr(context.node, 'getSafeChildNodes', None)
    if childNodeFunc:
        childNodes = childNodeFunc(startNode)
    else:
        childNodes = context.node.childNodes

    nextStep = getattr(self, nextStepAttr)
    
    nodeTest = None
    if childNodeFunc:
        step = findNextStep(nextStep)
        nodeTest = getattr(step, '_nodeTest', None)

    for child in childNodes:
        context.node = child

        #if an RxPath DOM then only evaluate predicate nodes
        if childNodeFunc:            
            if isPredicate(context, [child]):                
                if nodeTest: #no nodeTest is equivalent to node()
                    if not nodeTest.match(context, context.node, step._axis.principalType):
                        continue#we're a RxPath dom and the nodetest didn't match, don't examine the node's descendants
                results = nextStep.select(context)
            else:
                results = []
        else:
            results = nextStep.select(context)

        # Ensure no duplicates
        if results:
            if preNodeSorting4Suite:
                #need to do inplace filtering
                nodeset.extend(filter(lambda n, s=nodeset: n not in s, results))
            else:
                nodeset.extend(results)
                nodeset = Set.Unique(nodeset)
                                
        if child.nodeType == Node.ELEMENT_NODE:
            nodeset = self._descendants(context, nodeset, startNode)
    return nodeset

_ParsedAbbreviatedRelativeLocationPath_oldEvaluate = XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath.evaluate.im_func
def _ParsedAbbreviatedRelativeLocationPath_evaluate(self, context):    
    if getattr(context.node, 'getSafeChildNodes', None):
        step = findNextStep(self._right)
        if isChildAxisSpecifier(step):
            #change next step from child to descendant
            #todo: bug if you reuse this parsed expression on a non-RxPath dom
            step._axis = XPath.ParsedAxisSpecifier.ParsedAxisSpecifier('descendant')
            if hasattr(self, '_middle'): #for older 4Suite versions
                   #make _middle does no filtering
                   self._middle._axis = XPath.ParsedAxisSpecifier.ParsedAxisSpecifier('self')
            nodeset = self._left.select(context)

            state = context.copy()
            
            size = len(nodeset)
            result = []
            for pos in range(size):
                context.node, context.position, context.size = \
                              nodeset[pos], pos + 1, size
                subRt = self._right.select(context)
                result = Set.Union(result, subRt)

            context.set(state)
            return result            
    return _ParsedAbbreviatedRelativeLocationPath_oldEvaluate(self, context)

XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath\
    .evaluate = _ParsedAbbreviatedRelativeLocationPath_evaluate
XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath\
    .select = XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath.evaluate
XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath\
    ._descendants = lambda self, context, nodeset, startNode=None: \
                         _descendants(self, context, nodeset, '_right', startNode)
        
def _ParsedAbbreviatedAbsoluteLocationPath_evaluate(self, context):    
    state = context.copy()

    # Start at the document node    
    context.node = context.node.rootNode

    if getattr(context.node, 'getSafeChildNodes', None):
        #todo: bug if you reuse this parsed expression on a non-RxPath dom
        step = findNextStep(self._rel)
        if isChildAxisSpecifier(step):
            #change next step from child to descendant
            step._axis = XPath.ParsedAxisSpecifier.ParsedAxisSpecifier('descendant')
            nodeset = self._rel.select(context)
            context.set(state)
            return nodeset

    nodeset = self._rel.select(context)
    _nodeset = self._descendants(context, nodeset)
    if _nodeset is not None: 
        nodeset = _nodeset #4suite 1.0b1 and later

    context.set(state)
    return SortDocOrder(context, nodeset)

XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath\
    .evaluate = _ParsedAbbreviatedAbsoluteLocationPath_evaluate
XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath\
    .select = XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath.evaluate
XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath\
    ._descendants = lambda self, context, nodeset, startNode=None: \
                         _descendants(self, context, nodeset, '_rel', startNode)

_ParsedPathExpr_oldEvaluate = XPath.ParsedExpr.ParsedPathExpr.evaluate.im_func
def _ParsedPathExpr_evaluate(self, context):
    descendant = getattr(self, '_step', getattr(self, '_descendant', None))
    if getattr(context.node, 'getSafeChildNodes', None) and descendant:
        step = findNextStep(self._right)
        if isChildAxisSpecifier(step):
            #change next step from child to descendant
            #todo: bug if you reuse this parsed expression on a non-RxPath dom
            step._axis = XPath.ParsedAxisSpecifier.ParsedAxisSpecifier('descendant')
            if getattr(self, '_step', None): #before 4Suite 1.0b1
                #make _step do no filtering
                self._step._axis = XPath.ParsedAxisSpecifier.ParsedAxisSpecifier('self')
            else:
                self._descendant = False #skip descendant checking
    return _ParsedPathExpr_oldEvaluate(self, context)
XPath.ParsedExpr.ParsedPathExpr.evaluate = _ParsedPathExpr_evaluate

#patch XPath.ParsedNodeTest.QualifiedNameTest:
_QualifiedNameTest_oldMatch = XPath.ParsedNodeTest.QualifiedNameTest.match.im_func
def _QualifiedNameTest_match(self, context, node, principalType=Node.ELEMENT_NODE):    
    if not hasattr(node, 'matchName'):
        return _QualifiedNameTest_oldMatch(self, context, node, principalType)
    else:
        try:
            return node.nodeType == principalType and node.matchName(
                    context.processorNss[self._prefix], self._localName)
        except KeyError:
            raise XPath.RuntimeException(XPath.RuntimeException.UNDEFINED_PREFIX, self._prefix)        
    
XPath.ParsedNodeTest.QualifiedNameTest.match = _QualifiedNameTest_match

_NamespaceTest_oldMatch = XPath.ParsedNodeTest.NamespaceTest.match.im_func
def _NamespaceTest_match(self, context, node, principalType=Node.ELEMENT_NODE):
    if not hasattr(node, 'matchName'):
        return _NamespaceTest_oldMatch(self, context, node, principalType)
    else:
        try:
            return node.nodeType == principalType and node.matchName(context.processorNss[self._prefix], '*')
        except KeyError:
            raise XPath.RuntimeException(XPath.RuntimeException.UNDEFINED_PREFIX, self._prefix)        
        
XPath.ParsedNodeTest.NamespaceTest.match = _NamespaceTest_match

if preNodeSorting4Suite: #if prior to 4suite b1
    def _FunctionCallEvaluate(self, context, oldFunc):
        #make XPath.ParsedExpr.FunctionCall*.evaluate have no side effects so we can cache them
        if self._name != 'evalRxPathQuery':
            self._func = None
        
        retVal = oldFunc(self, context)    
        #prevent expressions that are just function calls
        #from returning nodesets with duplicate nodes
        if type(retVal) == type([]):
           return Set.Unique(retVal)
        else:
           return retVal
        
    XPath.ParsedExpr.FunctionCall.evaluate = lambda self, context, \
        func = XPath.ParsedExpr.FunctionCall.evaluate.im_func: \
            _FunctionCallEvaluate(self, context, func)

    XPath.ParsedExpr.FunctionCall1.evaluate = lambda self, context, \
        func = XPath.ParsedExpr.FunctionCall1.evaluate.im_func: \
            _FunctionCallEvaluate(self, context, func)

    XPath.ParsedExpr.FunctionCall2.evaluate = lambda self, context, \
        func = XPath.ParsedExpr.FunctionCall2.evaluate.im_func: \
            _FunctionCallEvaluate(self, context, func)

    XPath.ParsedExpr.FunctionCall3.evaluate = lambda self, context, \
        func = XPath.ParsedExpr.FunctionCall3.evaluate.im_func: \
            _FunctionCallEvaluate(self, context, func)

    XPath.ParsedExpr.FunctionCallN.evaluate = lambda self, context, \
        func = XPath.ParsedExpr.FunctionCallN.evaluate.im_func: \
            _FunctionCallEvaluate(self, context, func)

#patch this function so that higher-level code has
#access to the underlying exception
from Ft.Xml.Xslt import XsltRuntimeException, Error,XsltFunctions,AttributeInfo
def ExpressionWrapper_evaluate(self,context):
 try:
     return self.expression.evaluate(context)
 except XPath.RuntimeException, e:
     from Ft.Xml.Xslt import MessageSource
     e.message = MessageSource.EXPRESSION_POSITION_INFO % (
         self.element.baseUri, self.element.lineNumber,
         self.element.columnNumber, self.original, str(e))
     # By modifying the exception value directly, we do not need
     # to raise with that value, thus leaving the frame stack
     # intact (original traceback is displayed).
     raise
 except XsltRuntimeException, e:
     from Ft.Xml.Xslt import MessageSource
     e.message = MessageSource.XSLT_EXPRESSION_POSITION_INFO % (
         str(e), self.original)
     # By modifying the exception value directly, we do not need
     # to raise with that value, thus leaving the frame stack
     # intact (original traceback is displayed).
     raise
 except Exception, e:
     from Ft.Xml.Xslt import MessageSource     
     tb = StringIO.StringIO()
     tb.write("Lower-level traceback:\n")
     traceback.print_exc(1000, tb)
     raise utils.NestedException(MessageSource.EXPRESSION_POSITION_INFO % (
         self.element.baseUri, self.element.lineNumber,
         self.element.columnNumber, self.original, tb.getvalue()),
                       useNested = False)
AttributeInfo.ExpressionWrapper.evaluate = ExpressionWrapper_evaluate
