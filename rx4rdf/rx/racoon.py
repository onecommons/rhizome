"""
    Engine and helper classes for Racoon

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import utils, glock
from RDFDom import *
from Ft.Rdf.Drivers import Memory
import os, time, cStringIO, sys, base64, mimetypes, types
from Ft.Xml.Lib.Print import PrettyPrint
from Ft.Xml.XPath.Conversions import StringValue        
from Ft.Xml import SplitQName
from Ft.Xml.XPath import RuntimeException,FT_EXT_NAMESPACE
from Ft.Lib import Uri, UriException
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
    return generateBnode(name)

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

def AssignMetaData(kw, context, name, val):
    '''
    new variable and values don't affect corresponding xpath variable 
    '''
    def _assign(local, dict):
        #oldval = dict.get(local, None)
        dict[local] = val
        return val
    #print >>sys.stderr,'AssignMetaData ', name, ' ' , val
    return _onMetaData(kw, context, name, _assign)

def RemoveMetaData(kw, context, name):
    def _delete(local, dict):
        if dict.has_key(local):
            del dict[local]
            return True
        else:
            return False
    return _onMetaData(kw, context, name, _delete)

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
    else:
        raise 'unusable namespace: ', namespace 
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
        #print 'invoke', kw
        kw.update( self.server.requestContext )
        kw['_name']=name
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

class Action(object):    
    def __init__(self, queries, action = None, matchFirst = True, forEachNode = False, depthFirst = True, requiresContext = False):
        '''Queries is a list of RxPath expressions associated with this action
Action must be a function with this signature:    
def action(resultNodeset, kw, contextNode, retVal) where:
    resultNodeset is result of the RxPath expression associated with this action
    kw is dictionary of the parameters associated with the request
    contentNode is context node of used when the RxPath expressions were evaluated
    retVal was return value of the last action invoked in the in action sequence or None
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

    import MRUCache
    import Ft.Xml.XPath
    expCache = MRUCache.MRUCache(200, XPath.Compile)
    
    def __init__(self,argv):
        self.requestContext = {}
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
        #else: todo: support for xml, rdf? 
        def initConstants(varlist, default):
            import copy 
            for name in varlist:                
                value = kw.get(name, copy.copy(default))
                if not isinstance(value, type(default)):
                    raise 'config variable %s must be compatible with type %s' % name, type(default)
                setattr(self, name, value)
                        
        initConstants( [ 'nsMap', 'extFunctions', 'contentProcessors', 'actions'], {} )
        initConstants( [ 'STORAGE_PATH', 'STORAGE_TEMPLATE_PATH', 'STORAGE_TEMPLATE', 'APPLICATION_MODEL'], '')
        initConstants( ['ROOT_PATH'], '/')
        assert self.ROOT_PATH[0] == '/', "ROOT_PATH must start with a '/'"
        initConstants( ['BASE_MODEL_URI'], self.BASE_MODEL_URI)
        initConstants( ['MAX_MODEL_LITERAL'], -1)
        self.SAVE_DIR = kw.get('SAVE_DIR', 'content/')
        self.PATH = kw.get('PATH', self.PATH)
        self.SECURE_FILE_ACCESS= kw.get('SECURE_FILE_ACCESS', True)        
        self.cmd_usage = DEFAULT_cmd_usage + kw.get('cmd_usage', '')    
        self.nsMap.update(DefaultNsMap)
        self.contentProcessors.update(DefaultContentProcessors)
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
        source = self.source
        if not source:
            if os.path.exists(self.STORAGE_PATH):
                source = self.STORAGE_PATH
            else:
                if not os.path.exists(self.STORAGE_TEMPLATE_PATH):
                    outputfile = file(self.STORAGE_TEMPLATE_PATH, "w+", -1)
                    outputfile.write(self.STORAGE_TEMPLATE)
                    outputfile.close()
                source = self.STORAGE_TEMPLATE_PATH
        else:
            if source.endswith('.nt'):
                self.STORAGE_PATH = source
            else:
                self.STORAGE_PATH = os.path.splitext(self.source)[0] + '.nt'
                                    
        if not self.lock:
            lockName = self.STORAGE_PATH + '.lock'
            self.lock = glock.GlobalLock(lockName)
            
        lock = self.getLock()
        
        model, memorydb = utils.deserializeRDF(source)        
        if self.APPLICATION_MODEL:
            utils.DeserializeFromN3File(cStringIO.StringIO(self.APPLICATION_MODEL), model = model, scope='application')
                                        
        self.revNsMap = dict(map(lambda x: (x[1], x[0]), self.nsMap.items()) )#reverse namespace map #todo: bug! revNsMap doesn't work with 2 prefixes one ns
        self.rdfDom = RDFDoc(model, self.revNsMap)
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

    COMPLEX_REQUESTVARS = ['__requestor__', '__server__','_request', '_response','_session', '_prevkw', '__argv__']
    
    def mapToXPathVars(self, kw):
        '''map request kws to xpath vars (include http request headers)'''
        extFuncs = self.extFunctions.copy()
        extFuncs.update({
        (RXWIKI_XPATH_EXT_NS, 'assign-metadata') : lambda context, name, val: AssignMetaData(kw, context, name, val),
        (RXWIKI_XPATH_EXT_NS, 'remove-metadata') : lambda context, name: RemoveMetaData(kw, context, name),
        (RXWIKI_XPATH_EXT_NS, 'has-metadata') : lambda context, name: HasMetaData(kw, context, name),
        (RXWIKI_XPATH_EXT_NS, 'get-metadata') : lambda context, name: GetMetaData(kw, context, name),        
        })
        #add most kws to vars (skip references to non-simple types):
        vars = dict( [( (None, x[0]), x[1] ) for x in kw.items()\
                      if x[0] not in self.COMPLEX_REQUESTVARS] )       
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
            if not vars:
                context = node or self.rdfDom 
                vars = { (None, '_context'): [ context ] } #we also set this in doActions()
            return evalXPath(self.rdfDom, xpath, nsMap = self.nsMap, vars=vars, extFunctionMap = extFunctionMap , node = node, expCache = self.expCache)
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
                    if name == '_resource' and isinstance(result, type([])): #todo: fix this hack to work around xlst bug
                        result = result[0]
                    kw[name] = result
                    break
            if not result:
                kw[name] = result
            
    def doActions(self, sequence, kw = None, contextNode = None, retVal = None):
        if kw is None: kw = {}
        kw['__requestor__'] = self.requestDispatcher
        kw['__server__'] = self 
        for action in sequence:
            if isinstance(contextNode, type([])):
                contextNode = contextNode[0]
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
                                result.reverse()#we probably want the reverse of document order (e.g. the deepest first)
                            for node in result:
                                retVal = action.action(node, kw, contextNode, retVal)
                        else:
                            retVal = action.action(result, kw, contextNode, retVal)
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
        for k, v in kw.items():
            #initialize the templates variable map copying the core request kws
            #and copy the rest (the application specific kws) to _prevkw
            #this way the template processing doesn't mix with the orginal request
            #but are made available in the 'previous' namespace (think of them as template parameters)
            if k in self.COMPLEX_REQUESTVARS + globalVars:
                templatekw[k] = v
            else:
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

    def transform(self, stylesheet, kw=None):
        if kw is None: kw = {}        
        vars, funcs = self.mapToXPathVars(kw)
        return applyXslt(self.rdfDom, stylesheet, vars, funcs, baseUri='path:')

    def xupdateRDFDom(self, rdfDom, outputfile, xupdate=None, kw=None, uri=None):
        kw = kw or {}
        baseUri= uri or 'path:'
        vars, funcs = self.mapToXPathVars(kw)
        applyXUpdate(rdfDom, xupdate, vars, funcs, uri=baseUri)

        #rdfDomOutput = StringIO.StringIO()                  
        #Ft.Xml.Lib.Print.PrettyPrint(rdfDom, asHtml=1, stream=rdfDomOutput)
        #print rdfDomOutput.getvalue()
                          
        db = Memory.CreateDb('', 'default')
        outputModel = Ft.Rdf.Model.Model(db)                
        treeToModel(rdfDom, outputModel, '') #just save the default scope, not the 'application' scope
        stmts = db._statements['default'] #get statements directly, avoid copying list
        utils.writeTriples(stmts, outputfile)
        
    def xupdate(self, xupdate=None, kw=None, uri=None):        
        if kw is None: kw = {}
        baseUri=uri or 'path:'
        #print xupdate
        lock = self.getLock()
        #todo: use _xupdateRDFDom with "two-phase commit" to temp file
        vars, funcs = self.mapToXPathVars(kw)
        applyXUpdate(self.rdfDom, xupdate,  vars = vars, extFunctionMap = funcs, uri=baseUri)
        db = Memory.CreateDb('', 'default')
        outputModel = Ft.Rdf.Model.Model(db)        
        treeToModel(self.rdfDom, outputModel, '') #just save the default scope, not the 'application' scope
        outputfile = file(self.STORAGE_PATH, "w+", -1)
        stmts = db._statements['default'] #get statements directly, avoid copying list
        utils.writeTriples(stmts, outputfile)
        ##end xupdateRDFDom
        outputfile.close()        
        self.loadModel()
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
   
    def processXslt(self, source, contents, kw = None, uri='path:'):
        if kw is None: kw = {}
        vars, extFunMap = self.mapToXPathVars(kw)
        from Ft.Xml.Xslt.Processor import Processor
        processor = Processor()
        #print 'xslt ', uri
        #print 'xslt template:', source
        #print 'xslt source: ', contents
        processor.appendStylesheet( InputSource.DefaultFactory.fromString(source, uri)) 
        for (k, v) in extFunMap.items():
            namespace, localName = k
            processor.registerExtensionFunction(namespace, localName, v)        
        return processor.run(InputSource.DefaultFactory.fromString(contents, uri), topLevelParams = vars) 
    
    def processRxML(self, xml, resources=None):      
      from Ft.Xml import Domlette
      import rxml
      #parse the xml    
      isrc = InputSource.DefaultFactory.fromString(xml)
      #print >>sys.stderr, 'rxml', xml
      doc = Domlette.NonvalidatingReader.parse(isrc)
      #replace the resources with the statements in the doc
      #should we assert the doc only has statements about this resource?
      #delete our resource from the dom:      
      #print >>sys.stderr, 'resources', resources
      lock = self.getLock()
      if resources:
          if not isinstance(resources, ( types.ListType, types.TupleType ) ):
            resources = ( resources, )
          for resource in resources:
              self.rdfDom.removeChild(resource)
      #write RDFDom out to a model 
      db = Memory.CreateDb('', 'default')
      outputModel = Ft.Rdf.Model.Model(db)
      treeToModel(self.rdfDom, outputModel, '') #just save the default scope, not the 'application' scope  
      #update the model with the resource's new statements
      nsMap = self.nsMap.copy()
      nsMap.update( { 
                    None : rxml.RX_NS,
                   'rx': rxml.RX_NS  
                    })
      
      rxml.addRxdom2Model(doc, outputModel, nsMap , self.rdfDom)        
      #save and reload the model
      outputfile = file(self.STORAGE_PATH, "w+", -1)        
      stmts = db._statements['default'] #get statements directly, avoid copying list
      utils.writeTriples(stmts, outputfile)
      outputfile.close()      
      self.loadModel()
      lock.release()      

###########################################
## http request handling
###########################################
        
    def handleRequest(self, _name_, **kw):
        #print 'name:', _name_
        kw['_name'] = _name_ #explictly replace _name -- do it this way to avoid TypeError: handleRequest() got multiple values for keyword argument '_name'

        i=_name_.rfind('.')
        if i!=-1:
            ext=_name_[i:]      
            contentType=mimetypes.types_map.get(ext, "text/html")
            kw['_response'].headerMap['content-type']=contentType

        try:
            rc = {}
            rc['_session']=kw['_session']
            #todo: probably should put request.simpleCookie in the requestContext somehow too
            self.requestContext= rc

            result = self.runActions('handle-request', kw)
            
            if result is not None: #'cause '' is OK
                return result
        finally:
            self.requestContext = {}
        
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

if __name__ == '__main__':
    eatNext = False
    mainArgs, rootArgs = [], []
    for i in range(1, len(sys.argv)):
        if sys.argv[i] == '-a':
            rootArgs += sys.argv[i:]
            break        
        if sys.argv[i] in ['-d', '-r', '-x', '-s', '-l', '-h', '--help'] or (eatNext and sys.argv[i][0] != '-'):
            eatNext = sys.argv[i] in ['-d', '-s', '-l']
            mainArgs.append( sys.argv[i] )
        else:
            rootArgs.append( sys.argv[i] )
            
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
        logging.basicConfig()

    root = Root(rootArgs)
       
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
        Server.start_server(root, debug) #kicks off the whole process
