#! /usr/bin/env python
"""
    Engine and helper classes for Raccoon

    Copyright (c) 2003-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
if __name__ == '__main__':
    #we do this to avoid a lameness of Python where two Raccoon modules
    #can get loaded: <module '__main__' (built-in)>
    #and <module 'rx.Raccoon' from 'g:\_dev\rx4rdf\rx\raccoon.py'>
    #and so two different set of class definitions that won't be equal
    #which means for example an exception thrown by one module won't
    #get caught in code that imported the other module
    from rx import raccoon
    import sys
    raccoon.main(sys.argv[1:])
else:
    from rx import utils, glock, RxPath, MRUCache, XUpdate
    from Ft.Rdf.Drivers import Memory
    import os, time, sys, base64, mimetypes, types, traceback
    import urllib, re
    from Ft.Xml.Lib.Print import PrettyPrint
    from Ft.Xml.Xslt import XSL_NAMESPACE

    try:
        import cPickle
        pickle = cPickle
    except ImportError:
        import pickle
    try:
        import cStringIO
        StringIO = cStringIO
    except ImportError:
        import StringIO
    from rx import logging #for python 2.2 compatibility

    log = logging.getLogger("raccoon")
    _defexception = utils.DynaExceptionFactory(__name__)

    _defexception('CmdArgError')
    _defexception('unusable namespace error')
    _defexception('not authorized')

    class DoNotHandleException(Exception):
        '''
        RequestProcessor.doActions() will not invoke error handler actions on
        exceptions derived from this class.
        '''

    from rx.ExtFunctions import *
    from rx.Caching import *
    from rx.UriResolvers import *
    from rx import ContentProcessors
    
    def OsPath2PathUri(context, path):
        """
        Returns the given OS path as a path URI.
        """
        return SiteUriResolver.OsPathToPathUri(StringValue(path))
    DefaultExtFunctions[(RXWIKI_XPATH_EXT_NS, 'ospath2pathuri')] = OsPath2PathUri
    
    ############################################################
    ##Raccoon defaults
    ############################################################

    DefaultNsMap = { 'owl': 'http://www.w3.org/2002/07/owl#',
               'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'rdfs' : 'http://www.w3.org/2000/01/rdf-schema#',
               'wf' : RXWIKI_XPATH_EXT_NS,
               'request-header' : RXIKI_HTTP_REQUEST_HEADER_NS,
               'response-header' : RXIKI_HTTP_RESPONSE_HEADER_NS,
               'request-cookie' : RXIKI_REQUEST_COOKIES_NS,
               'response-cookie' : RXIKI_RESPONSE_COOKIES_NS,                 
               'session' : RXIKI_SESSION_NS,
               'previous' : RXIKI_PREV_NS,
               'error' : RXIKI_ERROR_NS,
               'f' : 'http://xmlns.4suite.org/ext',
               'bnode': RxPath.BNODE_BASE,
            }

    ############################################################
    ##Helper classes and functions
    ############################################################

    class Requestor(object):
        '''
        Requestor is a helper class that allows python code to invoke a Raccoon request as if it was function call
        Usage:
        response = __requestor__.requestname(**kw) where keywords are the optional request parameters
        An AttributeError exception is raised if the server does recognize the request
        '''
        def __init__(self, server, triggerName = None):
            self.server = server
            self.triggerName = triggerName

        #the trailing __ so you can have requests named 'invoke' without conflicting    
        def invoke__(self, name, **kw):
            return self.invokeEx__(name, kw)[0]
            
        def invokeEx__(self, name, kw):        
            kw.update( self.server.requestContext[-1] )
            kw['_name']=name
            if not kw.has_key('_path'):
                kw['_path'] = name
            #print 'invoke', kw
            #defaultTriggerName let's us have different trigger type per thread
            #allowing site:/// urls to rely on the defaultTriggerName
            triggerName = self.triggerName or self.server.defaultRequestTrigger
            result = self.server.runActions(triggerName, kw)
            if result is not None: #'cause '' is OK
                return (result, kw)
            else:
                raise AttributeError, name
        
        def __getattr__(self, name):
            if name in ['__hash__','__nonzero__', '__cmp__', '__del__']: #undefined but reserved attribute names
                raise AttributeError("'Requestor' object has no attribute '%s'" %name)
            return lambda **k: self.invoke__(name, **k)
            #else:raise AttributeError, name #we can't do this yet since we may need the parameters to figure out what to invoke (like a multimethod)

    def defaultActionCacheKeyPredicateFactory(action, cacheKeyPredicate):
        '''    
        returns a predicate to extract a key for the action out of a request
        This function give an action a chance to customize the cacheKeyPredicate for the particulars of the action instance.
        At the very least it must bind the action instance with the cacheKeyPredicate to disambiguate keys from different actions.
        '''
        actionid = id(action) #do this to avoid memory leaks
        return lambda resultNodeset, kw, contextNode, retVal: (
            actionid, cacheKeyPredicate(resultNodeset, kw, contextNode, retVal) )
        
    def notCacheableKeyPredicate(*args, **kw):
        raise MRUCache.NotCacheable

    class Action(object):
        '''
The Action class encapsulates a step in the request processing pipeline.

An Action has two parts, one or more match expressions and an action
function that is invoked if the request metadata matches one of the
match expressions. The action function returns a value which is passed
onto the next Action in the sequence.
        '''
                
        def __init__(self, queries, action = None, matchFirst = True, forEachNode = False,
                     depthFirst=True, requiresContext=False, cachePredicate=notCacheableKeyPredicate,
                     sideEffectsPredicate=None, sideEffectsFunc=None, isValueCacheableCalc=None,
                     cachePredicateFactory=defaultActionCacheKeyPredicateFactory,
                     canReceiveStreams=False):
            '''Queries is a list of RxPath expressions associated with this action
            
    action must be a function with this signature:    
    def action(matchResult, kw, contextNode, retVal) where:
        result is the result of the action's matching RxPath query 
        kw is the dictionary of metadata associated with the request
        contentNode is the context node used when the RxPath expressions were evaluated
        retVal was the return value of the last action invoked in the in action sequence or None

    If action is None this action will set the context node to the first node in the nodeset returned by the matching expression

    If matchFirst is True (the default) the requesthandler will stop after the first matching query.
    Otherwise all the match expression be evaluated and the action function call after each match.

    If forEachNode is True then the action function will be called for each node in a matching expression's result nodeset.
    The action function's result parameter will be a nodeset contain only that current node.
    '''        
            self.queries = queries
            self.action = action
            self.matchFirst = matchFirst 
            self.forEachNode = forEachNode
            self.requiresContext = requiresContext
            self.depthFirst = depthFirst
            self.preVars = []
            self.postVars = []        
            # self.requiresRetVal = requiresRetVal not yet implemented
            self.cacheKeyPredicate = cachePredicateFactory(self, cachePredicate)
            self.sideEffectsPredicate = sideEffectsPredicate
            self.sideEffectsFunc = sideEffectsFunc
            self.isValueCacheableCalc = isValueCacheableCalc
            self.canReceiveStreams = canReceiveStreams

        def assign(self, varName, *exps, **kw):
            '''
            Add a variable and expression list.
            Before the Action is run each expression evaluated, the first one that returns a non-empty value is assigned to the variable.
            Otherwise, the result of last expression is assigned (so you can choose between '', [], and 0).
            If the 'assignEmpty' keyword argument is set to False the variable will only be assigned if the result is non-zero (default is True).
            If the 'post' keyword argument is set to True the variable will be assigned after the Action is run (default is False).
            '''
            assert len(exps), 'Action.assign requires at least one expression'
            assignWhenEmpty = kw.get('assignEmpty', True)
            if kw.get('post', False):
                self.postVars.append( (varName,  exps, assignWhenEmpty) )
            else:
                self.preVars.append( (varName,  exps, assignWhenEmpty) )
                
    class FunctorAction(Action):        
        def __init__(self, actionFunc, indexes = [], **kw):
            Action.__init__(self, ['true()'], (lambda *args: actionFunc(*[args[i] for i in indexes])), **kw)
                                                         
    def assignVars(self, kw, varlist, default):
        '''
        Helper function for assigning variables from the config file.
        Also used by rhizome.py.
        '''
        import copy 
        for name in varlist:
            try:
                defaultValue = copy.copy(default)
            except TypeError:
                #probably ok, can't copy certain non-mutable objects like functions
                defaultValue = default
            value = kw.get(name, defaultValue)
            if default is not None and not isinstance(value, type(default)):
                raise 'config variable %s (of type %s) must be compatible with type %s' % (name, type(value), type(default))
            setattr(self, name, value)

    #utility function, c.f. Ft.Xml.Xslt.Processor._normalizeParams
    def toXPathDataType(value, ownerDocument):
        #todo: handle XML-RPC classes DateTime and Binary
        #todo: handle dictionaries that have keys as strings by using
        # the dictionary name as the namespace (optional param)
        if isinstance(value, ( list, tuple ) ):            
            newvalue = []
            for item in value:
                if getattr(item, 'nodeType', None):
                    newvalue.append(item)
                else:
                    if not isinstance(item, unicode):
                        item = unicode(str(item), 'utf8')
                    newvalue.append( ownerDocument.createTextNode(item))
            return newvalue
        else:
            import Ft.Xml.XPath
            assert isinstance(value, (str, Ft.Xml.XPath.boolean.BooleanType,
                                     bool, unicode, int, float, type(None)) )\
                   or getattr(value, 'nodeType', None), 'not a valid XPath datatype %s: ' % type(value)
            #todo: if is string: string = unicode(string,'utf8')
            #todo: add externalobject wrapper class if not an XPath class or UnicodeError is thrown (to handle binary strings)
            return value
        
    ############################################################
    ##Raccoon main class
    ############################################################
    class RequestProcessor(object):
        DEFAULT_CONFIG_PATH = ''#'raccoon-default-config.py'
        lock = None
        DefaultDisabledContentProcessors = []        
                    
        requestContext = utils.createThreadLocalProperty('__requestContext',
            doc='variables you want made available to anyone during this request (e.g. the session)')

        inErrorHandler = utils.createThreadLocalProperty('__inErrorHandler', initValue=0)
        
        previousResolvers = utils.createThreadLocalProperty('__previousResolvers', initValue=None)

        expCache = MRUCache.MRUCache(0, XPath.Compile)#, sideEffectsFunc=_resetFunctions)
                
        requestsRecord = None
        log = log        
        
        def __init__(self,a=None, m=None, p=None, argsForConfig=None,
                     appBase='/', model_uri=None, appName=''):
            self.requestContext = [{}] #stack of dicts
            configpath = a or self.DEFAULT_CONFIG_PATH
            self.source = m
            self.PATH = p or os.environ.get('RACCOONPATH',os.getcwd())
            self.BASE_MODEL_URI = model_uri
            #use first directory on the PATH as the base for relative paths
            #unless this was specifically set it will be the current dir            
            self.baseDir = self.PATH.split(os.pathsep)[0]
            self.appBase = appBase or '/'
            self.appName = appName
            self.cmd_usage = DEFAULT_cmd_usage
            self.styleSheetCache = MRUCache.MRUCache(0, styleSheetValueCalc)
            self.loadConfig(configpath, argsForConfig)
            self.requestDispatcher = Requestor(self)            
            self.resolver = SiteUriResolver(self)            
            self.loadModel()
            self.handleCommandLine(argsForConfig or [])
                    
        def handleCommandLine(self, argv):
            '''        
            the command line is translated into XPath variables as follows:
            * arguments beginning with a '-' are treated as a variable name with its value
            being the next argument unless that argument also starts with a '-'
            
            * the whole command line is assigned to the variable '_cmdline'
            '''
            kw = argsToKw(argv, self.cmd_usage)
            kw['_cmdline'] = '"' + '" "'.join(argv) + '"' 
            self.runActions('run-cmds', kw)        
                
        def loadConfig(self, path, argsForConfig=None):
            if not path:
                raise CmdArgError('you must specify a config file using -a') #path = self.DEFAULT_CONFIG_PATH
            if not os.path.exists(path):
                raise CmdArgError('%s not found' % path) 

            kw = {}
            if not self.BASE_MODEL_URI:
                import socket            
                self.BASE_MODEL_URI= 'http://' + socket.getfqdn() + '/'
            
            def includeConfig(path):
                 kw['__configpath__'].append(os.path.abspath(path))
                 execfile(path, globals(), kw)
                 kw['__configpath__'].pop()
                         
            kw['__server__'] = self
            kw['__argv__'] = argsForConfig or []
            kw['__include__'] = includeConfig
            kw['__configpath__'] = [os.path.abspath(path)]
            execfile(path, globals(), kw)

            def initConstants(varlist, default):
                return assignVars(self, kw, varlist, default)
                            
            initConstants( [ 'nsMap', 'extFunctions', 'actions',  'authorizationDigests',
                             'NOT_CACHEABLE_FUNCTIONS', ], {} )
            initConstants( [ 'STORAGE_PATH', 'STORAGE_TEMPLATE', 'APPLICATION_MODEL',
                             'DEFAULT_MIME_TYPE', 'transactionLog'], '')
            setattr(self, 'initModel', kw.get('initModel', RxPath.initFileModel))            
            initConstants( ['appBase'], self.appBase)
            assert self.appBase[0] == '/', "appBase must start with a '/'"
            initConstants( ['BASE_MODEL_URI'], self.BASE_MODEL_URI)
            initConstants( ['appName'], self.appName)
            #appName is a unique name for this request processor instance
            if not self.appName:            
                self.appName = re.sub(r'\W','_', self.BASE_MODEL_URI)            
            self.log = logging.getLogger("raccoon." + self.appName)
            
            self.defaultRequestTrigger = kw.get('DEFAULT_TRIGGER', 'http-request')
            initConstants( ['globalRequestVars'], [])
            self.globalRequestVars.extend( ['_name', '_noErrorHandling'] )
            self.defaultPageName = kw.get('defaultPageName', 'index')
            #cache settings:                
            initConstants( ['LIVE_ENVIRONMENT', 'useEtags'], 1)
            initConstants( ['XPATH_CACHE_SIZE','ACTION_CACHE_SIZE'], 1000)
            initConstants( ['XPATH_PARSER_CACHE_SIZE','STYLESHEET_CACHE_SIZE'], 200)
            initConstants( ['maxCacheableStream','FILE_CACHE_SIZE'], 0)#10000000) #~10mb     
            self.styleSheetCache.capacity = self.STYLESHEET_CACHE_SIZE
                        
            #todo: these caches are global, only let the root RequestProcessor set these value                   
            fileCache.maxFileSize = kw.get('MAX_CACHEABLE_FILE_SIZE', 0)                        
            self.expCache.capacity = self.XPATH_PARSER_CACHE_SIZE
            fileCache.capacity = self.FILE_CACHE_SIZE
            fileCache.hashValue = lambda path: getFileCacheKey(path, fileCache.maxFileSize)
                    
            self.PATH = kw.get('PATH', self.PATH)
            
            #security and authorization settings:
            self.SECURE_FILE_ACCESS= kw.get('SECURE_FILE_ACCESS', True)
            self.disabledContentProcessors = kw.get('disabledContentProcessors',
                                            self.DefaultDisabledContentProcessors)            
            initConstants(['authorizeAdditions', 'authorizeRemovals',],None)            
            self.authorizeMetadata = kw.get('authorizeMetadata', lambda *args: True)
            self.validateExternalRequest = kw.get('validateExternalRequest', lambda *args: True)            
            self.getPrincipleFunc = kw.get('getPrincipleFunc', lambda kw: '')
            self.authorizeXPathFuncs = kw.get('authorizeXPathFuncs', lambda self, funcMap, kw: funcMap)
            
            self.MODEL_UPDATE_PREDICATE = kw.get('MODEL_UPDATE_PREDICATE')
            self.MODEL_RESOURCE_URI = kw.get('MODEL_RESOURCE_URI', self.BASE_MODEL_URI)
            
            self.cmd_usage = DEFAULT_cmd_usage + kw.get('cmd_usage', '')
            #todo: shouldn't these be set before so it doesn't override config changes?:
            self.NOT_CACHEABLE_FUNCTIONS.update(DefaultNotCacheableFunctions)
            if self.LIVE_ENVIRONMENT:
                self.NOT_CACHEABLE_FUNCTIONS.update( EnvironmentDependentFunctions )
                self.styleSheetCache.isValueCacheableCalc = isStyleSheetCacheable
            else:
                self.styleSheetCache.sideEffectsFunc = self.styleSheetParserSideEffectsFunc
                self.styleSheetCache.sideEffectsCalc = self.styleSheetParserSideEffectsCalc
                
            self.nsMap.update(DefaultNsMap)

            self.contentProcessors = dict([ (x.uri, x) for x in
                                ContentProcessors.DefaultContentProcessors])
            self.contentProcessors.update( dict([ (x.uri, x) for x in
                                kw.get('contentProcessors', [])]) )

            self.authorizeContentProcessorsDefault = None
            for uri, authFunc in kw.get('authorizeContentProcessors', {}).items():
                if uri == 'default':
                    self.authorizeContentProcessorsDefault = authFunc                    
                cp = self.contentProcessors.get(uri)
                if cp:
                    #pass self so the signature match with the method 
                    cp.authorize = lambda *args: authFunc(cp, *args) 
            
            for disable in self.disabledContentProcessors:                
                if self.contentProcessors.get(disable):
                    del contentProcessors[disable]
            
            self.extFunctions.update(DefaultExtFunctions)
            
            if kw.get('configHook'):
                kw['configHook'](kw)

        def getLock(self):
            '''
            acquires the class lock.
            Call release() on the returned lock object to release it
            (Though this is not absolutely required since it will try to be released when garbage collected.)
            '''
            assert self.lock
            return glock.LockGetter(self.lock)

        def loadModel(self):        
            if self.source:
                source = self.source
            else:
                source = self.STORAGE_PATH
            if not source:
                self.log.warning('no model path given and STORAGE_PATH not set -- model is read-only.')
            elif not os.path.isabs(source): #todo its possible for source to not be file path -- this will break that
                source = os.path.join( self.baseDir, source)

            if not self.lock:            
                lockName = 'r' + `hash(repr(source))` + '.lock'
                self.lock = glock.GlobalLock(lockName)
                
            lock = self.getLock()            
            model = self.initModel(source, StringIO.StringIO(self.STORAGE_TEMPLATE))
                    
            if self.APPLICATION_MODEL:
                appmodel, appdb = utils.DeserializeFromN3File(StringIO.StringIO(self.APPLICATION_MODEL), scope='application')
                model = RxPath.MultiModel(model, RxPath.FtModel(appmodel))
                
            if self.transactionLog:
                model = RxPath.MirrorModel(model, RxPath.initFileModel(self.transactionLog, StringIO.StringIO('')) )
                
            self.revNsMap = dict(map(lambda x: (x[1], x[0]), self.nsMap.items()) )#reverse namespace map #todo: bug! revNsMap doesn't work with 2 prefixes one ns
            self.rdfDom = RxPath.createDOM(model, self.revNsMap)
            
            self.rdfDom.queryCache = MRUCache.MRUCache(self.XPATH_CACHE_SIZE, lambda compExpr, context: compExpr.evaluate(context),
                    lambda compExpr, context: getKeyFromXPathExp(compExpr, context, self.NOT_CACHEABLE_FUNCTIONS),
                    processXPathExpSideEffects, calcXPathSideEffects)
            self.rdfDom.actionCache = MRUCache.MRUCache(self.ACTION_CACHE_SIZE)
            lock.release()
    ##        outputfile = file('debug.xml', "w+", -1)
    ##        from Ft.Xml.Domlette import Print, PrettyPrint
    ##        outputfile.write('<root>')
    ##        PrettyPrint(self.rdfDom, outputfile, asHtml=1)
    ##        outputfile.write('</root>')
    ##        #outputfile.write(self.dump())
    ##        outputfile.close()
    ##        self.dump()
            self.runActions('load-model')

    ###########################################
    ## request handling engine
    ###########################################
            
        def runActions(self, triggerName, kw = None):
            '''        
            Retrieve the action sequences associated with the triggerName.    
            Each Action has a list of RxPath expressions that are evaluated after 
            mapping runActions keyword parameters to RxPath variables.  If an
            expression returns a non-empty nodeset the Action is invoked and the
            value it returns is passed to the next invoked Action until the end of
            the sequence, upon which the final return value is return by this function.
            '''
            if kw is None: kw = {}            
            sequence = self.actions.get(triggerName)
            if sequence:
                try:
                    #this is a stack in case runActions is re-entrant
                    if self.previousResolvers is None:
                        self.previousResolvers = []                    
                    self.previousResolvers.append( InputSource.DefaultFactory.resolver )
                    InputSource.DefaultFactory.resolver = self.resolver
                    return self.doActions(sequence, kw)
                finally:
                    InputSource.DefaultFactory.resolver = self.previousResolvers.pop()
                    
        COMPLEX_REQUESTVARS = ['__requestor__', '__server__','_request','_response',
                               '_session', '_prevkw', '__argv__', '_errorInfo']
        
        STOP_VALUE = u'2334555393434302' #hack
        
        def mapToXPathVars(self, kw):
            '''map request kws to xpath vars (include http request headers)'''
            extFuncs = self.extFunctions.copy()
            extFuncs.update({
            (RXWIKI_XPATH_EXT_NS, 'assign-metadata') : lambda context, name, val: AssignMetaData(kw, context, name, val, recordChange = '_metadatachanges'),
            (RXWIKI_XPATH_EXT_NS, 'remove-metadata') : lambda context, name: RemoveMetaData(kw, context, name, recordChange = '_metadatachanges'),
            (RXWIKI_XPATH_EXT_NS, 'has-metadata') : lambda context, name: HasMetaData(kw, context, name),
            (RXWIKI_XPATH_EXT_NS, 'get-metadata') : lambda context, name, default=False: GetMetaData(kw, context, name, default),
            (RXWIKI_XPATH_EXT_NS, 'evaluate') : self.Evaluate
            })        
            #add most kws to vars (skip references to non-simple types):
            #todo: use of toXPathDataType is inconsistent -- should use throughout -- especially with prevkw
            vars = dict( [( (None, x[0]), toXPathDataType(x[1], self.rdfDom) ) for x in kw.items()\
                          if x[0] not in self.COMPLEX_REQUESTVARS and x[0] != '_metadatachanges'] )
            #magic constants:
            vars[(None, 'STOP')] = self.STOP_VALUE
            vars[(None, '_APP_BASE')] = self.appBase
            vars[(None, 'BASE_MODEL_URI')] = self.BASE_MODEL_URI        
            #http request and response vars:
            request = kw.get('_request', None)
            if request:
                vars[(None, '_url')] = request.browserUrl
                vars[(None, '_base-url')] = request.base            
                vars[(None, '_path')] = request.browserPath
                vars[(None, '_url-query')] = request.browserQuery
                vars[(None, '_method')] = request.method
                #print kw['_name'], request.browserUrl, request.browserBase, request.browserPath
                vars.update( dict(map(lambda x: ((RXIKI_HTTP_REQUEST_HEADER_NS, x[0]), x[1]), request.headerMap.items()) ) )
                vars.update( dict(map(lambda x: ((RXIKI_REQUEST_COOKIES_NS, x[0]), x[1].value), request.simpleCookie.items()) ) )
            response = kw.get('_response', None)
            if response:
                vars.update( dict(map(lambda x: ((RXIKI_HTTP_RESPONSE_HEADER_NS, x[0]), x[1]), response.headerMap.items()) ) )
                vars.update( dict(map(lambda x: ((RXIKI_RESPONSE_COOKIES_NS, x[0]), x[1].value), response.simpleCookie.items()) ) )
            session = kw.get('_session', None)
            if session:
                vars.update( dict(map(lambda x: ((RXIKI_SESSION_NS, x[0]), x[1]), session.items()) ) )
            prevkw = kw.get('_prevkw', None)
            if prevkw:
                vars.update( dict(map(lambda x: ((RXIKI_PREV_NS, x[0]), x[1]), prevkw.items()) ) )
            errorkw = kw.get('_errorInfo', None)
            if errorkw:
                errorItems = [((RXIKI_ERROR_NS, x[0]), x[1]) for x in errorkw.items()
                                 if x[0] not in ['type', 'value', 'traceback'] ] #skip non-simple types
                vars.update( dict(errorItems) )
            #print 'vars', vars
            return vars, extFuncs

        def evalXPath(self, xpath,  vars=None, extFunctionMap = None, node = None):
            #print 'eval node', node        
            try:
                node = node or self.rdfDom
                if extFunctionMap is None:
                    extFunctionMap = self.extFunctions
                if vars is None:
                   vars = {}
                vars[ (None, '__context')] = [ node ] #we also set this in doActions()
                    
                context = XPath.Context.Context(node, varBindings = vars,
                            extFunctionMap = extFunctionMap, processorNss = self.nsMap)
                return RxPath.evalXPath(xpath, context, expCache = self.expCache,
                        queryCache=getattr(self.rdfDom, 'queryCache', None))
            except (RuntimeException), e:
                if e.errorCode == RuntimeException.UNDEFINED_VARIABLE:                            
                    self.log.debug(e.message) #undefined variables are ok
                    return None
                else:
                    raise

        def __assign(self, actionvars, kw, contextNode):
            context = XPath.Context.Context(None, processorNss = self.nsMap)
            for name, exps, assignEmpty in actionvars:
                vars, extFunMap = self.mapToXPathVars(kw)            
                for exp in exps:
                    result = self.evalXPath(exp, vars=vars, extFunctionMap = extFunMap, node = contextNode)                    
                    if result:
                        break
                #print name, exp; print result
                if assignEmpty or result:
                    AssignMetaData(kw, context, name, result, authorize=False)
                    #print name, result, contextNode
                
        def doActions(self, sequence, kw = None, contextNode = None, retVal = None):
            if kw is None: kw = {}
            result = None
            #todo: reexamine this logic
            if isinstance(contextNode, type([])) and contextNode:
                contextNode = contextNode[0]        

            kw['__requestor__'] = self.requestDispatcher
            kw['__server__'] = self
            kw['__context'] = [ contextNode ]  #__context so access to the rdf database is available to xsl, xupdate, etc. processing

            try:
                for action in sequence:            
                    if action.requiresContext:
                        if not contextNode: #if the next action requires a contextnode and there isn't one, end the sequence
                            return retVal

                    self.__assign(action.preVars, kw, contextNode)
                                        
                    for xpath in action.queries:
                        #print xpath, 'contextNode', contextNode
                        #todo add _root variable also? 
                        vars, extFunMap = self.mapToXPathVars(kw)
                        result = self.evalXPath(xpath, vars=vars, extFunctionMap = extFunMap, node = contextNode)
                        if result is self.STOP_VALUE:#for $STOP
                            break
                        if result: #todo: != []: #if not equal empty nodeset (empty strings ok)
                            if not action.action: #if no action is defined this action resets the contextNode instead
                                assert type(result) == type([]) and len(result) #result must be a nonempty nodeset
                                contextNode = result[0]
                                kw['__context'] = [ contextNode ]
                                self.log.debug('context changed: %s', result)
                                assert action.matchFirst #why would you want to evalute every query in this case?
                                break
                            else:
                                if not action.canReceiveStreams and hasattr(retVal, 'read'):
                                    retVal = retVal.read()
                                if action.forEachNode:
                                    assert type(result) == type([]), 'result must be a nodeset'
                                    if action.depthFirst:
                                        #we probably want the reverse of document order (e.g. the deepest first)
                                        result = result[:] #copy the list since it might have been cached
                                        result.reverse()
                                        #print '!!!res', contextNode.childNodes
                                    for node in result:
                                        if kw.get('_metadatachanges'): del kw['_metadatachanges']
                                        retVal = self.rdfDom.actionCache.getOrCalcValue(action.action,
                                            [node], kw, contextNode, retVal, hashCalc=action.cacheKeyPredicate,
                                            sideEffectsCalc=action.sideEffectsPredicate,
                                            sideEffectsFunc=action.sideEffectsFunc,
                                            isValueCacheableCalc=action.isValueCacheableCalc)
                                else:
                                    if kw.get('_metadatachanges'): del kw['_metadatachanges']
                                    retVal = self.rdfDom.actionCache.getOrCalcValue(action.action,
                                                result, kw, contextNode, retVal,
                                                hashCalc=action.cacheKeyPredicate,
                                                sideEffectsCalc=action.sideEffectsPredicate,
                                                sideEffectsFunc=action.sideEffectsFunc,
                                                isValueCacheableCalc=action.isValueCacheableCalc)
                            if action.matchFirst:
                                break
                    self.__assign(action.postVars, kw, contextNode)
            except:
                if self.inErrorHandler or kw.get('_noErrorHandling'):#avoid endless loops
                    raise
                else:
                    self.inErrorHandler += 1
                try:
                    if isinstance(sys.exc_info()[1], DoNotHandleException):
                        raise
                    errorSequence = self.actions.get('on-error')
                    if errorSequence and sequence is not errorSequence:
                        import traceback as traceback_module
                        def extractErrorInfo(type, value):
                            #these maybe either the nested exception or the wrapper exception
                            message = str(value)
                            module = '.'.join( str(type).split('.')[:-1] )
                            name = str(type).split('.')[-1]
                            errorCode = getattr(value, 'errorCode', '')
                            return message, module, name, errorCode
                        
                        def getErrorKWs():                            
                            type, value, traceback = sys.exc_info()
                            if isinstance(value, utils.NestedException) and value.useNested:
                                 message, module, name, errorCode = extractErrorInfo(
                                     value.nested_exc_info[0], value.nested_exc_info[1])
                            else:
                                message, module, name, errorCode = extractErrorInfo(type, value)                            
                            #these should always be the wrapper exception:     
                            fileName, lineNumber, functionName, text = traceback_module.extract_tb(traceback, 1)[0]
                            details = ''.join( traceback_module.format_exception(type, value, traceback) )
                            return locals()
                        kw['_errorInfo'] = getErrorKWs()
                        self.log.warning("invoking error handler on exception", exc_info=1)
                        #todo provide a protocol for mapping exceptions to XPath variables, e.g. line # for parsing errors
                        #kw['errorInfo'].update(self.extractXPathVars(kw['errorInfo']['value']) )
                        return self.callActions(errorSequence, self.globalRequestVars, result, kw, contextNode, retVal)
                    else:
                        raise
                finally:
                    self.inErrorHandler -= 1
            return retVal

        def callActions(self, actions, globalVars, resultNodeset, kw, contextNode, retVal):
            '''
            process another set of actions using the current context as input,
            but without modified the current context.
            Particularly useful for template processing.
            '''
            prevkw = kw.get('_prevkw', {}).copy() #merge previous prevkw, overriding vars as necessary
            templatekw = {}

            #globalVars are variables that should be present through out the whole request
            #so copy them into templatekw instead of _prevkw
            globalVars = self.COMPLEX_REQUESTVARS + globalVars

            for k, v in kw.items():
                #initialize the templates variable map copying the core request kws
                #and copy the r est (the application specific kws) to _prevkw
                #this way the template processing doesn't mix with the orginal request
                #but are made available in the 'previous' namespace (think of them as template parameters)
                if k in globalVars:
                    templatekw[k] = v
                elif k != '_metadatachanges':
                    prevkw[k] = v
            templatekw['_prevkw'] = prevkw
            if hasattr(retVal, 'read'): #todo: delay doing this until $_contents is required
                retVal = retVal.read()            
            templatekw['_contents'] = retVal
            
            #nodeset containing current resource
            templatekw['_previousContext'] = [ contextNode ]
            templatekw['_originalContext'] = kw.get('_originalContext', templatekw['_previousContext'])
            #use the resultNodeset as the contextNode for call action
            return self.doActions(actions, templatekw, resultNodeset) 

        def Evaluate(self, context, expr):
            ''' Like 4Suite's 'evaluate' extension function but adds
            all the configured namespace mappings to the context. '''
            
            oldNss = context.processorNss.copy()
            context.processorNss.update(self.nsMap)
            DOMnsMap = dict([(y, x) for x,y in getattr(context.node.ownerDocument, 'nsRevMap', {}).items()] )
            context.processorNss.update(DOMnsMap)
            xpath = StringValue(expr)
            #use if caches available
            compExpr = self.expCache.getValue(xpath) #todo: nsMap should be part of the key -- until then clear the cache if you change that!        
            queryCache= getattr(context.node.ownerDocument, 'queryCache', None)
            if queryCache:
                res = queryCache.getValue(compExpr, context)         
            else:
                res = compExpr.evaluate(context)
            context.processorNss = oldNss    
            return res
                
    ###########################################
    ## content processing 
    ###########################################        
        def processContents(self, result, kw, contextNode, contents, dynamicFormat = False):        
            if contents is None:
                return contents        
            formatType = StringValue(result)        
            self.log.debug('enc %s', formatType)
            if kw.get('_staticFormat'):
                kw['__lastFormat']=formatType
                staticFormat = True
            else:
                staticFormat = False            
            
            while formatType:
                contentProcessor = self.contentProcessors.get(formatType)
                assert contentProcessor, formatType
                authorizeContentFunc = contentProcessor.authorize or self.authorizeContentProcessorsDefault
                if authorizeContentFunc:
                    authorizeContentFunc(contents, formatType, kw, dynamicFormat)        
                
                useCache = True
                if hasattr(contents, 'read'):            
                    if not contentProcessor.processStream: #contentProcessor can't handle streams
                        contents = contents.read()  
                    elif contentProcessor.getCachePredicate and self.maxCacheableStream:
                        #if the contentProcessor is cachable 
                        #try to read up to the maximum size we want to read at a time
                        #if the stream isn't bigger than we can use the cache
                        value = contents.read(self.maxCacheableStream + 1)        
                        if len(value) > self.maxCacheableStream:
                            #too big to read all at once
                            #use CombinedStream since we've already read from the stream            
                            stream = ContentProcessors.CombinedReadOnlyStream(StringIO(value), contents), -1
                            retVal = contentProcessor.processStream(result, kw, contextNode, stream)
                            useCache = False                
                        else:
                            contents = value
                    else:
                        retVal = contentProcessor.processStream(result, kw, contextNode, contents)
                        useCache = False                
                            
                if useCache:
                    kw['_preferStreamThreshhold'] = self.rdfDom.actionCache.maxValueSize
                    retVal = self.rdfDom.actionCache.getOrCalcValue(                            
                        contentProcessor.processContents,
                        result, kw, contextNode, contents,
                        hashCalc=contentProcessor.getCachePredicate or notCacheableKeyPredicate,
                        sideEffectsFunc=contentProcessor.processSideEffects,
                        sideEffectsCalc=contentProcessor.getSideEffectsPredicate,
                        isValueCacheableCalc=contentProcessor.isValueCacheablePredicate )
                    del kw['_preferStreamThreshhold']

                if type(retVal) is tuple:
                    #print retVal
                    contents, formatType = retVal
                    if staticFormat:
                        return contents
                    else:
                        dynamicFormat = True
                        kw['__lastFormat']=formatType
                else:
                    kw['__lastFormat']=formatType                    
                    return retVal
            return contents
            
            #trigger = kw.get('_update-trigger')
            #if trigger:
            #    del kw['_update-trigger']
            #    self.runActions(trigger, kw)
    
        def authorizeByDigest(self, contents, *args):
            '''Raises a NotAuthorized exception if the SHA1 digest of
            the contents argument is not present in the dictionary
            assigned to the "authorizationDigests" config variable.'''
            
            digest = utils.shaDigestString(contents)
            if not self.authorizationDigests.get(digest):
                raise NotAuthorized(
                 'This application is not configured to process the content with a SHA1 digest of '
                 + digest)

        def processContentsXPath(self, context, contents, formatURI, *args):
            ''' This XPath extention function lets you invoke the
            content processors on an arbitrary string of content.
            Because of potential security risks, it is not added by
            default to the external function namespace and so needs to
            be added to application's "extFunctions" dictionary. '''
            
            kw = {}
            kw['__requestor__'] = self.requestDispatcher
            kw['__server__'] = self

            kwIter = iter(args)
            try:
                while 1:
                    n, v = kwIter.next(), kwIter.next()
                    kw[ n ] = v
            except StopIteration:
                pass
            #print >>sys.stderr, 'kw', kw
            
            contextNode = kw.get('__context')
            if contextNode:
                contextNode = contextNode[0]
            else:
                contextNode = context.node
            return self.processContents(formatURI, kw, contextNode, contents, True)    
            
        def processRxSLT(self, stylesheet, kw=None):
            '''
            process RxSLT
            '''
            if kw is None: kw = {}        
            vars, funcs = self.mapToXPathVars(kw)
            self.authorizeXPathFuncs(self, funcs, kw)
            
            processor = RxPath.RxSLTProcessor()
            contents = RxPath.applyXslt(self.rdfDom, stylesheet, vars, funcs,
                        baseUri='path:',styleSheetCache=self.styleSheetCache,
                                        processor=processor)
            format = kw.get('_nextFormat')            
            if format is None:
                format = self._getFormatFromStyleSheet(processor.stylesheet)
            else:
                del kw['_nextFormat']
            return (contents, format)
                    
        def executePython(self, cmds, kw = None):
            if kw is None: kw = {}
            #todo: thread synchronize
            #print cmds
            output = StringIO.StringIO()
            sys_stdout = sys.stdout
            sys.stdout = output
            try:        
                #exec only likes unix-line feeds
                exec cmds.strip().replace('\r', '\n')+'\n' in globals(), kw
                contents = output.getvalue()
            except:
                sys.stdout = sys_stdout
                self.log.exception('got this far before exception %s', output.getvalue())
                raise
            else:   #can't have a finally here
                sys.stdout = sys_stdout
            return contents

        def processPython(self, contents, kw):
            locals = {}
            locals['__requestor__'] = self.requestDispatcher
            locals['__server__'] = self
            locals['__kw__'] = kw
            
            contents = self.executePython(contents, locals)             
            if '_nextFormat' in kw: #doc
                nextFormat = kw['_nextFormat']
                del kw['_nextFormat']
                return contents, nextFormat
            else:
                return contents

        def _getFormatFromStyleSheet(self,styleSheet):
            '''
            Find the output method specified in the <xsl:output>, if present.
            '''
            outputElements = [child for child in styleSheet.children \
                if child.expandedName[0] == XSL_NAMESPACE and \
                    child.expandedName[1] == 'output' and child._method]
           
            if outputElements and outputElements[-1]._method[1] not in ('xml', 'html'):
                return None #text or unknown output method -- no further processing
            else:
                return 'http://rx4rdf.sf.net/ns/wiki#item-format-xml'
            
        def processXslt(self, styleSheetContents, contents, kw = None, uri='path:'):
            if kw is None: kw = {}
            vars, extFunMap = self.mapToXPathVars(kw)
            self.authorizeXPathFuncs(self, extFunMap, kw)
            
            from Ft.Xml.Xslt.Processor import Processor
            processor = Processor()
            #processor = utils.XsltProcessor()        
            #def contextHook(context): context.varBindings[(None, '_kw')] = kw
            #processor.contextSetterHook = contextHook
            
            #print 'xslt ', uri
            #print 'xslt template:', styleSheetContents
            #print 'xslt source: ', contents
            styleSheet = self.styleSheetCache.getValue(styleSheetContents, uri)
            processor.appendStylesheetInstance( styleSheet, uri) 
            for (k, v) in extFunMap.items():
                namespace, localName = k
                processor.registerExtensionFunction(namespace, localName, v)
            try:
                if type(contents) == type(u''):
                    contents = contents.encode('utf8')
                contents = processor.run(InputSource.DefaultFactory.fromString(contents, uri),
                                     topLevelParams = vars)
            except Ft.Xml.Xslt.XsltException:
                #if Error.SOURCE_PARSE_ERROR
                #probably because there's no root element, try wrapping in a <div>
                if contents[:5] == '<?xml':
                    contents = '<div>'+contents[contents.find('?>')+2:]+'</div>'
                else:
                    contents = '<div>'+contents+'</div>'
                contents = processor.run(InputSource.DefaultFactory.fromString(contents, uri),
                                 topLevelParams = vars)
            format = kw.get('_nextFormat')
            if format is None:
                format = self._getFormatFromStyleSheet(styleSheet)
            else:
                del kw['_nextFormat']            
            return (contents, format)

        def styleSheetParserSideEffectsCalc(self, cacheValue, *args):
            '''
            We use sideEffects here to store a key based on the value
            (we can't store this in the key because the key has to be calculated before the value)
            SideEffectsFunc will raise KeyError if current key doesn't match
            '''
            if not cacheValue.standAlone: #should be a StylesheetElement created in raccoon.styleSheetValueCalc
                #if the stylesheet relies on other files (e.g. through xsl:import)
                #we want to include the state of the store so that when it changes we invalidate this key
                #and recalculate the value -- just in case one of those referenced files have changed                
                key = [id(self.rdfDom), getattr(self.rdfDom, 'revision', None)]
            else:
                key = None
            return key

        def styleSheetParserSideEffectsFunc(self, cacheValue, sideEffects, *args):                    
            if sideEffects:
                key = [id(self.rdfDom), getattr(self.rdfDom, 'revision', None)]
                if sideEffects != key:
                    #if the model has changed, raise a KeyError so we reparse the stylesheet
                    raise KeyError
            else:
                assert cacheValue.standAlone

    ###########################################
    ## update processing (to be refactored)
    ###########################################        

        def addUpdateStatement(self, rdfDom):
            '''
            Add a statement representing the current state of the model.
            This is a bit of hack right now, just generates a random value.
            '''
            modelNode = rdfDom.findSubject(self.MODEL_RESOURCE_URI)
            if not modelNode:
                self.log.warning("model resource not found: %s" % self.MODEL_RESOURCE_URI)
                return
            for p in modelNode.childNodes:
                if p.stmt.predicate == self.MODEL_UPDATE_PREDICATE:
                    modelNode.removeChild(p)
            object = RxPath.generateBnode()[RxPath.BNODE_BASE_LEN:]
            stmt = RxPath.Statement(modelNode.uri, self.MODEL_UPDATE_PREDICATE,
                                 object, objectType=RxPath.OBJECT_TYPE_LITERAL)
            RxPath.addStatements(rdfDom, [stmt])
        
        def xupdateRDFDom(self, rdfDom, xupdate=None, kw=None, uri=None):
            '''execute the xupdate script on the specified RxPath DOM
            '''
            kw = kw or {}
            baseUri= uri or 'path:'
            vars, funcs = self.mapToXPathVars(kw)
            #don't do an authorization check for the XPath functions
            #because we don't other authorization for xupdate and
            #we need to call XUpdate on behalf of others 
            #self.authorizeXPathFuncs(self, funcs, kw)
            output = StringIO.StringIO()
            rdfDom.begin()        
            try:
                RxPath.applyXUpdate(rdfDom, xupdate, vars, funcs,
                                    uri=baseUri, msgOutput=output)
                if self.MODEL_UPDATE_PREDICATE:
                    self.addUpdateStatement(rdfDom)            
            except:
                rdfDom.rollback()
                raise
            else:
                rdfDom.commit(source=self.getPrincipleFunc(kw))
            return output.getvalue()            
            
        def processXUpdate(self, xupdate=None, kw=None, uri=None):
            '''execute the xupdate script, updating the server's model
            '''        
            lock = self.getLock()        
            try:
                return self.xupdateRDFDom(self.rdfDom, xupdate, kw, uri)
            finally:
                lock.release()
                
        def processRxML(self, xml, resources=None, source=''):
            '''        
            Update the model with the RxML document.
            
            The resources is a list of resources originally contained in
            RxML document before it was edited. If present, this list is
            used to create a diff between those resources statements in
            the model and the statements in the current RxML doc.
            
            If resources is None, the RxML statements are treated as new
            to the model and bNode labels are renamed if they are used in
            the existing model. '''
            import rxml
            rxmlDom  = rxml.rxml2RxPathDOM(StringIO.StringIO(xml))
            authorizeTuple = []
            def authorizeHook(*args):
                authorizeTuple.append(args)

            if resources is None:
                #no resources specified -- just add all the statements            
                newStatements, removedNodes = RxPath.addDOM(self.rdfDom, rxmlDom,
                                                            authorizeHook)
            else:
                newStatements, removedNodes = RxPath.mergeDOM(self.rdfDom, rxmlDom,
                                                resources, authorizeHook)
            return self.updateDom(newStatements, removedNodes, source, authorizeTuple[0])

        def saveRxML(self, context, contents, user=None, about=None):
          ''' XPath extension function for saving RxML. Because of
          potential security risks, it is not added by default to the
          external function namespace and so needs to be added to
          application's "extFunctions" dictionary. '''
          
          try:
              import zml
              xml = zml.zmlString2xml(contents, mixed=False, URIAdjust = True)#parse the zml to xml
                        
              if isinstance(about, ( types.ListType, types.TupleType ) ):            
                  #about may be a list of text nodes, convert to a list of strings
                  about = [StringValue(x) for x in about]
              elif about is not None:
                  about = [ about ]
              xml ='<rx:rx>'+ xml+'</rx:rx>'
              self.processRxML(xml, about, source=user)
          except NotAuthorized:
            raise
          except:
            self.log.exception("metadata save failed")
            raise
                
        def updateDom(self, addStmts, removedNodes=None, source='', authorize=None):
            '''update our DOM
            addStmts is a list of Statements to add
            removedNodes is a list of RxPath nodes (either subject or predicate nodes) to remove
            '''
            removedNodes = removedNodes or []
            lock = self.getLock()        
            self.rdfDom.begin()
            #log.debug('removing %s' % removeResources)
            try:
                if authorize and source and self.authorizeRemovals:
                    #we must authorize the removes while their still in the DOM
                    #(the authorize function needs to know their relations with the DOM)
                    self.authorizeRemovals(authorize[0],authorize[1],authorize[2], source)            
                #delete the statements or whole resources from the dom:            
                for node in removedNodes:
                    node.parentNode.removeChild(node)

                if authorize and source and self.authorizeAdditions:
                    #we must authorize the add before they've been added to the DOM
                    #to prevent the addition from messing with the authorizatin logic
                    #note: even though whole list and containers have been removed,
                    #we can still traverse through them if needed because the list resource
                    #should still be present if referenced as the object of a statement
                    self.authorizeAdditions(authorize[0],authorize[1],authorize[2], source)            
                    
                #and add the statements
                RxPath.addStatements(self.rdfDom, addStmts)

                #todo: invoke 'before' triggers
                #todo: invoke validation
                
                if self.MODEL_UPDATE_PREDICATE:
                    self.addUpdateStatement(self.rdfDom) 
            except:
                self.rdfDom.rollback()
                lock.release()
                raise
            else:
                self.rdfDom.commit(source=source)
                lock.release()
            #todo: invoke 'after' triggers

        #dignostic utility
        def dump(self):
            '''returns a xml representation of the rdf model'''
            oldVal = self.rdfDom.globalRecurseCheck
            self.rdfDom.globalRecurseCheck=True
            try:
                strIO = StringIO.StringIO()        
                PrettyPrint(self.rdfDom, strIO, asHtml=1) #asHtml to suppress <?xml ...>
            finally:
                self.rdfDom.globalRecurseCheck=oldVal
            return '<RxPathDOM>'+strIO.getvalue() +'</RxPathDOM>'
            #this is faster than the equivalent:
            styleSheet=r'''<?xml version="1.0" ?>        
            <xsl:stylesheet version="1.0"
                    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:output method="xml" indent="yes" />
            
            <xsl:template match="/">
            <RxPathDOM>
            <xsl:apply-templates />
            </RxPathDOM>
            </xsl:template>
            
            <xsl:template match="node()|@*">
            <xsl:copy>
                <xsl:apply-templates select="node()|@*"/>
            </xsl:copy>
            </xsl:template>
             
            </xsl:stylesheet>'''
            return self.processRxSLT(styleSheet)
        
    class HTTPRequestProcessor(RequestProcessor):
        '''
        Adds functionality for handling an HTTP request.
        '''                
        def handleHTTPRequest(self, name, kw):
            if self.requestsRecord is not None:
                self.requestsRecord.append([ name, kw ])

            request = kw['_request']
            
            #cgi: REQUEST_METHOD [http[s]://] HTTP_HOST : SERVER_PORT REQUEST_URI ? QUERY_STRING            
            #cherrypy:
            #request.base = http[s]:// + request.headerMap['host'] + [:port]
            #request.browserUrl = request.base + / + [request uri]
            #request.path = [path w/no leading or trailing slash]
            #name = urllib.unquote(request.path) or _usevdomain logic

            request.browserBase = request.base + '/'
            
            #the operative part of the url (browserUrl = browserBase + browserPath + '?' + browserQuery)
            path = request.browserUrl[len(request.browserBase):]
            if path.find('?') > -1:
                request.browserPath, request.browserQuery = path.split('?', 1)
            else:
                request.browserPath, request.browserQuery = path, ''

            appBaseLength = len(self.appBase)
            if appBaseLength > 1: #appBase always starts with /
                name = name[appBaseLength:] 
            if not name or name == '/':
                name = self.defaultPageName
            kw['_name'] = name
            #import pprint; pprint.pprint(kw)

            #if the request name has an extension try to set a default mimetype before executing the request
            i=name.rfind('.')
            if i!=-1:
                ext=name[i:]      
                contentType=mimetypes.types_map.get(ext)
                if contentType:
                    kw['_response'].headerMap['content-type']=contentType

            try:                
                rc = {}
                #requestContext is used by all Requestor objects in the current thread 
                rc['_session']=kw['_session']
                rc['_request']=kw['_request']
                self.requestContext.append(rc)
                
                self.validateExternalRequest(kw)
                result = self.runActions('http-request', kw)
                if result is not None: #'cause '' is OK
                    if hasattr(result, 'read'): #we don't yet support streams
                        result = result.read()
                    else:
                        #an http request must return a string (not unicode, for example)
                        result = str(result) 
                    
                    #if mimetype is not set, make another attempt
                    if not kw['_response'].headerMap.get('content-type'):
                        contentType = self.guessMimeTypeFromContent(result)
                        if contentType:
                            kw['_response'].headerMap['content-type']=contentType
                    #todo:
                    #if isinstance(kw['_response'].headerMap.get('status'), (float, int)):
                    #    kw['_response'].headerMap['status'] = self.stdStatusMessages[
                    #                              kw['_response'].headerMap['status']]
                    if self.useEtags:
                        resultHash = kw['_response'].headerMap.get('etag')
                        #if the app already set the etag use that value instead
                        if resultHash is None:
                            import md5                                
                            resultHash = '"' + md5.new(result).hexdigest() + '"'
                            kw['_response'].headerMap['etag'] = resultHash
                        etags = kw['_request'].headerMap.get('if-none-match')
                        if etags and resultHash in [x.strip() for x in etags.split(',')]:
                            kw['_response'].headerMap['status'] = "304 Not Modified"
                            return ''
                    return result
            finally:
                self.requestContext.pop()
                    
            return self.default_not_found(kw)

        def guessMimeTypeFromContent(self, result):
            #obviously this could be improved,
            #e.g. detect encoding in xml header or html meta tag
            #or handle the BOM mark in front of the <?xml 
            #detect binary vs. text, etc.
            test = result[:30].strip().lower()
            if test.startswith("<html") or result.startswith("<!doctype html"):
                return "text/html"
            elif test.startswith("<?xml"):
                return "text/xml"
            elif self.DEFAULT_MIME_TYPE:
                return self.DEFAULT_MIME_TYPE
            else:
                return None

        def default_not_found(self, kw):            
            kw['_response'].headerMap["content-type"]="text/html"
            kw['_response'].headerMap['status'] = "404 Not Found"
            return '''<html><head><title>Error 404</title>
<meta name="robots" content="noindex" />
</head><body>
<h2>HTTP Error 404</h2>
<p><strong>404 Not Found</strong></p>
<p>The Web server cannot find the file or script you asked for. Please check the URL to ensure that the path is correct.</p>
<p>Please contact the server's administrator if this problem persists.</p>
</body></html>'''

        def saveRequestHistory(self):
            if self.requestsRecord:
                requestRecordFile = file(requestRecordFilePath, 'wb')
                pickle.dump(requestsRecord, requestRecordFile)
                requestRecordFile.close()       

    #################################################
    ##command line handling
    #################################################
    def argsToKw(argv, cmd_usage):
        kw = { } 

        i = iter(argv)
        try:
            arg = i.next()
            while 1:
                if arg[0] != '-':
                    raise CmdArgError('missing arg')
                name = arg.lstrip('-')                
                kw[name] = True
                arg = i.next()
                if arg[0] != '-':                    
                    kw[name] = arg
                    arg = i.next()  
        except StopIteration: pass
        #print 'args', kw
        return kw

    DEFAULT_cmd_usage = 'python raccoon.py -l [log.config] -r -d [debug.pkl] -x -s server.cfg -p path -m store.nt -a config.py '
    cmd_usage = '''
    -h this help message
    -s server.cfg specify an alternative server.cfg
    -l [log.config] specify a config file for logging
    -r record requests (ctrl-c to stop recording) 
    -d [debug.pkl]: debug mode (replay the requests saved in debug.pkl)
    -x exit after executing config specific cmd arguments
    -p specify the path (overrides RACCOONPATH env. variable)
    -m [store.nt] load the RDF model
       (default model supports .rdf, .nt, .mk)
    -a config.py run the application specified
    '''

    DEFAULT_LOGLEVEL = logging.INFO

    def main(argv, out=sys.stdout):
        root = None
        try:
            eatNext = False
            mainArgs, rootArgs, configArgs = [], [], []
            for i in range(len(argv)):
                if argv[i] == '-a':
                    rootArgs += argv[i:i+2]
                    configArgs += argv[i+2:] 
                    break        
                if argv[i] in ['-d', '-r', '-x', '-s', '-l', '-h', '--help'] or (eatNext and argv[i][0] != '-'):
                    eatNext = argv[i] in ['-d', '-s', '-l']
                    mainArgs.append( argv[i] )
                else:
                    rootArgs.append( argv[i] )
                    
            if '-l' in mainArgs:
                try:
                    logConfig=mainArgs[mainArgs.index("-l")+1]
                    if logConfig[0] == '-':
                        raise ValueError
                except (IndexError, ValueError):
                    logConfig = 'log.config'        
                if sys.version_info < (2, 3):
                    import logging22.config as log_config
                else:
                    import logging.config as log_config
                if not os.path.exists(logConfig):
                    raise CmdArgError("%s not found" % logConfig)
                log_config.fileConfig(logConfig) #todo document loggers: rhizome, server, raccoon, rdfdom
                #any logger already created and not explicitly specified in the log config file is disabled
                #this seems like a bad design -- certainly took me a while to why understand things weren't getting logged
                #so re-enable the loggers
                for logger in logging.Logger.manager.loggerDict.itervalues():
                    logger.disabled = 0        
            else: #set defaults        
                logging.BASIC_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"
                logging.root.setLevel(DEFAULT_LOGLEVEL)
                logging.basicConfig()

            kw = argsToKw(rootArgs, DEFAULT_cmd_usage)
            kw['argsForConfig'] = configArgs        
            #print 'ma', mainArgs
            if '-h' in mainArgs or '--help' in mainArgs:
                raise CmdArgError('')
            try:
                root = HTTPRequestProcessor(appName='root', **kw)
            except (TypeError), e:
                index = str(e).find('argument') #bad keyword arguement
                if index > -1:                    
                    raise CmdArgError('invalid ' +str(e)[index:])
                else:
                    raise
            if '-d' in mainArgs: 
                try:
                    debugFileName=mainArgs[mainArgs.index("-d")+1]
                    if debugFileName[0] == '-':
                        raise ValueError
                except (IndexError, ValueError):
                    debugFileName = 'debug-wiki.pkl'
                requests = pickle.load(file(debugFileName, 'rb'))
                for request in requests:
                    root.handleHTTPRequest(request[0], request[1])
            elif '-x' not in mainArgs: #if -x (execute cmdline and exit) we're done
                sys.argv = mainArgs #hack for Server
                from rx import Server
                if '-r' in mainArgs:
                    root.requestsRecord = []                    
                    root.requestRecordPath = 'debug-wiki.pkl' 
                #print 'starting server!'
                Server.start_server(root) #kicks off the whole process
                #print 'dying!'
        except (CmdArgError), e:
            print>>out, e
            if root:
                cmd_line = root.cmd_usage
            else:
                cmd_line = DEFAULT_cmd_usage +'[config specific options]'
            print>>out, 'usage:'
            print>>out, cmd_line
            print>>out, cmd_usage

            
