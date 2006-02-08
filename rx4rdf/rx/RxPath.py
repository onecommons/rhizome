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
from rx.RxPathSchema import *

import os.path, sys, traceback

from rx import logging #for python 2.2 compatibility
log = logging.getLogger("RxPath")

def createDOM(model, nsRevMap = None, modelUri=None, schemaClass = defaultSchemaClass):
    from rx import RxPathDom
    return RxPathDom.Document(model, nsRevMap,modelUri,schemaClass)


class Tupleset(object):
    '''
    Interface for representing a set of tuples
    '''
    
    def filter(self, conditions=None):        
        '''Returns a iterator of the tuples in the set
           where conditions is a position:value mapping
        '''

    def left_inner(self):
        return self
    
    def asBool(self):
        size = self.size()
        if size < sys.maxint:
            return bool(size)
        else:
            for row in self:
                return True
            return False

    def size(self):
        '''
        If unknown return sys.maxint
        '''
        return sys.maxint

    def __iter__(self):
        return self.filter()

    def __contains__(self, row):
        #filter for a row that matches all the columns of this row
        for test in self.filter(dict(enumerate(row))):
            if row == test:
                return True
        return False

    def update(self, rows):
        raise TypeError('Tupleset is read only')

    def append(self, row, *moreRows):
        raise TypeError('Tupleset is read only')
    
class Model(Tupleset):
    ### Transactional Interface ###

    def commit(self, **kw):
        return

    def rollback(self):
        return

    ### Tupleset interface ###

    def filter(self,conditions=None):
        kw = {}
        if conditions:
            labels = ('subject', 'predicate','object', 'objecttype','context')
            for key, value in conditions.iteritems():
                kw[labels[key] ] = value
        for stmt in self.getStatements(**kw):
            yield stmt

    def update(self, rows):
        for row in rows:
            assert len(row) == 5
            self.addStatement(row)

    def append(self, row, *moreRows):
        assert not moreRows
        assert len(row) == 5
        self.addStatement(row)

    def describe(self, out, indent=''):        
        print >>out, indent, self.__class__.__name__,hex(id(self))
        
    ### Operations ###
                
    def getResources(self, schema=None):
        '''All resources referenced in the model, include resources that only appear as objects in a triple.
           Returns a list of resources are sorted by their URI reference
        '''
        
    def getStatements(self, subject = None, predicate = None, object=None,
                      objecttype=None,context=None):
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
        '''Removes the statement. If 'scope' isn't specified, the statement
           will be removed from all contexts it appears in.
        '''

    reifiedIDs = None
    def findStatementIDs(self, stmt):        
        if self.reifiedIDs is None:
           self.reifiedIDs = getReifiedStatements(self.getStatements())
        triple = (stmt.subject, stmt.predicate, stmt.object, stmt.objectType)
        return self.reifiedIDs.get(triple)
   
def getReifiedStatements(stmts):
    '''
    Find statements created by reification and return a list of the statements being reified 
    '''
    reifyPreds = { RDF_MS_BASE+'subject':0, RDF_MS_BASE+'predicate':1, RDF_MS_BASE+'object':2}
    reifiedStmts = {} #reificationURI => (triple)
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
            reifiedDict.setdefault(tuple(triple), []).append(stmtUri)
        #else: log.warning('incomplete reified statement')
    return reifiedDict

def removeDupStatementsFromSortedList(aList, pred=None):
    def removeDups(x, y):
        if pred and not pred(y):
            return x
        if not x or x[-1] != y:            
            x.append(y)
        #else: #x[-1] == y but Statement.__cmp__ doesn't consider the reified URI
        #    #its a duplicate statement but second one has a reified URI
        #    if x and y.uri: #the reified statement URI
        #        x[-1].uri = y.uri #note: we only support one reification per statement
        return x
    return reduce(removeDups, aList, [])

