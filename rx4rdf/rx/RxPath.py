from __future__ import generators

from Ft.Rdf import OBJECT_TYPE_RESOURCE, OBJECT_TYPE_LITERAL, Util, BNODE_BASE, BNODE_BASE_LEN,RDF_MS_BASE
from Ft.Xml import XPath, InputSource
from Ft.Rdf.Statement import Statement
from rx import utils
from rx.utils import generateBnode
import os.path, sys

from rx import logging #for python 2.2 compatibility
log = logging.getLogger("RxPath")

#from Ft.Rdf import RDF_MS_BASE -- for some reason we need this to be unicode for the xslt engine:
RDF_MS_BASE=u'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
OBJECT_TYPE_XMLLITERAL='http://www.w3.org/1999/02/22-rdf-syntax-ns#XMLLiteral'

def createDOM(model, nsRevMap = None):
    from rx import RxPathDom
    return RxPathDom.Document(model, nsRevMap)

class Model(object):
    ### Transactional Interface ###

    def begin(self):
        return

    def commit(self):
        return

    def rollback(self):
        return

    ### Operations ###
    
    def getResources(self):
        '''All resources referenced in the model, include resources that only appear as objects in a triple.
           Returns a list of resources are sorted by their URI reference
        '''
        
    def getStatements(self, subject = None, predicate = None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        
    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        
    def removeStatement(self, statement ):
        '''removes the statement'''

def removeDupsFromSortedList(aList):       
    def removeDups(x, y):
        if not x or x[-1] != y:
            x.append(y)
        return x
    return reduce(removeDups, aList, [])

class FtModel(Model):
    '''
    wrapper around 4Suite's Ft.Rdf.Model
    '''
    def __init__(self, ftmodel):
        self.model = ftmodel

    def begin(self):
        self.model._driver.begin()

    def commit(self):
        self.model._driver.commit()

    def rollback(self):
        self.model._driver.rollback()        
    
    def getResources(self):
        '''All resources referenced in the model, include resources that only appear as objects in a triple.
           Returns a list of resources are sorted by their URI reference
        '''        
        def f(l, stmt):
            l.append(stmt.subject)
            if stmt.objectType == OBJECT_TYPE_RESOURCE:
                l.append(stmt.object)
            return l
        resources = reduce(f, self.model.complete(None, None, None), [])
        resources.sort()
        return removeDupsFromSortedList(resources)        
        
    def getStatements(self, subject = None, predicate = None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        statements = self.model.complete(subject, predicate, None) 
        statements.sort()
        return removeDupsFromSortedList(statements)
                     
    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        self.model.add( statement )

    def removeStatement(self, statement ):
        '''removes the statement'''
        self.model.remove( statement)
        
class MultiModel(Model):
    '''
    This allows one writable model and multiple read-only models.
    All mutable methods will be called on the writeable model only.
    Useful for allowing static information in the model, for example representations of the application.    
    '''
    def __init__(self, writableModel, *readonlyModels):
        self.models = (writableModel,) + readonlyModels        

    def begin(self):
        self.models[0].begin()

    def commit(self):
        self.models[0].commit()

    def rollback(self):
        self.models[0].rollback()        

    def getResources(self):
        statements = []
        for model in self.models:
            statements += model.getResources()
        statements.sort()
        return removeDupsFromSortedList(statements)
                    
    def getStatements(self, subject = None, predicate = None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        statements = []
        for model in self.models:
            statements += model.getStatements(subject, predicate)
        statements.sort()
        return removeDupsFromSortedList(statements)
                     
    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        self.models[0].addStatement( statement )
        
    def removeStatement(self, statement ):
        '''removes the statement'''
        self.models[0].removeStatement( statement)

class TransactionModel(object):
    '''
    Provides transaction functionality.
    This class typically needs to be most derived; for example:
    
    MyModel(Model):
        def __init__(self): ...
        
        def addStatement(self, stmt): ...
        
    TransactionalMyModel(TransactionModel, MyModel): pass
    '''
    queue = None
    
    def begin(self):
        self.queue = []

    def commit(self):        
        super(TransactionModel, self).begin()
        for stmt in self.queue:
            if stmt[0] is utils.Removed:
                super(TransactionModel, self).removeStatement( stmt[1] )
            else:
                super(TransactionModel, self).addStatement( stmt[0] )
        super(TransactionModel, self).commit()

        self.queue = None
        
    def rollback(self):
        self.queue = None

    def _match(self, stmt, subject = None, predicate = None):
        if subject and stmt.subject != subject:
            return False
        if predicate and stmt.predicate != predicate:
            return False
        #if object is not None and stmt.object != object:
        #    return False        
        return True
        
    def getStatements(self, subject = None, predicate = None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        statements = super(TransactionModel, self).getStatements(subject, predicate)
        if self.queue is None: #not in a transaction
            return statements

        #avoid phantom reads, etc.        
        for stmt in self.queue:
            if stmt[0] is utils.Removed:
                if self._match(stmt[1], subject, predicate):
                    statements.remove( stmt[1] )
            else:
                if self._match(stmt[0], subject, predicate):
                    statements.append( stmt[0] )
        
        statements.sort()
        return removeDupsFromSortedList(statements)

    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        if self.queue is None: #not in a transaction
            super(TransactionModel, self).addStatement( statement )
        else:
            self.queue.append( (statement,) )
        
    def removeStatement(self, statement ):
        '''removes the statement'''
        if self.queue is None: #not in a transaction
            super(TransactionModel, self).removeStatement( statement)
        else:
            self.queue.append( (utils.Removed, statement) )

class NTriplesFileModel(FtModel):
    def __init__(self, inputfile, outputpath):        
        self.path = outputpath
        if isinstance(inputfile, ( type(''), type(u'') )): #assume its a file path or URL
            memorymodel, memorydb = utils.deserializeRDF(inputfile)
        else: #assume its is a file stream of NTriples
            memorymodel, memorydb = utils.DeserializeFromN3File(inputfile)
        FtModel.__init__(self, memorymodel)

    def begin(self):
        self.model._driver.begin()

    def commit(self):
        self.model._driver.commit()
        outputfile = file(self.path, "w+", -1)
        stmts = self.model._driver._statements['default'] #get statements directly, avoid copying list
        utils.writeTriples(stmts, outputfile)
        outputfile.close()
        
    def rollback(self):
        self.model._driver.rollback()

class _IncrementalNTriplesFileModelBase(NTriplesFileModel):

    def commit(self):
        self.model._driver.commit()

        import os.path
        if os.path.exists(self.path):
            outputfile = file(self.path, "a+")
            def unmapQueue():
                for stmt in self.queue:
                    if stmt[0] is utils.Removed:
                        yield utils.Removed, self.model._unmapStatements( (stmt[1],))[0]
                    else:
                        yield self.model._unmapStatements( (stmt[0],))[0]
                    
            utils.writeTriples( unmapQueue(), outputfile)
            outputfile.close()
        else: #first time
            outputfile = file(self.path, "w+")
            stmts = self.model._driver._statements['default'] #get statements directly, avoid copying list
            utils.writeTriples(stmts, outputfile)
            outputfile.close()

class IncrementalNTriplesFileModel(TransactionModel, _IncrementalNTriplesFileModelBase): pass

def initFileModel(location, defaultModel):
    '''
    If location doesn't exist create a new model and initialize it with the statements specified in defaultModel,
    a NTriples file object
    '''    
    if os.path.exists(location):
        source = location
    else:
        source = defaultModel

    #we only support writing to a NTriples file 
    if location.endswith('.nt'):
        destination = location
    else:
        destination = os.path.splitext(location)[0] + '.nt'
        
    return IncrementalNTriplesFileModel(source, destination)

try:
    import RDF #import Redland RDF
    
    def node2String(node):
        if node.is_blank():
            return BNODE_BASE + node.blank_identifier
        elif node.is_literal():
            return unicode(node.literal_value['string'])
        else:
            return unicode(node.uri)

    def URI2node(uri): 
        if uri.startswith(BNODE_BASE):
            return RDF.Node(blank=uri[BNODE_BASE_LEN:])
        else:
            return RDF.Node(uri_string=uri)

    def statement2Redland(statement):
        if statement.objectType == OBJECT_TYPE_LITERAL:            
            object = RDF.Node(literal=statement.object)            
        else:
            object = URI2node(statement.object)
        return RDF.Statement(URI2node(statement.subject), URI2node(statement.predicate), object)

    def redland2Statements(redlandStatements):
        '''RDF.Statement to Statement'''
        for stmt in redlandStatements:
            if stmt.object.is_literal():
                objectType = OBJECT_TYPE_LITERAL
            else:
                objectType = OBJECT_TYPE_RESOURCE            
            yield Statement(node2String(stmt.subject), node2String(stmt.predicate),
                            node2String(stmt.object), objectType=objectType)
        
    class RedlandModel(Model):
        '''
        wrapper around Redland's RDF.Model
        '''
        def __init__(self, redlandModel):
            self.model = redlandModel

        def begin(self):
            pass

        def commit(self):
            self.model.sync()

        def rollback(self):
            pass
            
        def getResources(self):
            '''All resources referenced in the model, include resources that only appear as objects in a triple.
               Returns a list of resources are sorted by their URI reference
            '''        
            def f(l, stmt):
                l.append(stmt.subject)
                if stmt.objectType == OBJECT_TYPE_RESOURCE:
                    l.append(stmt.object)
                return l
            
            stmts = redland2Statements( self.model.find_statements(RDF.Statement()) )
            resources = reduce(f, stmts, [])
            resources.sort()
            return removeDupsFromSortedList(resources)        
            
        def getStatements(self, subject = None, predicate = None):
            ''' Return all the statements in the model that match the given arguments.
            Any combination of subject and predicate can be None, and any None slot is
            treated as a wildcard that matches any value in the model.'''
            if subject:
                subject = URI2node(subject)
            if predicate:
                predicate = URI2node(predicate)                
            statements = list( redland2Statements( self.model.find_statements(RDF.Statement(subject, predicate)) ) )
            statements.sort()
            return removeDupsFromSortedList(statements)
                         
        def addStatement(self, statement ):
            '''add the specified statement to the model'''            
            self.model.add_statement( statement2Redland(statement) )

        def removeStatement(self, statement ):
            '''removes the statement'''
            self.model.remove_statement( statement2Redland(statement))

    class TransactionalRedlandModel(TransactionModel, RedlandModel): pass

    def initRedlandHashBdbModel(location, defaultModel):
        if os.path.exists(location + '-sp2o.db'):
            storage = RDF.HashStorage(location, options="hash-type='bdb'")
            model = RDF.Model(storage)
        else:
            # Create a new BDB store
            storage = RDF.HashStorage(location, options="new='yes',hash-type='bdb'")
            model = RDF.Model(storage)
            
            makebNode = lambda bNode: BNODE_BASE + bNode
            for stmt in utils.parseTriples(defaultModel,  makebNode):
                model.add_statement( statement2Redland(
                    Statement(stmt[0], stmt[1], stmt[2], '', '', stmt[3]) ) )            
            #ntriples = defaultModel.read()            
            #parser=RDF.Parser(name="ntriples", mime_type="text/plain")                        
            #parser.parse_string_into_model(model, ntriples, base_uri=RDF.Uri("file:"))
            model.sync()
        return TransactionalRedlandModel(model)
    
except ImportError:
    log.debug("Redland not installed")
        
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
                return (uri, '')
    if not uri[index+1:].replace('_', '0').replace('.', '0').replace('-', '0').isalnum():
        return (uri, '')
    local = uri[index+1:]
    if local and not local.lstrip('_'): #must be all '_'s
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
    if not local.lstrip('_'): #must be all '_'s
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

def applyXUpdate(rdfdom, xup = None, vars = None, extFunctionMap = None, uri='file:'):
    """
    Executes the XUpdate script on the given RxPathDOM.  The XUpdate document is either
    contained as a string in the xup parameter or as an URL specified in the uri parameter.
    """
    #from Ft.Xml import XUpdate #buggy -- use our patched version
    from rx import XUpdate
    xureader = XUpdate.Reader()
    processor = XUpdate.Processor()
    if xup is None:
        xupInput = InputSource.DefaultFactory.fromUri(uri)
    else:
        xupInput = InputSource.DefaultFactory.fromString(xup, uri) 
    xupdate = xureader.fromSrc(xupInput)
    if extFunctionMap:
        extFunctionMap.update(BuiltInExtFunctions)
    else:
        extFunctionMap = BuiltInExtFunctions    
    processor.execute(rdfdom, xupdate, vars, extFunctionMap = extFunctionMap)

def evalXPath(xpath, context, expCache=None, queryCache=None):
    log.debug(xpath)

    context.functions.update(BuiltInExtFunctions)
    
    if expCache:
       compExpr = expCache.getValue(xpath) #todo: nsMap should be part of the key -- until then clear the cache if you change that!
    else:
        compExpr = XPath.Compile(xpath)
    
    if queryCache:
        res = queryCache.getValue(compExpr, context)         
    else:
        res = compExpr.evaluate(context)
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
    if nodeset is None:
        nodeset = [ context.node ]
        
    if nodeset and nodeset[0].nodeType == Node.ELEMENT_NODE and nodeset[0].parentNode\
       and isResource(context, nodeset[0].parentNode):
        if nodeset[1:]:
            return isPredicate(context, nodeset[1:])
        else:
            return True #we made it to the end 
    else:
        return False

def isResource(context, nodeset=None):
    if nodeset is None:
        nodeset = [ context.node ]
        
    if nodeset and nodeset[0].nodeType == Node.ELEMENT_NODE\
       and nodeset[0].getAttributeNS(RDF_MS_BASE, 'about'):#or instead use: and not isPredicate(context, nodeset[0])
        if nodeset[1:]:
            return isResource(context, nodeset[1:])
        else:
            return True #we made it to the end 
    else:
        return False

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
    return [getResourceFromNode(node) for node in nodeset if node.nodeType in [Node.ELEMENT_NODE, Node.TEXT_NODE, Node.ATTRIBUTE_NODE] ]

RFDOM_XPATH_EXT_NS = None #todo: put these in an extension namespace?
BuiltInExtFunctions = {
(RFDOM_XPATH_EXT_NS, 'isPredicate'): isPredicate,
(RFDOM_XPATH_EXT_NS, 'isResource'): isResource,
(RFDOM_XPATH_EXT_NS, 'getResource'): getResource,
}

##########################################################################
## "patches" to Ft.XPath
##########################################################################

#fix bug in Ft.Rdf.Statement:
def cmpStatements(self,other):
    if isinstance(other,Statement):        
        return cmp( (self.subject,self.predicate,self.object, self.objectType, self.scope),
                    (other.subject,other.predicate, other.object, self.objectType, other.scope))
    import traceback
    traceback.print_stack(file=sys.stderr)
    print >>sys.stderr, 'comparing??????', self, other
    return cmp(str(self),str(other)) #should this be here?

Statement.__cmp__ = cmpStatements

from xml.dom import Node

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
            
            if nodeTest(context, child, self.principalType):
                nodeSet.append(child)
            elif childNodeFunc:
                 continue#we're a RxPath dom and the nodetest didn't match, don't examine the node's descendants
             
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
    elif isinstance(parsed, (XPath.ParsedRelativeLocationPath.ParsedRelativeLocationPath, XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath)):
        return findNextStep(parsed._left)
    else:
        return None

def isChildAxisSpecifier(step):    
    axis = getattr(step, '_axis', None)
    if isinstance(axis, XPath.ParsedChildAxisSpecifier):
        return True
    else:
        return False
            
def _descendants(self, context, nodeset, startNode=None):
    startNode = startNode or context.node
    childNodeFunc = getattr(context.node, 'getSafeChildNodes', None)
    if childNodeFunc:
        childNodes = childNodeFunc(startNode)
    else:
        childNodes = context.node.childNodes
    
    for child in childNodes:
        context.node = child

        #skip for now: nodetest is always node() since we're an ParsedAbbreviatedAbsoluteLocationPath
        #if childNodeFunc and isPredictate(context):
        #    step = findNextStep(self._rel)
        #    if isChildAxisSpecifier(step):
        #       nodetest = getattr(step, '_nodeTest', XPathParsedNodeTest.NodeTest())
        #       if not nodetest.match(context, context.node, ??):
        #           continue
        #        results = self._rel.select(context)
                 # Ensure no duplicates
        #        nodeset.extend(filter(lambda n, s=nodeset: n not in s, results))
        
        results = self._rel.select(context)
        # Ensure no duplicates
        nodeset.extend(filter(lambda n, s=nodeset: n not in s, results))
                    
        if child.nodeType == Node.ELEMENT_NODE:
            self._descendants(context, nodeset, startNode)
XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath._descendants = _descendants

#patch XPath.ParsedNodeTest.QualifiedNameTest:
_QualifiedNameTest_oldMatch = XPath.ParsedNodeTest.QualifiedNameTest.match.im_func
def _QualifiedNameTest_match(self, context, node, principalType=Node.ELEMENT_NODE):
    if not hasattr(node, 'matchName'):
        return _QualifiedNameTest_oldMatch(self, context, node, principalType)
    else:
        try:
            return node.nodeType == principalType and node.matchName(context.processorNss[self._prefix], self._localName)
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

#patch a new GenerateId that uses hash(node) instead of id(node)
from Ft.Xml.Xslt import XsltRuntimeException, Error,XsltFunctions
def GenerateId(context, nodeSet=None):
    """
    Implementation of generate-id().

    Returns a string that uniquely identifies the node in the argument
    node-set that is first in document order. If the argument node-set
    is empty, the empty string is returned. If the argument is omitted,
    it defaults to the context node.
    """
    if nodeSet is not None and type(nodeSet) != type([]):
        raise XsltRuntimeException(Error.WRONG_ARGUMENT_TYPE,
                                   context.currentInstruction)
    if nodeSet is None:
        # If no argument is given, use the context node
        return u'id' + `hash(context.node)` #hash instead of id
    elif nodeSet:
        # first node in nodeset
        node = XPath.Util.SortDocOrder(context, nodeSet)[0]
        return u'id' + `hash(node)`
    else:
        # When the nodeset is empty, return an empty string
        return u''
XsltFunctions.GenerateId = GenerateId

#make XPath.ParsedExpr.FunctionCall*.evaluate have no side effects so we can cache them
def _FunctionCallEvaluate(self, context, oldFunc):
    self._func = None
    return oldFunc(self, context)
    
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
