"""
    DOMStore classes used by Raccoon.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from Ft.Xml import Domlette, InputSource
from rx import RxPath, transactions
import StringIO, os, os.path
from rx import logging #for python 2.2 compatibility

class DomStore(transactions.TransactionParticipant):
    '''
    Abstract interface for DomStores
    '''
    log = logging.getLogger("domstore")

    #impl. must expose the DOM as a read-only attribute named "dom"
    dom = None

    addTrigger = None
    removeTrigger = None
    newResourceTrigger = None

    def __init__(**kw):
        pass
    
    def loadDom(self,requestProcessor, location, defaultDOM):
        ''' 
        Load the DOM located at location (a filepath).
        If location does not exist create a new DOM that is a copy of 
        defaultDOM, a file-like of appropriate type
        (e.g. an XML or RDF NTriples file).
        '''
        self.log = logging.getLogger("domstore." + requestProcessor.appName)
                
    def evalXPath(self, xpath, context, expCache=None, queryCache = None):
        pass

    def applyXslt(self, xslStylesheet, topLevelParams = None, extFunctionMap = None,
              baseUri='file:', styleSheetCache = None):
        pass
        
    def commitTransaction(self, txnService):
        pass

    def abortTransaction(self, txnService):
        pass

    def getStateKey(self):
        '''
        Returns the a hashable object that uniquely identifies the current state of DOM.
        Used for caching.
        If this is not implemented, it should raise KeyError (the default implementation).
        '''
        raise KeyError

    def getTransactionContext(self):
        return None
        
    def _normalizeSource(self, requestProcessor, path):
        #if source was set on command line, override config source
        if requestProcessor.source:            
            source = requestProcessor.source
        else:
            source = path

        if not source:
            self.log.warning('no model path given and STORAGE_PATH'
                             ' is not set -- model is read-only.')            
        elif not os.path.isabs(source):
            #todo its possible for source to not be file path
            #     -- this will break that
            source = os.path.join( requestProcessor.baseDir, source)
        return source
    
class XMLDomStore(DomStore):
    _defaultModel = None
    _location = None
    prettyPrint = False

    def __init__(self, STORAGE_PATH ='', STORAGE_TEMPLATE='', **kw):
        self.STORAGE_PATH = STORAGE_PATH
        self._defaultModel = StringIO.StringIO(STORAGE_TEMPLATE)
    
    def loadDom(self, requestProcessor):        
        self.log = logging.getLogger("domstore." + requestProcessor.appName)
        source = self._normalizeSource(requestProcessor, self.STORAGE_PATH)

        if os.path.exists(source):
            inputSource = InputSource.DefaultFactory.fromUri(Uri.OsPathToUri(source))
        else:
            inputSource = InputSource.DefaultFactory.fromStream(self._defaultModel)
            
        self._location = source
        self.dom = Domlette.NonvalidatingReader.parse(inputSource)
        
    def evalXPath(self, xpath, context, expCache=None,queryCache=None):
        self.log.debug(xpath)
        if expCache:
            compExpr = expCache.getValue(xpath) #todo: nsMap should be part of the key -- until then clear the cache if you change that!
        else:
            compExpr = XPath.Compile(xpath)
        
        if queryCache:
            res = queryCache.getValue(compExpr, context)         
        else:
            res = compExpr.evaluate(context)
        return res
        

    def applyXslt(self, xslStylesheet, topLevelParams = None, extFunctionMap = None,
              baseUri='file:', styleSheetCache = None):
        extFunctionMap = extFunctionMap or {}

        from Ft.Xml.Xslt.Processor import Processor
        processor = Processor()

        if styleSheetCache:
            styleSheet = styleSheetCache.getValue(xslStylesheet, baseUri)
            processor.appendStylesheetInstance( styleSheet, baseUri ) 
        else:
            processor.appendStylesheet( InputSource.DefaultFactory.fromString
                                        (xslStylesheet, baseUri)) #todo: fix baseUri
            
        for (k, v) in extFunctionMap.items():
            namespace, localName = k
            processor.registerExtensionFunction(namespace, localName, v)
            
        return processor.runNode(self.dom, None, 0, topLevelParams), processor.stylesheet

    def commitTransaction(self, txnService):
        #write out the dom
        output = file(self._location, 'w+')
        from Ft.Xml.Domlette import Print, PrettyPrint
        if self.prettyPrint:
            PrettyPrint(doc, output)
        else:
            Print(doc, output)
        output.close()
        self._defaultModel = None
        
    def abortTransaction(self, txnService):
        #reload the file
        self.loadDom(None, self._location, self._defaultModel)
            
class RxPathDomStore(DomStore):

    def __init__(self, modelFactory=RxPath.IncrementalNTriplesFileModel,
                 schemaFactory=RxPath.defaultSchemaClass,                 
                 STORAGE_PATH ='',
                 STORAGE_TEMPLATE='',
                 APPLICATION_MODEL='',
                 transactionLog = '',
                 saveHistory = True,
                 VERSION_STORAGE_PATH='',
                 versionModelFactory=None, **kw):
        '''
        modelFactory is a RxPath.Model class or factory function that takes
        two parameters:
          a location (usually a local file path) and iterator of Statements
          to initialize the model if it needs to be creator 
        '''
        self.modelFactory = modelFactory
        self.versionModelFactory = versionModelFactory or modelFactory
        self.schemaFactory = schemaFactory
        self.APPLICATION_MODEL = APPLICATION_MODEL        
        self.STORAGE_PATH = STORAGE_PATH        
        self.VERSION_STORAGE_PATH = VERSION_STORAGE_PATH
        self.defaultTripleStream = StringIO.StringIO(STORAGE_TEMPLATE)
        self.transactionLog = transactionLog
        self.saveHistory = saveHistory
            
    def loadDom(self, requestProcessor):        
        self.log = logging.getLogger("domstore." + requestProcessor.appName)

        normalizeSource = getattr(self.modelFactory, 'normalizeSource',
                                  DomStore._normalizeSource)
        source = normalizeSource(self, requestProcessor,self.STORAGE_PATH)

        modelUri=requestProcessor.MODEL_RESOURCE_URI
        if self.saveHistory:
            from rx import RxPathGraph
            initCtxUri = RxPathGraph.getTxnContextUri(modelUri, 0)
        else:
            initCtxUri = ''
        defaultStmts = RxPath.NTriples2Statements(self.defaultTripleStream, initCtxUri)

        if self.VERSION_STORAGE_PATH:
            normalizeSource = getattr(self.versionModelFactory, 
                    'normalizeSource', DomStore._normalizeSource)
            versionStoreSource = normalizeSource(self, requestProcessor,
                                                 self.VERSION_STORAGE_PATH)
            delmodel = self.versionModelFactory(source=versionStoreSource,
                                                defaultStatements=[])
        else:
            delmodel = None

        #note: to override loadNtriplesIncrementally, set this attribute
        #on your custom modelFactory function
        if self.saveHistory and getattr(
                self.modelFactory, 'loadNtriplesIncrementally', False):
            if not delmodel:
                delmodel = RxPath.MemModel()
            dmc = RxPathGraph.DeletionModelCreator(delmodel)            
            model = self.modelFactory(source=source,
                    defaultStatements=defaultStmts, incrementHook=dmc)
            lastScope = dmc.lastScope
        else:
            model = self.modelFactory(source=source,
                    defaultStatements=defaultStmts)
            lastScope = None
                
        if self.APPLICATION_MODEL:
            appTriples = StringIO.StringIO(self.APPLICATION_MODEL)
            stmtGen = RxPath.NTriples2Statements(appTriples, RxPathGraph.APPCTX)
            appmodel = RxPath.MemModel(stmtGen)
            model = RxPath.MultiModel(model, appmodel)
            
        if self.transactionLog:
            model = RxPath.MirrorModel(model, RxPath.IncrementalNTriplesFileModel(
                self.transactionLog, []) )

        if self.saveHistory:
            graphManager = RxPathGraph.NamedGraphManager(model, delmodel,lastScope)
        else:
            graphManager = None
        
        #reverse namespace map #todo: bug! revNsMap doesn't work with 2 prefixes one ns            
        revNsMap = dict([(x[1], x[0]) for x in requestProcessor.nsMap.items()])
        self.dom = RxPath.createDOM(model, revNsMap,
                                modelUri=modelUri,
                                schemaClass = self.schemaFactory,
                                graphManager = graphManager)
        self.dom.addTrigger = self.addTrigger
        self.dom.removeTrigger = self.removeTrigger
        self.dom.newResourceTrigger = self.newResourceTrigger              
        
        #associate the queryCache with the DOM Document
        self.dom.queryCache = requestProcessor.queryCache 

    def applyXslt(self, xslStylesheet, topLevelParams=None, extFunctionMap=None,
              baseUri='file:', styleSheetCache = None):
        processor = RxPath.RxSLTProcessor()
        result = RxPath.applyXslt(self.dom, xslStylesheet, topLevelParams,
                extFunctionMap, baseUri, styleSheetCache, processor=processor)
        return result, processor.stylesheet        

    def evalXPath(self, xpath, context, expCache=None, queryCache=None):
        self.log.debug(xpath)
        return RxPath.evalXPath(xpath, context, expCache, queryCache)

    def isDirty(self, txnService):
        '''return True if this transaction participant was modified'''    
        return txnService.state.additions or txnService.state.removals
        
    def commitTransaction(self, txnService):
        self.dom.commit(**txnService.getInfo())

    def abortTransaction(self, txnService):
        from rx import MRUCache
        if not self.isDirty(txnService):
            return
        key = self.dom.getKey()
        self.dom.rollback()
        if isinstance(key, MRUCache.InvalidationKey):
            if txnService.server.actionCache:
                txnService.server.actionCache.invalidate(key)
            if txnService.server.queryCache:
                txnService.server.queryCache.invalidate(key)

    def getStateKey(self):
        if self.dom:
            return self.dom.getKey()
        else:
            return None

    def getTransactionContext(self):
        if self.dom._childNodes is not None:
            contextUri = self.dom.graphManager.getTxnContext()
            contextNode = self.dom.findSubject(contextUri)
            if contextNode:
                return [contextNode]
        return None
