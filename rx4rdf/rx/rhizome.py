"""
    Helper classes for Rhizome
    This classes includes functionality dependent on the Rhizome schemas
    and so aren't included in the Racoon module.

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx import rhizml, rxml, racoon, utils, RxPath
import Ft
from Ft.Lib import Uri
from Ft.Rdf import RDF_MS_BASE,OBJECT_TYPE_RESOURCE
from Ft.Xml import InputSource
import os, sys, types
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

class DocumentMarkupMap(rhizml.LowerCaseMarkupMap):
    TT = 'code'
    A = 'link'
    SECTION = 'section'
    
    def __init__(self, docType):
        super(DocumentMarkupMap, self).__init__()
        self.docType = docType
        self.wikiStructure['!'] = (self.SECTION, 'title')

    def H(self, level, line):
        return 'section'
        
class TodoMarkupMap(rhizml.LowerCaseMarkupMap):
    pass #todo

class SpecificationMarkupMap(DocumentMarkupMap):
    SECTION = 's'
    
    def __init__(self):
        super(SpecificationMarkupMap, self).__init__('http://rx4rdf.sf.net/ns/wiki#doctype-specification')
        self.wikiStructure['!'] = (self.SECTION, None)

    def canonizeElem(self, elem):
        if isinstance(elem, type(()) ) and elem[0][0] == 's' and elem[0][-1:].isdigit():
            return 's' #map section elems to s
        else:
            return elem
        
    def H(self, level, line):
        return ('s'+`level`, (('title',rhizml.xmlquote(line)),) )

class HTMLMarkupMap(rhizml.LowerCaseMarkupMap):
    def __init__(self, rhizome):
        super(HTMLMarkupMap, self).__init__()
        self.rhizome = rhizome
        
    def mapLinkToMarkup( self, link, name, annotations, isImage, isAnchorName):
        #any link that just a name turn into a site:/// url
        if not isAnchorName and link and link[0] not in './#?' and link.find(':') == -1:
            link = 'site:///' + link        
        tag, attribs, text = super(HTMLMarkupMap, self).mapLinkToMarkup(
                link, name, annotations, isImage, isAnchorName)
        if tag != self.A:
            return tag, attribs, text

        attribDict = dict(attribs)
        url = attribDict.get('href')
        if not url:
            return tag, attribs, text
        url = url[1:-1] #strip quotes

        value = rhizml.xmlquote('IgnorableMetadata')
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
                url = replacement + url[schemeIndex+1:]
                attribDict['href'] = rhizml.xmlquote(url)
                if self.rhizome.interWikiLinkIndicator:
                    attribDict['interwiki']=value
                return tag, attribDict.items(), text
                
        external = url.find('://') > -1 or url[0] == '/'

        if external:
            if self.rhizome.externalLinkIndicator:
                attribDict['external']=value
        elif not url.startswith('#') or not url.startswith('..'): #todo: normalize with $url
            if self.rhizome.undefinedPageIndicator:
                attribDict['undefined']=value
                
        return tag, attribDict.items(), text
    
class MarkupMapFactory(rhizml.DefaultMarkupMapFactory):
    map = {
        'faq' : DocumentMarkupMap('http://rx4rdf.sf.net/ns/wiki#doctype-faq'),
        'document' : DocumentMarkupMap('http://rx4rdf.sf.net/ns/wiki#doctype-document'),
        'specification' : SpecificationMarkupMap(),
        'todo' : TodoMarkupMap(),
        }
    
    def __init__(self, rhizome):
        self.rhizome = rhizome
        
    def startElement(self, elem):
        return self.map.get(elem)

    def getDefault(self):        
        return HTMLMarkupMap(self.rhizome)
    
METADATAEXT = '.metarx'

def kw2vars(**kw):
    return dict([((None, x[0]), x[1]) for x in kw.items()])
                 
class Rhizome(object):
    exts = { 'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate': 'xml',
    'http://rx4rdf.sf.net/ns/wiki#item-format-python' : 'py',
    'http://www.w3.org/1999/XSL/Transform' : 'xsl',
    'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' : 'rxsl',
    'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml' : 'rz',
    'http://rx4rdf.sf.net/ns/wiki#item-format-text': 'txt',
    'http://rx4rdf.sf.net/ns/wiki#item-format-xml':'xml',
    'http://rx4rdf.sf.net/ns/content#pydiff-patch-transform':'pkl'
    }
    
    def __init__(self, server):
        self.server = server
        #this is just like findContentAction except we don't want to try to retrieve alt-contents' ContentLocation        
        self.findPatchContentAction = racoon.Action(['.//a:contents/text()', 
        'wf:openurl(.//a:contents/a:ContentLocation)', #contents stored externally
        ], lambda result, kw, contextNode, retVal:\
            server.getStringFromXPathResult(result), requiresContext = True) #get its content
        self.mmf = MarkupMapFactory(self)
        self.interWikiMap = None

    def configHook(self, kw):
        def initConstants(varlist, default):
            return racoon.assignVars(self, kw, varlist, default)
        
        initConstants( ['MAX_MODEL_LITERAL'], -1)        
        self.SAVE_DIR = kw.get('SAVE_DIR', 'content/.rzvs/')
        self.ALTSAVE_DIR = kw.get('ALTSAVE_DIR', 'content/')
        self.interWikiMapURL = kw.get('interWikiMapURL', 'site:///intermap.txt')
        initConstants( ['undefinedPageIndicator', 'externalLinkIndicator', 'interWikiLinkIndicator' ], 0)
        initConstants( ['authPredicates', 'globalRequestVars'], [])
        initConstants( ['RHIZOME_APP_ID'], '')

        self.passwordHashProperty = kw.get('passwordHashProperty',
                                          self.BASE_MODEL_URI+'password-hash')
        self.secureHashSeed = kw.get('SECURE_HASH_SEED',
                                          'YOU REALLY SHOULD CHANGE THIS!')
        if self.secureHashSeed == 'YOU REALLY SHOULD CHANGE THIS!':
            log.warning("secureHashSeed using default seed -- set your own private value!")
        self.secureHashMap = kw.get('secureHashMap',        
            { self.passwordHashProperty :  self.secureHashSeed })
        #make this available as an XPath variable
        self.resourceAuthorizationAction.assign("__passwordHashProperty",
                        "'"+self.passwordHashProperty+"'")

        if not kw.get('ADMIN_PASSWORD_HASH') or not kw.get('ADMIN_PASSWORD'):
            log.warning("neither ADMIN_PASSWORD nor ADMIN_PASSWORD_HASH was set; using default admin password")
        #this is just like findResourceAction except we don't assign the 'not found' resource
        #used by hasPage
        self.checkForResourceAction = racoon.Action(self.findResourceAction.queries[:-1])
        self.checkForResourceAction.assign("__resource", '.', post=True)

    def getInterWikiMap(self):        
        if self.interWikiMap is not None:
            return self.interWikiMap
        interWikiMapURL = getattr(self, 'interWikiMapURL', None) #in case this is call before configuration is completed
        if interWikiMapURL:
           self.interWikiMap = rhizml.interWikiMapParser(InputSource.DefaultFactory.fromUri(interWikiMapURL).stream)
           return self.interWikiMap
        return {}

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
        elif operation == 'assign' and namespace == racoon.RXIKI_SESSION_NS and name == 'login':
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
            self.authorizeUpdate(user, node.stmt, authorizingResources,
                "http://rx4rdf.sf.net/ns/auth#permission-add-statement")

    def authorizeRemovals(self, additions, removals, reordered, user):
        forAllResource = self.server.rdfDom.findSubject(self.server.BASE_MODEL_URI + 'common-access-checks')
        for node in reduce(self._addPredicates, removals, []):
            assert getattr(node, 'stmt') #assert it's a predicate node
            authorizingResources = self.getAuthorizingResources( node.parentNode )
            if forAllResource:
                authorizingResources.append(forAllResource)
            self.authorizeUpdate(user, node.stmt, authorizingResources,
                "http://rx4rdf.sf.net/ns/auth#permission-remove-statement")
            
    def getAuthorizingResources(self, node, membershipList = None):
        rdfDom = node.ownerDocument
        nodeset = [ node ]
        authresources = [ node ]
        while nodeset:                
            nodeset = rdfDom.evalXPath('/*/*[* = $nodeset]', nsMap = self.server.nsMap,
                                       extFunctionMap = self.server.extFunctions,
                                       vars = kw2vars(nodeset = nodeset) )
            nodeset = [p.parentNode for p in nodeset
                        if p.stmt.predicate in self.authPredicates 
                         and (not membershipList or p in membershipList) 
                         and p.parentNode not in authresources] #avoid circularity
            authresources.extend(nodeset)
        return authresources
        
    def authorizeUpdate(self, user, stmt, authorizingResources, action):
        #check authorization on all the nodes in: find all the subject
        #resources that are reachable by inverse transitively
        #following the subject of the statement and applying the authorization
        #expression to them:
        #(.//auth:requires-authorization-for[* = $resource]/ancestors::*/..)[authquery]
        #for now its more efficient to manually find the ancestors:    
            
        #if any other the authresources requires an auth token the
        #user doesn't have access to the nodeset will be not empty        
        if self.server.evalXPath('($nodeset)[%s]'%self.authorizationQuery,
            kw2vars(__authAction=action, __user=user, nodeset = authorizingResources,
                    __authProperty=stmt.predicate, __authValue=stmt.object)):
           if action == 'http://rx4rdf.sf.net/ns/auth#permission-add-statement':
               actionName = 'add'
           elif action == 'http://rx4rdf.sf.net/ns/auth#permission-remove-statement':
               actionName = 'remove'
           else:
               actionName = action
           raise racoon.NotAuthorized('You are not authorized to %s this statement: %s %s %s'
                    % (actionName, stmt.subject, stmt.predicate,stmt.object))
        
    ###command line handlers####
    def doImport(self, path, recurse=False, r=False, disposition='', filenameonly=False,
                 xupdate="path:import.xml", doctype='', format='', dest=None, **kw):
          '''Import command line option
Import the file in a directory into the site.
If, for each file, there exists a matching file with ".metarx" appended, 
then import will attempt to use the metadata in the metarx file.          
-i -import path Location of files to import
Options:
-recurse -r whether to recursively import subdirectories 
-dest path If dest is present content will be copied to this directory, 
     otherwise the site will reference the content at the import directory.
-filenameonly don't include the full relative path in the imported item name     
-xupdate URL url to an RxUpdate file which is applied to each metarx file.
Can be used for schema migration, for example.
Default: "path:import.xml". This disgards previous revisions and points the content to the new import location.
'''
          defaultFormat=format
          defaultDisposition=disposition
          defaultDoctype=doctype          
          rootPath = os.path.normpath(path or '.').replace(os.sep, '/')
          log.info('beginning import of ' + rootPath)
          triples = []
          #folders = [] #list of relevant directory paths encounters
          if dest:
              prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(dest))  
          else:
              prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(rootPath))
          #todo: support storing contents directly in model (use saveContents()?)
              
          def fileFunc(path, filename):
              if os.path.splitext(filename)[1]==METADATAEXT:
                  return              
              if dest:
                  destpath = os.path.join(dest, filename)
              else:
                  destpath = path
              if prefixlen: #if the destination is on the Racoon path use a path: URL
                  loc = racoon.SiteUriResolver.OsPathToPathUri(os.path.abspath(destpath)[prefixlen+1:])
              else: #use a file:// URL 
                  loc = Uri.OsPathToUri(os.path.abspath(destpath))
                  
              if os.path.exists(path + METADATAEXT):
                  #parse the rzml to rxml then load it into a RxPath DOM
                  xml = rhizml.rhizml2xml(open(path + METADATAEXT))
                  rdfDom = rxml.rxml2RxPathDOM(StringIO.StringIO('<rx:rx>'+ xml+'</rx:rx>'))
                  #Ft.Xml.Lib.Print.PrettyPrint(rdfDom, asHtml=1, stream=file('rdfdom1.xml','w')) #asHtml to suppress <?xml ...>
                  
                  #check to see if the page already exists in the site                  
                  wikiname = rdfDom.evalXPath('string(/*/wiki:name)', nsMap = self.server.nsMap)
                  assert wikiname, 'could not find a wikiname when importing %s' % path + METADATAEXT
                  if self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                      log.warning('there is already an item named ' + wikiname +', skipping import')
                      return #hack for now skip if item already exists
                  else:                      
                      log.info('importing ' +filename)
                  
                  #dirsegments = wikiname.split('/')[:-1]
                  #paths = dirsegments[:1]
                  #for path in dirsegments[1:]:
                  #    paths.append( paths[-1] + '/' + path)                      
                  #folders += paths
                  
                  #update the page's metadata using the xupdate script
                  self.server.xupdateRDFDom(rdfDom, uri=xupdate,
                                    kw={ 'loc' : loc, 'name' : wikiname, 'base-uri' : self.BASE_MODEL_URI,
                                         'resource-uri' : self.BASE_MODEL_URI + wikiname })

                  #write out the model as nt triples
                  moreTriples = StringIO.StringIO()                  
                  stmts = rdfDom.model.getStatements() 
                  utils.writeTriples(stmts, moreTriples)
                  #print moreTriples.getvalue()
                  triples.append( moreTriples.getvalue() )

                  #create folder resources if necessary
                  pathSegments = wikiname.split('/')
                  rootFolder, folder = self.addFolders(pathSegments[:-1])
                  if folder:
                      #get the resource's uri (it might have changed)
                      itemUriRef = rdfDom.evalXPath('string(/*[wiki:name])', nsMap = self.server.nsMap)
                      assert itemUriRef
                      folder['wiki:has-child'] = itemUriRef
                  if rootFolder:
                      triples.append( rootFolder.toTriplesDeep() )
              else:
                  #no metadata file found -- try to guess the some default metadata             
                  if not filenameonly:
                      filepath = path[len(rootPath)+1:]
                  else:
                      filepath = filename
                  wikiname = filter(lambda c: c.isalnum() or c in '_-./', os.path.splitext(filepath)[0])
                  if self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                      log.warning('there is already an item named ' + wikiname +', skipping import')
                      return #hack for now skip if item already exists
                  else:
                      log.info('importing ' +filepath+ ' as ' + wikiname)
                  if not defaultFormat:
                      exts = { '.rz' : 'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml',
                      '.xsl' : 'http://www.w3.org/1999/XSL/Transform',
                      '.rxsl' : 'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt',
                      '.py' : 'http://rx4rdf.sf.net/ns/wiki#item-format-python',
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
                      if format == 'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml':
                          mm = rhizml.rhizml2xml(file(path), mmf=self.mmf, getMM=True)
                          doctype = mm.docType
                      else:
                          doctype=''
                  else:
                      doctype = defaultDoctype
                                    
                  triples.append( self.addItem(wikiname,loc=loc,format=format,
                                    disposition=disposition, doctype=doctype,
                                    contentLength = os.stat(path).st_size,
                                    digest = utils.shaDigest(file(path))
                                    ) )
              if dest:
                  import shutil
                  try: 
                    os.makedirs(dest)
                  except OSError: pass #dir might already exist
                  shutil.copy2(path, dest)                  

          if os.path.isdir(rootPath):
                if recurse or r:
                    recurse = 0xFFFF
                utils.walkDir(rootPath, fileFunc, recurse = recurse)
          else:
                fileFunc(rootPath)
          if triples:
              triples = ''.join(triples)
              model, db = utils.DeserializeFromN3File(StringIO.StringIO(triples))
              
##              #incrementally add references folders resources to minimize duplicate statements
##              rdfDom = RxPath.createDOM(RxPath.FtModel(model), self.server.revNsMap)
##              for folder in folders:
##                  if not rdfDom.evalXPath("/wiki:Folder[wiki:name='%s']"% folder,
##                                                      nsMap = self.server.nsMap):
##                      rootFolder, folder = self.addFolders(folder)                      
##                      folder['wiki:has-child'] = nameUriRef
##                      moreTriples = rootFolder.toTriplesDeep()
##                      folderModel, folderDb = utils.DeserializeFromN3File(StringIO.StringIO(moreTriples))
##                      rdfDom.addStatements(folderModel.statements() )

              #add all the statements from the model containing the newly imported triples
              #to our server's model
              self.server.updateDom(model.statements())
          
    def doExport(self, dir, xpath=None, filter='wiki:name', name=None, static=False, **kw):
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
-label Name of revision label
'''
         assert not (xpath and name), self.server.cmd_usage
         if not xpath and name: xpath = '/*[wiki:name="%s"]' % name
         else: xpath = xpath or ('/*[%s]' % filter) 
         results = self.server.evalXPath(xpath)
         for item in results:
             name = self.server.evalXPath('string(wiki:name)', node = item)
             assert name
             orginalName = name
             content = None
             log.info('attempting to export %s ' % name)
             if static:
                 try:                     
                     rc = { '_static' : static}
                     if kw.get('label'): rc['label'] = kw['label']
                     #todo: what about adding user context (default to administrator?)
                     #add these to the requestContext so invocation know its intent
                     self.server.requestContext.append(rc)
                     content = self.server.requestDispatcher.invoke__(orginalName) 
                     #todo: change rootpath
                     #todo: handle aliases 
                     #todo: what about external files (e.g. images)
                     #todo: change extension based on output mime type                     
                     #       (use invokeEx but move default mimetype handling out of handleRequest())
                     #       but adding an extension means fixing up links
                 except:
                     log.warning('%s is dynamic, can not do static export' % name)
                     self.server.requestContext.pop()
                     #note: only works with static site (ones with no required arguments)
                 else:
                     self.server.requestContext.pop()
             else:
                 #just run the revision action and the contentAction
                 #todo: process patch
                 content = self.server.doActions([self.findRevisionAction, self.findContentAction], kw.copy(), item)

                 format = self.server.evalXPath(
'string((wiki:revisions/*/rdf:first)[last()]/wiki:Item//a:contents/a:ContentTransform/a:transformed-by/wiki:ItemFormat)',
                     node = item)
                 ext = os.path.splitext(name)[1]
                 if not ext and format:                 
                    if self.exts.get(format):
                        name += '.' + self.exts[format]
                 
             if content is None:
                 continue
                
             dir = dir.replace(os.sep, '/')
             path = dir+'/'+ name
             try: os.makedirs(os.path.split(path)[0])
             except os.error: pass 
             itemfile = file(path, 'w+b')
             itemfile.write( content)
             itemfile.close()

             if not static:             
                 lastrevision = self.server.evalXPath(
                     '''(wiki:revisions/*/rdf:first)[last()]/wiki:Item |
                       (wiki:revisions/*/rdf:first)[last()]/wiki:Item//a:contents/*''',
                     node = item)
                 lastrevision.insert(0, item)
                 metadata = rxml.getRXAsRhizmlFromNode(lastrevision)
                 metadatafile = file(path + METADATAEXT, 'w+b')
                 metadatafile.write( metadata)
                 metadatafile.close()
                 
    ######content processing####
    def processRhizmlSideEffects(self, contextNode, kw):
        #optimization: only set the doctype (which will invoke wiki2html.xsl if we need links to be transformed)
        if self.undefinedPageIndicator or self.externalLinkIndicator or self.interWikiLinkIndicator:
            #wiki2html.xsl shouldn't get invoked with the doctype isn't html
            if not kw.get('_doctype') and self.server.evalXPath(
                "not(wiki:doctype) or wiki:doctype = 'http://rx4rdf.sf.net/ns/wiki#doctype-xhtml'",
                    node = contextNode):
                kw['_doctype'] = 'http://rx4rdf.sf.net/ns/wiki#doctype-wiki'
        
    def processRhizml(self, contextNode, contents, kw):
        self.processRhizmlSideEffects(contextNode, kw)
        contents = rhizml.rhizmlString2xml(contents,self.mmf)
        return (contents, 'http://rx4rdf.sf.net/ns/wiki#item-format-xml') #fixes up site://links
        
    def processTemplateAction(self, resultNodeset, kw, contextNode, retVal):
        #the resultNodeset is the template resource
        #so skip the first few steps that find the page resource
        actions = self.handleRequestSequence[3:]

        #so we can reference the template resource (will be placed in the the 'previous' namespace)
        #print 'template resource', resultNodeset
        kw["_template"] = resultNodeset
        
        return self.server.callActions(actions, self.globalRequestVars,
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

    def customProcessor(self, contents, kw):
        #return getattr(self.customHandler, kw['_name'])(contents.strip(), kw)
        name = contents.strip()
        if name=='dump':
            return self.server.dump()
        raise 'Error: unknown customHandler! ' + name
        
    ######XPath extension functions#####        
    def getRhizml(self, context, resultset = None):        
        if resultset is None:
            resultset = context.node
        contents = racoon.StringValue(resultset)
        return rhizml.rhizmlString2xml(contents,self.mmf )

    def getRxML(self, context, resultset = None, comment = '',
                                fixUp=None, fixUpPredicate=None):
      if resultset is None:
            resultset = [ context.node ]
      return rxml.getRXAsRhizmlFromNode(resultset, rescomment = comment,
                            fixUp=fixUp, fixUpPredicate=fixUpPredicate)

    def getSecureHash(self, context, plaintext, secureProperty=None):
        if not secureProperty:
            secureProperty = self.passwordHashProperty
        import sha
        return sha.sha(plaintext + self.secureHashMap[secureProperty] ).hexdigest()    
                
    def getContents(self, context, node=None):
        if node is None:
            node = context.node
        elif not node:
            return ''#empty nodeset
        #print 'getc', node
        return self.server.doActions([self.findContentAction], {}, node)

    def hasPage(self, context, resultset = None):
        '''
        return true if the page has been defined
        '''
        if resultset is None:
            resultset = context.node
        url = racoon.StringValue(resultset)

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
            return True
        else:
            return False
        
    def getNameURI(self, context, wikiname):
        #note filter: URI fragment might not match wikiname
        #python bug: filter() on a unicode returns a list not unicode
        #todo I8N (return a IRI?)
        return self.server.BASE_MODEL_URI + \
               filter(lambda c: c.isalnum() or c in '_-./', str(wikiname))

    def saveMetadata(self, context, contents, user=None, about=None):
      try:
          xml = rhizml.rhizmlString2xml(contents)#parse the rhizml to xml
          
          #make sure we authorized to modified each resource specified in about
          #authorizationNodes = eval("/*[. = $about]", vars = utils.kw2dict(about=about) )
          #for node in authorizationNodes: 
          #    if eval(self.authorizationQuery % 'true()',
          #            node = node, vars=utils.kw2dict(__authAction='view')):
          #        raise unathorized
          
          if isinstance(about, ( types.ListType, types.TupleType ) ):            
              #about may be a list of text nodes, convert to a list of strings
              about = [racoon.StringValue(x) for x in about]
          elif about is not None:
              about = [ about ]
          self.server.processRxML('<rx:rx>'+ xml+'</rx:rx>', about, source=user)
      except racoon.NotAuthorized:
        assignFunc = context.functions.get((racoon.RXWIKI_XPATH_EXT_NS, 'assign-metadata') )
        if assignFunc:
            assignFunc(context, 'error', sys.exc_value.msg)
        else:
            raise
      except:
        log.exception("metadata save failed")
        raise
    
    def generatePatch(self, context, contents, oldcontentsNode, base64decode):
        patch = ''
        if oldcontentsNode:
            if isinstance(oldcontentsNode, type([])):
                oldcontentsNode = oldcontentsNode[0]                
            oldContents = self.server.doActions([self.findPatchContentAction], {}, oldcontentsNode)
            if oldContents:
                if base64decode:
                    #we want to base64 decode the old content before attempting the diff
                    import base64
                    oldContents = base64.decodestring(oldContents)
                patchTupleList = utils.diff(contents, oldContents) #compare  
                if patchTupleList is not None:
                    patch = pickle.dumps(patchTupleList)                    
                    
        if patch:            
            #save patch to disk:
            filepath = self.server.evalXPath("string(.//a:contents/a:ContentLocation)", node=oldcontentsNode)            
            #replace the revision's file with the patch (and if the revision doesn't have a file don't save to disk)
            if not filepath or not filepath.startswith('path:'): 
                filepath = None
            else:
                filepath = filepath[len('path:'):]
            return self._saveContents(filepath, patch)
        else:
            return patch
              
    def saveContents(self, context, wikiname, format, contents, revisionCount):
        filename = wikiname
        if filename.find('.') == -1 and self.exts.get(format):
            filename += '.' + self.exts[format]

        filepath = self.SAVE_DIR + filename + '.' + str(int(revisionCount))
        
        return self._saveContents(filepath, contents, filename)
    
    def _saveContents(self, filepath, contents, altfilename=None):
        '''        
        this is kind of ugly; XUpdate doesn't have an eval() function, so we
        build up a string of xml and then parse it and then return the doc as
        a nodeset and use xupdate:copy-of on the nodeset
        '''
        #todo at some point add sha = utils.shaDigestString(contents)
        #print >>sys.stderr, 'sc', wikiname, format, contents, revisionCount
        ns = '''xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
            xmlns:a="http://rx4rdf.sf.net/ns/archive#"
            xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"'''
        contentLength = len(contents)
        if filepath and self.MAX_MODEL_LITERAL > -1 and contentLength > self.MAX_MODEL_LITERAL:            
            #save as file
            dir = os.path.split(filepath)[0]
            try: 
               os.makedirs(dir) 
            except OSError: pass #dir might already exist
            f = file(filepath, 'wb')
            f.write(contents)
            f.close()

            if altfilename and self.ALTSAVE_DIR:
                #we save another copy of the last revision in order that minor edit
                #or external changes don't effect diffs etc.                
                altfilepath = self.ALTSAVE_DIR + altfilename
                dir = os.path.split(altfilepath)[0]
                try:  os.makedirs(dir) 
                except OSError: pass #dir might already exist
                f = file(altfilepath, 'wb')
                f.write(contents)
                f.close()                
                altContents = "<wiki:alt-contents><a:ContentLocation rdf:about='path:%s' /></wiki:alt-contents>" % altfilepath
            else:
                altContents = ''

            digest=utils.shaDigestString(contents)
            contentProps = "<a:content-length>%u</a:content-length><a:sha1-digest>%s</a:sha1-digest>"\
                           % (contentLength, digest)
            
            #we assume SAVE_DIR and ALTSAVE_DIR is a relative path rooted in one of the directories on the RHIZOME_PATH
            xml = '''<a:ContentLocation %(ns)s rdf:about='path:%(filepath)s'>%(contentProps)s%(altContents)s</a:ContentLocation>''' % locals()
        else: #save the contents inside the model
            try:
                contents.encode('ascii') #test to see if is just ascii (all <128)
                return contents
                #contents = utils.htmlQuote(contents)
                #xml = '''<a:Content rdf:about='%(sha1urn)'>%(contentProps)s<a:contents>%(contents)s</a:contents></<a:Content>''' % locals()
            except UnicodeError:
                #could be binary, base64 encode
                encodedURI = utils.generateBnode()
                contents = base64.encodestring(contents)            
                xml = '''<a:ContentTransform %(ns)s rdf:about='%(encodedURI)s'>
                    <a:transformed-by><rdf:Description rdf:about='http://www.w3.org/2000/09/xmldsig#base64'/></a:transformed-by>
                    <a:contents>%(xml)s</a:contents>
                   </a:ContentTransform>''' % locals()

        #print >>sys.stderr, 'sc', xml
        from Ft.Xml import Domlette
        #why can't InputSource accept unicode? lame (thus we don't support unicode filenames right now)
        isrc = InputSource.DefaultFactory.fromString(str(xml), 'file:') 
        xmlDoc = Domlette.NonvalidatingReader.parse(isrc)
        #return a nodeset containing the root element of the doc
        #print >>sys.stderr, 'sc', xmlDoc.documentElement
        return [ xmlDoc.documentElement ]

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

    def addItemTuple(self, name, **kw):
        return (name, self.addItem(name, **kw))

    def addItem(self, name, loc=None, contents=None, disposition = 'complete', 
                format='binary', doctype='', handlesDoctype='', handlesDisposition='',
                title=None, label='http://rx4rdf.sf.net/ns/wiki#label-released',
                handlesAction=None, actionType='http://rx4rdf.sf.net/ns/archive#NamedContent',
                baseURI=None, owner='http://rx4rdf.sf.net/site/users/admin',
                accessTokens=['base:write-structure-token'], authorizationGroup='',
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
        itembNode['wiki:item-disposition'] = Res(kw2uri(disposition, 'wiki:item-disposition-'))

        if rootFolder:
            return rootFolder.toTriplesDeep()
        else:
            return nameUriRef.toTriplesDeep()