'''
Our approach to named graphs/contexts:
* the RxPath DOM and query engine always operate on triples, graphs are
   only used as a selection criteria to filter what appears to be in the underlying model
* this means a statement can appear multiple times in store under different context but appears as one statement
* we compose contexts from several names graphs using the a:includes and a:excludes
* we model a version history by moving removals of statements into contexts referenced by a:excludes
* when we remove a statement we remove it from every context it appears except when removing inside a shredding context
* 'applies-to' applies to the whole context, not just the named graph

a:includes
a:excludes
a:entails (use a more general property name than a:entails
  to encompass modeling things like patch sets or user customizations?)

a:applies-to
a:applies-to-all-including

Optionally this can be used with two separate stores, a primary one which has:
* txn contexts: for each added statement and references to included and excluded contexts
* add contexts: when a statement is added to a particular context

and a secondary one which has the rest of the types of contexts supported here:
* org contexts: where statements removed from a context are moved to
  (consists of an txn or add context followed by the del3 or del4 context that deleted it)
  Only be one per global remove, with preference given to non-context specific remove
* del3 contexts: context for statements globally removed from the store
  (records which contexts using a:applies-to-all-including) 
* del4 contexts: context for statements removed from a particular set of contexts
  (records which contexts using a:applies-to)  
* entailment contexts: context containing all the statements entails by a particular source
   (these are updated with adds and removes as the source changes). 
* other contexts. Same as entailment contexts... there will be an corresponding add context in the main store.

The primary one represents the current state of the model, the secondary one for version history.  
'''

from rx import RxPath
from RxPath import Statement,OBJECT_TYPE_RESOURCE,OBJECT_TYPE_LITERAL,RDF_MS_BASE
import time, re
from rx import logging #for python 2.2 compatibility
log = logging.getLogger("RxPath")
from rx import set

TXNCTX = 'context:txn:'  #+ modeluri:starttimestamp;version
DELCTX = 'context:del3:' #+ tnxctx (the tnxctx that excludes this)
DEL4CTX = 'context:del4:'#+ tnxctx;;sourcectx (the tnxctx that excludes this)
ORGCTX = 'context:org:' #+ (txnctx|addctx);;(del3|del4)ctx (the ctx it was removed from;; the ctx that removed it)
ADDCTX = 'context:add:' # + txnctx;;sourcectx (the context that the statement was added to;; the txnctx that includes this)
EXTRACTCTX = 'context:extracted:' #+sourceuri (source of the entailment)
APPCTX = 'context:application:'

#thus we can end up with URL like:
# org:add:txn:;3;;entail:http//;;del4:txn:ctx;;
#context:org:context:add:context:txn:http://foo.com/;3;;context:entail:http://foo.com/mypage.xml;;context:del4:context:txn:http://foo.com/;40

def splitContext(ctx):
    '''
    return a dictionary with the following keys:
    ORGCTX, ADDCTX, TXNCTX, EXTRACTCTX, DELCTX
    org, add, fromtxn,  srccontext, totxn,
    '''
    parts = ctx.split(';;')
    if ctx.startswith(ORGCTX):
        if parts[1].startswith(ADDCTX):
            if parts[2].startswith(DEL4CTX):
                delctx = parts[2]+';;'+parts[1]
            else:
                delctx = parts[2]
                #  org:   add:             txn:                        ;; src ctx ;;  delctx
            result=(ctx, ctx[len(ORGCTX):], parts[0][len(ORGCTX+ADDCTX):], parts[1], delctx)
        else:
            result=(ctx, '',                parts[0][len(ORGCTX):],        ''      ,  parts[1])
    elif ctx.startswith(ADDCTX):
          #  org:   add:               txn:                 ;; src ctx  ;;delctx
        result=('', ctx[len(ORGCTX):], parts[0][len(ADDCTX):], parts[1], '')
    elif ctx.startswith(DEL4CTX):
          #  org:   add:  txn:;;                src ctx     ;; delctx
        result=('', '', parts[0][len(DEL4CTX):], parts[1], ctx)
    elif ctx.startswith(DELCTX):
          #  org:   add:  txn:;; src ctx        ;;  delctx
        result=('', '', parts[0][len(DELCTX):], '', ctx)
    elif ctx.startswith(TXNCTX):
          #  org:   add:  txn:;; src ctx    ;;  txnctx
        result=('', '',    ctx,   '', '')
    else:
        result=('', '',    '',    ctx, '')
    return dict( zip((ORGCTX, ADDCTX, TXNCTX, EXTRACTCTX, DELCTX),result) )

