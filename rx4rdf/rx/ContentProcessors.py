"""
    Content Processors used by Raccoon

    Copyright (c) 2003-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import base64
from rx import utils, Caching, MRUCache
try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO

class ContentProcessor(object):
    '''
    Base class for ContentProcessor, default behavior 
    A content processor can return a string or file-like object which supports ^read()^
    '''
    processStream = None           #define if the ContentProcessor can handle incoming streams
    getCachePredicate = None       #define if the ContentProcessor is cacheable
    getSideEffectsPredicate = None #optional method for interacting with the cache
    #a side effects predicate returns a representation of the side effects of calculating the cacheValue
    processSideEffects  = None     #optional method for interacting with the cache
    #a side effects function that will be called after a value is retrieved from the cache (use to replay side effects)
    authorize = None #optional authorization method 
    label = '' #optional human readable label
    mimetype = '' #optional associated mimetype
    
    def __init__(self, uri=None, mimetype='', label=''):
        if uri is None:
            assert self.uri, 'the uri attribute must be defined at the class or instance level'
        else:
            self.uri = uri
        if mimetype:
            self.mimetype = mimetype
        if label:
            self.label = label
            
    def processContents(self, result, kw, contextNode, contents):
        '''
        Can return either a string or a file-like object which supports ^read()^
        processContent is being called by a cache '_preferStreamThreshhold' will be added to
        kw. To allow the result to be cached processContents should not return a 
        If the ContentProcessor is cachable, it should check for the exist of 
        in kw to see if this is being called by cache. If so, it should not return a stream
        if the size of the streaming content is less than value of '_preferStreamThreshhold'
        (which hold the maximum size the cache can handle).
        '''
        return contents

    def isValueCacheablePredicate(key, value, *args, **kwargs):
        '''
        This will be called to determine if a newly calculated
        value should be added to the cache (usually the
        contentProcessorCachePredicate takes care of this but
        sometimes you need to look at the resulting value itself)

        The default behavior is check if the value is a stream
        (by checking for a 'read' attribute)
        '''
        return not hasattr(value,'read')
    
class StreamingNoOpContentProcessor(ContentProcessor):
    def processStream(self, result, kw, contextNode, stream):
        '''
        Just return the stream
        '''
        return stream    

class Base64ContentProcessor(ContentProcessor):
    uri = 'http://www.w3.org/2000/09/xmldsig#base64'
    
    def processContents(self,result, kw, contextNode, contents):
        return base64.decodestring(contents)

    def getCachePredicate(self,result, kw, contextNode, contents):
        return contents

class SiteLinkFixer(utils.LinkFixer):
    '''
    Converts site: URLs to external (usually http) URLs.
    Absolute site links ('site:///') are fixed up as follows:
    
    url: If a relative url of the current document is specified site:/// links will be converted to relative paths.
    e.g. if the relative doc url is 'folder/foo/bar' then the 'site:///' prefix will be replaced with '../../'
    
    baseurl: Otherwise they will be replaced by prepending the specified baseurl (which defaults to '/')
    
    Relative site URLs ('site:') just have their 'site:' prefix stripped off
    '''
    def __init__(self, out, baseurl = '/', url = None, enableFormatPI = True):
        utils.LinkFixer.__init__(self, out)
        self.nextFormat = None
        self.ignorePIs = not enableFormatPI                
        if url is not None:
            #here we try to calculate a relative path from the base url back to the root
            #the advantage here is that 
            #too complicated to test right now
            index = url.find('?')
            if index > -1:
                url = url[:index]
            else:
                index = url.find('#')
                if index > -1:
                    url = url[:index]
            dirCount = url.count('/')                    
            self.rootpath = '../' * dirCount
        else:
            if baseurl[-1] != '/':                        
                baseurl = baseurl + '/'
            self.rootpath = baseurl 
        #print 'rootpath', repr(url), self.rootpath, baseurl

    def handle_pi(self, data):
        if data.startswith('raccoon-ignore'):
            self.ignorePIs = True
        elif not self.ignorePIs and data.startswith('raccoon-format'):
            self.nextFormat = data.split()[1].strip()                
            if self.nextFormat and self.nextFormat[-1] == '?': #data includes the final ?
                self.nextFormat = self.nextFormat[:-1]
        else:
            return utils.LinkFixer.handle_pi(self, data)
            
    def needsFixup(self, tag, name, value):
        if not value:
            return False
        elif (tag in ['script', 'style', 'link'] #in javascript,style, link (for rss)
              or (not name and value[0] == '<') #in comment/PI/doctype
              or name): #in attribute
            return value.find('site:') > -1
        else:
            return False

    def doFixup(self, tag, name, value, hint):
        '''
        replaces an absolute site reference with relative path to the root
        '''
        #first replace any absolute site URL prefix with rootpath

        #print 'replace ', value
        value = value.replace('site:///', self.rootpath)
        #print 'with', value
        #for any other site: URLs we assume they're relative and just strip out the 'site:'
        return value.replace('site:', '')

class XMLContentProcessor(ContentProcessor):
    uri = 'http://rx4rdf.sf.net/ns/wiki#item-format-xml'
    label = 'XML/XHTML'
    mimetype = 'text/html' #todo
    
    def processContents(self, result, kw, contextNode, contents):
        return self.processMarkup(contents, kw['__server__'].appBase)

    def getCachePredicate(self, result, kw, contextNode, contents):
        return contents

    def processMarkup(self, contents, baseURL, docpath=None, linkFixerFactory=None):
        ''' HTML/XML content processors. Fixes up any 'site:' URLs
        that appear in the XML or HTML content and handle
        <?raccoon-format contentprocessURI ?> processor
        instruction. '''
        out = StringIO.StringIO()
        if not linkFixerFactory:
            linkFixerFactory = SiteLinkFixer    
        fixlinks = linkFixerFactory(out, url=docpath, baseurl=baseURL)
        fixlinks.feed(contents)
        fixlinks.close()
        if fixlinks.nextFormat:
            return out.getvalue(), fixlinks.nextFormat
        else:
            return out.getvalue()

class RxSLTContentProcessor(ContentProcessor):
    uri = 'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt'
    label = 'RxSLT'

    def processContents(self, result, kw, contextNode, contents):        
        return kw['__server__'].processRxSLT(str(contents.strip()), kw)

    def getCachePredicate(self, result, kw, contextNode, styleSheetContents):
        styleSheetKeys = Caching.getXsltCacheKeyPredicate(kw['__server__'].styleSheetCache,
                            kw['__server__'].NOT_CACHEABLE_FUNCTIONS, styleSheetContents,
                            None, kw, contextNode, 'path:')            
        if isinstance(styleSheetKeys, MRUCache.NotCacheable):
            kw['__server__'].log.debug("stylesheet %s is not cacheable" % styleSheetUri)
        return styleSheetKeys
        
    def getSideEffectsPredicate(self, cacheValue, resultNodeset, kw, contextNode, retVal):
        return Caching.xsltSideEffectsCalc(cacheValue, resultNodeset, kw, contextNode, retVal)

    def processSideEffects(self, cacheValue, sideEffects, resultNodeset, kw, contextNode, retVal):
        return Caching.xsltSideEffectsFunc(cacheValue, sideEffects, resultNodeset, kw, contextNode, retVal)

class RxUpdateContentProcessor(ContentProcessor):
    uri = 'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate'
    label = 'RxUpdate'
    
    def processContents(self, result, kw, contextNode, contents):
        return kw['__server__'].processXUpdate(str(contents.strip()), kw)

class PythonContentProcessor(ContentProcessor):
    uri = 'http://rx4rdf.sf.net/ns/wiki#item-format-python'
    label = 'Python'

    def processContents(self, result, kw, contextNode, contents):
        return kw['__server__'].processPython(contents, kw)

    def authorize(self, contents, formatType, kw, dynamicFormat):
        return kw['__server__'].authorizeByDigest(contents, formatType, kw, dynamicFormat)

class CombinedReadOnlyStream:
    def __init__(self, left, right):
        self.left = left
        self.right = right
        
    def read(self, max=-1):        
        buffer = self.left.read(max)
        if max < 0:
            return buffer + self.right.read(max)
        sofar = len(buffer)
        if sofar < max:
            return buffer + self.right.read(max - sofar)
        else:
            return buffer

    def close():
        if hasattr(self.left, 'close'):
            self.left.close()
        if hasattr(self.right, 'close'):
            self.right.close()

DefaultContentProcessors = [
    StreamingNoOpContentProcessor('http://rx4rdf.sf.net/ns/wiki#item-format-text',
                     mimetype='text/plain', label='Text'),    
    StreamingNoOpContentProcessor('http://rx4rdf.sf.net/ns/wiki#item-format-binary',
                     mimetype='application/octet-stream', label='Binary'),
    Base64ContentProcessor(),
    XMLContentProcessor(),
    RxSLTContentProcessor(),
    RxUpdateContentProcessor(),
    PythonContentProcessor(),
]
                    
# we define a couple of content processors here instead of in Raccoon because
# they make assumptions about the underlying schema
class XSLTContentProcessor(ContentProcessor):
    uri = 'http://www.w3.org/1999/XSL/Transform' 
    label = 'XSLT'

    def _getStyleSheetURI(self, kw, contextNode):
        return kw.get('_contentsURI') or kw['__server__'].evalXPath( 
            'concat("site:///", (/a:NamedContent[wiki:revisions/*/*[.=$__context]]/wiki:name)[1])',
            node=contextNode)
    
    def processContents(self, result, kw, contextNode, contents):
        return kw['__server__'].processXslt(contents, kw['_contents'], kw,
                uri=self._getStyleSheetURI(kw, contextNode) )

    def getCachePredicate(self, result, kw, contextNode, styleSheetContents):
        styleSheetKeys = Caching.getXsltCacheKeyPredicate(
                            kw['__server__'].styleSheetCache,
                            kw['__server__'].NOT_CACHEABLE_FUNCTIONS, styleSheetContents,
                            kw['_contents'], kw, contextNode,
                                    styleSheetUri=self._getStyleSheetURI(kw, contextNode))

        if isinstance(styleSheetKeys, MRUCache.NotCacheable):
            kw['__server__'].log.debug("stylesheet %s is not cacheable" % styleSheetUri)
        return styleSheetKeys
                
    def getSideEffectsPredicate(self, cacheValue, resultNodeset, kw, contextNode, retVal):
        return Caching.xsltSideEffectsCalc(cacheValue, resultNodeset, kw, contextNode, retVal)

    def processSideEffects(self, cacheValue, sideEffects, resultNodeset, kw, contextNode, retVal):
        return Caching.xsltSideEffectsFunc(cacheValue, sideEffects, resultNodeset, kw, contextNode, retVal)

from rx import zml
class ZMLContentProcessor(ContentProcessor):
    uri = 'http://rx4rdf.sf.net/ns/wiki#item-format-zml'
    label = 'ZML'

    markupMapFactory = None
    
    undefinedPageIndicator=True
    externalLinkIndicator=True
    interWikiLinkIndicator=True

    def getInterWikiMap(self):
        return {}
    
    def getCachePredicate(self, result, kw, contextNode, contents):
        return contents
                
    def processZMLSideEffects(self, contextNode, kw):
        #optimization: only set the doctype (which will invoke wiki2html.xsl if we need links to be transformed)
        if self.undefinedPageIndicator or self.externalLinkIndicator or self.interWikiLinkIndicator:
            #wiki2html.xsl shouldn't get invoked with the doctype isn't html
            if not kw.get('_doctype') and kw['__server__'].evalXPath(
                "not(wiki:doctype) or wiki:doctype = 'http://rx4rdf.sf.net/ns/wiki#doctype-xhtml'",
                    node = contextNode):
                kw['_doctype'] = 'http://rx4rdf.sf.net/ns/wiki#doctype-wiki'

    def processSideEffects(self, cacheValue, sideEffects, resultNodeset, kw, contextNode, retVal):
        return self.processZMLSideEffects(contextNode, kw)
        
    def processContents(self, result, kw, contextNode, contents):
        self.processZMLSideEffects(contextNode, kw)
        contents = zml.zmlString2xml(contents,self.markupMapFactory)
        #todo: optimize: don't fix up links if doctype is set since we're gonna do that again anyway
        return (contents, 'http://rx4rdf.sf.net/ns/wiki#item-format-xml') #fixes up site://links

   
