"""
    URI resolves used by Raccoon
    Adds 'site:' and 'path:' URI schemes and takes over the 'file:'
    URL scheme to enable caching and secure access to the file system.

    Copyright (c) 2003-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import os, time, cStringIO, sys, base64, mimetypes, types, traceback
import urllib, re
from rx import MRUCache
from Ft.Lib import Uri

try:
    #needed for 4Suite versions > 1.0a3
    import Ft.Lib.Resolvers    
except ImportError:
    from Ft.Lib import UriException
    old4Suite = True
else:
    #import succeeded, use new-style UriException
    old4Suite = False
    def UriException(error, uri, msg):
        assert error == Ft.Lib.UriException.RESOURCE_ERROR
        return Ft.Lib.UriException(error, loc=uri, msg=msg)
    UriException.RESOURCE_ERROR = Ft.Lib.UriException.RESOURCE_ERROR
    
try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO

from rx import logging #for python 2.2 compatibility
log = logging.getLogger("raccoon")

def getFileCacheKey(path, maxSize = 0):    
    stats = os.stat(path)
    #raise notcacheable if the size is too big so we don't
    #waste the cache on a few large files
    if maxSize > 0 and stats.st_size > maxSize:
        raise MRUCache.NotCacheable
    return os.path.abspath(path), stats.st_mtime, stats.st_size

#this is disabled by default as it has a capacity of 0
#the root request processor instance sets its size based on the config setting.
fileCache = MRUCache.MRUCache(0, hashCalc = getFileCacheKey,
                capacityCalc = lambda k, v: k[2],
                valueCalc = lambda path: SiteUriResolver._resolveFile(path).read() )

class SiteUriResolver(Uri.SchemeRegistryResolver):
    '''
    SiteUriResolver supports the site URI scheme which is used to enable a Raccoon request to be invoked via an URL.
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
        self.supportedSchemes = root.DEFAULT_URI_SCHEMES[:]
        self.handlers['site'] = self.resolveSiteScheme
        self.supportedSchemes.append('site')
        self.server = root
        self.path=root.PATH.split(os.pathsep)
        self.handlers['path'] = self.resolvePathScheme
        self.supportedSchemes.append('path')
        if root.SECURE_FILE_ACCESS:
            self.handlers['file'] = self.secureFilePathresolve
        self.uriwhitelist = root.uriResolveWhitelist
        self.uriblacklist = root.uriResolveBlacklist

    def resolve(self, uri, base=None):
        if base:
           uri = self.normalize(uri, base)
        elif old4Suite:
            #workaround bug in older 4Suite, base resolve does check supportedSchemes
            self.normalize(uri, uri)
        if self.uriwhitelist:
            for regex in self.uriwhitelist:
                if re.match(regex,uri):
                    break
            else:
                raise UriException(UriException.RESOURCE_ERROR, uri, 'Unauthorized') 
        elif self.uriblacklist:
            for regex in self.uriblacklist:
                if re.match(regex,uri):
                    raise UriException(UriException.RESOURCE_ERROR, uri, 'Unauthorized') 
        return Uri.SchemeRegistryResolver.resolve(self, uri,base)

    def getPrefix(self, path):
        '''
        Return the PATH prefix that contains the given path (as an absolute path) or return an empty string.
        '''
        for prefix in self.path:
            absprefix = os.path.abspath(prefix)
            if os.path.abspath(path).startswith(absprefix):
                return absprefix
        return ''

    def OsPathToPathUri(path):
        fileUri = Uri.OsPathToUri(path, attemptAbsolute=False)
        return 'path:' + fileUri[len('file:'):].lstrip('/')
    OsPathToPathUri = staticmethod(OsPathToPathUri)

    def PathUriToOsPath(self, path):
        if path.startswith('path:'):
            #print 'path', path
            path = path[len('path:'):]

        prefix = self.findPrefix(path)
        return os.path.abspath(os.path.join(prefix, path))

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

    def findPrefix(self, uri):
        path = uri
        if path.startswith('path:'):
            #print 'path', path
            path = uri[len('path:'):]

        for prefix in self.path:                
            filepath = os.path.join(prefix.strip(), path)
            #check to make sure the path url was trying to sneak outside the path (i.e. by using ..)
            if self.server.SECURE_FILE_ACCESS:
                if not os.path.abspath(filepath).startswith(os.path.abspath(prefix)):                        
                    continue
            if os.path.exists(filepath):
               return prefix

        for prefix in self.path:                
            filepath = os.path.join(prefix.strip(), path)
            #check to make sure the path url was trying to sneak outside the path (i.e. by using ..)
            if self.server.SECURE_FILE_ACCESS:
                if not os.path.abspath(filepath).startswith(os.path.abspath(prefix)):
                    continue
            return prefix
        
        return '' #no safe prefix
                             
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
        log.debug('resolving uri: ' + uri)
        if base:
            uri = self.normalize(uri, base) 
        paramMap = {}
        if isinstance(uri, unicode):
            #we need uri to be a string so paramMap below will contain strings not unicode
            uri = uri.encode('utf8') 
        path = uri

        i=path.find('?')
        if i!=-1:
            if path[i+1:]:
                for _paramStr in path[i+1:].split('&'):
                    _sp=_paramStr.split('=')
                    if len(_sp)==2:
                        _key, _value=_sp
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
        if path and path[-1]=='/':
            path=path[:-1] # Remove trailing '/' if any
            trailingSlash = True
        else:
            trailingSlash = False
            
        if path.startswith('site://'):
            #print 'path', path
            name = path[len('site://'):] #assume we only get requests inside our home path
        else:
            name = path
        while name and name[0]=='/':
            name=name[1:] # Remove starting '/' if any e.g. from site:///

        if trailingSlash:
            paramMap['_path'] = name+'/'
        try:
            #print 'to resolve!', name, ' ', uri, paramMap
            contents = self.server.requestDispatcher.invoke__(name, **paramMap)
            #print 'resolved', name, ': ', contents
            if hasattr(contents, 'read'): #if its a stream
                return contents            
            if isinstance(contents, unicode):
                contents = contents.encode('utf8')
            return StringIO.StringIO( contents )
        except AttributeError, e: #not found'
            raise UriException(UriException.RESOURCE_ERROR, uri, 'Not Found')
