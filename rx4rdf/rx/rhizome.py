"""
    Helper classes for Rhizome
    This classes includes functionality dependent on the Rhizome schemas
    and so aren't included in the Raccoon module.

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx import zml, rxml, raccoon, utils, RxPath
import Ft
from Ft.Lib import Uri
from Ft.Rdf import RDF_MS_BASE,OBJECT_TYPE_RESOURCE
from Ft.Xml import InputSource
import os, os.path, sys, types, base64, fnmatch, traceback, re
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

        if self.rhizome.uninitialized or tag != self.A:
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

class SanitizeHTML(utils.BlackListHTMLSanitizer, raccoon.RequestProcessor.SiteLinkFixer):
    super = raccoon.RequestProcessor.SiteLinkFixer

    def onStrip(self, tag, name, value):
        #should we raise an exception instead?
        if name:
            log.warning('Stripping dangerous HTML attribute: ' + name + '=' + value)
        elif value:
            log.warning('Stripping dangerous content from: ' + tag)
        else:
            log.warning('Stripping dangerous HTML element: ' + tag)    
    
METADATAEXT = '.metarx'

def kw2vars(**kw):
    return dict([((None, x[0]), x[1]) for x in kw.items()])
                 
class Rhizome(object):
    exts = { 'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate': 'xml',
    'http://rx4rdf.sf.net/ns/wiki#item-format-python' : 'py',
    'http://www.w3.org/1999/XSL/Transform' : 'xsl',
    'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' : 'rxsl',
    'http://rx4rdf.sf.net/ns/wiki#item-format-zml' : 'zml',
    'http://rx4rdf.sf.net/ns/wiki#item-format-text': 'txt',
    'http://rx4rdf.sf.net/ns/wiki#item-format-xml':'xml',    
    'http://rx4rdf.sf.net/ns/content#pydiff-patch-transform':'pkl'
    }

    defaultIndexableFormats = ['http://rx4rdf.sf.net/ns/wiki#item-format-text',
                               'http://rx4rdf.sf.net/ns/wiki#item-format-xml',
                               'http://rx4rdf.sf.net/ns/wiki#item-format-zml']

    uninitialized = True
    
    def __init__(self, server):
        self.server = server
        #this is just like findContentAction except we don't want to try to retrieve alt-contents' ContentLocation        
        self.findPatchContentAction = raccoon.Action(['.//a:contents/text()', 
        'wf:openurl(.//a:contents/a:ContentLocation)', #contents stored externally
        ], lambda result, kw, contextNode, retVal:\
            server.getStringFromXPathResult(result), requiresContext = True) #get its content
        self.mmf = MarkupMapFactory(self)
        self.interWikiMap = None
      
    def _configSanitizer(self, kw, name, function):
        setting = kw.get(name)
        if setting is not None:
            isdict = isinstance(setting, dict)
            if isdict:
                setting = setting.items()
            result = map(function, setting)
            if isdict:
                result = dict(result)
        else:
            result = getattr(SanitizeHTML, name)
        setattr(self, name, result)
                    
    def configHook(self, kw):
        def initConstants(varlist, default):
            return raccoon.assignVars(self, kw, varlist, default)

        self.server.APPLICATION_MODEL += RxPath.RDFSSchema.schemaTriples
        
        initConstants( ['MAX_MODEL_LITERAL'], -1)        
        self.SAVE_DIR = os.path.abspath( kw.get('SAVE_DIR', 'content/.rzvs') )
        altsaveSetting = kw.get('ALTSAVE_DIR', 'content')
        if altsaveSetting:
            self.ALTSAVE_DIR = os.path.abspath( altsaveSetting )
        else:
            self.ALTSAVE_DIR = ''
        self.THEME_DIR = kw.get('THEME_DIR', 'themes/default')
            
        if not kw.has_key('PATH'):
            #theme path : rhizome path 
            #if PATH hasn't been set in the config, set the path to be:
            #ALT_SAVE_DIR: THEME_DIR : RhizomeDir
            #where RhizomeDir is directory that rhizome-config.py lives in
            #(i.e. probably 'rhizome')
            #we check that SAVE_DIR is a subdirectory of one of these directories
            #if not, you'll need to set the PATH manually
            rhizomeDir = os.path.split(kw['_rhizomeConfigPath'])[0] #set in rhizome-config.py
            if self.THEME_DIR:
                if not os.path.isabs(self.THEME_DIR):
                    themeDir = os.path.join(rhizomeDir, self.THEME_DIR)
                else:
                    themeDir = self.THEME_DIR
                self.server.PATH = themeDir + os.pathsep + rhizomeDir
            else:
                self.server.PATH = rhizomeDir
            if self.ALTSAVE_DIR:
                self.server.PATH = self.ALTSAVE_DIR + os.pathsep + self.server.PATH
        log.debug('path is %s' % self.server.PATH)
        if self.MAX_MODEL_LITERAL > -1:
            if self.ALTSAVE_DIR:
                assert [prefix for prefix in self.server.PATH
                 if self.ALTSAVE_DIR.startswith(os.path.abspath(prefix)) ],\
                    'ALT_SAVE_DIR must be on the PATH'
                
            #SAVE_DIR should be a sub-dir of one of the PATH
            #directories so that 'path:' URLs to files there include
            #the subfolder to make them distinctive. (Because you don't want to be able override them)
            saveDirPrefix = [prefix for prefix in self.server.PATH
                if self.SAVE_DIR.startswith(os.path.abspath(prefix)) ]
            assert saveDirPrefix and self.SAVE_DIR[len(saveDirPrefix[0]):],\
                  'SAVE_DIR must be a distinct sub-directory of a directory on the PATH'
                
        self.interWikiMapURL = kw.get('interWikiMapURL', 'site:///intermap.txt')
        initConstants( ['undefinedPageIndicator', 'externalLinkIndicator', 'interWikiLinkIndicator', 'useIndex' ], 1)
        initConstants( ['RHIZOME_APP_ID'], '')

        self.passwordHashProperty = kw.get('passwordHashProperty',
                                          self.BASE_MODEL_URI+'password-hash')
        self.secureHashSeed = kw.get('SECURE_HASH_SEED',
                                          'YOU REALLY SHOULD CHANGE THIS!')
        if self.secureHashSeed == 'YOU REALLY SHOULD CHANGE THIS!':
            log.warning("SECURE_HASH_SEED using default seed -- set your own private value!")
        self.secureHashMap = kw.get('secureHashMap',        
            { self.passwordHashProperty :  self.secureHashSeed })
        #make this available as an XPath variable
        self.resourceAuthorizationAction.assign("__passwordHashProperty",
                        "'"+self.passwordHashProperty+"'")

        if not kw.get('ADMIN_PASSWORD_HASH') or not kw.get('ADMIN_PASSWORD'):
            log.warning("neither ADMIN_PASSWORD nor ADMIN_PASSWORD_HASH was set; using default admin password")
        #this is just like findResourceAction except we don't assign the 'not found' resource
        #used by hasPage
        self.checkForResourceAction = raccoon.Action(self.findResourceAction.queries[:-1])
        self.checkForResourceAction.assign("__resource", '.', post=True)
        self.indexDir = kw.get('INDEX_DIR', 'contentindex')
        self.indexableFormats = kw.get('indexableFormats', self.defaultIndexableFormats)

        for args in [ ('blacklistedContent', lambda x,y: (re.compile(x), re.compile(y)) ),
          ('blacklistedElements',lambda x: x),
          ('blacklistedAttributes', lambda x,y: (re.compile(x), re.compile(y)) )
            ]:
            self._configSanitizer(kw, *args)

        self.uninitialized = False
        
    def getInterWikiMap(self):
        if self.interWikiMap is not None:
            return self.interWikiMap
        interWikiMapURL = getattr(self, 'interWikiMapURL', None) #in case this is call before configuration is completed
        if interWikiMapURL:
           self.interWikiMap = zml.interWikiMapParser(InputSource.DefaultFactory.fromUri(interWikiMapURL).stream)
           return self.interWikiMap
        return {}

    def validateExternalRequest(self, kw):
        '''
        Disallow (form variables, etc.) from starting with '__' 
        '''        
        for name in kw:
            if name.startswith('__'):
               raise raccoon.NotAuthorized(
    '%s: form variable names can not start with "__"' % (name))        
                
    def authorizeMetadata(self, operation, namespace, name, value, kw):
        ''' Because XPath functions may be made available in contexts
        where little access control is desired, we provide a simple
        access control mechanism for assign-metadata() and
        remove-metadata(): Any variable whose name that starts with 2
        leading underscores is considered read-only and can not be
        assigned or removed.
        Also, 'session:login' can only be assigned if
        $password is present and its SHA1 digest matches the user's
        digest. '''
        if name.startswith('__') and operation in ['assign', 'remove']:
            return False
        elif operation == 'assign' and namespace == raccoon.RXIKI_SESSION_NS and name == 'login':
            #for security
            #we only let session:login be set in the context where $password is present
            if not kw.has_key('password'):
                return False

            vars = kw2vars(password = kw['password'], login=value,
                           hashprop = self.passwordHashProperty)
            userResource = self.server.evalXPath(                
                "/*[wiki:login-name = $login][*[uri(.)=$hashprop] = wf:secure-hash($password)]",
                vars=vars)
            if not userResource:
                return False
        return True

    def _addPredicates(self, l, n):
        #its a resource
        if getattr(n, 'uri', None):
            l.extend(n.childNodes)
        else:
            l.append(n)
        return l

    def authorizeAdditions(self, additions, removals, reordered, user):
        #for additions we need to find all the possible authorizing
        #resources in the new nodes because the new statements may
        #create new linkages to authorzing resources
        forAllResource = self.server.rdfDom.findSubject(self.server.BASE_MODEL_URI + 'common-access-checks')
        newPredicates = reduce(self._addPredicates, additions, [])
        #print >>sys.stderr, 'new preds', newPredicates
        for node in newPredicates:
            assert getattr(node, 'stmt') #assert it's a predicate node
            #get all the new resources this node is linked via requires-authorization-for relations            
            newSubjects = self.getAuthorizingResources(node.parentNode, newPredicates)
            currentResources = [] #resource exists
            newResources = [] #resource doesn't currently exists
            for s in newSubjects:
                current = self.server.rdfDom.findSubject(s.uri)
                if current:
                    currentResources.append(current)
                else:
                    newResources.append(s)
                    
            authorizingResources = []
            for r in currentResources:
                authorizingResources += self.getAuthorizingResources( r )

            #new resources aren't in the current model but we still want
            #to look for any static (class-based access tokens)
            #so build up the list of classes resources and authorize those                        
            classResources = []
            for s in newResources:
                for p in s.childNodes:
                    if p.stmt.predicate == RDF_MS_BASE+'type':
                        classResource = self.server.rdfDom.findSubject(p.stmt.object)
                        if classResource:
                            authorizingResources.append(classResource)
            #always check any access tokens associated with this                
            if forAllResource:
                authorizingResources.append(forAllResource)

            authorizingResources.sort()
            authorizingResources = utils.removeDupsFromSortedList(authorizingResources)
            self.authorizeUpdate(user, authorizingResources,
                "http://rx4rdf.sf.net/ns/auth#permission-add-statement",
                node.stmt.subject, node.stmt.predicate,node.stmt.object)

    def authorizeRemovals(self, additions, removals, reordered, user):
        forAllResource = self.server.rdfDom.findSubject(self.server.BASE_MODEL_URI + 'common-access-checks')
        for node in reduce(self._addPredicates, removals, []):
            assert getattr(node, 'stmt') #assert it's a predicate node
            authorizingResources = self.getAuthorizingResources( node.parentNode )
            if forAllResource:
                authorizingResources.append(forAllResource)
            self.authorizeUpdate(user, authorizingResources,
                "http://rx4rdf.sf.net/ns/auth#permission-remove-statement",
                node.stmt.subject, node.stmt.predicate,node.stmt.object)
            
    def getAuthorizingResources(self, node, membershipList = None):
        #check authorization on all the applicable nodes: find all the subject
        #resources that are reachable by inverse transitively
        #following the subject of the statement and applying the authorization
        #expression to them. equivalent to:
        #(.//auth:requires-authorization-for[* = $resource]/ancestors::*/..)[authquery]
        #but for now its more efficient to manually find the ancestors:    

        rdfDom = node.ownerDocument
        nodeset = [ node ]
        authresources = [ node ]
        while nodeset:                
            nodeset = rdfDom.evalXPath('/*/auth:requires-authorization-for[* = $nodeset]', nsMap = self.server.nsMap,
                                       extFunctionMap = self.server.extFunctions,
                                       vars = kw2vars(nodeset = nodeset) )            
            nodeset = [p.parentNode for p in nodeset
                        if (not membershipList or p in membershipList) 
                            and p.parentNode not in authresources] #avoid circularity
            authresources.extend(nodeset)
        return authresources
        
    def authorizeUpdate(self, user, authorizingResources, action, subject,
                        predicate=0, object=0, noraise=False):            
        #if any of the authresources requires an auth token that the
        #user doesn't have access to, the nodeset will not be empty        
        result = self.server.evalXPath('($nodeset)[%s]'%self.authorizationQuery,
            kw2vars(__authAction=action, __user=user, nodeset = authorizingResources,
                    __authProperty=predicate, __authValue=object))
        if result and not noraise:
           if action == 'http://rx4rdf.sf.net/ns/auth#permission-add-statement':
               actionName = 'add'
           elif action == 'http://rx4rdf.sf.net/ns/auth#permission-remove-statement':
               actionName = 'remove'
           else:
               actionName = action
           raise raccoon.NotAuthorized('You are not authorized to %s this statement: %s %s %s'
                    % (actionName, subject, predicate,object))
        #return the nodes of the resources that user isn't authorized to perform this action on 
        return result

    def authorizeDynamicContent(self, accesstoken, calldefault, contents, formatType, kw, dynamicFormat):
        if dynamicFormat:
            if not self.server.evalXPath(
    '''$__user/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser' or
    /*[.='%s'][.=$__user/auth:has-rights-to/* or .=$__user/auth:has-role/*/auth:has-rights-to/*]'''
                % accesstoken, kw2vars(__user=kw.get('__user',[]))):
               raise raccoon.NotAuthorized(
    'You are not authorized to create dynamic content with this format: %s' 
                    % (formatType))
            elif not calldefault:
                #success so return now if we don't want try the default
                return         
        #try the default authorization, if any
        return self.server.authorizeContentProcessing(
                self.server.DefaultAuthorizeContentProcessors,
                contents, formatType, kw, dynamicFormat)

    def authorizeXPathFuncs(self, server, funcs, kw):
        #we don't authorization for accessing individual XPath extension functions yet,
        #but as a temporary security measure take advantage of the
        #fact that Raccoon doesn't call authorizeXPathFuncs for
        #XUpdate scripts, allowing us to delete unsafe from other contexts (e.g. XSLT)
        
        for unsafe in [(raccoon.RXWIKI_XPATH_EXT_NS, 'generate-patch'),
                       (raccoon.RXWIKI_XPATH_EXT_NS, 'save-contents')]:
            if unsafe in funcs:
                del funcs[unsafe]

    ###command line handlers####
    def doImport(self, path, recurse=False, r=False, disposition='',
                 filenameonly=False, xupdate="path:import.xml",
                 doctype='', format='', dest=None, folder=None, token = None,
                 label=None, keyword=None, keepext=False, noindex=False,
                 save=True, fixedBaseURI=None, **kw):
          '''Import command line option
Import the file in a directory into the site.
If, for each file, there exists a matching file with ".metarx" appended, 
then import will attempt to use the metadata in the metarx file.          
-i -import path Location of file(s) to import (* and ? wildcards OK)

Options:
-dest path If dest is present content will be copied to this directory, 
     otherwise the site will reference the content at the import directory.
-recurse -r whether to recursively import subdirectories 
-filenameonly (with recurse) don't include the relative path
             in the imported item name     
-xupdate URL url to an RxUpdate file which is applied to each metarx file.
Can be used for schema migration, for example.
Default: "path:import.xml". This disgards previous revisions and
         points the content to the new import location.
-noindex Don't add the content to the index

The following options only apply when no metarx file is present: 
-folder path (prepended to name and creates folder resource if necessary)
-keepext Don't drop the file extension when naming the page.
Each of these set the equivalent metadata property:
-disposition (wiki:item-disposition), -doctype (wiki:doctype),
-format (wiki:item-format), -token (auth:guarded-by),
-label  (wiki:has-label), -keyword (wiki:about)
Their value can be either an URI or a QName.
'''
          defaultFormat=format
          defaultDisposition=disposition
          defaultDoctype=doctype
          if folder and folder[-1] != '/':
              folder += '/'
          if token:
              accessTokens = [ token ]
          else:
              accessTokens = []
          if keyword:
              keywords = [ keyword ]
          else:
              keywords = []
              
          if '*' in os.path.split(path)[1] or '?' in os.path.split(path)[1]:
              path,filePattern = os.path.split(path)
          else:
              filePattern = ''
          rootPath = os.path.normpath(path or '.').replace(os.sep, '/')
          log.info('beginning import of ' + rootPath)
          triples = {}

          if fixedBaseURI:
              assert not (recurse or r), 'this combination of options is not supported yet'
          else:
              if dest:
                  prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(dest))  
              else:
                  prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(rootPath))
                
          #todo: support storing contents directly in model (use saveContents()?)
              
          def fileFunc(path, filename):
              if filePattern and not fnmatch.fnmatch(filename, filePattern):
                  return
              if os.path.splitext(filename)[1]==METADATAEXT:
                  return              

              if dest:
                  destpath = os.path.join(dest, filename)
              else:
                  destpath = path

              if fixedBaseURI:
                  loc = fixedBaseURI + filename                  
              elif prefixlen: #if the destination is on the raccoon path use a path: URL
                  loc = raccoon.SiteUriResolver.OsPathToPathUri(os.path.abspath(destpath)[prefixlen+1:])
              else: #use a file:// URL 
                  loc = Uri.OsPathToUri(os.path.abspath(destpath))
                  
              if os.path.exists(path + METADATAEXT):
                  #parse the rzml to rxml then load it into a RxPath DOM
                  xml = zml.zml2xml(open(path + METADATAEXT), URIAdjust = True)
                  rdfDom = rxml.rxml2RxPathDOM(StringIO.StringIO('<rx:rx>'+ xml+'</rx:rx>'))
                  #Ft.Xml.Lib.Print.PrettyPrint(rdfDom, asHtml=1, stream=file('rdfdom1.xml','w')) #asHtml to suppress <?xml ...>
                  
                  #check to see if the page already exists in the site                  
                  wikiname = rdfDom.evalXPath('string(/*/wiki:name)', nsMap = self.server.nsMap)
                  assert wikiname, 'could not find a wikiname when importing %s' % path + METADATAEXT
                  if save and self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                      log.warning('there is already an item named ' + wikiname +', skipping import')
                      return #hack for now skip if item already exists
                  else:                      
                      log.info('importing ' +filename)
                                    
                  #update the page's metadata using the xupdate script
                  self.server.xupdateRDFDom(rdfDom, uri=xupdate,
                                    kw={ 'loc' : loc, 'name' : wikiname, 'base-uri' : self.BASE_MODEL_URI,
                                         'resource-uri' : self.getNameURI(None,wikiname) })

                  #write out the model as nt triples
                  moreTriples = StringIO.StringIO()                  
                  stmts = rdfDom.model.getStatements() 
                  utils.writeTriples(stmts, moreTriples)
                  #print moreTriples.getvalue()
                  triples[wikiname] = moreTriples.getvalue() 

                  #get the resource's uri (it might have changed)
                  resourceURI = rdfDom.evalXPath('string(/*[wiki:name])', nsMap = self.server.nsMap)
                  assert resourceURI
                  resourceURI = rdfDom.evalXPath('/*[wiki:name]/', nsMap = self.server.nsMap)
                  
                  #create folder resources if necessary
                  pathSegments = wikiname.split('/')
                  rootFolder, parentFolder = self.addFolders(pathSegments[:-1])
                  if parentFolder:
                      parentFolder['wiki:has-child'] = resourceURI
                  if rootFolder:
                      triples['@importedfolders'] = \
                        triples.get('@importedfolders','') + rootFolder.toTriplesDeep() 
                      
                  format = rdfDom.evalXPath(
                  '''string((/*[wiki:name]/wiki:revisions/*/rdf:first)[last()]/
                     wiki:Item/a:contents/a:ContentTransform/a:transformed-by/wiki:ItemFormat)''',
                     nsMap = self.server.nsMap)
              else:
                  #no metadata file found -- try to guess the some default metadata             
                  if not filenameonly:
                      filepath = path[len(rootPath)+1:]
                  else:
                      filepath = filename
                  if folder:
                     filepath = folder + filepath
                  if not keepext:
                      wikiname = os.path.splitext(filepath)[0]
                  else:
                      wikiname = filepath
                  wikiname = filter(lambda c: c.isalnum() or c in '_-./', wikiname)
                  if save and self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                      log.warning('there is already an item named ' + wikiname +', skipping import')
                      return #hack for now skip if item already exists
                  else:
                      log.info('importing ' +filepath+ ' as ' + wikiname)
                  if not defaultFormat:
                      exts = { '.zml' : 'http://rx4rdf.sf.net/ns/wiki#item-format-zml',
                      '.xsl' : 'http://www.w3.org/1999/XSL/Transform',
                      '.rxsl' : 'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt',
                      '.py' : 'http://rx4rdf.sf.net/ns/wiki#item-format-python',
                      '.html':'http://rx4rdf.sf.net/ns/wiki#item-format-xml',
                      }
                      ext = os.path.splitext(path)[1]
                      format = exts.get(ext)
                      if format == None:
                          import mimetypes
                          type, encoding = mimetypes.guess_type(ext)
                          if type and type.startswith('text/') and not encoding:
                              format = 'http://rx4rdf.sf.net/ns/wiki#item-format-text'
                          else:
                              format = 'http://rx4rdf.sf.net/ns/wiki#item-format-binary'
                  else:
                      format = defaultFormat
                  if not defaultDisposition:
                      if format == 'http://rx4rdf.sf.net/ns/wiki#item-format-binary':
                          disposition = 'complete'
                      else:
                          disposition = 'entry'
                  else:
                      disposition = defaultDisposition
                  if not defaultDoctype:
                      if format == 'http://rx4rdf.sf.net/ns/wiki#item-format-zml':
                          mm = zml.detectMarkupMap(file(path), mmf=self.mmf)
                          doctype = mm.docType
                      else:
                          doctype=''
                  else:
                      doctype = defaultDoctype
                  triples[wikiname] = self.addItem(wikiname,loc=loc,format=format,
                                    disposition=disposition, doctype=doctype,
                                    contentLength = str(os.stat(path).st_size),
                                    digest = utils.shaDigest(path), keywords=keywords,
                                    label=label, accessTokens=accessTokens) 
                  title = ''
                  resourceURI = self.getNameURI(None, wikiname)
                  
              if dest:
                  import shutil
                  try: 
                    os.makedirs(dest)
                  except OSError: pass #dir might already exist
                  shutil.copy2(path, dest)
                  
              if save and self.index and not noindex:
                  if format in self.indexableFormats:
                      self.addToIndex(resourceURI, file(path, 'r').read(), title)
                  
          if os.path.isdir(rootPath):
                if recurse or r:
                    recurse = 0xFFFF
                utils.walkDir(rootPath, fileFunc, recurse = recurse)
          else:
                fileFunc(rootPath, os.path.split(rootPath)[1])                    
          if triples and save:
              model, db = utils.DeserializeFromN3File(
                  StringIO.StringIO(''.join(triples.values()) ))              
              #add all the statements from the model containing the newly imported triples
              #to our server's model
              self.server.updateDom(model.statements())
          return triples
          
    def doExport(self, dir, xpath=None, filter='wiki:name', name=None,
                 static=False, noalias=False, astriples=None, **kw):
         '''
Export command line option
Exports the content of each item in the site as a file.  Also, for each file, 
created a matching file with ".metarx" appended that contains the metadata for that item.
-e -export path Directory to export to.
Options:
-xpath RxPath expression that evaluates to a nodeset of items to export
-name  Name of item to export (for exporting one item) (no effect if -xpath is specified)
-static Have export attempt to render the content as html. Dynamic pages 
        (those that require parameters) are skipped.
-noalias Don't create static copies of page aliases (use with -static only)
-label Name of revision label
-astriples filepath Export the selected resources as an NTriples file. External content is
                    inserted in the file as string literals.
'''
         assert not (xpath and name), self.server.cmd_usage
         if not xpath and name: xpath = '/a:NamedContent[wiki:name="%s"]' % name
         else: xpath = xpath or ('/a:NamedContent[%s]' % filter) 
         
         results = self.server.evalXPath(xpath)
         if astriples:
             stmts = []
         for item in results:
             name = self.server.evalXPath('string(wiki:name)', node = item)
             assert name
             orginalName = name
             content = None
             log.info('attempting to export %s ' % name)
             if static:                 
                 try:
                     #we need this to store the mimetype:
                     class _dummyRequest:
                         def __init__(self):
                             self.headerMap = {}
                             self.simpleCookie = {}

                     rc = { '_static' : static,
                            '_noErrorHandling': 1,                            
                            }
                     
                     if kw.get('label'):
                         rc['label'] = kw['label']
                     #todo: what about adding user context (default to administrator?)
                     #add these to the requestContext so invocation know its intent
                     self.server.requestContext.append(rc)
                     content = self.server.requestDispatcher.invoke__(orginalName, _response=_dummyRequest() ) 
                     #todo: change rootpath
                     #todo: handle aliases 
                     #todo: what about external files (e.g. images)
                     #todo: change extension based on output mime type                     
                     #       (use invokeEx but move default mimetype handling out of handleRequest())
                     #       but adding an extension means fixing up links
                 except:
                     #traceback.print_exc()
                     log.warning('%s is dynamic, can not do static export' % name)
                     self.server.requestContext.pop()
                     #note: only works with static pages (ones with no required parameters)
                 else:
                     self.server.requestContext.pop()
             else:
                 #just run the revision action and the contentAction
                 #todo: process patch
                 content = self.server.doActions([self.findRevisionAction,
                                    self.findContentAction], kw.copy(), item)

                 format = self.server.evalXPath(
                    'string((wiki:revisions/*/rdf:first)[last()]/wiki:Item/'
                    'a:contents/a:ContentTransform/a:transformed-by/wiki:ItemFormat)',
                     node = item)
                 ext = os.path.splitext(name)[1]
                 if not ext and format:                 
                    if self.exts.get(format):
                        name += '.' + self.exts[format]
                 
             if not astriples:
                 if content is None:
                     continue                 
                 dir = dir.replace(os.sep, '/')
                 path = dir+'/'+ name
                 try: os.makedirs(os.path.split(path)[0])
                 except os.error:
                     #traceback.print_exc()
                     pass 
                 itemfile = file(path, 'w+b')
                 itemfile.write( content)
                 itemfile.close()

             if static:
                 if not noalias:
                    aliases = self.server.evalXPath('wiki:alias/text()', node = item)
                    for alias in aliases:
                         path = dir+'/'+ alias.nodeValue
                         try: os.makedirs(os.path.split(path)[0])
                         except os.error:
                             #traceback.print_exc()
                             pass 
                         itemfile = file(path, 'w+b')
                         itemfile.write( content)
                         itemfile.close()
             elif astriples:
                 from rx.utils import Res

                 resources = self.server.evalXPath(
                     '''. | (wiki:revisions/*/rdf:first)[last()]/wiki:Item |
                       ((wiki:revisions/*/rdf:first)[last()]/wiki:Item//a:contents/node())''',
                     node = item)[:-1] #skip final text() or ContentLocation                 

                 lastContents = resources[-1] #should be the last contents, i.e. a ContentTransform
                 assert self.server.evalXPath('self::a:ContentTransform', node = lastContents), resources

                 wikiItem = resources[1] #should be the Item                 
                 assert self.server.evalXPath('self::wiki:Item', node = wikiItem), wikiItem.childNodes
                 
                 #replace the final a:content statement with the actual contents 
                 #and only include the last revision
                 for res in resources:
                     for stmt in res.getModelStatements():
                         #todo: handle binary files                     
                         if (stmt.predicate == 'http://rx4rdf.sf.net/ns/archive#contents'
                             and stmt.subject == lastContents.uri):
                             stmts.append( RxPath.Statement(lastContents.uri,
                                'http://rx4rdf.sf.net/ns/archive#contents',
                                content, objectType=RxPath.OBJECT_TYPE_LITERAL))
                         elif stmt.predicate == 'http://rx4rdf.sf.net/ns/wiki#revisions':
                             lres = Res()
                             stmts.append( RxPath.Statement(stmt.subject,
                                        stmt.predicate,
                                        RxPath.BNODE_BASE+lres.uri[2:],
                                        objectType=RxPath.OBJECT_TYPE_RESOURCE) )                             
                             lres['rdf:first'] = Res(wikiItem.uri)
                             lres['rdf:rest'] = Res('rdf:nil')
                             lres['rdf:type'] = Res('rdf:List')
                             stmts.extend( lres.toStatements() )                                                  
                         else:
                             stmts.append(stmt)                 
             else:
                 #create a .metarx file along side the exported one
                 lastrevision = self.server.evalXPath(
                     '''(wiki:revisions/*/rdf:first)[last()]/wiki:Item |
                       (wiki:revisions/*/rdf:first)[last()]/wiki:Item//a:contents/*''',
                     node = item)
                 lastrevision.insert(0, item)
                 metadata = rxml.getRXAsZMLFromNode(lastrevision)
                 metadatafile = file(path + METADATAEXT, 'w+b')
                 metadatafile.write( metadata)
                 metadatafile.close()
                 
         if astriples:             
             stream = file(astriples, 'w+b')
             utils.writeTriples(stmts,stream)
             stream.close()
                 
    ######content processing####
    def processXSLT(self, result, kw, contextNode, contents):
        '''
        Invoke the transformation on the _contents metadata 
        '''
        return self.server.processXslt(contents, kw['_contents'], kw,
                uri=kw.get('_contentsURI') or self.server.evalXPath( 
    'concat("site:///", (/a:NamedContent[wiki:revisions/*/*[.=$__context]]/wiki:name)[1])',
                        node=contextNode) )
                
    def linkFixerFactory(self, *args):
        fixer = SanitizeHTML(*args)        
                                    
        fixer.blacklistedElements = self.blacklistedElements
        fixer.blacklistedContent = self.blacklistedContent
        fixer.blacklistedAttributeNames = self.blacklistedAttributes
        return fixer
    
    def processMarkup(self, accesstoken, result, kw, contextNode, contents):
        #if the content was not created by an user with the 
        #with the trusted author token we need to strip out any dangerous HTML        
        #because html maybe generated dynamically we need to check this while spitting out the HTML
        if not self.server.evalXPath(
    '''$__context/wiki:created-by/*/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser'
       or /*[.='%s'][.=$__context/wiki:created-by/*/auth:has-rights-to/*
        or .=$__context/wiki:created-by/*/auth:has-role/*/auth:has-rights-to/*]'''
                % accesstoken, node=contextNode):
            linkFixerFactory = self.linkFixerFactory
        else: #permission to generate any kind of html/xml -- so use the default
            linkFixerFactory = None
        path = kw.get('_docpath', kw.get('_path', getattr(kw.get('_request'),'browserPath', kw.get('_name'))) )
        return self.server.processMarkup(contents,path,linkFixerFactory)

    def processMarkupCachePredicate(self, result, kw, contextNode, contents):
        path = kw.get('_docpath', kw.get('_path', getattr(kw.get('_request'),'browserPath', kw.get('_name'))) )
        return (contents, contextNode, id(contextNode.ownerDocument),
                contextNode.ownerDocument.revision, path)
    
    def processZMLSideEffects(self, contextNode, kw):
        #optimization: only set the doctype (which will invoke wiki2html.xsl if we need links to be transformed)
        if self.undefinedPageIndicator or self.externalLinkIndicator or self.interWikiLinkIndicator:
            #wiki2html.xsl shouldn't get invoked with the doctype isn't html
            if not kw.get('_doctype') and self.server.evalXPath(
                "not(wiki:doctype) or wiki:doctype = 'http://rx4rdf.sf.net/ns/wiki#doctype-xhtml'",
                    node = contextNode):
                kw['_doctype'] = 'http://rx4rdf.sf.net/ns/wiki#doctype-wiki'
        
    def processZML(self, contextNode, contents, kw):
        self.processZMLSideEffects(contextNode, kw)
        contents = zml.zmlString2xml(contents,self.mmf)
        return (contents, 'http://rx4rdf.sf.net/ns/wiki#item-format-xml') #fixes up site://links
        
    def processTemplateAction(self, resultNodeset, kw, contextNode, retVal):
        #the resultNodeset is the template resource
        #so skip the first few steps that find the page resource
        actions = self.handleRequestSequence[3:]

        #so we can reference the template resource (will be placed in the the 'previous' namespace)
        log.debug('calling template resource: %s' % resultNodeset)
        kw["_template"] = resultNodeset
        
        return self.server.callActions(actions, self.server.globalRequestVars,
                                       resultNodeset, kw, contextNode, retVal)

    def processPatch(self, contents, kw, result):
        #we assume result is a:ContentTransform/a:transformed-by/*, set context to the parent a:ContentTransform
        patchBaseResource =  self.server.evalXPath('../../a:pydiff-patch-base/*', node = result[0])
        #print 'b', patchBaseResource
        #print 'context: ', result, result[0].parentNode, result[0].parentNode.parentNode
        #print 'type c', type(contents)
        #print 'c', contents
        
        #get the contents of the resource which this patch will use as the base to run its patch against
        #todo: issue kw.copy() is not a deep copy -- what to do?
        base = self.server.doActions([self.findPatchContentAction, self.processContentAction], kw.copy(), patchBaseResource)
        assert base, "patch failed: couldn't find contents for %s" % repr(base)
        patch = pickle.loads(str(contents)) 
        return utils.patch(base,patch)
        
    ######XPath extension functions#####        
    def getZML(self, context, resultset = None):        
        if resultset is None:
            resultset = context.node
        contents = raccoon.StringValue(resultset)
        return zml.zmlString2xml(contents,self.mmf )

    def getRxML(self, context, resultset = None, comment = '',
                                fixUp=None, fixUpPredicate=None):
      '''
      Returns a string of an RxML/ZML representation of the node.
      RxPathDOM nodes contained in resultset parameter. If
      resultset is None, it will be set to the context node
      '''
      if resultset is None:
            resultset = [ context.node ]
      return rxml.getRXAsZMLFromNode(resultset, rescomment = comment,
                            fixUp=fixUp, fixUpPredicate=fixUpPredicate)

    def getSecureHash(self, context, plaintext, secureProperty=None):
        if not secureProperty:
            secureProperty = self.passwordHashProperty
        import sha
        return sha.sha(plaintext + self.secureHashMap[secureProperty] ).hexdigest()    
                
    def getContents(self, context, node=None):
        '''
        Given a node, find the contents associated with it.
        '''
        if node is None:
            node = context.node
        elif not node:
            return ''#empty nodeset
        #print 'getc', node
        return self.server.doActions([self.findContentAction,
            self.processContentAction], {'action': 'view-source'}, node)

    def hasPage(self, context, resultset = None):
        '''
        return true if the page has been defined
        '''
        if resultset is None:
            resultset = context.node
        url = raccoon.StringValue(resultset)

        #it'd be better to normalize the url with the (relative) doc url
        #but for now rely on the fact that our fixed up links will always
        #include the full path (e.g. ../foo/bar instead of ./bar)
        index = 0
        for c in url:
            if c not in './':
                break
            else:
                index+=1
        url = url[index:]
        
        index = url.find('?')
        if index > -1:
            url = url[:index]
        else:
            index = url.find('#')
            if index > -1:
                url = url[:index]

        kw = { '_name' : url }
        self.server.doActions([self.checkForResourceAction], kw)
        if kw['__resource'] and kw['__resource'] != [self.server.rdfDom]\
           or kw.get('externalfile'):            
            return raccoon.XTrue
        else:
            return raccoon.XFalse
        
    def getNameURI(self, context, wikiname):
        #note filter: URI fragment might not match wikiname
        #python 2.2 bug: filter() on a unicode returns a list not unicode
        #todo I8N (return a IRI?)
        return self.server.BASE_MODEL_URI + \
               filter(lambda c: c.isalnum() or c in '_-./', str(wikiname))

    def findUnauthorizedActions(self, context, user, action, resources, predicate=0, object=0):
        '''
        Given an nodeset of resources, returns a nodeset
        containing the resources that user is authorized to perform the
        given action.
        '''        
        if predicate != 0:
            predicate = raccoon.StringValue(predicate)            
        if object != 0:
            object = raccoon.StringValue(object)
        return self.authorizeUpdate(user, resources,action, 
                '',predicate, object, noraise=True)
            
    def generatePatch(self, context, contents, oldcontentsNode, base64decode):
        patch = ''
        if oldcontentsNode:
            if isinstance(oldcontentsNode, type([])):
                oldcontentsNode = oldcontentsNode[0]                
            oldContents = self.server.doActions([self.findPatchContentAction], {}, oldcontentsNode)
            if oldContents:
                if base64decode:
                    #we want to base64 decode the old content before attempting the diff
                    oldContents = base64.decodestring(oldContents)
                if isinstance(contents, unicode):
                    contents = contents.encode('utf8')                
                if isinstance(oldContents, unicode):
                    oldContents = oldContents.encode('utf8')                
                patchTupleList = utils.diff(contents, oldContents) #compare  
                if patchTupleList is not None:
                    patch = pickle.dumps(patchTupleList)                    
                    
        if patch:            
            #save patch to disk:
            filepath = self.server.evalXPath("string(.//a:contents/a:ContentLocation)", node=oldcontentsNode)
            #replace the revision's file with the patch
            #(and if the revision doesn't have a file don't save the patch to disk)
            if not filepath or not filepath.startswith('path:'): 
                filepath = None
            else:        
                #convert from path back to os file path
                filepath = InputSource.DefaultFactory.resolver.PathUriToOsPath(filepath)                
                #if the revision we're replacing wasn't in the SAVE_DIR                
                if not filepath.startswith(self.SAVE_DIR):                    
                    #when we import content or for the initial rhizome files
                    #the initial version may not be in the SAVE_DIR, but we want to save it there
                    filepath = os.path.join(self.SAVE_DIR, os.path.split(filepath)[1] + '.1')                    
                    if os.path.exists(filepath):
                        #huh? this file shouldn't exist, so let's abandon
                        #patching so we don't accidently overwrite something we shouldn't
                        log.warning("aborting creation of patch: %s unexpectedly exists" % filepath)
                        return '' #no patch
            return self._saveContents(filepath, patch)
        else:
            return patch
              
    def saveContents(self, context, wikiname, format, contents, revisionCount,
                     indexURI=None, title='', previousContentURI='',
                     previousRevisionDigest=''):
        #only keep file system friendly characters
        filename = filter(lambda c: c.isalnum() or c in '_-./', str(wikiname))
        if filename.find('.') == -1 and self.exts.get(format):
            filename += '.' + self.exts[format]
        
        filepath = os.path.join(self.SAVE_DIR, filename) + '.' + str(int(revisionCount))

        abspath = os.path.abspath(filepath)        
        prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(abspath))
        fileURI = raccoon.SiteUriResolver.OsPathToPathUri(abspath[prefixlen+1:])

        #check if a file with the same name already exists and is not this resource's content file
        #if so choose another file name to avoid accidently overwriting something important
        if fileURI != previousContentURI:
            #note if the content uri for this revision == the content uri for the last revision then
            #we must be replacing the revisions (as in minor edit) and so want to do this check
            attempt = 1
            while os.path.exists(filepath): 
                #should not exist, perhaps we've renamed this page to the name of an old page?
                #well, it does so save the contents to a different name
                newfilepath = os.path.join(self.SAVE_DIR, filename) + str(attempt) + '.' + str(int(revisionCount))                
                log.warning("while saving content: %s unexpectedly exists, trying %s" % (filepath, newfilepath) )
                filepath = newfilepath
                attempt += 1
            
        #don't try to index binary content
        if format not in self.indexableFormats:
            indexURI = None 
        elif indexURI:
            indexURI = raccoon.StringValue(indexURI)
            title = raccoon.StringValue(title)
        return self._saveContents(filepath, contents, filename, indexURI, title,previousRevisionDigest)
    
    def _saveContents(self, filepath, contents, altfilename=None, indexURI=None,
                      title='',previousRevisionDigest='', maxLiteral=None):
        '''        
        this is kind of ugly; XUpdate doesn't have an eval() function, so we
        build up a string of xml and then parse it and then return the doc as
        a nodeset and use xupdate:copy-of on the nodeset
        '''
        if indexURI:
            self.addToIndex(indexURI, contents, title)
        if maxLiteral is None:
            maxLiteral = self.MAX_MODEL_LITERAL

        #print >>sys.stderr, 'sc', filepath, title, contents
        ns = '''xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
            xmlns:a="http://rx4rdf.sf.net/ns/archive#"
            xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"'''
        contentLength = len(contents)
        if filepath and maxLiteral > -1 and contentLength > maxLiteral:
            #save as file
            dir = os.path.split(filepath)[0]
            try: 
               os.makedirs(dir) 
            except OSError: pass #dir might already exist
            f = file(filepath, 'wb')
            f.write(contents)
            f.close()
            digest=utils.shaDigestString(contents)

            if altfilename and self.ALTSAVE_DIR:
                #we save another copy of the last revision in a location that
                #that can be safely accessed and modified by external programs
                #without breaking diffs etc.
                altfilepath = os.path.join(self.ALTSAVE_DIR, altfilename)
                abspath = os.path.abspath(altfilepath)        
                prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(abspath))
                assert prefixlen, ("filepath %s must be on Raccoon's PATH" % abspath)
                altPathURI = raccoon.SiteUriResolver.OsPathToPathUri(abspath[prefixlen+1:])

                #if the altfilepath already exists compare its digest with the previous
                #revisions digest and don't overwrite this file if they don't match
                #-- instead add a wiki:save-conflict property to the new contentlocation.
                if os.path.exists(altfilepath):
                    existingDigest = utils.shaDigest(altfilepath)
                    if existingDigest == digest:
                        #identical to the contents, so no need to write
                        saveAltFile = False
                        conflict = False
                    else:
                        conflict = True
                        if previousRevisionDigest:
                            #if these are equal, its ok to overwrite
                            saveAltFile = previousRevisionDigest == existingDigest
                        else:
                            saveAltFile = False                    
                else:
                    saveAltFile = True
                    
                altContents = ("<wiki:alt-contents><a:ContentLocation "
                        "rdf:about='%s' /></wiki:alt-contents>" % altPathURI)                    
                if saveAltFile:                    
                    dir = os.path.split(altfilepath)[0]                
                    try:  os.makedirs(dir) 
                    except OSError: pass #dir might already exist
                    f = file(altfilepath, 'wb')
                    f.write(contents)
                    f.close()                    
                elif conflict:
                    log.warning("conflict trying to save revision to ALTSAVE_DIR: "
                                "unrecognized contents at %s" % altfilepath)
                    altContents = ("<wiki:save-conflict><a:ContentLocation "
                            "rdf:about='%s' /></wiki:save-conflict>" % altPathURI)                    
            else:
                altContents = ''
            
            contentProps = ("<a:content-length>%u</a:content-length>"
              "<a:sha1-digest>%s</a:sha1-digest>"% (contentLength, digest))
            
            abspath = os.path.abspath(filepath)        
            prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(abspath))
            assert prefixlen, ("filepath %s must be on Raccoon's PATH" % abspath)
            filepathURI = raccoon.SiteUriResolver.OsPathToPathUri(abspath[prefixlen+1:])
            #print >>sys.stderr, abspath, abspath[prefixlen+1:], prefixlen, filepathURI
            xml = ("<a:ContentLocation %(ns)s rdf:about='%(filepathURI)s'>"
             "%(contentProps)s%(altContents)s</a:ContentLocation>" % locals())
        else: #save the contents inside the model
            try:
                if isinstance(contents, str):
                    #test to see if the string can be treated as utf8
                    contents.decode('utf8')
                return contents
                #contents = utils.htmlQuote(contents)
                #xml = '''<a:Content rdf:about='%(sha1urn)'>%(contentProps)s<a:contents>%(contents)s</a:contents></<a:Content>''' % locals()
            except UnicodeError:
                #could be binary, base64 encode
                encodedURI = utils.generateBnode()
                contents = base64.encodestring(contents)            
                xml = ("<a:ContentTransform %(ns)s rdf:about='%(encodedURI)s'>"
                    "<a:transformed-by>"
                    "<rdf:Description rdf:about='http://www.w3.org/2000/09/xmldsig#base64'/>"
                    "</a:transformed-by>"
                    "<a:contents>%(contents)s</a:contents>"
                   "</a:ContentTransform>" % locals())

        #print >>sys.stderr, 'sc', xml
        from Ft.Xml import Domlette
        #why can't InputSource accept unicode? lame (thus we don't support unicode filenames right now)
        isrc = InputSource.DefaultFactory.fromString(str(xml), 'file:') 
        xmlDoc = Domlette.NonvalidatingReader.parse(isrc)
        #return a nodeset containing the root element of the doc
        #print >>sys.stderr, 'sc', xmlDoc.documentElement
        return [ xmlDoc.documentElement ]

    ###text indexing ###
    #todo:
    #1.delete resource from index when page is deleted
    #1.handle multiple revisions, add query term based on context (e.g. 'released')
    #1.add refresh-index to deal with alt-content changes (store sha1 as field in index to compare)
    #1.index other metadata fields
    try:
        import lupy
        def initIndex(self):
            if not self.useIndex:
                self.index = None
                return

            import lupy.indexer
            try:
                self.index = lupy.indexer.Index(self.indexDir)
            except:
                #opening the index failed create a new one
                log.info('creating lupy index in %s' % self.indexDir)
                self.index = lupy.indexer.Index(self.indexDir, True)
                #get all the content in the site and add it to the index
                for node in self.server.evalXPath("/a:NamedContent"):
                    resource = node.uri
                    #print 'res', resource
                    kw = {}
                    self.server.doActions([self.findRevisionAction], kw, node)
                    revisionNode = kw['__context'][0] #context will be set to the revision
                    #print 'rn', revisionNode
                    format = self.server.evalXPath("string(a:contents/a:ContentTransform/a:transformed-by/*)",
                            node = revisionNode)
                    #print 'fmt', format
                    if format in self.indexableFormats:                        
                        kw['_staticFormat'] = 1 #don't do dynamic format chaining here
                        contents = self.server.doActions(
                            [self.findContentAction, self.processContentAction],
                            kw, revisionNode)                        
                        if contents:
                            title = ''
                            for predicate in revisionNode.childNodes:
                                if predicate.stmt.predicate == 'http://rx4rdf.sf.net/ns/wiki#title':
                                    title = predicate.stmt.object
                                    break
                            log.debug('adding resource %s to index', resource)
                            self.index.index(_resource = resource, contents = contents, title = title)

        def addToIndex(self, resource, contents, title=''):
            if not self.index:
                return
            #delete the existing resource if necessary
            self.index.delete(resource = resource)
            #lupy.store.writeString seems to assume the string is unicode since it tries to encode it as utf8
            #so try to create a unicode string here by assuming the string is utf8
            if not isinstance(contents, unicode):
                contents = contents.decode('utf8')
            if not isinstance(title, unicode):
                title = title.decode('utf8')
            self.index.index(_resource=resource, contents=contents,title=title)

        def deleteFromIndex(self, resource):
            if not self.index:
                return
            self.index.delete(resource = resource)

        def findInIndex(self, query, maxResults = sys.maxint):
            hits = self.index.find(query)
            #results = [x.get('resource') for x in hits]
            results = [] #list of resource URIs
            try:
                for i in xrange(maxResults):
                    results.append( hits[i].get('resource') )
                    #score = hits.score(i)
            except IndexError:
                #print sys.exc_info()
                pass            
            return results
            
    except ImportError:
        def initIndex(self, *args, **kw):
            self.index = None

        def addToIndex(self, *args, **kw):
            pass

        def deleteFromIndex(self, *args, **kw):
            pass
                        
    def searchIndex(self, context, query):
        query = raccoon.StringValue(query)            
        if self.index:
            return [self.server.rdfDom.findSubject(x)
                      for x in self.findInIndex(query)
                         if self.server.rdfDom.findSubject(x)]
        else:
            #linear search
            searchExp = '''/a:NamedContent[
            wiki:revisions/*/rdf:first/wiki:Item[
                (.//a:contents/*/a:transformed-by !='http://rx4rdf.sf.net/ns/wiki#item-format-binary'
                and contains( wf:get-contents(.), $search))
                or contains(wiki:title,$search)] ]'''
            return self.server.evalXPath(searchExp, vars = { (None, 'search'): query})
        
    ###template generation####
    def addFolders(self, pathSegments, baseURI=None):
        from rx.utils import Res
        Res.nsMap = self.nsMap
        
        if not baseURI:
            baseURI = self.BASE_MODEL_URI

        rootFolder = folder = parent = None
        pathSoFar = ''
        for seg in pathSegments:
            pathSoFar += seg + '/'
            folder = Res( baseURI + filter(lambda c: c.isalnum() or c in '_-./', pathSoFar) )
            folder['rdf:type'] = Res('wiki:Folder')
            folder['wiki:name'] = pathSoFar[:-1] #don't include final '/'
            if parent:
                parent['wiki:has-child'] = folder
            else:
                rootFolder = folder
            parent = folder
        return rootFolder, folder

    def _addItemTuple(self, name, keywords=('built-in',),
                        accessTokens=['base:save-only-token'], **kw):
        #this function is a confusing hack -- don't use it
        if keywords:
            #only add 'built-in' when other keywords are specified
            if 'built-in' not in keywords:
                keywords = keywords + ['built-in']
        else:
            keywords = ()
        return (name, self.addItem(name, keywords=keywords,
                                   accessTokens=accessTokens, **kw))

    def addItem(self, name, loc=None, contents=None, disposition = 'complete', 
                format='binary', doctype='', handlesDoctype='', handlesDisposition='',
                title=None, label='http://rx4rdf.sf.net/ns/wiki#label-released',
                handlesAction=None, actionType='http://rx4rdf.sf.net/ns/archive#NamedContent',
                baseURI=None, owner='http://rx4rdf.sf.net/site/users/admin',
                accessTokens=None, authorizationGroup='', keywords=None,
                contentLength = None, digest = None):
        '''
        Convenience function for adding an item the model. Returns a string of triples.
        '''
        def kw2uri(kw, default):
            if kw.find(':') == -1: #if not a URI
                return default + kw
            else:
                return kw

        from rx.utils import Res
        Res.nsMap = self.nsMap

        if not baseURI:
            baseURI = self.BASE_MODEL_URI

        #create folder resources if necessary
        pathSegments = name.split('/')
        rootFolder, folder = self.addFolders(pathSegments[:-1], baseURI)
            
        nameUriRef = Res(baseURI + filter(lambda c: c.isalnum() or c in '_-./', name))
        namebNode = '_:'+ filter(lambda c: c.isalnum(), name) 
        listbNode = Res(namebNode + '1List')
        itembNode = Res(namebNode + '1Item')

        contentbNode = Res(namebNode + '1Content')
        itembNode['a:contents'] = contentbNode
        contentbNode['rdf:type'] = Res('a:ContentTransform')
        
        contentbNode['a:transformed-by'] = Res(kw2uri(format, 'wiki:item-format-') )

        assert not (loc and contents)
        if loc:
            loc = Res(loc)
            loc['rdf:type'] = Res('a:ContentLocation')
            if contentLength is not None:
                loc['a:content-length'] = contentLength
            if digest:
                loc['a:sha1-digest'] = digest
            contentbNode['a:contents'] = loc
        else:
            contentbNode['a:contents'] = contents

        if title is not None:
            itembNode['wiki:title'] = title
    
        if label:
            itembNode['wiki:has-label'] = Res(kw2uri(label, 'wiki:label-'))
        
        if doctype:
            itembNode['wiki:doctype'] = Res(kw2uri(doctype, 'wiki:doctype-'))
        if handlesDoctype:
            nameUriRef['wiki:handles-doctype'] = Res(kw2uri(handlesDoctype, 'wiki:doctype-'))
        if handlesDisposition:
            nameUriRef['wiki:handles-disposition'] = Res(kw2uri(handlesDisposition, 'wiki:item-disposition-'))
            
        if handlesAction:                        
            nameUriRef['wiki:handles-action'] = [Res(kw2uri(x,'wiki:action-')) for x in handlesAction]
            if actionType:
                nameUriRef['wiki:action-for-type'] = Res(actionType)

        if accessTokens:
            nameUriRef['auth:guarded-by'] = [Res(x) for x in accessTokens]
            
        if authorizationGroup:
            nameUriRef['auth:uses-template'] = Res(authorizationGroup)
            
        if owner:
            if owner == 'http://rx4rdf.sf.net/site/users/admin':
                #fix up to be the admin user for this specific site
                owner = self.BASE_MODEL_URI + 'users/admin'
            itembNode['wiki:created-by'] = Res(owner)
                
        nameUriRef['wiki:name'] = name
        if folder:
            folder['wiki:has-child'] = nameUriRef
        nameUriRef['wiki:revisions'] = listbNode
        nameUriRef['rdf:type'] = Res('a:NamedContent')
        
        listbNode['rdf:type'] = Res('rdf:List')
        listbNode['rdf:first'] = itembNode
        listbNode['rdf:rest'] = Res('rdf:nil')
        
        itembNode['rdf:type'] = Res('wiki:Item')
        itembNode['a:created-on'] = "1057919732.750"
        if disposition:
            itembNode['wiki:item-disposition'] = Res(kw2uri(disposition, 'wiki:item-disposition-'))

        if keywords:
            nameUriRef['wiki:about'] = [Res(kw2uri(x,'wiki:')) for x in keywords]
            
        if rootFolder:
            return rootFolder.toTriplesDeep()
        else:
            return nameUriRef.toTriplesDeep()        