#! /usr/bin/env python
"""
    Engine and helper classes for Raccoon

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
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
    from xml.dom import Node as _Node

    from Ft.Rdf.Drivers import Memory
    import os, time, cStringIO, sys, base64, mimetypes, types
    from Ft.Xml.Lib.Print import PrettyPrint
    from Ft.Xml.XPath.Conversions import StringValue, NumberValue
    from Ft.Xml import SplitQName, XPath, InputSource, EMPTY_NAMESPACE
    from Ft.Xml.XPath import RuntimeException,FT_EXT_NAMESPACE
    from Ft.Xml.Xslt import XSL_NAMESPACE
    from Ft.Lib import Uri, UriException, number

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

    #xpath variable namespaces:
    RXIKI_HTTP_REQUEST_HEADER_NS = 'http://rx4rdf.sf.net/ns/raccoon/http-request-header#'
    RXIKI_HTTP_RESPONSE_HEADER_NS = 'http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
    RXIKI_REQUEST_COOKIES_NS = 'http://rx4rdf.sf.net/ns/raccoon/request-cookie#'
    RXIKI_RESPONSE_COOKIES_NS = 'http://rx4rdf.sf.net/ns/raccoon/response-cookie#'
    RXIKI_SESSION_NS = 'http://rx4rdf.sf.net/ns/raccoon/session#'
    RXIKI_PREV_NS = 'http://rx4rdf.sf.net/ns/raccoon/previous#'
    #XPath extension functions:
    RXWIKI_XPATH_EXT_NS = 'http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'

    ############################################################
    ##XPath extension functions
    ##(can be used with both RxPath/RxSLT/XUpdate and XPath/XSLT
    ############################################################

    #first delete insecure functions from FT's built-in extensions
    from Ft.Xml.XPath import BuiltInExtFunctions
    from Ft.Xml.Xslt import XsltFunctions, XsltContext
    if BuiltInExtFunctions.ExtFunctions.has_key((FT_EXT_NAMESPACE, 'spawnv')):
        for functionDict in [BuiltInExtFunctions.ExtFunctions, XPath.Context.Context.functions,
                             XsltContext.XsltContext.functions]:
            del functionDict[(FT_EXT_NAMESPACE, 'spawnv')]
            del functionDict[(FT_EXT_NAMESPACE, 'system')]
            del functionDict[(FT_EXT_NAMESPACE, 'env-var')]
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
        if not isinstance(nodeset, type([])):
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
        if not isinstance(nodeset, type([])):
            nodset = [ nodeset ]
        return reduce(f, map(NumberValue, nodeset), nanvalue)

    def DocumentAsText(content, url):
        '''
        if the url resolves to a file that contains bytes sequences that are not ascii or utf-8 (e.g. a binary file) this function can not be used in contexts such as xsl:value-of
        however, an raw xpath expression will return a non-unicode string and thus will work in those contexts
        '''
        urlString = StringValue( url )
        if not urlString:
            return [] #return an empty nodeset    
        #file = urllib2.urlopen(urlString) #use InputSource instead so our SiteUriResolver get used
        #print "urlstring", urlString
        file = InputSource.DefaultFactory.fromUri(urlString)
        bytes = file.read()
        #print 'bytes', bytes
        return bytes

    def String2NodeSet(context, string):
        '''Ft.Xml.Xslt.Exslt.Common.NodeSet is not implemented correctly -- this behavior should be part of it'''
        assert type(string) in (type(''), type(u''))
        return [context.node.ownerDocument.createTextNode(string)]

    def Split(context, string, pattern=u' '):
        '''Similar to Ft.Xml.Xslt.Exslt.String.Split but returns a node set of text nodes not 'token' elements.
        Also doesn't depend on a XSLT processor -- any XPath context will do.
        '''
        string = StringValue(string)
        pattern = StringValue(pattern)
        nodeset = []
        if pattern:
            for token in string.split(pattern):
                nodeset.append( context.node.ownerDocument.createTextNode(token) )
        else:
            for ch in string:
                nodeset.append( context.node.ownerDocument.createTextNode(ch) )
        return nodeset

    def GenerateBnode(context, name=None):
        if name is not None:
            name = StringValue(name)
        return utils.generateBnode(name)

    def FileExists(context, uri):
        path = StringValue(uri)
        if path.startswith('file:'):
            path = Uri.UriToOsPath(path)
            return os.path.exists(path)
        else:
            if path.startswith('path:'):
                path = path[len('path:'):]
            for prefix in InputSource.DefaultFactory.resolver.path:
                if os.path.exists(os.path.join(prefix.strip(), path) ):
                    return True
            return False                    

    def OsPath2PathUri(context, path):
        """
        Returns the given OS path as a path URI.
        """
        return SiteUriResolver.OsPathToPathUri(StringValue(path))
        
    def CurrentTime(context):
        #i just want a number i can accurately compare, not obvious how to do that with all the exslt date-time functions
        return "%.3f" % time.time() #limit precision

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
        
        se = Xslt.SortElement.SortElement(None, '','','')
        se._select = XPath.Compile(key)
        se._comparer = se.makeComparer(order,dataType, caseOrder)
        return Xslt.XPathExtensions.SortedExpression(
            DummyExpression(nodeset), [se]).evaluate(context)

    def If(context, cond, v1, v2=None):
        """
        just like Ft.Xml.XPath.BuiltInExtFunctions.If
        but the then and else parameters are strings that evaluated dynamically 
        thus supporting the short circuit logic you expect from if expressions
        """
        from Ft.Xml.XPath import parser
        from Ft.Xml.XPath import Conversions
        #todo: could use caches if available
        if Conversions.BooleanValue(cond):
            return parser.new().parse(Conversions.StringValue(v1)).evaluate(context)
        elif v2 is None:
            return []
        else:
            return parser.new().parse(Conversions.StringValue(v2)).evaluate(context)
        
    def HasMetaData(kw, context, name):
        def _test(local, dict):
            if dict and dict.has_key(local):
                return True
            else:
                return False
        return _onMetaData(kw, context, name, _test, 'has')

    def GetMetaData(kw, context, name, default=False):
        '''
        the advantage of using this instead of a variable reference is that it just returns 0 if the name doesn't exist, not an error
        '''
        def _get(local, dict):
            if dict and dict.has_key(local):
                return dict[local]
            else:
                return default
        return _onMetaData(kw, context, name, _get, 'get')

    def AssignMetaData(kw, context, name, val, recordChange = None, authorize=True):
        '''
        new variable and values don't affect corresponding xpath variable 
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

    def RemoveMetaData(kw, context, name, recordChange = None):
        def _delete(local, dict):
            if dict and dict.has_key(local):
                del dict[local]
                return True
            else:
                return False
        retVal = _onMetaData(kw, context, name, _delete, 'remove')
        if retVal and recordChange:
            kw.setdefault(recordChange, []).append( (context.processorNss, name) )
        return retVal

    _defexception('unusable namespace error')
    _defexception('not authorized')

    def _onMetaData(kw, context, name, func, opname, value=None, authorize=True):
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
            raise NotAuthorized('%s-metadata with %s:%s %s' % (opname, namespace, name, value))

        dict = None
        if not namespace:
            dict = kw
        elif namespace == RXIKI_HTTP_REQUEST_HEADER_NS:
            r = kw.get('_request')
            if r:
                dict = r.headerMap
        elif namespace == RXIKI_HTTP_RESPONSE_HEADER_NS:
            r = kw.get('_response')
            if r:
                dict = r.headerMap        
        elif namespace == RXIKI_REQUEST_COOKIES_NS: #assigning values will be automatically converted to a Morsel
            r = kw.get('_request')
            if r:
                dict = r.simpleCookie
        elif namespace == RXIKI_RESPONSE_COOKIES_NS: #assigning values will be automatically converted to a Morsel
            r = kw.get('_response')
            if r:
                dict = r.simpleCookie 
        elif namespace == RXIKI_SESSION_NS:
            r = kw.get('_session')
            if r is not None:
                dict = r        
        elif namespace == RXIKI_PREV_NS:
            r = kw.get('_prevkw')
            if r is not None:
                dict = r
        else:
            raise UnusableNamespaceError( '%s uses unusable namespace: %s' % (local, namespace) )
        if dict is None:
            log.debug('calling %s-metadata on an unavailable namespace %s' % (opname, namespace) )

        return func(local, dict)

    ############################################################
    ##Racoon defaults
    ############################################################

    DefaultExtFunctions = {
    (RXWIKI_XPATH_EXT_NS, 'string-to-nodeset'): String2NodeSet,
    (RXWIKI_XPATH_EXT_NS, 'openurl'): DocumentAsText,
    (RXWIKI_XPATH_EXT_NS, 'generate-bnode'): GenerateBnode,
    (RXWIKI_XPATH_EXT_NS, 'current-time'): CurrentTime,
    (RXWIKI_XPATH_EXT_NS, 'file-exists'):  FileExists,
    (RXWIKI_XPATH_EXT_NS, 'if'): If,
    (RXWIKI_XPATH_EXT_NS, 'sort'): Sort,
    (RXWIKI_XPATH_EXT_NS, 'ospath2pathuri'): OsPath2PathUri,
    (RXWIKI_XPATH_EXT_NS, 'split'): Split,
    (RXWIKI_XPATH_EXT_NS, 'min'): Min,
    (RXWIKI_XPATH_EXT_NS, 'max'): Max,
    }

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
               'xf' : 'http://xmlns.4suite.org/ext',
               'bnode': RxPath.BNODE_BASE,
            }

    ############################################################
    ##Helper Classes
    ############################################################

    class Requestor(object):
        '''
        Requestor is a helper class that allows python code to invoke a Racoon request as if it was function call
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
            #print 'invoke', kw
            #defaultTriggerName let's have different trigger type per thread
            #allowing site:/// urls to rely on the defaultTriggerName
            triggerName = self.triggerName or self.server.currentRequestTrigger        
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

    class SiteUriResolver(Uri.SchemeRegistryResolver):
        '''
        SiteUriResolver supports the site URI scheme which is used to enable a Racoon request to be invoked via an URL.
        Site URLs typically look like:
            "site:///index"
        or
            "site:///name?param1=value"
        Like the "file" URL scheme, site URLs require three slashes (///) because
        it needs to start with "site://" to indicate this scheme supports hierarchical names (to enable relative URIs, etc.)
        and yet there is no hostname component.
        '''

        def __init__(self, root):
            Uri.SchemeRegistryResolver.__init__(self)
            self.handlers['site'] = self.resolveSiteScheme
            self.supportedSchemes.append('site')
            self.server = root
            self.path=root.PATH.split(os.pathsep)
            self.handlers['path'] = self.resolvePathScheme
            self.supportedSchemes.append('path')
            if root.SECURE_FILE_ACCESS:
                self.handlers['file'] = self.secureFilePathresolve

        def getPrefix(self, path):
            for prefix in self.path:
                if os.path.abspath(path).startswith(os.path.abspath(prefix)):
                    return prefix
            return ''

        def OsPathToPathUri(path):
            fileUri = Uri.OsPathToUri(path)
            return 'path:' + fileUri[len('file:'):].lstrip('/')
        OsPathToPathUri = staticmethod(OsPathToPathUri)

        def _resolveFile(path):
            try:
                stream = open(path, 'rb')
            except IOError, e:
                raise UriException(UriException.RESOURCE_ERROR, path, str(e))
            return stream
        _resolveFile = staticmethod(_resolveFile)

        def secureFilePathresolve(self, uri, base=None):
            if base:
                uri = self.normalize(uri, base)        
            path =  Uri.UriToOsPath(uri)
            for prefix in self.path:
                if os.path.abspath(path).startswith(os.path.abspath(prefix)):
                    if fileCache:#todo: this only works if secure file access is on 
                        return StringIO.StringIO(fileCache.getValue(path))
                    else:
                        return SiteUriResolver._resolveFile(path)                
            raise UriException(UriException.RESOURCE_ERROR, uri, 'Unauthorized') 
            
        def resolvePathScheme(self, uri, base=None):
            path = uri
            if path.startswith('path:'):
                #print 'path', path
                path = uri[len('path:'):]

            unauthorized = False
            for prefix in self.path:
                filepath = os.path.join(prefix.strip(), path)
                #check to make sure the path url was trying to sneak outside the path (i.e. by using ..)
                if self.server.SECURE_FILE_ACCESS:
                    if not os.path.abspath(filepath).startswith(os.path.abspath(prefix)):
                        unauthorized = True
                        continue
                unauthorized = False
                if os.path.exists(filepath):
                    if fileCache:
                        return StringIO.StringIO(fileCache.getValue(filepath))
                    else:
                        return SiteUriResolver._resolveFile(filepath)

            if unauthorized:
                raise UriException(UriException.RESOURCE_ERROR, uri, 'Unauthorized')                 
            raise UriException(UriException.RESOURCE_ERROR, uri, 'Not Found')

        def resolveSiteScheme(self, uri, base=None):
            if base:
                uri = self.normalize(uri, base) 
            paramMap = {}        
            path = str(uri)

            i=path.find('?')
            if i!=-1:
                if path[i+1:]:
                    for _paramStr in path[i+1:].split('&'):
                        _sp=_paramStr.split('=')
                        if len(_sp)==2:
                            _key, _value=_sp
                            import urllib
                            _value=urllib.unquote_plus(_value)
                            if paramMap.has_key(_key):
                                # Already has a value: make a list out of it
                                if type(paramMap[_key])==type([]):
                                    # Already is a list: append the new value to it
                                    paramMap[_key].append(_value)
                                else:
                                    # Only had one value so far: start a list
                                    paramMap[_key]=[paramMap[_key], _value]
                            else:
                                paramMap[_key]=_value
                path = path[:i]
            if path and path[-1]=='/': path=path[:-1] # Remove trailing '/' if any
            if path.startswith('site://'):
                #print 'path', path
                name = path[len('site://'):] #assume we only get requests inside our home path
            else:
                name = path
            while name and name[0]=='/':
                name=name[1:] # Remove starting '/' if any e.g. from site:///
                            
            try:
                #print 'to resolve!', name, ' ', uri, paramMap
                contents = self.server.requestDispatcher.invoke__(name, **paramMap)
                #print 'resolved', name, ': ', contents
                return StringIO.StringIO( str(contents) ) #without the str() unicode values won't be converted correctly
            except AttributeError: #not found
                raise UriException(UriException.RESOURCE_ERROR, uri, 'Not Found')

    def getFileCacheKey(path, maxSize = 0):    
        stats = os.stat(path)
        #raise notcacheable if the size is too big so we don't
        #waste the cache on a few large files
        if maxSize > 0 and stats.st_size > maxSize:
            raise MRUCache.NotCacheable
        return os.path.abspath(path), stats.st_mtime, stats.st_size

    fileCache = MRUCache.MRUCache(0, hashCalc = getFileCacheKey,
                    capacityCalc = lambda k, v: k[2],
                    valueCalc = lambda path: SiteUriResolver._resolveFile(path).read() )

    def defaultActionCacheKeyPredicateFactory(action, cacheKeyPredicate):
        '''    
        returns a predicate to extract a key for the action out of a request
        This function give an action a chance to customize the cacheKeyPredicate for the particulars of the action instance.
        At the very least it must bind the action instance with the cacheKeyPredicate to disambiguate keys from different actions.
        '''
        actionid = id(action) #do this to avoid memory leaks
        return lambda resultNodeset, kw, contextNode, retVal: (actionid, cacheKeyPredicate(resultNodeset, kw, contextNode, retVal) )
        
    def notCacheableKeyPredicate(*args, **kw):
        raise MRUCache.NotCacheable

    class Action(object):    
        def __init__(self, queries, action = None, matchFirst = True, forEachNode = False,
                     depthFirst=True, requiresContext=False, cachePredicate=notCacheableKeyPredicate,
                     sideEffectsPredicate=None, sideEffectsFunc=None, isValueCacheableCalc=None,
                     cachePredicateFactory=defaultActionCacheKeyPredicateFactory):
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

        def assign(self, varName, *exps, **kw):
            '''
            Add a variable and expression list.
            Before the Action is run the each expression evaluated, the first one that returns a non-empty value is assigned to the variable.
            Otherwise, the result of last expression is assigned (so you can choose between '', [], and 0).
            '''
            assert len(exps), 'Action.assign requires at least one expression'
            if kw.get('post', False):
                self.postVars.append( (varName,  exps) )
            else:
                self.preVars.append( (varName,  exps) )
        
    #functions used by the caches
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

    def _getKeyFromXPathExp(compExpr, context, notCacheableXPathFunctions):
        '''
        return the key for the expression given a context.
        The key consists of:
            expr, context.node, (var1, value1), (var2, value2), etc. for each var referenced in the expression
        '''

        key = [ repr(compExpr) ]
        DomDependent = False
        for field in compExpr:
            if isinstance(field, XPath.ParsedExpr.ParsedVariableReferenceExpr):
               value = field.evaluate(context) #may raise RuntimeException.UNDEFINED_VARIABLE
               expanded = _splitKey(field._key, context)
               if type(value) is type([]):
                    value = tuple(value)
                    DomDependent = True
               elif isinstance(value, _Node):
                    DomDependent = True                
               key.append( (expanded, value) )
            elif isinstance(field, XPath.ParsedExpr.FunctionCall):
               DomDependent = True #we could check if its a 'static' function that isn't domdendent
               expandedKey = _splitKey(field._key, context)
               if expandedKey in notCacheableXPathFunctions:
                   keyfunc = notCacheableXPathFunctions[expandedKey]
                   if keyfunc:
                       key += keyfunc(field, context)
                   else:
                       raise MRUCache.NotCacheable
               #else: log.debug("%s cacheable! not in %s" % (str(expandedKey), str(notCacheableXPathFunctions) ) )
            else:
                DomDependent = True
        if DomDependent:
            key += [context.node, id(context.node.ownerDocument), getattr(context.node.ownerDocument, 'revision', None)]
        #print 'returning key', tuple(key)
        return tuple(key)

    def _calcXPathSideEffects(result, compExpr, context):    
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

    def _processXPathExpSideEffects(cacheValue, callList, compExpr, context):
        for function in callList:
            log.debug("performing side effect for %s with args %s" % (function._name, str(function._args) ) )
            function.evaluate(context) #invoke the function with a side effect
        return cacheValue

    def _resetFunctions(compiledExp, *ignoreArgs):
        '''because the function map is not part of the key for the
           expression cache we need to clear out _func field after retrieving
           the expression from the cache, thus forcing _func to be recalculated
           in order to guard against the function map values changing.
        '''
        for field in compiledExp:
            if isinstance(field, XPath.ParsedExpr.FunctionCall):
                print 'clearing ', field._name
                field._func = None

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
          iSrc = InputSource.DefaultFactory.fromString(source, uri)      
          _styReader = StylesheetReader()
          return _styReader.fromSrc(iSrc) #todo: support extElements=self.extElements

    def isStyleSheetCacheable(key, styleSheet, source, uri):
        return getattr(styleSheet, 'standAlone', True)
        
    DefaultNotCacheableFunctions = dict([(x, None) for x in [(RXWIKI_XPATH_EXT_NS, 'get-metadata'),
            (RXWIKI_XPATH_EXT_NS, 'has-metadata'),
            (FT_EXT_NAMESPACE, 'iso-time'),        
            (RXWIKI_XPATH_EXT_NS, 'current-time'),
            ('http://exslt.org/dates-and-times', 'date-time'), #todo: other exslt date-and-times functions but only if no arguments
            (RXWIKI_XPATH_EXT_NS, 'generate-bnode'),
            (FT_EXT_NAMESPACE, 'generate-uuid'),
            #functions that dynamically evaluate expression may have hidden dependencies so they aren't cacheable
            (RXWIKI_XPATH_EXT_NS, 'sort'),
            (RXWIKI_XPATH_EXT_NS, 'if'),
            (FT_EXT_NAMESPACE, 'evaluate'),
            ('http://exslt.org/dynamic', 'evaluate'), ]])
        #what about random? (ftext and exslt) 

    EnvironmentDependentFunctions = dict([(x, None) for x in [ (None, 'document'),
        (RXWIKI_XPATH_EXT_NS, 'openurl'),
        (RXWIKI_XPATH_EXT_NS, 'file-exists') ]])

    def assignVars(self, kw, varlist, default):    
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
        
    ############################################################
    ##Racoon main class
    ############################################################
    class RequestProcessor(object):
        '''        
        '''
        DEFAULT_CONFIG_PATH = 'raccoon-default-config.py'
        lock = None
        defaultDisabledDefaultContentProcessors = ['http://rx4rdf.sf.net/ns/wiki#item-format-python']
                    
        requestContext = utils.createThreadLocalProperty('__requestContext',
            doc='variables you want made available to anyone during this request (e.g. the session)')
                    
        expCache = MRUCache.MRUCache(0, XPath.Compile)#, sideEffectsFunc=_resetFunctions)

        def _setContentProcessorDefaults(self):
            self.DefaultContentProcessors = {
            'http://rx4rdf.sf.net/ns/wiki#item-format-text' : lambda result, kw, contextNode, contents: contents,
            'http://rx4rdf.sf.net/ns/wiki#item-format-binary' : lambda result, kw, contextNode, contents: contents,
            'http://rx4rdf.sf.net/ns/wiki#item-format-xml':
                lambda result, kw, contextNode, contents: self.processMarkup(contents,kw.get('_docpath', kw.get('_name'))),
            'http://www.w3.org/2000/09/xmldsig#base64' :
                lambda result, kw, contextNode, contents: base64.decodestring(contents),
            'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt':
                lambda result, kw, contextNode, contents: self.transform(str(contents.strip()), kw),
            'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate':
                lambda result, kw, contextNode, contents: self.xupdate(str(contents.strip()), kw),
            'http://rx4rdf.sf.net/ns/wiki#item-format-python':
                lambda result, kw, contextNode, contents: self.processPython(contents, kw),
            }

            self.DefaultContentProcessorCachePredicates = {
                'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' : lambda result, kw, contextNode, contents:\
                    self.partialXsltCacheKeyPredicate(contents, None, kw, contextNode, 'path:'),     
                'http://www.w3.org/2000/09/xmldsig#base64' :
                    lambda result, kw, contextNode, contents: contents, #the key is just the contents
                'http://rx4rdf.sf.net/ns/wiki#item-format-xml':
                    lambda result, kw, contextNode, contents: (kw.get('_docpath', kw.get('_name', '')).count('/'), contents)
            }

            self.DefaultContentProcessorSideEffectsFuncs = {
                'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' : self.xsltSideEffectsFunc }
            self.DefaultContentProcessorSideEffectsPredicates ={
                'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' :  self.xsltSideEffectsCalc }
            self.DefaultContentProcessorIsValueCacheablePredicates = {}

        def __init__(self,a=None, m=None, p=None, argsForConfig=None):
            self.requestContext = [{}] #stack of dicts
            configpath = a or self.DEFAULT_CONFIG_PATH
            self.source = m
            self.PATH = p or os.environ.get('RACCOONPATH',os.getcwd())
            
            self.cmd_usage = DEFAULT_cmd_usage
            self._setContentProcessorDefaults()
            self.loadConfig(configpath, argsForConfig)
            self.loadModel()
            self.requestDispatcher = Requestor(self)
            InputSource.DefaultFactory.resolver = SiteUriResolver(self)
            self.handleCommandLine(argsForConfig or [])
                    
        def handleCommandLine(self, argv):
            '''        
            the command line is translated into XPath variables as follows:
            * arguments beginning with a '-' are treated a variable name with its value
            being next argument unless that argument also starts with a '-'
            
            * the whole command line is assigned to the variable '_cmdline'
            '''
            kw = argsToKw(argv, self.cmd_usage)
            kw['_cmdline'] = '"' + '" "'.join(argv) + '"' 
            self.runActions('run-cmds', kw)        
                
        def loadConfig(self, path, argsForConfig=None):
            if not os.path.exists(path):
                raise 'you must specify a config file using -a' #path = self.DEFAULT_CONFIG_PATH

            kw = {}
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
                            
            initConstants( [ 'nsMap', 'extFunctions', 'actions', 'contentProcessors',
                             'NOT_CACHEABLE_FUNCTIONS', 'contentProcessorCachePredicates',
                             'contentProcessorSideEffectsFuncs','contentProcessorSideEffectsPredicates',
                             'contentProcessorIsValueCacheablePredicates'], {} )
            initConstants( [ 'STORAGE_PATH', 'STORAGE_TEMPLATE', 'APPLICATION_MODEL',
                             'DEFAULT_MIME_TYPE', 'transactionLog'], '')
            setattr(self, 'initModel', kw.get('initModel', RxPath.initFileModel))
            initConstants( ['ROOT_PATH'], '/')
            assert self.ROOT_PATH[0] == '/', "ROOT_PATH must start with a '/'"
            initConstants( ['BASE_MODEL_URI'], self.BASE_MODEL_URI)
            self.DEFAULT_TRIGGER = kw.get('DEFAULT_TRIGGER', 'http-request')
            self.__class__.currentRequestTrigger = utils.createThreadLocalProperty(
                '__currentRequestTrigger', initAttr=True, initValue=self.DEFAULT_TRIGGER)
            
            #cache settings:                
            initConstants( ['LIVE_ENVIRONMENT', 'useEtags'], 1)
            initConstants( ['XPATH_CACHE_SIZE','ACTION_CACHE_SIZE'], 1000)
            initConstants( ['XPATH_PARSER_CACHE_SIZE','STYLESHEET_CACHE_SIZE'], 200)
            initConstants( ['FILE_CACHE_SIZE'], 0)#10000000) #~10mb
            fileCache.maxFileSize = kw.get('MAX_CACHEABLE_FILE_SIZE', 0)        
            self.expCache.capacity = self.XPATH_PARSER_CACHE_SIZE
            styleSheetCache.capacity = self.STYLESHEET_CACHE_SIZE
            fileCache.capacity = self.FILE_CACHE_SIZE
            fileCache.hashValue = lambda path: getFileCacheKey(path, fileCache.maxFileSize)
                    
            self.PATH = kw.get('PATH', self.PATH)
            self.SECURE_FILE_ACCESS= kw.get('SECURE_FILE_ACCESS', True)
            self.disabledDefaultContentProcessors = kw.get('disabledDefaultContentProcessors',
                                                self.defaultDisabledDefaultContentProcessors)
            
            initConstants(['authorizeAdditions', 'authorizeRemovals'],None)
            self.authorizeMetadata = kw.get('authorizeMetadata', lambda *args: True)
            self.getPrincipleFunc = kw.get('getPrincipleFunc', lambda kw: '')

            self.MODEL_UPDATE_PREDICATE = kw.get('MODEL_UPDATE_PREDICATE')
            self.MODEL_RESOURCE_URI = kw.get('MODEL_RESOURCE_URI', self.BASE_MODEL_URI)
            
            self.cmd_usage = DEFAULT_cmd_usage + kw.get('cmd_usage', '')
            #todo: shouldn't these be set before so it doesn't override config changes?:
            self.NOT_CACHEABLE_FUNCTIONS.update(DefaultNotCacheableFunctions)
            if self.LIVE_ENVIRONMENT:
                self.NOT_CACHEABLE_FUNCTIONS.update( EnvironmentDependentFunctions )
                styleSheetCache.isValueCacheableCalc = isStyleSheetCacheable
                
            self.nsMap.update(DefaultNsMap)
            
            self.contentProcessors.update(self.DefaultContentProcessors)
            self.contentProcessorCachePredicates.update(self.DefaultContentProcessorCachePredicates)
            self.contentProcessorSideEffectsFuncs.update(self.DefaultContentProcessorSideEffectsFuncs)
            self.contentProcessorSideEffectsPredicates.update(self.DefaultContentProcessorSideEffectsPredicates)
            self.contentProcessorIsValueCacheablePredicates.update(self.DefaultContentProcessorIsValueCacheablePredicates)
            for disable in self.disabledDefaultContentProcessors:
                for cpDict in [self.contentProcessors, self.contentProcessorCachePredicates,
                               self.contentProcessorSideEffectsFuncs,
                               self.contentProcessorSideEffectsPredicates]:
                    if cpDict.get(disable):
                        del cpDict[disable]
            
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
                log.warning('no model path given and STORAGE_PATH not set -- model is read-only.')

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
                    lambda compExpr, context: _getKeyFromXPathExp(compExpr, context, self.NOT_CACHEABLE_FUNCTIONS),
                    _processXPathExpSideEffects, _calcXPathSideEffects)
            self.rdfDom.actionCache = MRUCache.MRUCache(self.ACTION_CACHE_SIZE)
            global styleSheetCache 
            if not styleSheetCache.isValueCacheableCalc:
                #invalidate this cache if we weren't checking for external dependencies
                styleSheetCache = MRUCache.MRUCache(self.STYLESHEET_CACHE_SIZE, styleSheetValueCalc)
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
                return self.doActions(sequence, kw)

        COMPLEX_REQUESTVARS = ['__requestor__', '__server__','_request','_response',
                               '_session', '_prevkw', '__argv__']
        
        STOP_VALUE = 2334555393434302 #hack
        
        def mapToXPathVars(self, kw):
            '''map request kws to xpath vars (include http request headers)'''
            extFuncs = self.extFunctions.copy()
            extFuncs.update({
            (RXWIKI_XPATH_EXT_NS, 'assign-metadata') : lambda context, name, val: AssignMetaData(kw, context, name, val, recordChange = '_metadatachanges'),
            (RXWIKI_XPATH_EXT_NS, 'remove-metadata') : lambda context, name: RemoveMetaData(kw, context, name, recordChange = '_metadatachanges'),
            (RXWIKI_XPATH_EXT_NS, 'has-metadata') : lambda context, name: HasMetaData(kw, context, name),
            (RXWIKI_XPATH_EXT_NS, 'get-metadata') : lambda context, name, default=False: GetMetaData(kw, context, name, default),        
            })        
            #add most kws to vars (skip references to non-simple types):
            vars = dict( [( (None, x[0]), utils.toXPathDataType(x[1], self.rdfDom) ) for x in kw.items()\
                          if x[0] not in self.COMPLEX_REQUESTVARS and x[0] != '_metadatachanges'] )
            #magic constants:
            vars[(None, 'STOP')] = self.STOP_VALUE
            vars[(None, 'ROOT_PATH')] = self.ROOT_PATH        
            vars[(None, 'BASE_MODEL_URI')] = self.BASE_MODEL_URI        
            #http request and response vars:
            request = kw.get('_request', None)
            if request:
                vars[(None, '_url')] = request.browserUrl
                vars[(None, '_base-url')] = request.browserBase            
                vars[(None, '_path')] = request.browserPath
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
            #print 'vars', vars
            return vars, extFuncs

        def evalXPath(self, xpath,  vars=None, extFunctionMap = None, node = None):
            #print 'eval node', node        
            try:
                node = node or self.rdfDom
                if extFunctionMap is None:
                    extFunctionMap = self.extFunctions
                if not vars:
                    context = node
                    vars = { (None, '__context'): [ context ] } #we also set this in doActions()
                    
                context = XPath.Context.Context(node, varBindings = vars,
                            extFunctionMap = extFunctionMap, processorNss = self.nsMap)
                return RxPath.evalXPath(xpath, context, expCache = self.expCache,
                        queryCache=getattr(self.rdfDom, 'queryCache', None))
            except (RuntimeException), e:
                if e.errorCode == RuntimeException.UNDEFINED_VARIABLE:                            
                    log.debug(e.message) #undefined variables are ok
                    return None
                else:
                    raise

        def getStringFromXPathResult(self, result):
            if type(result) in (type(''), type(u'')):
                return result
            elif isinstance(result, type([])):
                if result: #it's a non-empty nodeset
                    if type(result[0]) in (type(''), type(u'')):
                        return result[0]
                    return StringValue(result[0])
                else:
                    return None
            else: #assume its some sort of node
                return StringValue(result)

        def __assign(self, actionvars, kw, contextNode):
            context = XPath.Context.Context(None, processorNss = self.nsMap)
            for name, exps in actionvars:
                vars, extFunMap = self.mapToXPathVars(kw)            
                for exp in exps:
                    result = self.evalXPath(exp, vars=vars, extFunctionMap = extFunMap, node = contextNode)
                    #print name, exp; print result
                    if result:
                        break
                #print name, exp; print result
                AssignMetaData(kw, context, name, result, authorize=False)
                
        def doActions(self, sequence, kw = None, contextNode = None, retVal = None):
            if kw is None: kw = {}
            if isinstance(contextNode, type([])):
                contextNode = contextNode[0]        

            kw['__requestor__'] = self.requestDispatcher
            kw['__server__'] = self
            
            for action in sequence:            
                if action.requiresContext:
                    if not contextNode: #if the next action requires a contextnode and there isn't one, end the sequence
                        return retVal

                self.__assign(action.preVars, kw, contextNode)
                                    
                for xpath in action.queries:
                    #print 'contextNode', contextNode
                    kw['__context'] = [ contextNode ]  #__context so access to the rdf database is available to xsl, xupdate, etc. processing
                    #todo add _root variable also? 
                    vars, extFunMap = self.mapToXPathVars(kw)
                    result = self.evalXPath(xpath, vars=vars, extFunctionMap = extFunMap, node = contextNode)
                    if result == self.STOP_VALUE:#for $STOP
                        break
                    if result: #todo: != []: #if not equal empty nodeset (empty strings ok)
                        if not action.action: #if no action is defined this action resets the contextNode instead
                            assert type(result) == type([]) and len(result) #result must be a nonempty nodeset
                            contextNode = result[0]
                            log.debug('context changed: %s', result)
                            assert action.matchFirst #why would you want to evalute every query in this case?
                            break
                        else:
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
            globalVars = self.COMPLEX_REQUESTVARS + globalVars + ['_docpath', '_name']

            for k, v in kw.items():
                #initialize the templates variable map copying the core request kws
                #and copy the rest (the application specific kws) to _prevkw
                #this way the template processing doesn't mix with the orginal request
                #but are made available in the 'previous' namespace (think of them as template parameters)
                if k in globalVars:
                    templatekw[k] = v
                elif k != '_metadatachanges':
                    prevkw[k] = v
            templatekw['_prevkw'] = prevkw    
            templatekw['_contents'] = retVal
            
            #nodeset containing current resource
            templatekw['_previousContext'] = [ contextNode ]
            templatekw['_orginalContext'] = kw.get('_orginalContext', templatekw['_previousContext'])
            return self.doActions(actions, templatekw, resultNodeset) #the resultNodeset is the contextNode so skip the find resource step
                
    ###########################################
    ## content processing 
    ###########################################
        
        def processContents(self, result, kw, contextNode, contents):        
            if contents is None:
                return contents        
            formatType = self.getStringFromXPathResult(result)        
            log.debug('enc %s', formatType)
            enc = formatType
            while formatType:
                predicate = self.contentProcessorCachePredicates.get(formatType)
                if not predicate:
                    predicate = notCacheableKeyPredicate
                
                retVal = self.rdfDom.actionCache.getOrCalcValue(
                    self.contentProcessors[formatType],
                    result, kw, contextNode, contents,
                    hashCalc=predicate,
                    sideEffectsCalc=self.contentProcessorSideEffectsPredicates.get(formatType),
                    sideEffectsFunc=self.contentProcessorSideEffectsFuncs.get(formatType),
                    isValueCacheableCalc=self.contentProcessorIsValueCacheablePredicates.get(formatType) )            
                if type(retVal) == type(()):
                    contents, formatType = retVal
                    kw['__lastFormat']=formatType
                else:
                    kw['__lastFormat']=formatType
                    return retVal
            return contents
            
            #trigger = kw.get('_update-trigger')
            #if trigger:
            #    del kw['_update-trigger']
            #    self.runActions(trigger, kw)

        class SiteLinkFixer(utils.LinkFixer):
            '''
            Converts site: URLs to external (usually http) URLs.
            Absolute site links ('site:///') are fixed up as follows:
            If a relative url of the current document is specified they will be converted to relative paths.
            e.g. if the relative doc url is 'folder/foo/bar' then the 'site:///' prefix will be replaced with '../../'
            Otherwise it will be replaced with the specified baseurl (which defaults to '/')
            
            Relative site URLs ('site:') just have their 'site:' prefix stripped off
            '''
            def __init__(self, out, url = None, baseurl = '/'):
                utils.LinkFixer.__init__(self, out)
                
                if url:                
                    index = url.find('?')
                    if index > -1:
                        url = url[:index]
                    else:
                        index = url.find('#')
                        if index > -1:
                            url = url[:index]
                    self.rootpath = '../'* url.count('/')
                else:
                    self.rootpath = baseurl
                    
            def needsFixup(self, tag, name, value):
                if not value:
                    return False
                elif tag in ['script', 'style', 'link'] or (not name and value[0] == '<'):
                    #in javascript,style, link (for rss) or comment/PI/doctype
                    return value.find('site:') > -1
                elif name and value.startswith('site:'):#attribute
                    return True
                else:
                    return False

            def doFixup(self, tag, name, value):
                '''
                replaces an absolute site reference with relative path to the root
                '''
                #first replace any absolute site URL prefix with rootpath

                #print 'replace ', value
                value = value.replace('site:///', self.rootpath)
                #print 'with', value
                #for any other site: URLs we assume they're relative and just strip out the 'site:'
                return value.replace('site:', '')

        def processMarkup(self, contents, docpath):
            '''
            fixup any site: URLs that appear in the XML or HTML content
            '''
            out = StringIO.StringIO()
            fixlinks = self.SiteLinkFixer(out, docpath, self.ROOT_PATH)
            fixlinks.feed(contents)
            fixlinks.close()
            return out.getvalue()
            
        def transform(self, stylesheet, kw=None):
            '''
            process RxSLT
            '''
            if kw is None: kw = {}        
            vars, funcs = self.mapToXPathVars(kw)
            
            processor = RxPath.RxSLTProcessor()        
            contents = RxPath.applyXslt(self.rdfDom, stylesheet, vars, funcs, baseUri='path:',
                             styleSheetCache=styleSheetCache, processor = processor)
            format = kw.get('_nextFormat')                    
            if format is None:
                format = self._getFormatFromStyleSheet(processor.stylesheet)
            else:
                del kw['_nextFormat']
            return (contents, format)

        def addUpdateStatement(self, rdfDom):
            '''
            Add a statement representing the current state of the model.
            This is a bit of hack right now, just generates a random value.
            '''
            modelNode = rdfDom.findSubject(self.MODEL_RESOURCE_URI)
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
            output = StringIO.StringIO()
            rdfDom.begin()        
            try:
                RxPath.applyXUpdate(rdfDom, xupdate, vars, funcs,
                                    uri=baseUri, msgOutput=output)
                if self.MODEL_UPDATE_PREDICATE:
                    self.addUpdateStatement(rdfDom)            
            except:
                rdfDom.rollback()
                #application error generated by xupdate:message:
                if getattr(sys.exc_value, 'errorCode', None) == \
                   XUpdate.XUpdateException.STYLESHEET_REQUESTED_TERMINATION:
                    kw['error'] =  sys.exc_value.message
                else:
                    raise
            else:
                rdfDom.commit(source=self.getPrincipleFunc(kw))
            return output.getvalue()            
            
        def xupdate(self, xupdate=None, kw=None, uri=None):
            '''execute the xupdate script, updating the server's model
            '''        
            lock = self.getLock()        
            try:
                return self.xupdateRDFDom(self.rdfDom, xupdate, kw, uri)
            finally:
                lock.release()
                    
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
                log.exception('got this far before exception %s', output.getvalue())
                raise
            else:   #can't have a finally here
                sys.stdout = sys_stdout
            return contents

        def processPython(self, contents, kw):
            try:            
                contents = self.executePython(contents, kw)             
            except (NameError), e:              
                contents = "<pre>Unable to invoke script: \nerror:\n%s\nscript:\n%s</pre>" % (str(e), contents)
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
            
            from Ft.Xml.Xslt.Processor import Processor
            processor = Processor()
            #processor = utils.XsltProcessor()        
            #def contextHook(context): context.varBindings[(None, '_kw')] = kw
            #processor.contextSetterHook = contextHook
            
            #print 'xslt ', uri
            #print 'xslt template:', styleSheetContents
            #print 'xslt source: ', contents
            styleSheet = styleSheetCache.getValue(styleSheetContents, uri)
            processor.appendStylesheetInstance( styleSheet, uri) 
            for (k, v) in extFunMap.items():
                namespace, localName = k
                processor.registerExtensionFunction(namespace, localName, v)
            try:
                contents = processor.run(InputSource.DefaultFactory.fromString(contents, uri),
                                     topLevelParams = vars)
            except Ft.Xml.Xslt.XsltException:
                #if Error.SOURCE_PARSE_ERROR
                #probably because there's no root element, try wrapping in a <div>
                contents = '<div>'+contents+'</div>'
                contents = processor.run(InputSource.DefaultFactory.fromString(contents, uri),
                                     topLevelParams = vars)
            format = kw.get('_nextFormat')
            if format is None:
                format = self._getFormatFromStyleSheet(styleSheet)
            else:
                del kw['_nextFormat']            
            return (contents, format)
                
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
          '''
          XPath extension function for saving RxML
          '''        
          try:
              import zml
              xml = zml.zmlString2xml(contents)#parse the rhizml to xml
                        
              if isinstance(about, ( types.ListType, types.TupleType ) ):            
                  #about may be a list of text nodes, convert to a list of strings
                  about = [StringValue(x) for x in about]
              elif about is not None:
                  about = [ about ]
              self.processRxML('<rx:rx>'+ xml+'</rx:rx>', about, source=user)
          except NotAuthorized:
            assignFunc = context.functions.get((RXWIKI_XPATH_EXT_NS, 'assign-metadata') )
            if assignFunc:
                assignFunc(context, 'error', sys.exc_value.msg)
            else:
                raise
          except:
            log.exception("metadata save failed")
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
                
        def partialXsltCacheKeyPredicate(self, styleSheetContents, sourceContents, kw, contextNode, styleSheetUri='path:'):
          styleSheetNotCacheableFunctions = self.NOT_CACHEABLE_FUNCTIONS
          revision = getattr(contextNode.ownerDocument, 'revision', None)            
          key = [styleSheetContents, styleSheetUri, sourceContents, contextNode,
                 id(contextNode.ownerDocument), revision]
          
          styleSheet = styleSheetCache.getValue(styleSheetContents, styleSheetUri)
          
          try:
              styleSheetKeys = styleSheet.isCacheable
          except AttributeError:
              styleSheetKeys = styleSheet.isCacheable = getStylesheetCacheKey(
                      styleSheet.children, styleSheetNotCacheableFunctions)
              if isinstance(styleSheetKeys, MRUCache.NotCacheable):
                  log.debug("stylesheet %s is not cacheable" % styleSheetUri)
              
          if isinstance(styleSheetKeys, MRUCache.NotCacheable):
              raise styleSheetKeys
          else:
              key += styleSheetKeys

          #the top level xsl:param element determines the parameters of the stylesheet: extract them          
          topLevelParams = [child for child in styleSheet.children \
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

        def xsltSideEffectsCalc(self, cacheValue, resultNodeset, kw, contextNode, retVal):
            return kw.get('_metadatachanges', [])

        def xsltSideEffectsFunc(self, cacheValue, sideEffects, resultNodeset, kw, contextNode, retVal):
          for change in sideEffects:
             nssMap = change[0]
             change = change[1]
             #note: we don't really need the contextNode
             context = XPath.Context.Context(contextNode, processorNss = nssMap)
             if type(change) == type(()):
                AssignMetaData(kw, context, change[0],change[1])
             else:        
                RemoveMetaData(kw, context, change)
          return cacheValue

    ###########################################
    ## http request handling
    ###########################################
        def guessMimeTypeFromContent(self, result):
            #obviously this could be improved,
            #e.g. detect encoding in xml header or html meta tag
            #or handle the BOM mark in front of the <?xml 
            #detect binary vs. text, etc.
            if result.startswith("<html") or result.startswith("<HTML"):
                return "text/html"
            elif result.startswith("<?xml"):
                return "text/xml"
            elif self.DEFAULT_MIME_TYPE:
                return self.DEFAULT_MIME_TYPE
            else:
                return None
                
        def handleRequest(self, _name_, **kw):
            #print 'name:', _name_
            kw['_name'] = _name_ #explictly replace _name -- do it this way to avoid TypeError: handleRequest() got multiple values for keyword argument '_name'

            #if the request name has an extension try to set a default mimetype before executing the request
            i=_name_.rfind('.')
            if i!=-1:
                ext=_name_[i:]      
                contentType=mimetypes.types_map.get(ext)
                if contentType:
                    kw['_response'].headerMap['content-type']=contentType

            try:
                rc = {}
                rc['_session']=kw['_session']
                #todo: probably should put request.simpleCookie in the requestContext somehow too
                self.requestContext.append(rc)

                result = self.runActions('http-request', kw)
                if result is not None: #'cause '' is OK
                    #if mimetype is not set, make another attempt
                    if not kw['_response'].headerMap.get('content-type'):
                        contentType = self.guessMimeTypeFromContent(result)
                        if contentType:
                            kw['_response'].headerMap['content-type']=contentType
                            
                    if self.useEtags:
                        import md5                                
                        resultHash = '"' + md5.new(result).hexdigest() + '"'
                        kw['_response'].headerMap['etag'] = resultHash
                        etags = kw['_request'].headerMap.get('if-none-match')                
                        if etags and resultHash in [x.strip() for x in etags.split(',')]:
                            kw['_response'].headerMap['status'] = 304 #not modified
                            return ''
                    return str(result)
            finally:
                self.requestContext.pop()
                    
            return self.default_not_found(kw)

        def default_not_found(self, kw):
            '''if the _not_found page is not defined, we assume we're just viewing an arbitrary rdf model -- so just print its rdfdom xml representation'''
            kw['_response'].headerMap["content-type"]="text/xml"
            kw['_response'].headerMap['status'] = 404 #not found
            return self.dump() 

        def dump(self):
            '''returns a xml representation of the rdf model'''
            oldVal = self.rdfDom.globalRecurseCheck
            self.rdfDom.globalRecurseCheck=True
            try:
                strIO = cStringIO.StringIO()        
                PrettyPrint(self.rdfDom, strIO, asHtml=1) #asHtml to suppress <?xml ...>
            finally:
                self.rdfDom.globalRecurseCheck=oldVal
            return '<root>'+strIO.getvalue() +'</root>'
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
            return self.transform(styleSheet)

    #more cacheing functions (xslt, rxslt content processors)
        
    styleSheetCache = MRUCache.MRUCache(0, styleSheetValueCalc)

    def addXPathExprCacheKey(compExpr, nsMap, key, notCacheableXPathFunctions):
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
                       key.append( keyfunc(field, context) ) #may raise MRUCache.NotCacheable
                   else:
                       raise MRUCache.NotCacheable    

    def getStylesheetCacheKey(nodes, styleSheetNotCacheableFunctions, key = None):
        '''walk through the elements in the stylesheet looking for
        elements that reference XPath expressions; then iterate through each 
        expression looking for functions that aren't cacheable'''
        #todo: also look for extension elements that aren't cacheable
        from Ft.Xml.Xslt import AttributeInfo, AttributeValueTemplate    
        key = key or []
        try:
            for node in nodes: 
                attrDict = getattr(node, 'legalAttrs', None)
                if attrDict is not None:
                    for name, value in attrDict.items():
                        if isinstance(value, (AttributeInfo.Expression, AttributeInfo.Avt)):
                            #this attribute may have an expression expression in it
                            attributeName = '_' + SplitQName(name)[1].replace('-', '_') #see Ft.Xml.Xslt.StylesheetHandler
                            attributeValue = getattr(node, attributeName, None)
                            if isinstance(attributeValue, AttributeInfo.ExpressionWrapper):
                                #print 'ExpressionWrapper ', attributeValue.expression
                                addXPathExprCacheKey(attributeValue.expression,
                                    node.namespaces, key, styleSheetNotCacheableFunctions)                                
                            elif isinstance(attributeValue, AttributeValueTemplate.AttributeValueTemplate):
                                for expr in attributeValue._parsedParts:
                                    #print 'parsedPart ', expr
                                    addXPathExprCacheKey(expr, node.namespaces,
                                                    key, styleSheetNotCacheableFunctions)
                #handle LiteralElements
                outputAttrs = getattr(node, '_output_attrs', None) 
                if outputAttrs is not None:
                    for (qname, namespace, value) in outputAttrs:
                        if value is not None:
                            #value will be a AttributeValueTemplate.AttributeValueTemplate
                            for expr in value._parsedParts:
                                addXPathExprCacheKey(expr, node.namespaces,
                                                 key, styleSheetNotCacheableFunctions)                                
                
                if node.children is not None:
                    key = getStylesheetCacheKey(node.children, styleSheetNotCacheableFunctions, key)
                    if isinstance(key, MRUCache.NotCacheable):
                        return key
        except MRUCache.NotCacheable, e:
          return e
        
        return key

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
                    raise 'usage: '+ cmd_usage
                name = arg.lstrip('-')                
                kw[name] = True
                arg = i.next()
                if arg[0] != '-':                    
                    kw[name] = arg
                    arg = i.next()  
        except StopIteration: pass
        #print 'args', kw
        return kw

    DEFAULT_cmd_usage = 'python [raccoon.py -l [log.config] -r -d [debug.pkl] -x -s server.cfg -p path -m [store.nt] -a config.py [config specific options]'
    cmd_usage = '''\nusage:
    -h this help message
    -s server.cfg specify an alternative server.cfg
    -l [log.config] specify a config file for logging
    -r record requests (ctrl-c to stop recording) 
    -d [debug.pkl]: debug mode (replay the requests saved in debug.pkl)
    -x exit after executing config specific cmd arguments
    -p specify the path (overrides RACCOONPATH env. variable)
    -m [store.nt] load the RDF model
       (default model supports .rdf, .nt, .mk)
    -a [config.py] run the application specified
    '''

    def main(argv):
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
            log_config.fileConfig(logConfig) #todo document loggers: rhizome, server, raccoon, rdfdom
            #any logger already created and not explicitly specified in the log config file is disabled
            #this seems like a bad design -- certainly took me a while to why understand things weren't getting logged
            #so re-enable the loggers
            for logger in logging.Logger.manager.loggerDict.itervalues():
                logger.disabled = 0        
        else: #set defaults        
            logging.BASIC_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"
            logging.root.setLevel(logging.INFO)
            logging.basicConfig()

        kw = argsToKw(rootArgs, DEFAULT_cmd_usage)
        kw['argsForConfig'] = configArgs
        root = RequestProcessor(**kw)
        #print 'ma', mainArgs  
        if '-h' in mainArgs or '--help' in mainArgs:
            #print DEFAULT_cmd_usage,'[config specific options]'
            print root.cmd_usage
            print cmd_usage
        elif '-d' in mainArgs: 
            try:
                debugFileName=mainArgs[mainArgs.index("-d")+1]
                if debugFileName[0] == '-':
                    raise ValueError
            except (IndexError, ValueError):
                debugFileName = 'debug-wiki.pkl'
            requests = pickle.load(file(debugFileName))        
            for request in requests:
                root.handleRequest(request[0], **request[1])
        elif '-x' not in mainArgs: #if -x (execute cmdline and exit) we're done
            sys.argv = mainArgs #hack for Server
            from rx import Server
            debug = '-r' in mainArgs
            #print 'starting server!'
            Server.start_server(root, debug) #kicks off the whole process
            #print 'dying!'