class CurrentTxN:
    def __init__(self, txnCtxt):
        self.txnContext = txnCtxt

        self.specificContext = None
        self.includeCtxts = []
        self.excludeCtxts = []
        self.del3Ctxts = [] #list of contexts that have had statement remove from it during this txn
        self.del4Ctxts = {} #associate a del4context with the list of add contexts removed in it

    def rollback(self):
        self.specificContext = None
        self.includeCtxts = []
        self.excludeCtxts = []
        self.del3Ctxts = []
        self.del4Ctxts = {}      

class _StatementWithRemoveForContextMarker(Statement):
    removeForContext = True

def getTxnContextUri(modelUri, versionnum):
    return TXNCTX + modelUri + ';' + str(versionnum)
    
class NamedGraphManager(object):
    markLatest = True
    
    def __init__(self, addmodel, delmodel, lastScope):        
        if not delmodel:
            #if we don't use a separate store for version history
            #wrap the store so that DOM only sees the latest version of the model
            self.delmodel = addmodel
            self.managedModel = ExcludeDeletionsModel(addmodel)
        else:
            self.delmodel = delmodel
            self.managedModel = addmodel

        if not lastScope:
            oldLatest = addmodel.getStatements(predicate='http://rx4rdf.sf.net/ns/archive#latest')
            if oldLatest:
                lastScope = oldLatest[0].subject

        if lastScope:
            parts = lastScope.split(';')
            #context urls will always start with a txn context, with the version after the first ;
            assert int(parts[1])
            self.lastVersion = int(parts[1])   
        else:
            self.lastVersion = 0

    def getTxnContext(self):
        return self.currentTxn.txnContext
    
    def incrementTxnContext(self):
        self.lastVersion += 1
        return getTxnContextUri(self.doc.modelUri, self.lastVersion)        

    def setDoc(self, doc):
        self.doc = doc        
        doc.graphManager = self
        doc.model = self.managedModel
        
        self.currentTxn = CurrentTxN(self.incrementTxnContext())    
        
    def add(self, stmt):
        txnCtxt = self.getTxnContext()

        if self.currentTxn.specificContext:
            baseContext = self.currentTxn.specificContext
            addContext = ADDCTX + txnCtxt + ';;' + baseContext

            if addContext not in self.currentTxn.includeCtxts:
                #add info about the included context
                self.currentTxn.includeCtxts.append(addContext)

                newCtxStmts = [
                Statement(txnCtxt,'http://rx4rdf.sf.net/ns/archive#includes',
                        addContext,OBJECT_TYPE_RESOURCE, txnCtxt),
                #just infer this from a:includes rdfs:range a:Context
                #Statement(addContext, RDF_MS_BASE+'type',
                #    'http://rx4rdf.sf.net/ns/archive#Context',
                #              OBJECT_TYPE_RESOURCE, addContext),
                Statement(addContext, 'http://rx4rdf.sf.net/ns/archive#applies-to',
                        baseContext, OBJECT_TYPE_RESOURCE, addContext),
                ]
                for ctxStmt in newCtxStmts:            
                    self.doc.model.addStatement(ctxStmt)        

            self.doc.model.addStatement(Statement(
                    scope=addContext, *stmt[:4]) )
            #save the statement again using the original scope
            self.delmodel.addStatement(Statement(
                    scope=baseContext, *stmt[:4]) )
        else:
            self.doc.model.addStatement(Statement(
                    scope=txnCtxt, *stmt[:4]) )

    def _removeGlobal(self, stmt, currentDelContext):
        '''
        remove all statements that match
        '''
        stmts = self.doc.model.getStatements(asQuad=True, *stmt[:4])
        if not len(stmts):
            return False

        #there should only be at most one stmt with a txncontext as scope
        #and any number of stmts with a addcontext as scope
        txnctxEncountered = 0        
        for stmt in stmts:            
            #some statements are read-only and can't be removed
            if stmt.scope.startswith(APPCTX):
                continue

            if stmt.scope.startswith(TXNCTX):
                assert not txnctxEncountered
                txnctxEncountered = 1
                scope = stmt.scope or TXNCTX + self.doc.modelUri + ';0'
                self.delmodel.addStatement(Statement(stmt[0],stmt[1],stmt[2],                                                     
                 stmt[3],ORGCTX+ stmt.scope +';;'+currentDelContext))            
            elif stmt.scope.startswith(ADDCTX):
                self.delmodel.addStatement(Statement(stmt[0],stmt[1],stmt[2],                                                     
                         stmt[3],ORGCTX+ stmt.scope +';;'+currentDelContext))
                #record each context we're deleting from
                srcContext = stmt.scope.split(';;')[1]
                assert srcContext
                if srcContext not in self.currentTxn.del3Ctxts:    
                    self.delmodel.addStatement(Statement(currentDelContext,
                    'http://rx4rdf.sf.net/ns/archive#applies-to-all-including',
                        srcContext,OBJECT_TYPE_RESOURCE, currentDelContext) )
                    
                    self.currentTxn.del3Ctxts.append(srcContext)                                 
            elif not stmt.scope:
                scope = TXNCTX + self.doc.modelUri + ';0'
                self.delmodel.addStatement(Statement(stmt[0],stmt[1],stmt[2],                                                     
                 stmt[3],ORGCTX+ scope +';;'+currentDelContext))            
            else:                
                log.warn('skipping remove, unexpected context ' + stmt.scope)
                continue
            self.doc.model.removeStatement(stmt)
            
        return True
        
    def _removeFromContext(self, stmt, currentDelContext):
        '''
        Remove from the current specific context only:
        * remove the statement 
        * Add the stmt to the current del4 context    
        '''
        sourceContext = self.currentTxn.specificContext

        stmts = self.doc.model.getStatements(asQuad=True,*stmt[:4])
        for stmt in stmts:
            if stmt.scope.startswith(ADDCTX) and stmt.scope.endswith(
                                                    ';;'+sourceContext):
                #a bit of a hack: we use _StatementWithRemoveForContextMarker
                #to signal to the incremental NTriples file model that this
                #remove is specific to this context, not global
                self.doc.model.removeStatement(
                    _StatementWithRemoveForContextMarker(*stmt) )
                orginalAddContext = stmt.scope
                break
        else:
            orginalAddContext = None            
        
        self.delmodel.removeStatement(Statement(
                    scope=sourceContext, *stmt[:4]) )

        if not orginalAddContext:            
            #this must have been deleting by a global delete, so we'll have to figure out
            #when this statement was added to the source context
            delstmts = self.delmodel.getStatements(asQuad=True,*stmt[:4])
            orgcontexts = [s.scope for s in delstmts
                if (s.scope.startswith(ORGCTX+ADDCTX)
                    and splitContext(s.scope)[EXTRACTCTX] == sourceContext)]
            if not orgcontexts:
                return False #not found!!                
            orgcontexts.sort(lambda x,y: comparecontextversion(
                  getTransactionContext(x),getTransactionContext(y)) )
            orginalAddContext = splitContext(orgcontexts[-1])[ADDCTX]
            assert orginalAddContext
                                        
        #we add the stmt to the org context to record which transaction the removed statement was added
        #don't include the srcContext in ORGCTX since its already in the ADDCTX
        currentDelContextWithoutSrc = DEL4CTX + self.getTxnContext() 
        self.delmodel.addStatement(Statement(stmt[0],stmt[1],stmt[2],stmt[3],
             ORGCTX+ orginalAddContext +';;'+currentDelContextWithoutSrc))

        if orginalAddContext not in self.currentTxn.del4Ctxts.setdefault(currentDelContext,[]):
            self.delmodel.addStatement(Statement(currentDelContext,
                   'http://rx4rdf.sf.net/ns/archive#applies-to',
                orginalAddContext,OBJECT_TYPE_RESOURCE, currentDelContext))
            
            self.currentTxn.del4Ctxts[currentDelContext].append(orginalAddContext)

        return True        

    def remove(self, stmt):
        txnContext = self.getTxnContext()

        specificContext = self.currentTxn.specificContext
        if specificContext:            
            currentDelContext = DEL4CTX + txnContext + ';;' + specificContext
            if not self._removeFromContext(stmt, currentDelContext):
                log.debug('remove failed '+ str(stmt) + ' for context ' + specificContext)
                return            
        else:
            currentDelContext = DELCTX + txnContext
            if not self._removeGlobal(stmt, currentDelContext):
                log.debug('remove failed '+ str(stmt))
                return
        
        if currentDelContext not in self.currentTxn.excludeCtxts:
            #deleting stmts for the first time in this transaction
            #add statement declaring the deletion context
            removeCtxStmt = Statement(txnContext,
                    'http://rx4rdf.sf.net/ns/archive#excludes',
               currentDelContext,OBJECT_TYPE_RESOURCE, txnContext)

            self.doc.model.addStatement(removeCtxStmt)
            self.currentTxn.excludeCtxts.append(currentDelContext)
        
        self.delmodel.addStatement(Statement(stmt[0],stmt[1],stmt[2],stmt[3],
             currentDelContext))
            
    def commit(self, kw):
        scope = self.getTxnContext()
        assert scope
        if self.markLatest:
            oldLatest = self.doc.model.getStatements(predicate='http://rx4rdf.sf.net/ns/archive#latest')
            if oldLatest:
                self.doc.model.removeStatement(oldLatest[0])

        ctxStmts = [
            Statement(scope, RDF_MS_BASE+'type',
            'http://rx4rdf.sf.net/ns/archive#TransactionContext',OBJECT_TYPE_RESOURCE, scope),
            Statement(scope,'http://rx4rdf.sf.net/ns/archive#created-on',
             time.asctime(),OBJECT_TYPE_LITERAL, scope),
        ]

        if self.markLatest:
            ctxStmts.append(Statement(scope, 'http://rx4rdf.sf.net/ns/archive#latest', 
                unicode(self.lastVersion),OBJECT_TYPE_LITERAL, scope))
                
        if kw.get('source'):
            ctxStmts.append( Statement(scope,
                'http://rx4rdf.sf.net/ns/wiki#created-by',
               RxPath.StringValue(kw['source'][0]),OBJECT_TYPE_RESOURCE, scope))
        if kw.get('createdFrom'):
            ctxStmts.append( Statement(scope,
                'http://rx4rdf.sf.net/ns/wiki#created-from',
               RxPath.StringValue(kw['createdFrom'][0]),OBJECT_TYPE_LITERAL, scope))
        if kw.get('comment'):
            ctxStmts.append( Statement(scope,
                RxPath.RDF_SCHEMA_BASE + 'comment',
               RxPath.StringValue(kw['comment'][0]),OBJECT_TYPE_LITERAL, scope))
        if kw.get('minorEdit'):
            ctxStmts.append(Statement(scope, 'http://rx4rdf.sf.net/ns/wiki#minor-edit', 
                '1',OBJECT_TYPE_LITERAL, scope))

        for stmt in ctxStmts:            
            self.doc.model.addStatement(stmt)

        if self.delmodel != self.managedModel:
            self.delmodel.commit(**kw)
        
        #increment version and set new context
        self.currentTxn = CurrentTxN(self.incrementTxnContext())        

    def rollback(self):
        if self.delmodel != self.managedModel:
            self.delmodel.rollback()
        self.currentTxn.rollback() #reset context

    def pushContext(self,baseContext):
        '''
        Any future changes to the DOM will be specific to this context
        '''
        assert not self.currentTxn.specificContext, ("pushContext() only allowed"
        " inside a transaction context, not "+self.currentTxn.specificContext)
        
        self.currentTxn.specificContext = baseContext

        if baseContext.startswith(ORGCTX):
            #special case to allow history to be changed
            #this is used so we can efficiently store deltas
            assert 0 #todo!        
            
    def popContext(self):
        self.currentTxn.specificContext = None

    def getStatementsInGraph(self, contexturi):
        if contexturi.startswith(TXNCTX) or contexturi.startswith(ADDCTX):
            return self.doc.model.getStatements(context=contexturi)
        else:
            return self.delmodel.getStatements(context=contexturi)
        