def getResourcesFromStatements(stmts, schema=None):
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
    if schema:
        schema.inferResources(resourceDict, predicates, stmts)
    resources = resourceDict.keys()    
    for uri, isHead in lists.items():
        if isHead:
            resources.append(uri)
    resources.sort()
    return resources
    
class MemModel(Model):
    '''
    simple in-memory module
    '''
    def __init__(self,statements=None):
        self.by_s = {}
        self.by_p = {}
        self.by_o = {}
        self.by_c = {}
        if statements:
            for stmt in statements:
                self.addStatement(stmt)                                

    def size(self):
        return len(self.by_s)
    
    def getResources(self,schema=None):
        '''All resources referenced in the model, include resources that only appear as objects in a triple.
           Returns a list of resources are sorted by their URI reference
        '''
        return getResourcesFromStatements(self.getStatements(),schema)
        
    def getStatements(self, subject = None, predicate = None, object = None,
                      objecttype=None,context=None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        fs = subject is not None
        fp = predicate is not None
        fo = object is not None
        fot = objecttype is not None
        fc = context is not None
        
        if not fc:
            if fs:                
                stmts = self.by_s.get(subject,[])            
            elif fo:
                stmts = self.by_o.get(object, [])
            elif fp:
                stmts = self.by_p.get(predicate, [])
            else:
                #get all
                stmts = utils.flattenSeq(self.by_s.itervalues(), 1)
                #stmts = reduce(lambda l, i: l.extend(i) or l, self.by_s.values(), [])
                if fot:
                    stmts = [s for s in stmts if s.objectType == objecttype]
                else:
                    stmts = list(stmts)
                stmts.sort()
                return stmts
        else:
            by_cAnds = self.by_c[context]        
            if fs:                
                stmts = by_cAnds.get(subject,[])
            else:
                #stmts = reduce(lambda l, i: l.extend(i) or l, by_cAnds.values(), [])
                stmts = utils.flattenSeq(by_cAnds.itervalues(), 1)
                
        stmts = [s for s in stmts 
                    if not fs or s.subject == subject
                    and not fp or s.predicate == predicate
                    and not fo or s.object == object
                    and not fot or s.objectType == objecttype
                    and not fc or s.scope == context]
        stmts.sort()
        return stmts   
                     
    def addStatement(self, stmt ):
        '''add the specified statement to the model'''
        if stmt in self.by_s.get(stmt[0], []):
            return #statement already in
        self.by_s.setdefault(stmt[0], []).append(stmt)
        self.by_p.setdefault(stmt[1], []).append(stmt)
        self.by_o.setdefault(stmt[2], []).append(stmt)
        self.by_c.setdefault(stmt[4], {}).setdefault(stmt[0], []).append(stmt)
        
    def removeStatement(self, stmt ):
        '''removes the statement'''
        stmts = self.by_s.get(stmt.subject)
        if not stmts:
            return
        try:
            stmts.remove(stmt)
        except ValueError:
            return        
        self.by_p[stmt.predicate].remove(stmt)
        self.by_o[stmt.object].remove(stmt)
        try:
            self.by_c[stmt.scope][stmt.subject].remove(stmt)
        except (ValueError,KeyError):
            #this can happen since scope isn't part of the stmt's key
            for subjectDict in self.by_c.values():
                stmts = subjectDict.get(stmt.subject,[])
                try:
                    stmts.remove(stmt)
                except ValueError:
                    pass
                else:
                    return            
        
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

    def getResources(self, schema=None):
        resources = []
        changed = 0
        for model in self.models:
            moreResources = model.getResources(schema)
            if moreResources:
                changed += 1
                resources.extend(moreResources)
        if changed > 1:        
            resources.sort()
            return utils.removeDupsFromSortedList(resources)
        else:
            return resources
                    
    def getStatements(self, subject = None, predicate = None, object = None,
                      objecttype=None,context=None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        statements = []
        changed = 0
        for model in self.models:
            moreStatements = model.getStatements(subject, predicate,object,
                                              objecttype,context)
            if moreStatements:
                changed += 1
                statements.extend(moreStatements)
        if changed > 1:        
            statements.sort()
            return removeDupStatementsFromSortedList(statements)
        else:
            return statements            
                     
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

    def getResources(self, schema=None):
        return self.models[0].getResources(schema)
                            
    def getStatements(self, subject = None, predicate = None, object = None,
                      objecttype=None,context=None):
        return self.models[0].getStatements(subject, predicate, object,
                                            objecttype,context)
                     
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
    autocommit = True

    def __init__(self, *args, **kw):
        super(TransactionModel, self).__init__(*args, **kw)
        self.autocommit = False
    
    def commit(self, **kw):        
        if not self.queue:
            return     
        for stmt in self.queue:
            if stmt[0] is Removed:
                super(TransactionModel, self).removeStatement( stmt[1] )
            else:
                super(TransactionModel, self).addStatement( stmt[0] )
        super(TransactionModel, self).commit(**kw)

        self.queue = []
        
    def rollback(self):
        #todo: if self.autocommit: raise exception
        self.queue = []

    def _match(self, stmt, subject = None, predicate = None, object = None,
                                               objecttype=None,context=None):
        if subject and stmt.subject != subject:
            return False
        if predicate and stmt.predicate != predicate:
            return False
        if object is not None and stmt.object != object:
            return False
        #todo: handle objecttype
        if context is not None and stmt.scope != context:
            return False
        return True
        
    def getStatements(self, subject = None, predicate = None, object = None,
                      objecttype=None,context=None):
        ''' Return all the statements in the model that match the given arguments.
        Any combination of subject and predicate can be None, and any None slot is
        treated as a wildcard that matches any value in the model.'''
        statements = super(TransactionModel, self).getStatements(subject, predicate, object,
                                                                 objecttype,context)
        if not self.queue: 
            return statements

        #avoid phantom reads, etc.
        changed = False
        for stmt in self.queue:
            if stmt[0] is Removed:
                if self._match(stmt[1], subject, predicate, object,
                                               objecttype,context):
                    changed = True
                    if stmt[1] not in statements:
                        print stmt[1], stmt[1][0]
                        print [s for s in statements if s[0] == stmt[1][0] ]
                        print [repr(i) for i in (subject, predicate, object, objecttype,context)]
                    statements.remove( stmt[1] )
            else:
                if self._match(stmt[0], subject, predicate, object,
                                               objecttype,context):
                    changed = True
                    statements.append( stmt[0] )

        if changed:        
            statements.sort()
            return removeDupStatementsFromSortedList(statements)
        else:
            return statements

    def addStatement(self, statement ):
        '''add the specified statement to the model'''
        if self.autocommit:
            return super(TransactionModel, self).addStatement(statement)        
        if self.queue is None: 
            self.queue = []    
        self.queue.append( (statement,) )
        
    def removeStatement(self, statement ):
        '''removes the statement'''
        if self.autocommit:
            return super(TransactionModel, self).removeStatement(statement)
        if self.queue is None: 
            self.queue = []    
        self.queue.append( (Removed, statement) )

class NTriplesFileModel(MemModel):
    def __init__(self, path, defaultStatements, context=''):
        self.path, stmts, format = _loadRDFFile(path, defaultStatements,context)
        MemModel.__init__(self, stmts)    

    def commit(self, **kw):
        outputfile = file(self.path, "w+", -1)
        stmts = self.getStatements()
        writeTriples(stmts, outputfile)
        outputfile.close()
        
class _IncrementalNTriplesFileModelBase(object):
    '''
    Incremental save changes to an NTriples "transaction log"
    Use in a class hierarchy for Model where self has a path attribute
    and TransactionModel is preceeds this in the MRO.
    '''
    
    def commit(self, **kw):                
        import os.path, time
        if os.path.exists(self.path):
            outputfile = file(self.path, "a+")
            def unmapQueue():
                for stmt in self.queue:
                    if stmt[0] is Removed:
                        yield Removed, stmt[1]
                    else:
                        yield stmt[0]
                        
            comment = kw.get('source','')
            if isinstance(comment, (list, tuple)):                
                comment = comment and comment[0] or ''
            if getattr(comment, 'getAttributeNS', None):
                comment = comment.getAttributeNS(RDF_MS_BASE, 'about')
                
            outputfile.write("#begin " + comment + "\n")            
            writeTriples( unmapQueue(), outputfile)            
            outputfile.write("#end " + time.asctime() + ' ' + comment + "\n")
            outputfile.close()
        else: #first time
            super(_IncrementalNTriplesFileModelBase, self).commit()

class IncrementalNTriplesFileModel(TransactionModel, _IncrementalNTriplesFileModelBase, NTriplesFileModel): pass

def _loadRDFFile(path, defaultStatements,context=''):
    '''
    If location doesn't exist create a new model and initialize it
    with the statements specified in defaultModel
    '''
    if os.path.exists(path):
        uri = Uri.OsPathToUri(path)
        stmts = parseRDFFromURI(uri, scope=context)
    else:
        stmts = defaultStatements

    #we only support writing to a NTriples file 
    if not path.endswith('.nt'):
        base, ext = os.path.splitext(path)
        path = base + '.nt'
        if ext == '.rdf':
            format = 'rdfxml'
        else:
            format = 'unsupported'
    else:
        format = 'ntriples'
    
    return path,stmts,format

try:
    import Ft.Rdf.Model
    from Ft.Rdf.Statement import Statement as FtStatement   
    from Ft.Rdf.Drivers import Memory
    from Ft.Rdf import OBJECT_TYPE_UNKNOWN #"?"

    if not hasattr(FtStatement, 'asTuple'):
        #bug fix for pre beta1 versions of 4Suite
        def cmpStatements(self,other):
            if isinstance(other,FtStatement):        
                return cmp( (self.subject,self.predicate,self.object, self.objectType),#, self.scope),
                            (other.subject,other.predicate, other.object, other.objectType))#, other.scope))
            else:
                raise TypeError("Object being compared must be a Statement, not a %s" % type(other))
        FtStatement.__cmp__ = cmpStatements
    #todo: we (and 4Suite) doesn't consider scope, change this when we change our model

    def Ft2Statements(statements, defaultScope=''):
        for stmt in statements:
            if stmt.objectType == OBJECT_TYPE_UNKNOWN:
                objectType = OBJECT_TYPE_LITERAL
            else:
                objectType = stmt.objectType
            yield Statement(stmt.subject, stmt.predicate,  stmt.object,
                    objectType=objectType, scope=stmt.scope or defaultScope)
        
    def statement2Ft(stmt):
        return FtStatement(stmt.subject, stmt.predicate, stmt.object,
                objectType=stmt.objectType, scope=stmt.scope)
    
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
        
        def getResources(self,schema=None):
            '''All resources referenced in the model, include resources that only appear as objects in a triple.
               Returns a list of resources are sorted by their URI reference
            '''
            self._beginIfNecessary()
            return getResourcesFromStatements(self.model.complete(None, None, None),schema)
            
        def getStatements(self, subject = None, predicate = None, object = None,
                          objecttype=None,context=None):
            ''' Return all the statements in the model that match the given arguments.
            Any combination of subject and predicate can be None, and any None slot is
            treated as a wildcard that matches any value in the model.'''
            self._beginIfNecessary()        
            statements = list(Ft2Statements(
                self.model.complete(subject, predicate, object,scope=context)))
            statements.sort()
            #4Suite doesn't support selecting based on objectype so filter here
            if objecttype:
                pred = lambda stmt: stmt.objectType == objecttype
            else:
                pred = None
            return removeDupStatementsFromSortedList(statements, pred)
                         
        def addStatement(self, statement ):
            '''add the specified statement to the model'''
            self._beginIfNecessary()
            self.model.add( statement2Ft(statement) )

        def removeStatement(self, statement ):
            '''removes the statement'''
            self._beginIfNecessary()
            self.model.remove( statement2Ft(statement) )

    class NTriplesFtModel(FtModel):
        def __init__(self, path, defaultStatements, context=''):
            self.path, stmts, format = _loadRDFFile(path, defaultStatements,context)
            db = Memory.GetDb('', 'default')
            model = Ft.Rdf.Model.Model(db)
            stmts = [statement2Ft(stmt) for stmt in stmts]
            model.add(stmts)
            FtModel.__init__(self, model)    
        
        def commit(self, **kw):
            self.model._driver.commit()
            outputfile = file(self.path, "w+", -1)
            stmts = self.model._driver._statements['default'] #get statements directly, avoid copying list
            def mapStatements(stmts):
                #map 4Suite's tuples to Statements
                for stmt in stmts:                    
                    if stmt[5] == OBJECT_TYPE_UNKNOWN:
                        objectType = OBJECT_TYPE_LITERAL
                    else:
                        objectType = stmt[5]
                    yield (stmt[0], stmt[1], stmt[2], objectType, stmt[3])
            writeTriples(mapStatements(stmts), outputfile)
            outputfile.close()

    class IncrementalNTriplesFtModel(TransactionModel, _IncrementalNTriplesFileModelBase, NTriplesFtModel): pass

except ImportError:
    log.debug("4Suite RDF not installed")

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
        if isinstance(uri, unicode):
            uri = uri.encode('utf8')
        if uri.startswith(BNODE_BASE):
            return RDF.Node(blank=uri[BNODE_BASE_LEN:])
        else:
            return RDF.Node(uri_string=uri)

    def object2node(object, objectType):
        if objectType == OBJECT_TYPE_RESOURCE:            
            return URI2node(object)
        else:
            if isinstance(object, unicode):
                object = object.encode('utf8')
            if isinstance(objectType, unicode):
                objectType = objectType.encode('utf8')
                
            kwargs = { 'literal':object}
            if objectType.find(':') > -1:
                kwargs['datatype'] = objectType
            elif len(objectType) > 1: #must be a language id
                kwargs['language'] = objectType
            return RDF.Node(**kwargs)            
        
    def statement2Redland(statement):
        object = object2node(statement.object, statement.objectType)
        return RDF.Statement(URI2node(statement.subject),
                             URI2node(statement.predicate), object)

    def redland2Statements(redlandStatements, defaultScope=''):
        '''RDF.Statement to Statement'''
        for stmt in redlandStatements:
            if stmt.object.is_literal():                
                objectType = stmt.object.literal_value.get('language') or \
                             stmt.object.literal_value.get('datatype') or OBJECT_TYPE_LITERAL
            else:
                objectType = OBJECT_TYPE_RESOURCE
            yield Statement(node2String(stmt.subject), node2String(stmt.predicate),                            
                            node2String(stmt.object), objectType=objectType,
                            scope=redlandStatements.context() or defaultScope)
        
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
            
        def getResources(self, schema=None):
            '''All resources referenced in the model, include resources that only appear as objects in a triple.
               Returns a list of resources are sorted by their URI reference
            '''
            import time
            stmts = redland2Statements( self.model.find_statements(RDF.Statement()) )
            return getResourcesFromStatements(stmts,schema)
        
        def getStatements(self, subject=None, predicate=None, object=None,
                          objecttype=None,context=None):
            ''' Return all the statements in the model that match the given arguments.
            Any combination of subject and predicate can be None, and any None slot is
            treated as a wildcard that matches any value in the model.'''
            if subject:
                subject = URI2node(subject)
            if predicate:
                predicate = URI2node(predicate)
            if object is not None:
                object = object2node(object, objectType)
            redlandStmts = self.model.find_statements(
                                RDF.Statement(subject, predicate, object),
                                context=context or None)
            statements = list( redland2Statements( redlandStmts ) )
            statements.sort()
            return removeDupStatementsFromSortedList(statements)
                         
        def addStatement(self, statement ):
            '''add the specified statement to the model'''
            self.model.add_statement(statement2Redland(statement),
                                      context=statement.scope or None)

        def removeStatement(self, statement ):
            '''removes the statement'''
            self.model.remove_statement(statement2Redland(statement),
                                        context=statement.scope or None)

    class RedlandHashBdbModel(TransactionModel, RedlandModel):
        def __init__(self,location, defaultStatements=()):
            if os.path.exists(location + '-sp2o.db'):
                storage = RDF.HashStorage(location, options="hash-type='bdb'")
                model = RDF.Model(storage)
            else:
                # Create a new BDB store
                storage = RDF.HashStorage(location, options="new='yes',hash-type='bdb'")
                model = RDF.Model(storage)                
                for stmt in defaultStatements:
                    model.add_statement( statement2Redland(stmt), context=stmt.scope)
                model.sync()
            super(RedlandHashBdbModel, self).__init__(model)

except ImportError:
    log.debug("Redland not installed")

try:
    import rdflib
    from rdflib.Literal import Literal
    from rdflib.BNode import BNode
    from rdflib.URIRef import URIRef
    
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
        return (RDFLibModel.URI2node(statement.subject),
                RDFLibModel.URI2node(statement.predicate), object)

    def rdflib2Statements(rdflibStatements, defaultScope=''):
        '''RDFLib triple to Statement'''
        for (subject, predicate, object) in rdflibStatements:
            if isinstance(object, Literal):                
                objectType = object.language or object.datatype or OBJECT_TYPE_LITERAL
            else:
                objectType = OBJECT_TYPE_RESOURCE            
            yield Statement(RDFLibModel.node2String(subject),
                            RDFLibModel.node2String(predicate),
                            RDFLibModel.node2String(object),
                            objectType=objectType, scope=defaultScope)

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
            
        def getResources(self, schema=None):
            '''All resources referenced in the model, include resources that only appear as objects in a triple.
               Returns a list of resources are sorted by their URI reference
            '''                    
            stmts = rdflib2Statements( self.model.triples( (None, None, None)) ) 
            return getResourcesFromStatements(stmts,schema)
        
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
        def __init__(self,path, defaultStatements=(), context=''):
            ntpath, stmts, format = _loadRDFFile(path, defaultStatements,context)
            if format == 'unsupported':                
                self.format = 'nt'
                self.path = ntpath
            else:
                self.format = (format == 'ntriples' and 'nt') or (
                               format == 'rdfxml' and 'xml') or 'error'
                assert self.format != 'error', 'unexpected format'
                self.path = path
                
            from rdflib.TripleStore import TripleStore                                    
            RDFLibModel.__init__(self, TripleStore())
            for stmt in stmts:
                self.addStatement( stmt )             
    
        def commit(self):
            self.model.save(self.path, self.format)

    class TransactionalRDFLibFileModel(TransactionModel, RDFLibFileModel): pass
        
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
    statements = doc.model.getStatements(context=uri)
    for stmt in statements:
        assert stmt.scope == uri
        subjectNode = doc.findSubject(stmt.subject)
        predNode = subjectNode.findPredicate(stmt)
        assert predNode
        predicates.append(predNode)
    return predicates

def rdfDocument(context, object,type='unknown', nodeset=None):
    #note: XSLT only
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

(RFDOM_XPATH_EXT_NS, 'get-statement-uris'): getReified,
(RFDOM_XPATH_EXT_NS, 'get-graph-predicates'): getGraphPredicates,
(RFDOM_XPATH_EXT_NS, 'rdfdocument'): rdfDocument,
}
from Ft.Xml.Xslt import XsltContext
XsltContext.XsltContext.functions[(RFDOM_XPATH_EXT_NS, 'rdfdocument')] = rdfDocument
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
