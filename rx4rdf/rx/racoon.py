"""
    Engine and helper classes for Racoon

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import utils, glock
import RxPath
from xml.dom import Node as _Node

from Ft.Rdf.Drivers import Memory
import os, time, cStringIO, sys, base64, mimetypes, types
from Ft.Xml.Lib.Print import PrettyPrint
from Ft.Xml.XPath.Conversions import StringValue        
from Ft.Xml import SplitQName, XPath, InputSource
from Ft.Xml.XPath import RuntimeException,FT_EXT_NAMESPACE
from Ft.Xml.Xslt import XSL_NAMESPACE
from Ft.Lib import Uri, UriException
import MRUCache
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
log = logging.getLogger("racoon")
_defexception = utils.DynaExceptionFactory(__name__)

#xpath variable namespaces:
RXIKI_HTTP_REQUEST_HEADER_NS = 'http://rx4rdf.sf.net/ns/racoon/http-request-header#'
RXIKI_HTTP_RESPONSE_HEADER_NS = 'http://rx4rdf.sf.net/ns/racoon/http-response-header#'
RXIKI_REQUEST_COOKIES_NS = 'http://rx4rdf.sf.net/ns/racoon/request-cookie#'
RXIKI_RESPONSE_COOKIES_NS = 'http://rx4rdf.sf.net/ns/racoon/response-cookie#'
RXIKI_SESSION_NS = 'http://rx4rdf.sf.net/ns/racoon/session#'
RXIKI_PREV_NS = 'http://rx4rdf.sf.net/ns/racoon/previous#'
#XPath extension functions:
RXWIKI_XPATH_EXT_NS = 'http://rx4rdf.sf.net/ns/racoon/xpath-ext#'

############################################################
##XPath extension functions
##(can be used with both RxPath/RxSLT/XUpdate and XPath/XSLT
############################################################

#first delete insecure functions from FT's built-in extensions
from Ft.Xml.XPath import BuiltInExtFunctions
if BuiltInExtFunctions.ExtFunctions.has_key((FT_EXT_NAMESPACE, 'spawnv')):
    del BuiltInExtFunctions.ExtFunctions[(FT_EXT_NAMESPACE, 'spawnv')]
    del BuiltInExtFunctions.ExtFunctions[(FT_EXT_NAMESPACE, 'system')]

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

def GenerateBnode(context, name=None):
    if name is not None:
        name = StringValue(name)
    return utils.generateBnode(name)

def FileExists(context, uri):
    path = StringValue(uri)
    if path.startswith('file:'):
        path = Uri.UriToOsPath(uri)
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

def If(context, cond, v1, v2=None):
    """
    just like Ft.Xml.XPath.BuiltInExtFunctions.If
    but the then and else parameters are strings that evaluated dynamically 
    thus supporting the short circuit logic you expect from if expressions
    """
    # contributed by Lars Marius Garshol;
    # originally using namespace URI 'http://garshol.priv.no/symbolic/'
    from Ft.Xml.XPath import parser
    from Ft.Xml.XPath import Conversions
    if Conversions.BooleanValue(cond):
        return parser.new().parse(Conversions.StringValue(v1)).evaluate(context)
    elif v2 is None:
        return []
    else:
        return parser.new().parse(Conversions.StringValue(v2)).evaluate(context)
    
def HasMetaData(kw, context, name):
    def _test(local, dict):
        if dict.has_key(local):
            return True
        else:
            return False
    return _onMetaData(kw, context, name, _test)

def GetMetaData(kw, context, name):
    '''
    the advantage of using this instead of a variable reference is that it just returns 0 if the name doesn't exist, not an error
    '''
    def _get(local, dict):
        if dict.has_key(local):
            return dict[local]
        else:
            return False
    return _onMetaData(kw, context, name, _get)

def AssignMetaData(kw, context, name, val, recordChange = None):
    '''
    new variable and values don't affect corresponding xpath variable 
    '''
    def _assign(local, dict):
        #oldval = dict.get(local, None)
        dict[local] = val
        return val
    #print >>sys.stderr,'AssignMetaData ', name, ' ' , val    
    retVal = _onMetaData(kw, context, name, _assign)
    if recordChange:
        kw.setdefault(recordChange, []).append( (context.processorNss, (name, val)) )
    return retVal

def RemoveMetaData(kw, context, name, recordChange = None):
    def _delete(local, dict):
        if dict.has_key(local):
            del dict[local]
            return True
        else:
            return False
    retVal = _onMetaData(kw, context, name, _delete)
    if retVal and recordChange:
        kw.setdefault(recordChange, []).append( (context.processorNss, name) )
    return retVal

_defexception('unusable namespace error')

def _onMetaData(kw, context, name, func):
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
    if not namespace:
        retVal = func(local, kw)
    elif namespace == RXIKI_HTTP_REQUEST_HEADER_NS:
        retVal = func(local, kw['_request'].headerMap)
    elif namespace == RXIKI_HTTP_RESPONSE_HEADER_NS:
        retVal = func(local, kw['_response'].headerMap)     
    elif namespace == RXIKI_REQUEST_COOKIES_NS: #assigning values will be automatically converted to a Morsel
        retVal = func(local, kw['_request'].simpleCookie)
    elif namespace == RXIKI_RESPONSE_COOKIES_NS: #assigning values will be automatically converted to a Morsel
        retVal = func(local, kw['_response'].simpleCookie)        
    elif namespace == RXIKI_SESSION_NS:
        retVal = func(local, kw['_session'])
    elif namespace == RXIKI_PREV_NS:
        retVal = func(local, kw['_prevkw'])
    else:
        raise UnusableNamespaceError( '%s uses unusable namespace: %s' % (local, namespace) )
    return retVal

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
(RXWIKI_XPATH_EXT_NS, 'ospath2pathuri'): OsPath2PathUri,
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
            'prev' : RXIKI_PREV_NS,
           'xf' : 'http://xmlns.4suite.org/ext'
        }

DefaultContentProcessors = {
    'http://rx4rdf.sf.net/ns/wiki#item-format-text' : lambda self, contents, *args: contents,
    'http://rx4rdf.sf.net/ns/wiki#item-format-binary' : lambda self, contents, *args: contents,
    'http://rx4rdf.sf.net/ns/wiki#item-format-xml': lambda self, contents, *args: contents,
    'http://www.w3.org/2000/09/xmldsig#base64' : lambda self,contents, *args: base64.decodestring(contents),
    'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt': lambda self, contents, kw, *args: self.transform(str(contents.strip()), kw),
    'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate': lambda self, contents, kw, *args: self.xupdate(str(contents.strip()), kw),
    'http://rx4rdf.sf.net/ns/wiki#item-format-python': lambda self, contents, kw, *args: self.processPython(contents, kw),
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
    def __init__(self, server, triggerName = 'handle-request'):
        self.server = server
        self.triggerName = triggerName

    #the trailing __ so you can have requests named 'invoke' without conflicting    
    def invoke__(self, name, **kw):
        return self.invokeEx__(name, kw)[0]
        
    def invokeEx__(self, name, kw):        
        kw.update( self.server.requestContext[-1] )
        kw['_name']=name
        #print 'invoke', kw
        result = self.server.runActions(self.triggerName, kw) 
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
    
    def secureFilePathresolve(self, uri, base=None):
        if base:
            uri = self.normalize(uri, base)        
        path =  Uri.UriToOsPath(uri)
        for prefix in self.path:
            if os.path.abspath(path).startswith(os.path.abspath(prefix)):
                return Uri.BaseUriResolver.resolve(self, uri)          
        raise UriException(UriException.RESOURCE_ERROR, uri, 'Unauthorized') 
        
    def resolvePathScheme(self, uri, base=None):
        path = uri
        if path.startswith('path:'):
            #print 'path', path
            path = uri[len('path:'):]
            
        for prefix in self.path:
            if os.path.exists(os.path.join(prefix.strip(), path) ):
                return file(os.path.join(prefix.strip(), path), 'rb')
        raise UriException(UriException.RESOURCE_ERROR, uri, 'Not Found')

    def resolveSiteScheme(self, uri, base=None):
        if base:
            uri = self.normalize(uri, base) 
        paramMap = {}        
        path = uri        

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
            path = path[:i+1]
        if path and path[-1]=='/': path=path[:-1] # Remove trailing '/' if any
        if path.startswith('site://'):
            #print 'path', path
            name = path[len('site://'):] #assume we only get requests inside our home path
        else:
            name = path
        while name and name[0]=='/':
            name=name[1:] # Remove starting '/' if any e.g. from site:///
                        
        try:
            #print 'to resolve!', name, ' ', uri
            contents = self.server.requestDispatcher.invoke__(name, **paramMap)
            #print 'resolved', name, ': ', contents
            return StringIO.StringIO( contents )
        except AttributeError: #not found
            raise UriException(UriException.RESOURCE_ERROR, uri, 'Not Found')


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
def action(resultNodeset, kw, contextNode, retVal) where:
    resultNodeset is the result of the RxPath query associated with this action
    kw is dictionary of the parameters associated with the request
    contentNode is the context node of used when the RxPath expressions were evaluated
    retVal was the return value of the last action invoked in the in action sequence or None
If action is None this action will reset the context node

if matchFirst is True the requesthandler will only run the action using the first matching xpath expression in queries

if forEachNode is True then if a xpath expression returns a nodeset the action will be called one for each in node,
otherwise the action will be called once and whole nodeset will passed as the resultNodeset param
    '''        
        self.queries = queries
        self.action = action
        self.matchFirst = matchFirst 
        self.forEachNode = forEachNode
        self.requiresContext = requiresContext
        self.depthFirst = depthFirst
        self.preVars = {}
        self.postVars = {}        
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
            self.postVars[varName] = exps
        else:
            self.preVars[varName] = exps

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
        log.debug("performing side effect for %s with args %s" % (field._name, str(field._args) ) )
        function.evaluate(context) #invoke the function with a side effect

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
    
DefaultNotCacheableFunctions = [(RXWIKI_XPATH_EXT_NS, 'get-metadata'),
        (RXWIKI_XPATH_EXT_NS, 'has-metadata'),
        (FT_EXT_NAMESPACE, 'iso-time'),        
        (RXWIKI_XPATH_EXT_NS, 'current-time'),
        ('http://exslt.org/dates-and-times', 'date-time'), #todo: other exslt date-and-times functions but only if no arguments
        (RXWIKI_XPATH_EXT_NS, 'generate-bnode'),
        (FT_EXT_NAMESPACE, 'generate-uuid'),
        #functions that dynamically evaluate expression may have hidden dependencies so they aren't cacheable
        (RXWIKI_XPATH_EXT_NS, 'if'),
        (FT_EXT_NAMESPACE, 'evaluate'),
        ('http://exslt.org/dynamic', 'evaluate'), ]
    #what about random? (ftext and exslt) 

EnvironmentDependentFunctions = [ (None, 'document'),
    (RXWIKI_XPATH_EXT_NS, 'openurl'),
    (RXWIKI_XPATH_EXT_NS, 'file-exists') ]
    
############################################################
##Racoon main class
############################################################
class Root(object):
    '''    
    * special purpose, reserved item names (optional defined): index (maps to /)
    * parameters passed to:
        xslt, xupdate: _name, _content
        python: _name, _content, _request, _response, __requestor__
        
    '''
    DEFAULT_CONFIG_PATH = 'wiki-default-config.py'
    lock = None
                
    requestContext = utils.createThreadLocalProperty('__requestContext',
        doc='variables you want made available to anyone during this request (e.g. the session)')
            
    expCache = MRUCache.MRUCache(0, XPath.Compile)#, sideEffectsFunc=_resetFunctions)

    def __init__(self,argv):
        self.requestContext = [] #stack of dicts
        configpath = self.DEFAULT_CONFIG_PATH
        self.source = None
        i = 0
        self.PATH = os.environ.get('RHIZPATH',os.getcwd())
        while i < len(argv):        
            arg = argv[i]            
            if arg == '-a': 
                i += 1
                configpath = argv[i]
                break #must be last arg
            elif arg == '-m':
                i += 1
                self.source = argv[i]
            elif arg == '-p':
                self.PATH = argv[i]
            else:#try to guess
                if arg.endswith('.py'):
                    configpath = arg
                else:               
                    self.source = arg
                break
            i += 1
        argsForConfig = argv[i+1:]        
        self.cmd_usage = DEFAULT_cmd_usage
        self.loadConfig(configpath, argsForConfig)
        self.loadModel()
        self.requestDispatcher = Requestor(self)
        InputSource.DefaultFactory.resolver = SiteUriResolver(self)
        self.handleCommandLine(argsForConfig)
        
    def handleCommandLine(self, argv):
        '''        
        the command line is translated into XPath variables as follows:
        * arguments beginning with a '-' are treated a variable name with its value
        being next argument unless that argument also starts with a '-'
        
        * the whole command line is assigned to the variable '_cmdline'
        '''
        kw = { '_cmdline' : '"' + '" "'.join(argv) + '"'} 

        i = iter(argv)
        try:
            arg = i.next()
            while 1:
                if arg[0] != '-':
                    raise 'usage: '+ self.cmd_usage
                name = arg.lstrip('-')                
                kw[name] = True
                arg = i.next()
                if arg[0] != '-':                    
                    kw[name] = arg
                    arg = i.next()  
        except StopIteration: pass
        #print 'args', kw
        self.runActions('run-cmds', kw)        
            
    def loadConfig(self, path, argsForConfig=None):
        if not os.path.exists(path):
            path = self.DEFAULT_CONFIG_PATH
        kw = {}
        import socket
        self.BASE_MODEL_URI= 'http://' + socket.getfqdn() + '/'
        
        def includeConfig(path):
             kw['__configpath__'].append(os.path.abspath(path))
             execfile(path, globals(), kw)
             kw['__configpath__'].pop()
        if path.endswith('.py'):            
            kw['__server__'] = self
            kw['__argv__'] = argsForConfig or []
            kw['__include__'] = includeConfig
            kw['__configpath__'] = [os.path.abspath(path)]
            execfile(path, globals(), kw)

        def initConstants(varlist, default):
            import copy 
            for name in varlist:                
                value = kw.get(name, copy.copy(default))
                if not isinstance(value, type(default)):
                    raise 'config variable %s must be compatible with type %s' % name, type(default)
                setattr(self, name, value)
                        
        initConstants( [ 'nsMap', 'extFunctions', 'actions', 'contentProcessors',
                         'contentProcessorCachePredicates',
                         'contentProcessorSideEffectsFuncs',
                         'contentProcessorSideEffectsPredicates'], {} )
        initConstants( [ 'STORAGE_PATH', 'STORAGE_TEMPLATE', 'APPLICATION_MODEL', 'DEFAULT_MIME_TYPE'], '')
        setattr(self, 'initModel', kw.get('initModel', RxPath.initFileModel))
        initConstants( ['ROOT_PATH'], '/')
        assert self.ROOT_PATH[0] == '/', "ROOT_PATH must start with a '/'"
        initConstants( ['BASE_MODEL_URI'], self.BASE_MODEL_URI)
        initConstants( ['MAX_MODEL_LITERAL'], -1)        
        #cache settings:
        initConstants( ['NOT_CACHEABLE_FUNCTIONS'], [])
        initConstants( ['LIVE_ENVIRONMENT'], 1)
        initConstants( ['XPATH_CACHE_SIZE','ACTION_CACHE_SIZE'], 1000)
        initConstants( ['XPATH_PARSER_CACHE_SIZE','STYLESHEET_CACHE_SIZE'], 200)
        self.expCache.capacity = self.XPATH_PARSER_CACHE_SIZE
        styleSheetCache.capacity = self.STYLESHEET_CACHE_SIZE
        
        self.SAVE_DIR = kw.get('SAVE_DIR', 'content/')
        self.PATH = kw.get('PATH', self.PATH)
        self.SECURE_FILE_ACCESS= kw.get('SECURE_FILE_ACCESS', True)        
        self.cmd_usage = DEFAULT_cmd_usage + kw.get('cmd_usage', '')
        #todo: shouldn't these be set before so it doesn't override config changes?:
        self.NOT_CACHEABLE_FUNCTIONS += DefaultNotCacheableFunctions
        if self.LIVE_ENVIRONMENT:
            self.NOT_CACHEABLE_FUNCTIONS += EnvironmentDependentFunctions
            styleSheetCache.isValueCacheableCalc = isStyleSheetCacheable
            
        self.nsMap.update(DefaultNsMap)
        self.contentProcessors.update(DefaultContentProcessors)
        self.contentProcessorCachePredicates.update(DefaultContentProcessorCachePredicates)
        self.contentProcessorSideEffectsFuncs.update(DefaultContentProcessorSideEffectsFuncs)
        self.contentProcessorSideEffectsPredicates.update(DefaultContentProcessorSideEffectsPredicates)
        self.extFunctions.update(DefaultExtFunctions)

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
        assert source, 'no model path given and STORAGE_PATH not set!'

        if not self.lock:            
            lockName = 'r' + `hash(repr(source))` + '.lock'
            self.lock = glock.GlobalLock(lockName)
            
        lock = self.getLock()            
        model = self.initModel(source, StringIO.StringIO(self.STORAGE_TEMPLATE))
                
        if self.APPLICATION_MODEL:
            appmodel, appdb = utils.DeserializeFromN3File(StringIO.StringIO(self.APPLICATION_MODEL), scope='application')
            model = RxPath.MultiModel(model, RxPath.FtModel(appmodel))
                                        
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
    
    def mapToXPathVars(self, kw):
        '''map request kws to xpath vars (include http request headers)'''
        extFuncs = self.extFunctions.copy()
        extFuncs.update({
        (RXWIKI_XPATH_EXT_NS, 'assign-metadata') : lambda context, name, val: AssignMetaData(kw, context, name, val, recordChange = '_metadatachanges'),
        (RXWIKI_XPATH_EXT_NS, 'remove-metadata') : lambda context, name: RemoveMetaData(kw, context, name, recordChange = '_metadatachanges'),
        (RXWIKI_XPATH_EXT_NS, 'has-metadata') : lambda context, name: HasMetaData(kw, context, name),
        (RXWIKI_XPATH_EXT_NS, 'get-metadata') : lambda context, name: GetMetaData(kw, context, name),        
        })        
        #add most kws to vars (skip references to non-simple types):
        vars = dict( [( (None, x[0]), x[1] ) for x in kw.items()\
                      if x[0] not in self.COMPLEX_REQUESTVARS and x[0] != '_metadatachanges'] )
        #magic constants:
        vars[(None, 'STOP')] = 0
        vars[(None, 'ROOT_PATH')] = self.ROOT_PATH        
        vars[(None, 'BASE_MODEL_URI')] = self.BASE_MODEL_URI        
        #http request and response vars:
        request = kw.get('_request', None)
        if request:
            vars[(None, '_url')] = request.browserUrl
            vars[(None, '_base-url')] = request.browserBase            
            vars[(None, '_path')] = request.browserPath 
            vars.update( dict(map(lambda x: ((RXIKI_HTTP_REQUEST_HEADER_NS, x[0]), x[1]), request.headerMap.items()) ) )
            vars.update( dict(map(lambda x: ((RXIKI_REQUEST_COOKIES_NS, x[0]), x[1].value), request.simpleCookie.items()) ) )
        response = kw.get('_response', None)
        if response:
            vars.update( dict(map(lambda x: ((RXIKI_HTTP_RESPONSE_HEADER_NS, x[0]), x[1]), response.headerMap.items()) ) )
            vars.update( dict(map(lambda x: ((RXIKI_RESPONSE_COOKIES_NS, x[0]), x[1].value), request.simpleCookie.items()) ) )
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
            if not vars:
                context = node
                vars = { (None, '_context'): [ context ] } #we also set this in doActions()
                
            context = XPath.Context.Context(node, varBindings = vars,
                        extFunctionMap = extFunctionMap, processorNss = self.nsMap)
            #sorry this confusing... call RDFDom modules' evalXPath
            return RxPath.evalXPath(xpath, context, expCache = self.expCache,
                    queryCache=getattr(self.rdfDom, 'queryCache', None))
        except (RuntimeException), e:
            if e.errorCode == RuntimeException.UNDEFINED_VARIABLE:                            
                log.debug(e.message) #undefined variables are ok
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
        for name, exps in actionvars.items():            
            vars, extFunMap = self.mapToXPathVars(kw)
            for exp in exps:
                #print exp
                result = self.evalXPath(exp, vars=vars, extFunctionMap = extFunMap, node = contextNode)
                if result:
                    kw[name] = result
                    break
            if not result:
                kw[name] = result
            
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
                kw['_context'] = [ contextNode ]  #_context so access to the rdf database is available to xsl, xupdate, etc. processing
                #todo add _root variable also? 
                vars, extFunMap = self.mapToXPathVars(kw)
                result = self.evalXPath(xpath, vars=vars, extFunctionMap = extFunMap, node = contextNode)
                if type(result) in [types.IntType,types.FloatType]:#for $STOP
                    break
                if result: #todo: != []: #if not equal empty nodeset (empty strings ok)
                    if not action.action: #if no action is defined this action resets the contextNode instead
                        contextNode = result
                        log.debug('context changed: %s', result)
                        assert action.matchFirst #why would you want to evalute every query in this case?
                        break;
                    else:
                        if not isinstance(result, type([])):
                            result = [ result ]
                        if action.forEachNode:
                            if action.depthFirst:
                                #we probably want the reverse of document order (e.g. the deepest first)
                                result = result[:] #copy the list since it might have been cached
                                result.reverse()
                                #print '!!!res', contextNode.childNodes
                            for node in result:
                                if kw.get('_metadatachanges'): del kw['_metadatachanges']
                                retVal = self.rdfDom.actionCache.getOrCalcValue(action.action,
                                    node, kw, contextNode, retVal, hashCalc=action.cacheKeyPredicate,
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
            if isinstance(contextNode, type([])):
                contextNode = contextNode[0]                    
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
        for k, v in kw.items():
            #initialize the templates variable map copying the core request kws
            #and copy the rest (the application specific kws) to _prevkw
            #this way the template processing doesn't mix with the orginal request
            #but are made available in the 'previous' namespace (think of them as template parameters)
            if k in self.COMPLEX_REQUESTVARS + globalVars:
                templatekw[k] = v
            elif k != '_metadatachanges':
                prevkw[k] = v
        templatekw['_prevkw'] = prevkw    
        templatekw['_contents'] = retVal            
        templatekw['_prevnode'] = [ contextNode ] #nodeset containing current resource

        return self.doActions(actions, templatekw, resultNodeset) #the resultNodeset is the contextNode so skip the find resource step
            
###########################################
## content processing 
###########################################
    def processContents(self, result, kw, contextNode, contents):
        if contents is None:
            return contents        
        formatType = self.getStringFromXPathResult(result)        
        log.debug('enc %s', formatType)
        if formatType:
            return self.contentProcessors[formatType](self, contents, kw, result,contextNode)
        else:
            return contents
        trigger = kw.get('_update-trigger')
        if trigger:
            del kw['_update-trigger']
            self.runActions(trigger, kw)

    def getProcessContentsCachePredicate(self, result, kw, contextNode, contents):
        formatType = self.getStringFromXPathResult(result)
        if formatType and self.contentProcessorCachePredicates.get(formatType):
            return self.contentProcessorCachePredicates[formatType](self, 
                                                    result, kw, contextNode, contents)
        else:
            raise MRUCache.NotCacheable 

    def getProcessContentsSideEffectsPredicate(self, cacheValue, result, kw, contextNode, contents):
        '''
        returns a predicate that returns a representation of the side effects of calculating the cacheValue
        '''
        formatType = self.getStringFromXPathResult(result)
        if formatType and self.contentProcessorSideEffectsPredicates.get(formatType):
            return self.contentProcessorSideEffectsPredicates[formatType](
                                self, cacheValue, result, kw, contextNode, contents)
        else:
            return None 

    def getProcessContentsSideEffectsFunc(self, cacheValue, sideEffects, result, kw, contextNode, contents):
        '''
        returns a function that replayes the side effects for the cacheValue.
        sideEffects is the object returned by sideEffects predicate for that cacheValue
        '''
        formatType = self.getStringFromXPathResult(result)
        if formatType and self.contentProcessorSideEffectsFuncs.get(formatType):
            return self.contentProcessorSideEffectsFuncs[formatType](
                    self, cacheValue, sideEffects, result, kw, contextNode, contents)
        else:
            return None 
        
    def transform(self, stylesheet, kw=None):
        if kw is None: kw = {}        
        vars, funcs = self.mapToXPathVars(kw)
        
        #processor = utils.XsltProcessor()        
        #def contextHook(context): context.varBindings[(None, '_kw')] = kw
        #processor.contextSetterHook = contextHook 
        
        return RxPath.applyXslt(self.rdfDom, stylesheet, vars, funcs, baseUri='path:',
                         styleSheetCache=styleSheetCache)#, processor = processor)

    def xupdateRDFDom(self, rdfDom, xupdate=None, kw=None, uri=None):
        '''execute the xupdate script on the specified RxPath DOM
        '''
        kw = kw or {}
        baseUri= uri or 'path:'
        vars, funcs = self.mapToXPathVars(kw)
        lock = self.getLock()
        rdfDom.begin()
        try:
            RxPath.applyXUpdate(rdfDom, xupdate, vars, funcs, uri=baseUri)
        except:
            rdfDom.rollback()
            lock.release()
            raise
        else:
            rdfDom.commit()
            lock.release()
        
    def xupdate(self, xupdate=None, kw=None, uri=None):
        '''execute the xupdate script, updating the server's model
        '''        
        lock = self.getLock()
        self.xupdateRDFDom(self.rdfDom, xupdate, kw, uri)
        lock.release()
                
    def executePython(self, cmds, kw = None):
        if kw is None: kw = {}
        #todo: thread synchronize
        #print cmds
        output = cStringIO.StringIO()
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
        return contents
        
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
        return processor.run(InputSource.DefaultFactory.fromString(contents, uri), topLevelParams = vars) 

    def processRxML(self, xml, resources=None):
        '''Updates the DOM and model by replaceing the resources contained in the resources list with the statements asserted in the RxML doc.
        If resources is None, the RxML statements are just added to the 
        '''
        from Ft.Xml import Domlette
        import rxml
        #parse the rxml
        #print >>sys.stderr, 'rxml', xml
        isrc = InputSource.DefaultFactory.fromString(xml)
        rxmlDoc = Domlette.NonvalidatingReader.parse(isrc)
        
        #create a temporary model to write the rxml statements to 
        db = Memory.CreateDb('', 'default')
        outputModel = Ft.Rdf.Model.Model(db)

        nsMap = self.nsMap.copy()
        nsMap.update( { 
                    None : rxml.RX_NS,
                   'rx': rxml.RX_NS  
                    })        
        rxml.addRxdom2Model(rxmlDoc, outputModel, nsMap , self.rdfDom)        
                    
        return self.updateDom(outputModel.statements(), resources, True)
            
    def updateDom(self, addStmts, removeResources=None, removeListObjects=False):
        '''update our DOM
        addStmts is a list of Statements to add
        removeResources is a list of resource URIs to remove
        '''
        lock = self.getLock()        
        self.rdfDom.begin()
        #log.debug('removing %s' % removeResources)
        try:
            #delete the resources from the dom:        
            if removeResources:
                for uri in removeResources:
                    self.rdfDom.removeResource(uri, removeListObjects)
            #and add the statements
            self.rdfDom.addStatements(addStmts)
        except:
            self.rdfDom.rollback()
            lock.release()
            raise
        else:
            self.rdfDom.commit()        
            lock.release()
            
    def partialXsltCacheKeyPredicate(self, styleSheetContents, sourceContents, kw, contextNode, styleSheetUri):
      styleSheetNotCacheableFunctions = self.NOT_CACHEABLE_FUNCTIONS
      revision = getattr(contextNode.ownerDocument, 'revision', None)            
      key = [styleSheetContents, styleSheetUri, sourceContents, contextNode,
             id(contextNode.ownerDocument), revision]
      
      styleSheet = styleSheetCache.getValue(styleSheetContents, styleSheetUri)
      
      try:
          isCacheable = styleSheet.isCacheable
      except AttributeError:
          isCacheable = styleSheet.isCacheable = isCacheableStylesheet(
                  styleSheet.children, styleSheetNotCacheableFunctions)
          if not isCacheable:
              log.debug("stylesheet %s is not cacheable" % styleSheetUri)
      #todo: similarly, the stylesheet might reference functions that are cacheable if given a chance to modify the key
          
      if not isCacheable:
          raise MRUCache.NotCacheable

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

###########################################
## http request handling
###########################################
    def guessMimeTypeFromContent(self, result):
        #obviously this could improved,
        #e.g. detect encoding in xml header or html meta tag
        #or handle the BOM mark in front of the <?xml 
        #detect binary vs. text, etc.
        if result.startswith("<html"):
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

            result = self.runActions('handle-request', kw)
            
            if result is not None: #'cause '' is OK
                #if mimetype is not set, make another attempt
                if not kw['_response'].headerMap.get('content-type'):
                    contentType = self.guessMimeTypeFromContent(result)
                    if contentType:
                        kw['_response'].headerMap['content-type']=contentType
                return result
        finally:
            self.requestContext.pop()
        
        kw['_response'].headerMap['status'] = 404 #not found
        return self._default_not_found(kw)

    def _default_not_found(self, kw):
        '''if the _not_found page is not defined, we assume we're just viewing an arbitrary rdf model -- so just print its rdfdom xml representation'''
        kw['_response'].headerMap["content-type"]="text/xml"
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
        <root>
        <xsl:apply-templates />
        </root>
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

def isXPathExprCacheable(compExpr, nsMap, notCacheableXPathFunctions):
    for field in compExpr:
        if isinstance(field, XPath.ParsedExpr.FunctionCall):
          (prefix, local) = field._key
          if prefix:
              expanded = (nsMap[prefix], local)
          else:
              expanded = field._key
          if expanded in notCacheableXPathFunctions:
              return False
    return True

def isCacheableStylesheet(nodes, styleSheetNotCacheableFunctions):
    '''walk through the elements in the stylesheet looking for
    elements that reference XPath expressions; then iterate through each 
    expression looking for functions that aren't cacheable'''
    #todo: also look for extension elements that aren't cacheable
    from Ft.Xml.Xslt import AttributeInfo, AttributeValueTemplate
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
                        if not isXPathExprCacheable(attributeValue.expression,
                            node.namespaces, styleSheetNotCacheableFunctions):
                            return False
                    elif isinstance(attributeValue, AttributeValueTemplate.AttributeValueTemplate):
                        for expr in attributeValue._parsedParts:
                            #print 'parsedPart ', expr
                            if not isXPathExprCacheable(expr, node.namespaces,
                                             styleSheetNotCacheableFunctions):
                                return False
        #handle LiteralElements
        outputAttrs = getattr(node, '_output_attrs', None) 
        if outputAttrs is not None:
            for (qname, namespace, value) in outputAttrs:
                if value is not None:
                    #value will be a AttributeValueTemplate.AttributeValueTemplate
                    for expr in value._parsedParts:
                        if not isXPathExprCacheable(expr, node.namespaces,
                                         styleSheetNotCacheableFunctions):
                            return False        
        
        if node.children is not None:
            if not isCacheableStylesheet(node.children, styleSheetNotCacheableFunctions):
                return False
    return True

DefaultContentProcessorCachePredicates = {
    'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' : lambda self, result, kw, contextNode, contents:\
        self.partialXsltCacheKeyPredicate(contents, None, kw, contextNode, 'path:'), 
    
    'http://www.w3.org/2000/09/xmldsig#base64' :
        lambda self, result, kw, contextNode, contents: contents #the key is just the contents
}

DefaultContentProcessorSideEffectsFuncs = {
    'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' : Root.xsltSideEffectsFunc }
DefaultContentProcessorSideEffectsPredicates ={
    'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' :  Root.xsltSideEffectsCalc }

#################################################
##command line handling
#################################################
DEFAULT_cmd_usage = 'python [racoon.py -l [log.config] -r -d [debug.pkl] -x -s server.cfg -p path -m store.nt] -a config.py [config specific options]'
cmd_usage = '''\nusage:
-h this help message
-s server.cfg specify an alternative server.cfg
-l [log.config] specify a config file for logging
-r record requests (ctrl-c to stop recording) 
-d [debug.pkl]: debug mode (replay the requests saved in debug.pkl)
-x exit after executing config specific cmd arguments
-p specify the path (overrides RHIZPATH env. variable)
-m [store.nt] load the RDF model (.rdf, .nt, .mk supported)
   (if file is type NTriple it will override STORAGE_PATH
   otherwise it is used as the template)
-a [config.py] run the application specified
'''

def main(argv):
    eatNext = False
    mainArgs, rootArgs = [], []
    for i in range(len(argv)):
        if argv[i] == '-a':
            rootArgs += argv[i:]
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
        log_config.fileConfig(logConfig) #todo document loggers: rhizome, server, racoon, rdfdom
        #any logger already created and not explicitly specified in the log config file is disabled
        #this seems like a bad design -- certainly took me a while to why understand things weren't getting logged
        #so re-enable the loggers
        for logger in logging.Logger.manager.loggerDict.itervalues():
            logger.disabled = 0        
    else: #set defaults        
        logging.BASIC_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"
        logging.root.setLevel(logging.INFO)
        logging.basicConfig()

    root = Root(rootArgs)
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
        import Server
        debug = '-r' in mainArgs
        #print 'starting server!'
        Server.start_server(root, debug) #kicks off the whole process
        #print 'dying!'

if __name__ == '__main__':
    main(sys.argv[1:])
