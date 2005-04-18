"""
    Markup and content processing helper classes used by Rhizome.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import re
from rx import zml, rxml, raccoon, utils, RxPath
from rx import logging #for python 2.2 compatibility
log = logging.getLogger("rhizome")

class RhizomeBaseMarkupMap(zml.LowerCaseMarkupMap):
    def __init__(self, rhizome):
        super(RhizomeBaseMarkupMap, self).__init__()
        self.rhizome = rhizome
        
    def mapLinkToMarkup( self, link, name, annotations, isImage, isAnchorName):
        #any link that just a name turn into a site:/// url
        if not isAnchorName and link and link[0] not in './#?' and link.find(':') == -1:
            link = 'site:///' + link        
        tag, attribs, text = super(RhizomeBaseMarkupMap, self).mapLinkToMarkup(
                link, name, annotations, isImage, isAnchorName)

        if tag != self.A:
            #todo: this means that interwiki links only work in <a> tags
            return tag, attribs, text

        attribDict = dict(attribs)
        url = attribDict.get('href')
        if not url:
            return tag, attribs, text
        url = url[1:-1] #strip quotes

        value = zml.xmlquote('IgnorableMetadata')
        if url.startswith('site:'):
            if self.rhizome.undefinedPageIndicator:
                attribDict['undefined']=value            
                return tag, attribDict.items(), text
            else:#unchanged 
                return tag, attribs, text
        
        schemeIndex = url.find(':')
        if schemeIndex > -1:
            scheme = url[:schemeIndex]
            if scheme == 'wiki': #e.g. wiki:meatball:something
                schemeIndex = url[schemeIndex+1:].find(':')
                if schemeIndex == -1:
                    schemeIndex = url[schemeIndex+1:].find('/')
                scheme = url[:schemeIndex]
            replacement = self.rhizome.getInterWikiMap().get(scheme.lower())
            if replacement:
                if name is None: #don't include the interlink scheme in the name
                    text = url[schemeIndex+1:]
                url = replacement + url[schemeIndex+1:]
                attribDict['href'] = zml.xmlquote(url)
                if self.rhizome.interWikiLinkIndicator:
                    if replacement[0] != '.' and not replacement.startswith('site:'):
                        attribDict['interwiki']=value                
                return tag, attribDict.items(), text
                
        external = (url.find(':') > -1 or url[0] == '/') and not url.startswith('site:')

        if external:
            if self.rhizome.externalLinkIndicator:
                attribDict['external']=value
        elif not url.startswith('#') or not url.startswith('..'): #todo: normalize with $url
            if self.rhizome.undefinedPageIndicator:
                attribDict['undefined']=value
                
        return tag, attribDict.items(), text

class DocumentMarkupMap(RhizomeBaseMarkupMap):
    TT = 'code'
    A = 'link'
    SECTION = 'section'
    IMG = 'figure' #todo: figure is block, icon is inline
    
    def __init__(self, docType,rhizome):
        super(DocumentMarkupMap, self).__init__(rhizome)
        self.docType = docType
        self.wikiStructure['!'] = (self.SECTION, 'title')

    def H(self, level, line):
        return 'section'
        
class TodoMarkupMap(RhizomeBaseMarkupMap):
    pass #todo

class SpecificationMarkupMap(DocumentMarkupMap):
    SECTION = 's'
    
    def __init__(self, rhizome):
        super(SpecificationMarkupMap, self).__init__('http://rx4rdf.sf.net/ns/wiki#doctype-specification',rhizome)
        self.wikiStructure['!'] = (self.SECTION, None)

    def canonizeElem(self, elem):
        if isinstance(elem, type(()) ) and elem[0][0] == 's' and elem[0][-1:].isdigit():
            return 's' #map section elems to s
        else:
            return elem
        
    def H(self, level, line):
        return ('s'+`level`, (('title',zml.xmlquote(line)),) )
    
class MarkupMapFactory(zml.DefaultMarkupMapFactory):
    def __init__(self, rhizome):
        self.rhizome = rhizome        

        faqMM = DocumentMarkupMap('http://rx4rdf.sf.net/ns/wiki#doctype-faq', rhizome)
        documentMM = DocumentMarkupMap('http://rx4rdf.sf.net/ns/wiki#doctype-document', rhizome)
        specificationMM = SpecificationMarkupMap(rhizome)
        todoMM = TodoMarkupMap(rhizome)
        
        self.elemMap = {
            'faq' : faqMM,
            'faqs' : faqMM,
            'document' : documentMM,
            'specification' : specificationMM,
            'todo' : todoMM,
            }

        self.mmMap = {
            'http://rx4rdf.sf.net/ns/wiki#doctype-faq': faqMM,
            'http://rx4rdf.sf.net/ns/wiki#doctype-document': documentMM,
            'http://rx4rdf.sf.net/ns/wiki#doctype-specification': specificationMM,
            }
        
    def startElement(self, elem):
        return self.elemMap.get(elem)

    def getDefault(self):        
        return RhizomeBaseMarkupMap(self.rhizome)

    def getMarkupMap(self, uri):
        mm = self.mmMap.get(uri)
        if not mm:
            return zml.DefaultMarkupMapFactory(self, uri)
        else:
            return mm

class SanitizeHTML(utils.BlackListHTMLSanitizer, raccoon.ContentProcessors.SiteLinkFixer):
    _BlackListHTMLSanitizer__super = raccoon.ContentProcessors.SiteLinkFixer

    addRelNofollow = True
    
    def handle_starttag(self, tag, attrs):
        '''
        Add support for google's anti-comment spam system 
        see http://www.google.com/googleblog/2005/01/preventing-comment-spam.html
        since we assume the user is untrusted if we're santizing the html
        '''
        if self.addRelNofollow and tag == 'a':
            needsNoFollow = [name for (name,value) in attrs
                    if name == 'href' and value.strip().startswith('http')]
            if needsNoFollow:
                relValue = [value for name,value in attrs if name=='rel']
                if relValue:
                    relValue = relValue[0]
                    attrs[attrs.index(('rel', relValue))] = ('rel', 'nofollow')                        
                    #we don't know how the value was quoted but this hack
                    #should work in almost any real world cases:
                    self._HTMLParser__starttag_text = self._HTMLParser__starttag_text.replace(
                        '"'+relValue+'"', '"nofollow"').replace("'"+relValue+"'", '"nofollow"')
                else:
                    attrs.append(('rel', 'nofollow'))
                    starttaglist = list(self._HTMLParser__starttag_text)                                                
                    starttaglist.insert(self._HTMLParser__starttag_text[-2] == '/' and -2 or -1, 
                                       ' rel="nofollow" ') 
                    self._HTMLParser__starttag_text = ''.join(starttaglist) 
        return utils.BlackListHTMLSanitizer.handle_starttag(self, tag, attrs)        

    def onStrip(self, tag, name, value):
        #should we raise an exception instead?
        if name:
            log.warning('Stripping dangerous HTML attribute: ' + name + '=' + value)
        elif value:
            if tag:
                log.warning('Stripping dangerous content from: ' + tag)
            else:
                log.warning('Stripping dangerous PI: ' + value)            
        elif tag:
            log.warning('Stripping dangerous HTML element: ' + tag)    
        else:
            log.warning('Stripping dangerous ??: %s, %s, %s' % tag, name, value)    

class TruncateHTML(utils.HTMLTruncator, SanitizeHTML):
    _HTMLTruncator__super = SanitizeHTML
    
    def onStrip(self, tag, name, value):
        #DoNotHandleException cause we don't the action error handler to catch this
        raise raccoon.DoNotHandleException('Contains HTML that can not be safely embedded in another HTML page')

class RhizomeXMLContentProcessor(raccoon.ContentProcessors.XMLContentProcessor):
    '''
    Replaces the xml/html content processor with one that sanitizes
    the markup if the user doesn't have the proper access token
    '''    
    blacklistedElements = SanitizeHTML.blacklistedElements
    blacklistedContent = SanitizeHTML.blacklistedContent 
    blacklistedAttributes = SanitizeHTML.blacklistedAttributes

    def __init__(self,sanitizeToken=None, nospamToken=None):
        super(RhizomeXMLContentProcessor, self).__init__()
        self.sanitizeToken=sanitizeToken
        self.nospamToken=nospamToken
                 
    def linkFixerFactory(self, sanitize, addNoFollow, args, kwargs):
        fixer = SanitizeHTML(*args, **kwargs)        
        fixer.addRelNofollow = addNoFollow
        fixer.blacklistedElements = sanitize and self.blacklistedElements or []
        fixer.blacklistedContent = sanitize and self.blacklistedContent or {}
        fixer.blacklistedAttributeNames = sanitize and self.blacklistedAttributes or {}
        return fixer

    def truncateHTMLFactory(self, maxwords, maxlines, args, kwargs):
        fixer = TruncateHTML(*args, **kwargs)        
                                    
        fixer.blacklistedElements = self.blacklistedElements
        fixer.blacklistedContent = self.blacklistedContent
        fixer.blacklistedAttributeNames = self.blacklistedAttributes
        if maxwords:
            fixer.maxWordCount = int(maxwords)
        if maxlines:
            fixer.maxLineCount = int(maxlines)
        return fixer
        
    def processContents(self, result, kw, contextNode, contents):
        #if the content was not created by an user with a 
        #trusted author token we need to strip out any dangerous HTML.
        #Because html maybe generated dynamically we need to check this while spitting out the HTML.
        maxwords = kw.get('maxwords') or (kw.get('_prevkw') and kw.get('_prevkw').get('maxwords'))
        maxlines = kw.get('maxlines') or (kw.get('_prevkw') and kw.get('_prevkw').get('maxlines'))
        if maxwords or maxlines:
            #we always santize the HTML when rendering HTML for a summary
            linkFixerFactory = lambda *args, **kwargs: self.truncateHTMLFactory(maxwords, maxlines, args, kwargs)
        else:
            sanitize = nofollow = True
            #get the accessTokens granted to the author of the content            
            result = kw['__server__'].evalXPath('''$__context/wiki:created-by/*/auth:has-role/*[.='http://rx4rdf.sf.net/ns/auth#role-superuser']
            | $__context/wiki:created-by/*/auth:has-rights-to/* | $__context/wiki:created-by/*/auth:has-role/*/auth:has-rights-to/*''',
                                           node=contextNode)
            for token in result:                
                if token.uri == 'http://rx4rdf.sf.net/ns/auth#role-superuser':
                    #super users can do anything
                    sanitize = nofollow = False
                    break
                elif token.uri == self.sanitizeToken:
                    santize = False
                elif token.uri == self.nospamToken:
                    nofollow = False

            if sanitize or nofollow:
                linkFixerFactory = lambda *args, **kwargs: self.linkFixerFactory(sanitize, nofollow, args, kwargs)
            else: #permission to generate any kind of html/xml -- so use the default                        
                linkFixerFactory = None

        return self.processMarkup(contents,kw['__server__'].appBase,
                                  linkFixerFactory=linkFixerFactory)

    def processMarkupCachePredicate(self, result, kw, contextNode, contents):
        return (contents, contextNode, id(contextNode.ownerDocument),
                contextNode.ownerDocument.revision,
                kw.get('maxwords') or (kw.get('_prevkw') and kw.get('_prevkw').get('maxwords')),
                kw.get('maxlines') or (kw.get('_prevkw') and kw.get('_prevkw').get('maxlines'))
                )

class PatchContentProcessor(raccoon.ContentProcessors.ContentProcessor):
    uri = 'http://rx4rdf.sf.net/ns/content#pydiff-patch-transform'

    def __init__(self, rhizome):
        super(PatchContentProcessor, self).__init__()
        self.rhizome = rhizome
        
    def processContents(self,result, kw, contextNode, contents):
        return self.rhizome.processPatch(contents, kw, result)
