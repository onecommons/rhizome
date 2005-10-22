'''
    An implementation of RxPath.
    Loads and saves the DOM to a RDF model.

    See RxPathDOM.py for more notes and todos.

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
'''
from __future__ import generators

from rx import utils
from Ft.Lib.boolean import false as XFalse, true as XTrue, bool as Xbool
from Ft.Rdf import OBJECT_TYPE_RESOURCE, OBJECT_TYPE_LITERAL, Util
from Ft.Rdf import BNODE_BASE, BNODE_BASE_LEN,RDF_MS_BASE,RDF_SCHEMA_BASE
import Ft.Rdf.Model
from Ft.Xml.XPath.Conversions import StringValue, NumberValue
from Ft.Xml import XPath, InputSource, SplitQName, EMPTY_NAMESPACE
from Ft.Rdf.Statement import Statement
from rx.utils import generateBnode
from rx.RxPathSchema import *
import os.path, sys, StringIO, traceback

from rx import logging #for python 2.2 compatibility
log = logging.getLogger("RxPath")

#from Ft.Rdf import RDF_MS_BASE -- for some reason we need this to be unicode for the xslt engine:
RDF_MS_BASE=u'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
OBJECT_TYPE_XMLLITERAL='http://www.w3.org/1999/02/22-rdf-syntax-ns#XMLLiteral'

#If true, the RDFLib RDF/XML parser will be used instead of the broken 4Suite one
#this is set to True if RDFLib is installed 
useRDFLibParser = False

def createDOM(model, nsRevMap = None, modelUri=None, schemaClass = RDFSSchema):
    from rx import RxPathDom
    return RxPathDom.Document(model, nsRevMap,modelUri,schemaClass)