class DeletionModelCreator(object):
    '''
    This reconstructs the delmodel from add and remove events generated by
    loading a NTriples transaction log (see NTriples2Statements)
    '''
    doUpgrade = False #todo

    def __init__(self, delmodel):
        self.currRemoves = []
        self.currRemovesForContext = {}
        self.delmodel = delmodel
        self.lastScope = None

    oldContextPattern = re.compile('context:(.*)_....-..-..T.._.._..Z')
    def _upgradeScope(self,scope):
        return scope      
##        if scope:
##            match = oldContextPattern.match(scope)
##            if match:                
##                #looks like an old transaction context
##                self.lastScope = TXNCTX + match.group(1) + ';' + str(self.lastVersion)                
##            else:
##                #convert to an ADDCTX
##                scope = ADDCTX + self.lastScope + ';;' + scope
##        return scope
              
    def add(self, stmt):
        scope = self.upgradeScope(stmt[4])
        if stmt[4]:
            if stmt[4].startswith(ADDCTX):
                #reconstruct user defined contexts
                self.delmodel.addStatement(
                    Statement(stmt[0],stmt[1],stmt[2],stmt[3],
                       stmt[4].split(';;')[1]))
            elif not scope.startswith(TXNCTX):
                assert self.doUpgrade
            self.lastScope = stmt[4]
        return stmt

    def _looksLikeSystemRemove(self, stmt):
        if (stmt[1] == 'http://rx4rdf.sf.net/ns/archive#latest'
            or stmt[4].startswith(APPCTX)):
            return True
        else:
            return False
          
    def remove(self, stmt, forContext):
        scope = stmt[4]
        if forContext:
            assert scope.startswith(ADDCTX)
            assert forContext == scope
            self.currRemovesForContext.setdefault(forContext,[]).append(stmt)
        elif scope.startswith(TXNCTX) or scope.startswith(ADDCTX):
            if not self._looksLikeSystemRemove(stmt):
                self.currRemoves.append(stmt)
        else:
            assert self.doUpgrade #this should only occur when upgrading
            
        return stmt

    def comment(self, line):
        if line.startswith('begin'):
            self.currRemoves = []
            self.currRemovesForContext = {}

        if line.startswith('end'):
            #transaction ended
            #record removes that were specific to a context
            for ctxt, stmts in self.currRemovesForContext.values():
                assert ctxt.startswith(ADDCTX)
                srcCtxt = ctxt.split(';;')[1]

                #reconstruct user defined contexts
                self.delmodel.removeStatement(
                    Statement(stmt[0],stmt[1],stmt[2],stmt[3], srcCtxt))

                currentDelContext = DEL4CTX + self.lastScope + ';;' + srcCtxt
                for stmt in stmts:
                    assert stmt[4]==ctxt, "%s != %s" % (stmt[4], ctxt)
                    
                    self.delmodel.addStatement(
                     Statement(stmt[0],stmt[1],stmt[2],stmt[3],currentDelContext))
                    
                    self.delmodel.addStatement(
                        Statement(stmt[0],stmt[1],stmt[2],stmt[3],
                       ORGCTX+ctxt +';;' +DEL4CTX+self.lastScope))

                #re-create statements that would be added to the delmodel:
                self.delmodel.addStatement(Statement(currentDelContext,
                'http://rx4rdf.sf.net/ns/archive#applies-to',
                srcCtx,OBJECT_TYPE_RESOURCE, currentDelContext))

            #record global removes 
            currentDelContext = DELCTX + self.lastScope
            stmtsRemovedSoFar = set()
            for stmt in self.currRemoves:
                if stmt not in stmtsRemovedSoFar:
                    self.delmodel.addStatement(
                        Statement(stmt[0],stmt[1],stmt[2],stmt[3],
                       currentDelContext))
                    stmtsRemovedSoFar.add(stmt)
                
                scope = stmt[4] or TXNCTX + self.doc.modelUri + ';0'
                self.delmodel.addStatement(
                    Statement(stmt[0],stmt[1],stmt[2],stmt[3],
                      ORGCTX+ stmt[4] +';;'+currentDelContext))

            for srcCtx in set([s[4].split(';;')[1] for s in self.currRemoves
                               if s[4].startswith(ADDCTX)]):           
                self.delmodel.addStatement(Statement(currentDelContext,
                'http://rx4rdf.sf.net/ns/archive#applies-to-all-including',
                srcCtx,OBJECT_TYPE_RESOURCE, currentDelContext))

            self.currRemovesForContext = {}                
            self.currRemoves = []

