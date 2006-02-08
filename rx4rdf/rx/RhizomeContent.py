"""
    Markup and content processing helper classes used by Rhizome.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx.RhizomeBase import *

class RhizomeBaseMarkupMap(zml.LowerCaseMarkupMap):
    def __init__(self, rhizome):
        super(RhizomeBaseMarkupMap, self).__init__()
        self.rhizome = rhizome
        
    def mapLinkToMarkup( self, link, name, annotations, isImage, isAnchorName):
        rhizome = self.rhizome
        #any link that is just a plain name turn into a site:/// url
        if (not isAnchorName and link and link[0] not in './#?'
            and link.find(':') == -1):
            link = 'site:///' + link
        tag, attribs, text = super(
            RhizomeBaseMarkupMap, self).mapLinkToMarkup(
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
            if rhizome and rhizome.undefinedPageIndicator:
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
            replacement = rhizome and rhizome.getInterWikiMap().get(
                scheme.lower())
            if replacement:                
                if name is None:
                    #don't include the interlink scheme in the name
                    text = url[schemeIndex+1:]
                url = replacement + url[schemeIndex+1:]
                attribDict['href'] = zml.xmlquote(url, escape=False)
                if rhizome and rhizome.interWikiLinkIndicator:
                    if replacement[0] != '.' and not replacement.startswith(
                        'site:'):
                        attribDict['interwiki']=value                
                return tag, attribDict.items(), text
                
        external = (url.find(':') > -1 or url[0] == '/'
                    ) and not url.startswith('site:')

        if external:
            if rhizome and rhizome.externalLinkIndicator:
                attribDict['external']=value
        elif not url.startswith('#') or not url.startswith('..'):
            #todo: normalize with $url
            if rhizome and rhizome.undefinedPageIndicator:
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

class DocBookMarkupMap(DocumentMarkupMap):
    P = 'para'
    PRE = 'programlisting' #todo: should be literallayout but first fix xsl
    IMG = 'graphic' #todo: src : fileref, alt : srccredit (sort of)
    A = 'ulink' #todo: url instead of href
    TT = 'computeroutput' #todo: should be literal but first fix xsl
    TABLE = 'informaltable'
    LI = 'listitem'
    UL = 'itemizedlist'
    OL = 'orderedlist' 
    
class SpecificationMarkupMap(DocumentMarkupMap):
    SECTION = 's'
    
    def __init__(self, rhizome):
        super(SpecificationMarkupMap, self).__init__(
            'http://rx4rdf.sf.net/ns/wiki#doctype-specification',rhizome)
        self.wikiStructure['!'] = (self.SECTION, None)

    def canonizeElem(self, elem):
        if isinstance(
            elem, type(()) ) and elem[0][0] == 's' and elem[0][-1:].isdigit():
            return 's' #map section elems to s
        else:
            return elem
        
    def H(self, level, line):
        return ('s'+`level`, (('title',zml.xmlquote(line)),) )
    
class MarkupMapFactory(zml.DefaultMarkupMapFactory):
    def __init__(self, rhizome=None):
        self.rhizome = rhizome        

        faqMM = DocumentMarkupMap(
            'http://rx4rdf.sf.net/ns/wiki#doctype-faq', rhizome)
        documentMM = DocumentMarkupMap(
            'http://rx4rdf.sf.net/ns/wiki#doctype-document', rhizome)
        specificationMM = SpecificationMarkupMap(rhizome)
        todoMM = TodoMarkupMap(rhizome)
        docbookMM = DocBookMarkupMap(
            'http://rx4rdf.sf.net/ns/wiki#doctype-docbook', rhizome)
        
        self.elemMap = {
            'faq' : faqMM,
            'faqs' : faqMM,
            'document' : documentMM,
            'section' : documentMM,
            'specification' : specificationMM,
            'todo' : todoMM,
            
            'set' : docbookMM,
            'book' : docbookMM,
            'chapter' : docbookMM,
            'article' : docbookMM,
            }

        self.mmMap = {
        'http://rx4rdf.sf.net/ns/wiki#doctype-faq': faqMM,
        'http://rx4rdf.sf.net/ns/wiki#doctype-document': documentMM,
        'http://rx4rdf.sf.net/ns/wiki#doctype-specification': specificationMM,
        'http://rx4rdf.sf.net/ns/wiki#doctype-docbook': docbookMM,
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

class SanitizeHTML(utils.BlackListHTMLSanitizer,
                   raccoon.ContentProcessors.SiteLinkFixer):
    _BlackListHTMLSanitizer__super = raccoon.ContentProcessors.SiteLinkFixer

    addRelNofollow = True
    
    def handle_starttag(self, tag, attrs):
        '''
        Add support for google's anti-comment spam system (see
        http://www.google.com/googleblog/2005/01/preventing-comment-spam.html)
        since we assume the user is untrusted if we're santizing the
        html
        '''
        if self.addRelNofollow and tag == 'a':
            needsNoFollow = [name for (name,value) in attrs
                    if name == 'href' and value.strip().startswith('http')]
            if needsNoFollow:
                relValue = [value for name,value in attrs if name=='rel']
                #ugly: modify private HTMLParser variable
                if relValue:
                    #replace the existing rel value with 'nofollow'
                    relValue = relValue[0]
                    attrs[attrs.index(('rel', relValue))] = ('rel', 'nofollow')                        
                    #we don't know how the value was quoted but this hack
                    #should work in almost any real world cases:
                    newStartTagText=self._HTMLParser__starttag_text.replace(
                        '"'+relValue+'"', '"nofollow"').replace(
                            "'"+relValue+"'", '"nofollow"')                    
                    self._HTMLParser__starttag_text = newStartTagText
                else:
                    attrs.append(('rel', 'nofollow'))
                    starttaglist = list(self._HTMLParser__starttag_text)                                                
                    starttaglist.insert(
                        self._HTMLParser__starttag_text[-2] == '/' and -2 or -1, 
                        ' rel="nofollow" ') 
                    self._HTMLParser__starttag_text = ''.join(starttaglist) 
        return utils.BlackListHTMLSanitizer.handle_starttag(self, tag, attrs)        

    def onStrip(self, tag, name, value):
        #should we raise an exception instead?
        if name:
            log.warning('Stripping dangerous HTML attribute: '
                        + name + '=' + value)
        elif value:
            if tag:
                log.warning('Stripping dangerous content from: ' + tag)
            else:
                log.warning('Stripping dangerous PI: ' + value)            
        elif tag:
            log.warning('Stripping dangerous HTML element: ' + tag)    
        else:
            log.warning('Stripping dangerous ??: %s, %s, %s'
                        % tag, name, value)    

class TruncateHTML(utils.HTMLTruncator, SanitizeHTML):
    _HTMLTruncator__super = SanitizeHTML
    
    def onStrip(self, tag, name, value):
        #use DoNotHandleException because we don't the action error handler
        #to catch this
        raise raccoon.DoNotHandleException(
        'Contains HTML that can not be safely embedded in another HTML page')

class RhizomeXMLContentProcessor(
    raccoon.ContentProcessors.XMLContentProcessor):
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
        if sanitize:
            fixer.blacklistedElements = self.blacklistedElements
            fixer.blacklistedContent = self.blacklistedContent
            fixer.blacklistedAttributeNames = self.blacklistedAttributes
        else:
            fixer.blacklistedElements = []
            fixer.blacklistedContent = {}
            fixer.blacklistedAttributeNames = {}            
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

    def getMaxes(self,kw):
        return (kw.get('maxwords') or (kw.get('_prevkw')
                        and kw.get('_prevkw').get('maxwords')),
                kw.get('maxlines') or (kw.get('_prevkw')
                        and kw.get('_prevkw').get('maxlines')))
        
    def processContents(self, result, kw, contextNode, contents):
        '''If the content was not created by an user with a trusted
        author token we need to strip out any dangerous HTML. Because
        html maybe generated dynamically, we need to check this while
        spitting out the HTML.
        '''
        maxwords, maxlines = self.getMaxes(kw)
        if maxwords or maxlines:
            #we always santize the HTML when rendering HTML for a summary
            linkFixerFactory = lambda *args,**kwargs: self.truncateHTMLFactory(
                maxwords, maxlines, args, kwargs)
        else:
            sanitize = nofollow = True
            #get the accessTokens granted to the author of the content            
            result = kw['__server__'].evalXPath(
           '''$__context/wiki:created-by/*/auth:has-role/*
               [.='http://rx4rdf.sf.net/ns/auth#role-superuser']
            | $__context/wiki:created-by/*/auth:has-rights-to/*
            | $__context/wiki:created-by/*/auth:has-role/*/auth:has-rights-to/*''',
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
                linkFixerFactory = lambda *args, **kwargs: self.linkFixerFactory(
                    sanitize, nofollow, args, kwargs)
            else: #permission to generate any kind of html/xml -- so use the default                        
                linkFixerFactory = None

        return self.processMarkup(contents,kw.get('_APP_BASE',
                                  kw['__server__'].appBase),
                                  linkFixerFactory=linkFixerFactory)

    def getCachePredicate(self, result, kw, contextNode, contents):
        return (self.uri, contents, contextNode.getKey(),
                kw.get('_APP_BASE', kw['__server__'].appBase),
                self.getMaxes(kw))

class PatchContentProcessor(raccoon.ContentProcessors.ContentProcessor):
    uri = 'http://rx4rdf.sf.net/ns/content#pydiff-patch-transform'

    def __init__(self, rhizome):
        super(PatchContentProcessor, self).__init__()
        self.rhizome = rhizome
        
    def processContents(self,result, kw, contextNode, contents):
        return self.rhizome.processPatch(contents, kw, result)

class XMLShredder(raccoon.ContentProcessors.ContentProcessor):
    uri = 'http://rx4rdf.sf.net/ns/wiki#item-format-xml'
    label = 'XML/XHTML'
    mimetype = 'text/html' #todo

    def __init__(self, rhizome,defaultShredderStylesheetName):
        self.rhizome = rhizome
        self.defaultShredderStylesheetName = defaultShredderStylesheetName
        
    def processContents(self,result, kw, contextNode, contents):
        #deduce content type from root element
        #if it corresponds to one of the contentprocessor formats used by the shredder
        #return that format so that contentprocessor will process it
        ns, prefix, local = utils.getRootElementName(contents)
        #print ns, local, contents[:500]
        if ns == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#' or local=='rx':
            #it's rdf: either rdfxml or rxml_xml
            return contents, 'http://rx4rdf.sf.net/ns/wiki#item-format-rdf'
        elif kw.get('_deduceDynamic'):
            del kw['_deduceDynamic'] #only do this once

            if ns == "http://www.xmldb.org/xupdate" :
                return contents, 'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate'
            elif ns == 'http://www.w3.org/1999/XSL/Transform':
                assert kw.get('_contents') or kw.get('_contentsDoc'), 'XSLT source missing'
                return contents, 'http://www.w3.org/1999/XSL/Transform'

        #otherwise invoke the generic XML shredder stylesheet
        kw['_contents'] = contents
        kw['_contentURI'] = 'site:///'+self.defaultShredderStylesheetName
        #we'll need to figure out what the XSLT is outputting
        kw['_deduceDynamic'] = True 
        stylesheetContents = self.rhizome.makeRequest(None,
                self.defaultShredderStylesheetName, 'action', 'view-source')
        return stylesheetContents, 'http://www.w3.org/1999/XSL/Transform' 

class RhizomeContent(RhizomeBase):
    def __init__(self, server):
        self.server = server
        #this is just like findContentAction except we don't want
        #to try to retrieve alt-contents' ContentLocation        
        self.findPatchContentAction = raccoon.Action([
            './/a:contents/text()',
            #contents stored externally
            'wf:openurl(.//a:contents/a:ContentLocation)', 
        ], lambda result, kw, contextNode, retVal:
            isinstance(result, str) and result or raccoon.StringValue(result),
                                    requiresContext = True) #get its content
        self.interWikiMap = None
        self.zmlContentProcessor=raccoon.ContentProcessors.ZMLContentProcessor()
        self.zmlContentProcessor.getInterWikiMap = self.getInterWikiMap
        self.mmf = MarkupMapFactory(self.zmlContentProcessor)
        self.zmlContentProcessor.markupMapFactory = self.mmf

    def getInterWikiMap(self):
        if self.interWikiMap is not None:
            return self.interWikiMap
        #in case this is call before configuration is completed
        interWikiMapURL = getattr(self, 'interWikiMapURL', None) 
        if interWikiMapURL:
           self.interWikiMap = zml.interWikiMapParser(
               InputSource.DefaultFactory.fromUri(interWikiMapURL).stream)
           return self.interWikiMap
        return {}

    ######content processing####    
    def processTemplateAction(self, resultNodeset, kw, contextNode, retVal):
        #the resultNodeset is the template resource
        #so skip the first few steps that find the page resource
        actions = self.handleRequestSequence[3:]

        #so we can reference the template resource
        #(will be placed in the the 'previous' namespace)
        self.log.debug('calling template resource: %s' % resultNodeset)
        kw["_template"] = resultNodeset

        errorSequence = self.server.actions.get('http-request-error')
        return self.server.callActions(actions, resultNodeset, kw,
                    contextNode, retVal,
                    globalVars=self.server.globalRequestVars,
                    errorSequence=errorSequence)

    def processPatch(self, contents, kw, result):
        #we assume result is a:ContentTransform/a:transformed-by/*,
        #set context to the parent a:ContentTransform
        patchBaseResource =  self.server.evalXPath(
            '../../a:pydiff-patch-base/*', node = result[0])
        #print 'b', patchBaseResource
        #print 'type c', type(contents)
        #print 'c', contents
        
        #get the contents of the resource which this patch
        #will use as the base to run its patch against
        #todo: issue kw.copy() is not a deep copy -- what to do?
        base = self.server.doActions([self.findPatchContentAction,
                    self.processContentAction], kw.copy(), patchBaseResource)
        assert base, "patch failed: couldn't find contents for %s" % repr(base)
        patch = pickle.loads(str(contents)) 
        return utils.patch(base,patch)

    def startShredding(self, context, resource, format, content):
        format = raccoon.StringValue(format)
        if format in ['http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate',
                      'http://www.w3.org/1999/XSL/Transform',
                      'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt']:
            #treat these formats as plain xml -- we just want to analyze
            #them, not execute them
            format = 'http://rx4rdf.sf.net/ns/wiki#item-format-xml'
        elif format not in self.shredders:
            #don't try to shred unsupported formats
            #todo: processContents should support a default content processor
            return raccoon.XFalse
        kw = {}
        kw['__resource'] = resource
        kw['_format'] = format
        changeCount = len(self.server.txnSvc.state.additions)
        result = self.server.runActions('shred', kw, content,newTransaction=False)
        changes = len(self.server.txnSvc.state.additions) > changeCount
        #change is inaccurate if the shredder removed some change
        #and then added the same number of new ones
        return changes and raccoon.XTrue or raccoon.XFalse

    def shredWithStylesheet(self, context, stylesheetUri, sourceNode,
                                                        sourceResource):
        '''
        This function can be called by a shredder stylesheet that is
        shredding a document to support nested shredding on the same
        document.
        Returns true is if any statements were extracted.
        '''
        stylesheetUri = raccoon.StringValue(stylesheetUri)
        kw = {}
        kw['_contentsDoc'] = sourceNode[0]
        kw['__resource'] = sourceResource
        kw['_format'] = 'http://www.w3.org/1999/XSL/Transform' 
        #the stylesheet will output xml that needs to be further processed
        #so set _deduceFormat to signal XMLShredder to try to figure out how
        #to process the result
        kw['_deduceDynamic'] = True
        if stylesheetUri.startswith('site:'):
            if '?' in stylesheetUri:
                if stylesheetUri[-1] == '?':
                    delim = ''
                else:
                    delim = '&'
            else:
                delim = '?'
            stylesheetUri += delim+'action=view-source'
        kw['_contentURI'] = stylesheetUri
        
        changeCount = len(self.server.txnSvc.state.additions)
        inputSource = InputSource.DefaultFactory.fromUri(stylesheetUri)
        initVal = inputSource.stream.read()
        inputSource.stream.close()
        result = self.server.runActions('shred', kw, initVal, newTransaction=False)
        changes = len(self.server.txnSvc.state.additions) > changeCount
        return changes and raccoon.XTrue or raccoon.XFalse

