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
        
    def loadDom(self,requestProcessor, location, defaultDOM):
        ''' Load the DOM located at location (a filepath).
        If location doesn't exist create a new DOM that is a copy of 
        defaultDOM, a file-like of appropriate type
        (e.g. an XML or RDF NTriples file).
        '''
        
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
        
class XMLDomStore(DomStore):
    _defaultModel = None
    _location = None
    prettyPrint = False
    
    def loadDom(self, requestProcessor, source, defaultModel):
        self.log = logging.getLogger("domstore." + requestProcessor.appName)        
        if os.path.exists(source):
            inputSource = InputSource.DefaultFactory.fromUri(Uri.OsPathToUri(source))
        else:
            inputSource = InputSource.DefaultFactory.fromStream(defaultModel)
            self._defaultModel = defaultModel
            
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
    def __init__(self, modelFactory=RxPath.IncrementalNTriplesFileModel, schemaFactory=RxPath.defaultSchemaClass):
        '''
        modelFactory is a RxPath.Model class or factory function that takes
        two parameters:
          a location (usually a local file path) and iterator of Statements
          to initialize the model if it needs to be creator
                
        schemaClass 
        '''
        self.modelFactory = modelFactory
        self.schemaFactory = schemaFactory
                                        
    def loadDom(self, requestProcessor, source, defaultTripleStream):        
        self.log = logging.getLogger("domstore." + requestProcessor.appName)
        model = self.modelFactory(source,
                        RxPath.NTriples2Statements(defaultTripleStream))
                
        if requestProcessor.APPLICATION_MODEL:
            appTriples = StringIO.StringIO(requestProcessor.APPLICATION_MODEL)
            stmtGen = RxPath.NTriples2Statements(appTriples, 'context:application')
            appmodel = RxPath.MemModel(stmtGen)
            model = RxPath.MultiModel(model, appmodel)
            
        if requestProcessor.transactionLog:
            model = RxPath.MirrorModel(model, RxPath.IncrementalNTriplesFileModel(
                requestProcessor.transactionLog, []) )
            
        #reverse namespace map #todo: bug! revNsMap doesn't work with 2 prefixes one ns            
        revNsMap = dict(map(lambda x: (x[1], x[0]), requestProcessor.nsMap.items()) )
        self.dom = RxPath.createDOM(model, revNsMap,
                                modelUri=requestProcessor.MODEL_RESOURCE_URI,
                                    schemaClass = self.schemaFactory)
        self.dom.addTrigger = self.addTrigger
        self.dom.removeTrigger = self.removeTrigger
        self.dom.newResourceTrigger = self.newResourceTrigger              
        
        #associate the queryCache with the DOM Document
        self.dom.queryCache = requestProcessor.queryCache 

    def applyXslt(self, xslStylesheet, topLevelParams = None, extFunctionMap = None,
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