class ExcludeDeletionsModel(RxPath.MultiModel):
    def __init__(self, model):
        RxPath.MultiModel.__init__(self, model)

    def getStatements(self, subject = None, predicate = None, object = None,
                      objecttype=None,context=None, asQuad=False):        
        result = self.models[0].getStatements(subject, predicate, object,
                                            objecttype,context,asQuad)
        return filter(lambda s: not s.scope or s.scope == APPCTX or
                          s.scope.startswith(TXNCTX)
                          or s.scope.startswith(ADDCTX), result)
        
def getTransactionContext(contexturi):
    txnpart = contexturi.split(';;')[0]
    index = txnpart.find(TXNCTX)
    if index < 0:
        return '' #not a txn context (e.g. empty or context:application, etc.)
    return txnpart[index:]

    #if index < 0: 
    #while not contexturi.startswith(TXNCTX):
    #    stmts = model.getStatements(object=contexturi,
    #        predicate='http://rx4rdf.sf.net/ns/archive#includes')
    #    assert len(stmts) == 1
    #    contexturi = stmts[0].subject #find parent txncontxt
    #
    #return contexturi

def _getRevisions(resource):    
    stmts = resource.ownerDocument.model.getStatements(subject=resource.uri,
                                                                asQuad=True)        
    delstmts = resource.ownerDocument.graphManager.delmodel.getStatements(
                                            subject=resource.uri,asQuad=True)
    #get a unique set of transaction context uris, sorted by revision order
    import itertools
    contexts = set([getTransactionContext(s.scope)
                for s in itertools.chain(stmts, delstmts)]) #todo: 2.3 dep
    contexts = list(contexts)
    contexts.sort(comparecontextversion)
    return contexts, stmts, delstmts