class Model(object):
    ### Transactional Interface ###

    def commit(self, **kw):
        return

    def rollback(self):
        return

    ### Operations ###
    
    def getResources(self):
        '''All resources referenced in the model, include resources that only appear as objects in a triple.
           Returns a list of resources are sorted by their URI reference
        '''
        
    def getStatements(self, subject = None, predicate = None, object=None, objecttype=None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject, predicate or object can be None, and any None slot is
        treated as a wildcard that matches any value in the model.
        If objectype is specified, it should be one of:
        OBJECT_TYPE_RESOURCE, OBJECT_TYPE_LITERAL, an ISO language code or an URL representing the datatype.
        '''
        assert object is not None or objecttype
        
    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        
    def removeStatement(self, statement ):
        '''removes the statement'''

    reifiedIDs = None
    def findStatementID(self, stmt):        
        if self.reifiedIDs is None:
           self.reifiedIDs = getReifiedStatements(self.getStatements())
        triple = (stmt.subject, stmt.predicate, stmt.object, stmt.objectType)
        return self.reifiedIDs.get(triple)
   
def getReifiedStatements(stmts):
    '''
    Find statements created by reification and return a list of the statements being reified 
    '''
    reifyPreds = { RDF_MS_BASE+'subject':0, RDF_MS_BASE+'predicate':1, RDF_MS_BASE+'object':2}
    reifiedStmts = {}
    for stmt in stmts:
        index = reifyPreds.get(stmt.predicate)
        if index is not None:
            reifiedStmts.setdefault(stmt.subject, ['','',None, ''])[index] = stmt.object
            if index == 2:
                reifiedStmts[stmt.subject][3] = stmt.objectType
    reifiedDict = {}
    #make a new dict, with the triple as key, while ignoring any incomplete statements
    for stmtUri, triple in reifiedStmts.items():
        if triple[0] and triple[1] and triple[2] is not None:
            #reifiedStmt = Statement(triple[0], triple[1], triple[2],
            #            objectType=triple[3], statementUri=stmtUri)
            reifiedDict[tuple(triple)] = stmtUri
        #else: log.warning('incomplete reified statement')
    return reifiedDict

def removeDupStatementsFromSortedList(aList, pred=None):       
    def removeDups(x, y):
        if pred and not pred(y):
            return x
        if not x or x[-1] != y:            
            x.append(y)
        else: #x[-1] == y but Statement.__cmp__ doesn't consider the reified URI
            #its a duplicate statement but second one has a reified URI
            if x and y.uri: #the reified statement URI
                x[-1].uri = y.uri #note: we only support one reification per statement
        return x
    return reduce(removeDups, aList, [])

def getResourcesFromStatements(stmts):
    '''
    given a lists of statements return all the resources that appear as either or subject or object,
    except for non-head list resources.
    '''
    resourceDict = {}
    lists = {}
    predicates = {}
    for stmt in stmts:
        if stmt.predicate == RDF_MS_BASE+'rest':
            lists[stmt.object] = 0 #mark this as not the head 
            continue #ignore these       
        elif stmt.object == RDF_MS_BASE+'List' and stmt.predicate == RDF_MS_BASE+'type':
            if not lists.has_key(stmt.subject):
                lists[stmt.subject] = 1
        elif stmt.predicate != RDF_MS_BASE+'first':
            #we only add list resources that are the object of another statement
            resourceDict[stmt.subject] = 1
        if stmt.objectType == OBJECT_TYPE_RESOURCE:
            resourceDict[stmt.object] = 1
        predicates[stmt.predicate] = 1
    assert not resourceDict.has_key(''), resourceDict.get('')
    resourceDict.update( predicates )
    #todo: get rid of this hack!:    
    for x in RDFSSchema.requiredProperties + RDFSSchema.requiredClasses:
        resourceDict[x] = 1
    #todo: a more complete approach would be to call _baseSchema.findStatements()
    #on each resource and add any new resources in the resulting statements
    resources = resourceDict.keys()    
    for uri, isHead in lists.items():
        if isHead:
            resources.append(uri)
    
    resources.sort()
    return resources
    
class FtModel(Model):
    '''
    wrapper around 4Suite's Ft.Rdf.Model
    '''
    def __init__(self, ftmodel):
        self.model = ftmodel

    def _beginIfNecessary(self):
        if not getattr(self.model._driver, '_db', None):
            #all the 4Suite driver classes that require begin() set a _db attribute
            #and for the ones that don't, begin() is a no-op
            self.model._driver.begin()

    def commit(self, **kw):
        self.model._driver.commit()

    def rollback(self):
        self.model._driver.rollback()        
    
    def getResources(self):
        '''All resources referenced in the model, include resources that only appear as objects in a triple.
           Returns a list of resources are sorted by their URI reference
        '''
        self._beginIfNecessary()
        return getResourcesFromStatements(self.model.complete(None, None, None))
        
    def getStatements(self, subject = None, predicate = None, object = None, objecttype=None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        self._beginIfNecessary()        
        statements = self.model.complete(subject, predicate, object)        
        statements.sort()
        #4Suite doesn't support selecting based on objectype so filter here
        def matchType(stmt):
            return stmt.objectType == objecttype
        pred = objecttype and matchType or None
        return removeDupStatementsFromSortedList(statements, pred)
                     
    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        self._beginIfNecessary()
        self.model.add( statement )

    def removeStatement(self, statement ):
        '''removes the statement'''
        self._beginIfNecessary()
        self.model.remove( statement)
        
class MultiModel(Model):
    '''
    This allows one writable model and multiple read-only models.
    All mutable methods will be called on the writeable model only.
    Useful for allowing static information in the model, for example representations of the application.    
    '''
    def __init__(self, writableModel, *readonlyModels):
        self.models = (writableModel,) + readonlyModels        

    def commit(self, **kw):
        self.models[0].commit(**kw)

    def rollback(self):
        self.models[0].rollback()        

    def getResources(self):
        resources = []
        for model in self.models:
            resources += model.getResources()
        resources.sort()
        return utils.removeDupsFromSortedList(resources)
                    
    def getStatements(self, subject = None, predicate = None, object = None, objecttype=None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        statements = []
        for model in self.models:
            statements += model.getStatements(subject, predicate,object, objecttype)
        statements.sort()
        return removeDupStatementsFromSortedList(statements)
                     
    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        self.models[0].addStatement( statement )
        
    def removeStatement(self, statement ):
        '''removes the statement'''
        self.models[0].removeStatement( statement)

class MirrorModel(Model):
    '''
    This mirrors updates to multiple models
    Updates are propagated to all models
    Reading is only done from the first model (it assumes all models are identical)
    '''
    def __init__(self, *models):
        self.models = models

    def commit(self, **kw):
        for model in self.models:
            model.commit(**kw)

    def rollback(self):
        for model in self.models:
            model.rollback()

    def getResources(self):
        return self.models[0].getResources()
                            
    def getStatements(self, subject = None, predicate = None, object = None, objecttype=None):
        return self.models[0].getStatements(subject, predicate, object, objecttype)
                     
    def addStatement(self, statement ):
        for model in self.models:
            model.addStatement( statement )
        
    def removeStatement(self, statement ):
        for model in self.models:
            model.removeStatement( statement )
                
class TransactionModel(object):
    '''
    Provides transaction functionality for models that don't already have that.
    This class typically needs to be most derived; for example:
    
    MyModel(Model):
        def __init__(self): ...
        
        def addStatement(self, stmt): ...
        
    TransactionalMyModel(TransactionModel, MyModel): pass
    '''
    queue = None
    
    def commit(self, **kw):        
        if not self.queue:
            return     
        for stmt in self.queue:
            if stmt[0] is utils.Removed:
                super(TransactionModel, self).removeStatement( stmt[1] )
            else:
                super(TransactionModel, self).addStatement( stmt[0] )
        super(TransactionModel, self).commit(**kw)

        self.queue = []
        
    def rollback(self):
        #todo: if self.autocommit: raise exception
        self.queue = []

    def _match(self, stmt, subject = None, predicate = None, object = None, objecttype=None):
        if subject and stmt.subject != subject:
            return False
        if predicate and stmt.predicate != predicate:
            return False
        if object is not None and stmt.object != object:
            return False
        #todo: handle objecttype
        return True
        
    def getStatements(self, subject = None, predicate = None, object = None, objecttype=None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        statements = super(TransactionModel, self).getStatements(subject, predicate, object, objecttype)
        if not self.queue: 
            return statements

        #avoid phantom reads, etc.        
        for stmt in self.queue:
            if stmt[0] is utils.Removed:
                if self._match(stmt[1], subject, predicate, object, objecttype):
                    statements.remove( stmt[1] )
            else:
                if self._match(stmt[0], subject, predicate, object, objecttype):
                    statements.append( stmt[0] )
        
        statements.sort()
        return removeDupStatementsFromSortedList(statements)

    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        if self.queue is None: 
            self.queue = []    
        self.queue.append( (statement,) )
        
    def removeStatement(self, statement ):
        '''removes the statement'''
        if self.queue is None: 
            self.queue = []    
        self.queue.append( (utils.Removed, statement) )

class NTriplesFileModel(FtModel):
    def __init__(self, inputfile, outputpath):        
        self.path = outputpath
        if isinstance(inputfile, ( type(''), type(u'') )): #assume its a file path or URL
            memorymodel, memorydb = utils.deserializeRDF(inputfile)
        else: #assume its is a file stream of NTriples
            memorymodel, memorydb = utils.DeserializeFromN3File(inputfile)
        FtModel.__init__(self, memorymodel)

    def commit(self, **kw):
        self.model._driver.commit()
        outputfile = file(self.path, "w+", -1)
        stmts = self.model._driver._statements['default'] #get statements directly, avoid copying list
        utils.writeTriples(stmts, outputfile)
        outputfile.close()
        
class _IncrementalNTriplesFileModelBase(object):
    '''
    Incremental save changes to an NTriples "transaction log"
    Use in a class hierarchy for Model where self has a path attribute
    and TransactionModel is preceeds this in the MRO.
    '''
    #just so we can call _unmapStatements
    dummyFtModel = Ft.Rdf.Model.Model(None)
    
    def commit(self, **kw):                
        import os.path, time
        if os.path.exists(self.path):
            #self.model._driver.commit() #memory based stores don't need this
            outputfile = file(self.path, "a+")
            def unmapQueue():
                for stmt in self.queue:
                    if stmt[0] is utils.Removed:
                        yield utils.Removed, self.dummyFtModel._unmapStatements( (stmt[1],))[0]
                    else:
                        yield self.dummyFtModel._unmapStatements( (stmt[0],))[0]
                        
            comment = kw.get('source','')
            if isinstance(comment, (list, tuple)):                
                comment = comment and comment[0] or ''
            if getattr(comment, 'getAttributeNS', None):
                comment = comment.getAttributeNS(RDF_MS_BASE, 'about')
                
            outputfile.write("#begin " + comment + "\n")            
            utils.writeTriples( unmapQueue(), outputfile)            
            outputfile.write("#end " + time.asctime() + ' ' + comment + "\n")
            outputfile.close()
        else: #first time
            super(_IncrementalNTriplesFileModelBase, self).commit()

class IncrementalNTriplesFileModel(TransactionModel, _IncrementalNTriplesFileModelBase, NTriplesFileModel): pass

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
            literal = node.literal_value['string']
            if not isinstance(literal, unicode):
                return unicode(literal, 'utf8')
            else:
                return literal
        else:
            return unicode(node.uri)

    def URI2node(uri): 
        if uri.startswith(BNODE_BASE):
            return RDF.Node(blank=uri[BNODE_BASE_LEN:])
        else:
            return RDF.Node(uri_string=uri)

    def object2node(object, objectType):
        if objectType == OBJECT_TYPE_RESOURCE:            
            return URI2node(object)
        else:
            kwargs = { 'literal':object}
            if objectType.find(':') > -1:
                kwargs['datatype'] = objectType
            elif len(objectType) > 1: #must be a language id
                kwargs['language'] = objectType
            return RDF.Node(**kwargs)            
        
    def statement2Redland(statement):
        object = object2node(statement.object, statement.objectType)
        return RDF.Statement(URI2node(statement.subject), URI2node(statement.predicate), object)

    def redland2Statements(redlandStatements):
        '''RDF.Statement to Statement'''
        for stmt in redlandStatements:
            if stmt.object.is_literal():                
                objectType = stmt.object.literal_value.get('language') or \
                             stmt.object.literal_value.get('datatype') or OBJECT_TYPE_LITERAL
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

        def commit(self):
            self.model.sync()

        def rollback(self):
            pass
            
        def getResources(self):
            '''All resources referenced in the model, include resources that only appear as objects in a triple.
               Returns a list of resources are sorted by their URI reference
            '''                    
            stmts = redland2Statements( self.model.find_statements(RDF.Statement()) )
            return getResourcesFromStatements(stmts)
        
        def getStatements(self, subject = None, predicate = None, object = None, objecttype=None):
            ''' Return all the statements in the model that match the given arguments.
            Any combination of subject and predicate can be None, and any None slot is
            treated as a wildcard that matches any value in the model.'''
            if subject:
                subject = URI2node(subject)
            if predicate:
                predicate = URI2node(predicate)
            if object is not None:
                object = object2node(object, objectType)
            statements = list( redland2Statements( self.model.find_statements(
                                RDF.Statement(subject, predicate, object)) ) )
            statements.sort()
            return removeDupStatementsFromSortedList(statements)
                         
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

try:
    import rdflib
    from rdflib.Literal import Literal
    from rdflib.BNode import BNode
    from rdflib.URIRef import URIRef
    
    useRDFLibParser = True
    
    def statement2rdflib(statement):
        if statement.objectType == OBJECT_TYPE_RESOURCE:            
            object = RDFLibModel.URI2node(statement.object)
        else:
            kwargs = {}
            if statement.objectType.find(':') > -1:
                kwargs['datatype'] = statement.objectType
            elif len(statement.objectType) > 1: #must be a language id
                kwargs['lang'] = statement.objectType
            object = Literal(statement.object, **kwargs)            
        return (RDFLibModel.URI2node(statement.subject), RDFLibModel.URI2node(statement.predicate), object)

    def rdflib2Statements(rdflibStatements):
        '''RDFLib triple to Statement'''
        for (subject, predicate, object) in rdflibStatements:
            if isinstance(object, Literal):                
                objectType = object.language or object.datatype or OBJECT_TYPE_LITERAL
            else:
                objectType = OBJECT_TYPE_RESOURCE            
            yield Statement(RDFLibModel.node2String(subject), RDFLibModel.node2String(predicate),
                            RDFLibModel.node2String(object), objectType=objectType)

    class RDFLibModel(Model):
        '''
        wrapper around rdflib's TripleStore
        '''

        def node2String(node):
            if isinstance(node, BNode):
                return BNODE_BASE + unicode(node[2:])
            else:
                return unicode(node)
        node2String = staticmethod(node2String)
        
        def URI2node(uri): 
            if uri.startswith(BNODE_BASE):
                return BNode('_:'+uri[BNODE_BASE_LEN:])
            else:
                return URIRef(uri)
        URI2node = staticmethod(URI2node)

        def object2node(object, objectType):
            if objectType == OBJECT_TYPE_RESOURCE:            
                return URI2node(object)
            else:
                kwargs = {}
                if objectType.find(':') > -1:
                    kwargs['datatype'] = objectType
                elif len(objectType) > 1: #must be a language id
                    kwargs['lang'] = objectType
                return Literal(object, **kwargs)                                
        object2node = staticmethod(object2node)
        
        def __init__(self, tripleStore):
            self.model = tripleStore

        def commit(self):
            pass

        def rollback(self):
            pass
            
        def getResources(self):
            '''All resources referenced in the model, include resources that only appear as objects in a triple.
               Returns a list of resources are sorted by their URI reference
            '''                    
            stmts = rdflib2Statements( self.model.triples( (None, None, None)) ) 
            return getResourcesFromStatements(stmts)
        
        def getStatements(self, subject = None, predicate = None, object = None, objecttype=None):
            ''' Return all the statements in the model that match the given arguments.
            Any combination of subject and predicate can be None, and any None slot is
            treated as a wildcard that matches any value in the model.'''
            if subject:
                subject = self.URI2node(subject)
            if predicate:
                predicate = self.URI2node(predicate)
            if object is not None:
                object = object2node(object, objectType)
            statements = list( rdflib2Statements( self.model.triples((subject, predicate, object)) ) )
            statements.sort()
            return removeDupStatementsFromSortedList(statements)
                         
        def addStatement(self, statement ):
            '''add the specified statement to the model'''            
            self.model.add( statement2rdflib(statement) )

        def removeStatement(self, statement ):
            '''removes the statement'''
            self.model.remove( statement2rdflib(statement))

    class RDFLibFileModel(RDFLibModel):
        def __init__(self, inputfile, outputpath, format="xml"):        
            self.path = outputpath
            self.format = format

            from rdflib.TripleStore import TripleStore                                    
            RDFLibModel.__init__(self, TripleStore())
            
            if isinstance(inputfile, ( type(''), type(u'') )): #assume its a file path or URL                
                self.model.load(inputfile,format) #model is the tripleStore                            
            else: #assume its is a file stream of NTriples
                makebNode = lambda bNode: BNODE_BASE + bNode
                for stmt in utils.parseTriples(inputfile,makebNode):
                    self.addStatement( Statement(stmt[0], stmt[1], stmt[2], '', '', stmt[3]) ) 
    
        def commit(self):
            self.model.save(self.path, self.format)

    class TransactionalRDFLibFileModel(TransactionModel, RDFLibFileModel): pass
    
    def initRDFLibModel(location, defaultModel, format="xml"):
        '''
        If location doesn't exist create a new model and initialize it with the statements specified in defaultModel,
        which should be a NTriples file object. Whenever changes to the model are committed, location will be updated.
        '''        
        if os.path.exists(location):
            source = location
        else:
            source = defaultModel
            
        return TransactionalRDFLibFileModel(source, location, format)
    
except ImportError:
    log.debug("rdflib not installed")


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

def evalXPath(xpath, context, expCache=None, queryCache=None):
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

def addStatements(rdfDom, stmts):
    '''
    Update the DOM (and so the underlying model) with the given list of statements.
    If the statements include RDF list or container statements, it must include all items of the list
    '''
    #we have this complete list requirement because otherwise we'd have to figure out
    #the head list resource and update its children and possible also do this for every nested list 
    #resource not included in the statements (if the model exposed them)
    listLinks = {}
    listItems = {}
    tails = []
    containerItems = {}
    for stmt in stmts:
        #print 'stmt', stmt
        if stmt.predicate == RDF_MS_BASE+'first':
            listItems[stmt.subject] = stmt
            #we handle these below
        elif stmt.predicate == RDF_MS_BASE+'rest':                
            if stmt.object == RDF_MS_BASE+'nil':
                tails.append(stmt.subject)
            else:
                listLinks[stmt.object] = stmt.subject
        elif stmt.predicate.startswith(RDF_MS_BASE+'_'): #rdf:_n
            containerItems[(stmt.subject, int(stmt.predicate[len(RDF_MS_BASE)+1:]) )] = stmt
        else:
            subject = rdfDom.findSubject(stmt.subject) or rdfDom.addResource(stmt.subject)
            subject.addStatement(stmt)

    #for each list encountered
    for tail in tails:            
        orderedItems = [ listItems[tail] ]            
        #build the list from last to first
        head = tail
        while listLinks.has_key(head):
            head = listLinks[head]
            orderedItems.append(listItems[head])            
        orderedItems.reverse()
        for stmt in orderedItems:
            listid = stmt.subject
            stmt.subject = head #set the subject to be the head of the list
            subject = rdfDom.findSubject(stmt.subject) or rdfDom.addResource(stmt.subject)
            subject.addStatement(stmt, listid)
        
    #now add any container statements in the correct order
    containerKeys = containerItems.keys()
    containerKeys.sort()
    for key in containerKeys:
        stmt = containerItems[key]
        listid = stmt.predicate
        head = stmt.subject
        stmt.predicate = RDF_SCHEMA_BASE+u'member'
        subject = rdfDom.findSubject(stmt.subject) or rdfDom.addResource(stmt.subject)
        subject.addStatement(stmt, listid)

def diffResources(sourceDom, resourceNodes):
    ''' Given a list of Subject nodes from another RxPath DOM, compare
    them with the resources in the source DOM. This assumes that the
    each Subject node contains all the statements it is the subject
    of.

    Returns the tuple (Subject or Predicate nodes to add list, Subject
    or Predicate nodes to remove list, Re-ordered resource dictionary)
    where Reordered is a dictionary whose keys are RDF list or
    collection Subject nodes from the source DOM that have been
    modified or reordered and whose values is the tuple (added node
    list, removed node list) containing the list item Predicates nodes
    added or removed.  Note that a compoundresource could be
    re-ordered but have no added or removed items and so the lists
    will be empty.
    
    This diff routine punts on blank node equivalency; this means bNode
    labels must match for the statements to match. The exception is
    RDF lists and containers -- in this case the bNode label or exact
    ordinal value of the "rdf:_n" property is ignored -- only the
    order is compared.  '''
    removals = []
    additions = []
    reordered = {}
    for resourceNode in resourceNodes:
        currentNode = sourceDom.findSubject(resourceNode.uri)
        if currentNode: 
            isCompound = currentNode.isCompound()
            isNewCompound = resourceNode.isCompound()
            if isNewCompound != isCompound:
                #one's a compound resource and the other isn't (or they're different types of compound resource)
                if isNewCompound and isCompound and isCompound != \
                    RDF_MS_BASE + 'List' and isNewCompound != RDF_MS_BASE + 'List':
                    #we're switching from one type of container (Seq, Alt, Bag) to another
                    #so we just need to add and remove the type statements -- that will happen below
                    diffResource = True
                else:
                    #remove the previous resource
                    removals.append(currentNode) 
                    #and add the resource's current statements
                    #we add all the its predicates instead just adding the
                    #resource node because it isn't a new resource
                    for predicate in resourceNode.childNodes:
                        additions.append( predicate) 
                    
                    diffResource = False
            else:
                diffResource = True
        else:
            diffResource = False
            
        if diffResource:
            def update(currentChildren, resourceChildren, added, removed):
                changed = False
                for tag, alo, ahi, blo, bhi in opcodes:#to turn a into b
                    if tag in ['replace', 'delete']:
                        changed = True
                        for currentPredicate in currentChildren[alo:ahi]:
                            #if we're a list check that the item hasn't just been reordered, not removed
                            if not isCompound or \
                                toListItem(currentPredicate) not in resourceNodeObjects:
                                    removed.append( currentPredicate)
                    if tag in ['replace','insert']:
                        changed = True
                        for newPredicate in resourceChildren[blo:bhi]:
                            #if we're a list check that the item hasn't just been reordered, not removed
                            if not isCompound or \
                                toListItem(newPredicate) not in currentNodeObjects:                            
                                    added.append( newPredicate )                    
                    #the only other valid value for tag is 'equal'
                return changed
            
            if isCompound:
                #to handle non-membership statements we split the childNode lists
                #and handle each separately (we can do that the RxPath spec says all non-membership statements will come first)
                i = 0
                for p in currentNode.childNodes:
                    if p.stmt.predicate in [RDF_MS_BASE + 'first', RDF_SCHEMA_BASE + 'member']:
                        break
                    i+=1
                currentChildren = currentNode.childNodes[:i]
                j = 0
                for p in resourceNode.childNodes:
                    if p.stmt.predicate in [RDF_MS_BASE + 'first', RDF_SCHEMA_BASE + 'member']:
                        break
                    j+=1                
                resourceChildren = resourceNode.childNodes[:j]
                
                #if it's a list or collection we just care about the order, ignore the predicates
                import difflib
                toListItem = lambda x: (x.stmt.objectType, x.stmt.object)
                currentListNodes = currentNode.childNodes[i:]
                currentNodeObjects = map(toListItem, currentListNodes)
                resourceListNodes = resourceNode.childNodes[j:]
                resourceNodeObjects = map(toListItem, resourceListNodes)
                opcodes = difflib.SequenceMatcher(None, currentNodeObjects,
                                           resourceNodeObjects).get_opcodes()
                if opcodes:
                    #print opcodes
                    currentAdded = []
                    currentRemoved = []
                    #if the list has changed
                    if update(currentListNodes, resourceListNodes, currentAdded, currentRemoved):
                           reordered[ currentNode ] = ( currentAdded, currentRemoved )
            else:
                currentChildren = currentNode.childNodes
                resourceChildren = resourceNode.childNodes
                
            opcodes = utils.diffSortedList(currentChildren,resourceChildren,
                    lambda a,b: cmp(a.stmt, b.stmt) )
            update(currentChildren,resourceChildren,additions, removals)
        else: #new resource (add all the statements)
            additions.append(resourceNode)
    return additions, removals, reordered

def mergeDOM(sourceDom, updateDOM, resources, authorize=None):
    '''
    Performs a 2-way merge of the updateDOM into the sourceDom.
    
    Resources is a list of resource URIs originally contained in
    update DOM before it was edited. If present, this list is
    used to create a diff between those resources statements in
    the source DOM and the statements in the update DOM.

    All other statements in the update DOM are added to the source
    DOM. (Conflicting bNode labels are not re-labeled as we assume
    update DOM was orginally derived from the sourceDOM.)

    This doesn't modify the source DOM, instead it returns a pair
    of lists (Statements to add, nodes to remove) that can be used to
    update the DOM, e.g.:
    
    >>> statements, nodesToRemove = mergeDOM(sourceDom, updateDom ,resources)
    >>> for node in nodesToRemove:
    >>>    node.parentNode.removeChild(node)
    >>> addStatements(sourceDom, statements)    
    '''
    #for each of these resources compare its statements in the update dom
    #with those in the source dom and add or remove the differences    
    newNodes = []
    removeResources = []            
    resourcesToDiff = []
    for resUri in resources:
        resNode = updateDOM.findSubject(resUri)
        if resNode: #do a diff on this resource
            #print 'diff', resUri
            resourcesToDiff.append(resNode)
        else:#a resource no longer in the rxml has all their statements removed
            removeNode = sourceDom.findSubject(resUri)
            if removeNode:
                removeResources.append(removeNode)
                        
    for resNode in updateDOM.childNodes:
        #resources in the dom but not in resources just have their statements added
        if resNode.uri not in resources:                    
            if resNode.isCompound():
                #if the node is a list or container we want to compare with the list in model
                #because just adding its statements with existing list statements would mess things up
                #note: thus we must assume the list in the updateDOM is complete
                #print 'list to diff', resNode
                resourcesToDiff.append(resNode)
            else:
                sourceResNode  = sourceDom.findSubject(resNode.uri)
                if sourceResNode:
                    #not a new resource: add each statement that doesn't already exist in the sourceDOM
                    for p in resNode.childNodes:
                        if not sourceResNode.findPredicate(p.stmt):
                            newNodes.append(p)                    
                else:
                    #new resource: add the subject node
                    newNodes.append(resNode)
        else:
            assert resNode in resourcesToDiff #resource in the list will have been added above
                       
    additions, removals, reordered = diffResources(sourceDom, resourcesToDiff)

    newNodes.extend( additions )
    removeResources.extend( removals)
    if authorize:
        authorize(newNodes, removeResources, reordered)

    newStatements = reduce(lambda l, n: l.extend(n.getModelStatements()) or l, newNodes, [])
    
    #for modified lists we just remove the all container and collection resource
    #and add all its statements    
    for compoundResource in reordered.keys():
        removeResources.append(compoundResource)
        newCompoundResource = updateDOM.findSubject( compoundResource.uri)
        assert newCompoundResource
        newStatements = reduce(lambda l, p: l.extend(p.getModelStatements()) or l,
                        newCompoundResource.childNodes, newStatements)
    return newStatements, removeResources

def addDOM(sourceDom, updateDOM, authorize=None):
    ''' Add the all statements in the update RxPath DOM to the source
    RxPathDOM. If the updateDOM contains RDF lists or containers that
    already exist in sourceDOM they are replaced instead of added
    (because just adding the statements could form malformed lists or
    containers). bNode labels are renamed if they are used in the
    existing model. If you don't want to relabel conflicting bNodes
    use mergeDOM with an empty resource list.

    This doesn't modify the source DOM, instead it returns a pair
    of lists (Statements to add, nodes to remove) that can be used to
    update the DOM in the same manner as mergeDOM.
    '''
    stmts = updateDOM.model.getStatements()    
    bNodes = {}
    replacingListResources = []
    for stmt in stmts:                
        def updateStatement(attrName):
            '''if the bNode label is used in the sourceDom choose a new bNode label'''
            uri = getattr(stmt, attrName)
            if uri.startswith(BNODE_BASE):
                if bNodes.has_key(uri):
                    newbNode = bNodes[uri]
                    if newbNode:
                        setattr(stmt, attrName, newbNode)
                else: #encountered for the first time
                    if sourceDom.findSubject(uri):
                        #generate a new bNode label
                           
                        #todo: this check doesn't handle detect inner list bnodes
                        #most of the time this is ok because the whole list will get removed below
                        #but if the bNode is used by a inner list we're not removing this will lead to a bug
                        
                        #label used in the model, so we need to rename this bNode
                        newbNode = generateBnode()
                        bNodes[uri] = newbNode
                        setattr(stmt, attrName, newbNode)
                    else:
                        bNodes[uri] = None
            else:                
                if not bNodes.has_key(uri):                    
                    resNode = updateDOM.findSubject(uri)
                    if resNode and resNode.isCompound() and sourceDom.findSubject(uri):
                        #if the list or container resource appears in the source DOM we need to compare it
                        #because just adding its statements with existing list statements would mess things up
                        #note: thus we must assume the list in the updateDom is complete                         
                        replacingListResources.append(resNode)
                    bNodes[uri] = None
        updateStatement('subject')        
        if stmt.objectType == OBJECT_TYPE_RESOURCE:
            updateStatement('object')
    #todo: the updateDOM will still have the old bnode labels, which may mess up authorization
            
    additions, removals, reordered = diffResources(sourceDom,replacingListResources)
    assert [getattr(x, 'stmt') for x in additions] or not len(additions) #should be all predicate nodes

    #now filter out any statements that already exist in the source dom:
    #(note: won't match statements with bNodes since they have been renamed
    alreadyExists = []
    newStmts = []
    for stmt in stmts:
        resNode = sourceDom.findSubject(stmt.subject)
        if resNode and resNode.findPredicate(stmt):
            alreadyExists.append(stmt)
        else:
            newStmts.append(stmt)
    
    if authorize:
        #get all the predicates in the updatedom except the ones in replacingListResources        
        newResources = [x for x in updateDOM.childNodes if x not in replacingListResources]
        newPredicates = reduce(lambda l, s: l.extend(
            [p for p in s.childNodes if p.stmt not in alreadyExists]) or l,
                                       newResources, additions)
        authorize(newPredicates, removals, reordered)
        
    #return statements to add, list resource nodes to remove
    #note: additions should contained by stmts, so we don't need to return them
    return newStmts, reordered.keys() 

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
       
RFDOM_XPATH_EXT_NS = None #todo: put these in an extension namespace?
BuiltInExtFunctions = {
(RFDOM_XPATH_EXT_NS, 'is-predicate'): isPredicate,
(RFDOM_XPATH_EXT_NS, 'is-resource'): isResource,
(RFDOM_XPATH_EXT_NS, 'resource'): getResource,

(RFDOM_XPATH_EXT_NS, 'is-instance-of'): isInstanceOf,
(RFDOM_XPATH_EXT_NS, 'is-subproperty-of'): isProperty,
(RFDOM_XPATH_EXT_NS, 'is-subclass-of'): isType,

(RFDOM_XPATH_EXT_NS, 'name-from-uri'): getQNameFromURI,
(RFDOM_XPATH_EXT_NS, 'prefix-from-uri'): getPrefixFromURI,
(RFDOM_XPATH_EXT_NS, 'local-name-from-uri'): getLocalNameFromURI,
(RFDOM_XPATH_EXT_NS, 'namespace-uri-from-uri'): getNamespaceURIFromURI,
(RFDOM_XPATH_EXT_NS, 'uri'): getURIFromElement,
}

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

#fix bug in Ft.Rdf.Statement:
def cmpStatements(self,other):
    if isinstance(other,Statement):        
        return cmp( (self.subject,self.predicate,self.object, self.objectType, self.scope),
                    (other.subject,other.predicate, other.object, self.objectType, other.scope))
    return cmp(str(self),str(other)) #should this be here?

Statement.__cmp__ = cmpStatements

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
                       useNested = True)
AttributeInfo.ExpressionWrapper.evaluate = ExpressionWrapper_evaluate