def getRevisionContexts(context, resourcenode):    
    assert len(resourcenode) == 1 and hasattr(resourcenode[0], 'uri')
    contexts, addstmts, removestmts = _getRevisions(resourcenode[0])    
    #order by ancestory xpath('id($graphs)//depends-on/*')
    contextnodes = RxPath.Id(context, contexts)
    contextnodes.sort(lambda x,y: comparecontextversion(x.uri,y.uri)) 
    return contextnodes  
    
def _showRevision(contexts, addstmts, removestmts, revision):
    '''revision is 0 based'''
    rev2Context = dict( [ (x[1],x[0]) for x in enumerate(contexts)] )

    #include every add stmt whose context <= revision    
    stmts = [s for s in addstmts if rev2Context[s.scope] <= revision]    
    
    #include every deleted stmt whose original context <= revision 
    #and whose deletion context > revision        
    stmts.extend([s for s in removestmts if s.scope.startswith(ORGCTX)                                
        and rev2Context[
            getTransactionContext(s.scope)
            ] <= revision 
        and rev2Context[
            s.scope[len(ORGCTX):].split(';;')[-1][len(DELCTX):]
            ] > revision])
    
    return stmts

def showRevision(context, resourceNodeset, revisionNum):
    '''revisionNum is 1-based'''
    if not revisionNum:
        return []
    revisionNum = RxPath.NumberValue(revisionNum)-1
    contextsenum, addstmts, removestmts = _getRevisions(resourceNodeset[0])
    stmts = _showRevision(contextsenum, addstmts, removestmts, revisionNum)
    
    docTemplate = resourceNodeset[0].ownerDocument
    revdoc = RxPath.RxPathDOMFromStatements(stmts,
                                docTemplate.nsRevMap,
                                docTemplate.modelUri,
                                docTemplate.schemaClass)
    return [ revdoc.findSubject(resourceNodeset[0].uri) ]

def comparecontextversion(ctxUri1, ctxUri2):    
    assert (not ctxUri1 or ctxUri1.startswith(TXNCTX),
                    ctxUri1 + " doesn't look like a txn context URI")
    assert (not ctxUri2 or ctxUri2.startswith(TXNCTX),
                    ctxUri2 + " doesn't look like a txn context URI")
    assert len(ctxUri1.split(';'))>1, ctxUri1 + " doesn't look like a txn context URI"
    assert len(ctxUri2.split(';'))>1, ctxUri2 + " doesn't look like a txn context URI"

    return cmp(ctxUri1 and int(ctxUri1.split(';')[1]) or 0,
               ctxUri2 and int(ctxUri2.split(';')[1]) or 0)

##def comparecontextversion(versionString1, versionString2):
##    '''return True if the versionId1 is a superset of versionId2'''
##    versionId1, versionId2 = versionString1[1:].split('.'), versionString2[1:].split('.')    
##    if len(versionId1) != len(versionId2):
##        return False
##    for i, (v1, v2) in enumerate(zip(versionId1, versionId2)): 
##      if i%2: #odd -- revision number
##         if int(v1) < int(v2):
##            return False            
##      else: #even -- branch id
##        if v1 != v2:
##            return False
##    return True

def _getContextRevisions(model, delmodel, srcContext):
    #find the txn contexts with changes to the srcContext
    addchangecontexts = [s.subject for s in model.getStatements(
        object=srcContext,
        predicate='http://rx4rdf.sf.net/ns/archive#applies-to',asQuad=True)]
    #todo: this is redundent if model and delmodel are the same:    
    delchangecontexts = [s.subject for s in delmodel.getStatements(
        object=srcContext,
        predicate='http://rx4rdf.sf.net/ns/archive#applies-to',asQuad=True)]
    del3changecontexts = [s.subject for s in delmodel.getStatements(
        object=srcContext,
        predicate='http://rx4rdf.sf.net/ns/archive#applies-to-all-including',
        asQuad=True)]

    #get a unique set of transaction context uris, sorted by revision order
    txns = {}
    for ctx in addchangecontexts:
        txns.setdefault(getTransactionContext(ctx), []).append(ctx)
    for ctx in delchangecontexts:
        txns.setdefault(getTransactionContext(ctx), []).append(ctx)
    for ctx in del3changecontexts:
        txns.setdefault(getTransactionContext(ctx), []).append(ctx)
    txncontexts = txns.keys()
    txncontexts.sort(comparecontextversion)

    return txncontexts, txns

def _showContextRevision(model, delmodel, srcContext, revision):
    txncontexts, txns = _getContextRevisions(model, delmodel, srcContext)

    stmts = set()
    delstmts = set()
    for rev, txnctx in enumerate(txncontexts):
        if rev > revision:
            break
        for ctx in txns[txnctx]:
            if ctx.startswith(ADDCTX):
                addstmts = set([s for s in model.getStatements(context=ctx) if s.subject != ctx])
                stmts += addstmts
                delstmts -= addstmts
            elif ctx.startswith(DELCTX):
                globaldelstmts = set([s for s in delmodel.getStatements(context=ctx) if s.subject != ctx])
                #re-add these if not also removed by del4
                globaldelstmts -= delstmts
                stmts += globaldelstmts
            elif ctx.startswith(DEL4CTX):
                delstmts = set([s for s in delmodel.getStatements(context=ctx) if s.subject != ctx])
                stmts -= delstmts
            else:
                assert 0, 'unrecognized context type: ' + ctx
            
    return list(stmts)

def getRevisionContextsForContext(context, contextNodeset):    
    srcContext = RxPath.StringValue(contextNodeset)
    if not srcContext:
        return []

    doc = contextNodeset[0].rootNode or context.node.rootNode
    assert doc        
    contexts, txns = _getContextRevisions(doc.model,
                        doc.graphManager.delmodel, srcContext)    
    #order by ancestory xpath('id($graphs)//depends-on/*')
    contextnodes = RxPath.Id(context, contexts)
    contextnodes.sort(lambda x,y: comparecontextversion(x.uri,y.uri)) 
    return contextnodes  

def showContextRevision(context, contextNodeset, revisionNum):
    '''revisionNum is 1-based'''
    if not revisionNum:
        return []
    revisionNum = RxPath.NumberValue(revisionNum)-1

    srcContext = RxPath.StringValue(contextNodeset)
    if not srcContext:
        return []

    doc = contextNodeset[0].rootNode or context.node.rootNode
    assert doc
    stmts = _showContextRevision(doc.model, doc.graphManager.delmodel,
                                                srcContext, revisionNum)
    
    docTemplate = doc
    revdoc = RxPath.RxPathDOMFromStatements(stmts,
                                docTemplate.nsRevMap,
                                docTemplate.modelUri,
                                docTemplate.schemaClass)
    return [ revdoc ]

RxPath.BuiltInExtFunctions.update({
(RxPath.RXPATH_EXT_NS, 'get-revision-contexts-for-subject'): getRevisionContexts,
(RxPath.RXPATH_EXT_NS, 'get-revision'): showRevision,
(RxPath.RXPATH_EXT_NS, 'get-revision-contexts-for-context'): getRevisionContextsForContext,
(RxPath.RXPATH_EXT_NS, 'get-context-revision'): showContextRevision,
})
