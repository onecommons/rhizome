"""
    Helper classes for Rhizome

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import rhizml, rxml, racoon
import utils, RDFDom
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

class MarkupMapFactory(rhizml.DefaultMarkupMapFactory):
    map = {
        'faq' : DocumentMarkupMap('http://rx4rdf.sf.net/ns/wiki#doctype-faq'),
        'document' : DocumentMarkupMap('http://rx4rdf.sf.net/ns/wiki#doctype-document'),
        'specification' : SpecificationMarkupMap(),
        'todo' : TodoMarkupMap(),
        }
    
    def startElement(self, elem):
        return self.map.get(elem)

METADATAEXT = '.metarx'

class Rhizome:
    exts = { 'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate': 'xml',
    'http://rx4rdf.sf.net/ns/wiki#item-format-python' : 'py',
    'http://www.w3.org/1999/XSL/Transform' : 'xsl',
    'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' : 'rxsl',
    'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml' : 'rz',
    'http://rx4rdf.sf.net/ns/wiki#item-format-text': 'txt',
    'http://rx4rdf.sf.net/ns/wiki#item-format-xml':'xml',
    }
    
    def __init__(self, server):
        self.server = server

    def processTemplateAction(self, resultNodeset, kw, contextNode, retVal):
        #the resultNodeset is the template resource
        #so skip the first few steps that find the page resource
        actions = self.handleRequestSequence[3:]
        return self.server.callActions(actions, [ '_user', '_name' ],
                                       resultNodeset, kw, contextNode, retVal)
    
    def doImport(self, path, recurse=False, r=False, disposition='', xupdate="path:import.xml", format='', dest=None, **kw):
          '''Import command line option
Import the file in a directory into the site.
If, for each file, there exists a matching file with ".metarx" appended, 
then import will attempt to use the metadata in the metarx file.          
-i -import path Location of files to import
Options:
-recurse -r whether to recursively import subdirectories 
-dest path If dest is present content will be copied to this directory, 
     otherwise the site will reference the content at the import directory.
-xupdate URL url to an RxUpdate file which is applied to each metarx file.
Can be used for schema migration, for example.
Default: "path:import.xml". This disgards previous revisions and points the content to the new import location.
'''
          defaultFormat=format
          defaultDisposition=disposition
          path = path or '.'
          triples = []
          if dest:
              prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(dest))  
          else:
              prefixlen = len(InputSource.DefaultFactory.resolver.getPrefix(path))
              
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
                  xml = rhizml.rhizml2xml(open(path + METADATAEXT))#parse the rxity to rx xml
                  try:
                      model, db = rxml.rx2model(StringIO.StringIO('<rx:rx>'+ xml+'</rx:rx>'))
                  except:
                      #file('badrxml.xml','w').write(xml)
                      raise
                  rdfDom = RDFDom.RDFDoc(model, self.server.revNsMap)                  
                  #Ft.Xml.Lib.Print.PrettyPrint(rdfDom, asHtml=1, stream=file('rdfdom1.xml','w')) #asHtml to suppress <?xml ...>
                  #delete all revisions except last 
                  #replace the innermost a:contents with content location
                  #print map(lambda x: x.firstChild, RDFDom.evalXPath(rdfDom, '/*/wiki:revisions/*//a:contents', nsMap = self.server.nsMap))
                  #print map(lambda x: x.firstChild, RDFDom.evalXPath(rdfDom, '(/*/wiki:revisions/*//a:contents)[last()]', nsMap = self.server.nsMap))
                  wikiname = rdfDom.evalXPath('string(/*/wiki:name)', nsMap = self.server.nsMap)
                  assert wikiname
                  if self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                      log.warning('there is already an item named ' + wikiname +', skipping import')
                      return #hack for now skip if item already exists
                  else:                    
                      log.info('importing ' +filename)
                  moreTriples = StringIO.StringIO()                  
                  self.server.xupdateRDFDom(rdfDom,moreTriples, uri=xupdate,
                                    kw={ 'loc' : loc, 'name' : wikiname, 'base-uri' : self.BASE_MODEL_URI,
                                         'resource-uri' : self.BASE_MODEL_URI + wikiname })
                  #print moreTriples.getvalue()
                  triples.append( moreTriples.getvalue() )
              else:
                  #try to guess the wikiname
                  wikiname = filter(lambda c: c.isalnum() or c in '_-./', os.path.splitext(filename)[0])
                  if self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                      log.warning('there is already an item named ' + wikiname +', skipping import')
                      return #hack for now skip if item already exists
                  else:
                      log.info('importing ' +filename+ ' as ' + wikiname)
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
                  if format == 'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml':
                      mm = rhizml.rhizml2xml(file(path), mmf=MarkupMapFactory(), getMM=True)
                      doctype = mm.docType
                  else:
                      doctype=''
                  triples.append( self.addItem(wikiname,loc=loc,format=format, disposition=disposition, doctype=doctype) )
              if dest:
                  import shutil
                  try: 
                    os.makedirs(dest)
                  except OSError: pass #dir might already exist                    
                  shutil.copy2(path, dest)                  

          if os.path.isdir(path):
                if recurse or r:
                    recurse = 0xFFFF
                utils.walkDir(path, fileFunc, recurse = recurse)
          else:
                fileFunc(path)
          if triples:
              triples = ''.join(triples)
              #get current model
              db = Ft.Rdf.Drivers.Memory.CreateDb('', 'default')
              outputModel = Ft.Rdf.Model.Model(db)
              lock = self.server.getLock()
              RDFDom.treeToModel(self.server.rdfDom, outputModel, '')
              #add the new imported statements
              utils.DeserializeFromN3File(StringIO.StringIO(triples), model = outputModel)
              #save the model and reload the RDFDom
              outputfile = file(self.server.STORAGE_PATH, "w+", -1)
              stmts = db._statements['default'] #get statements directly, avoid copying list
              utils.writeTriples(stmts, outputfile)
              outputfile.close()
              self.server.loadModel()
              lock.release()              
          
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
'''
         assert not (xpath and name), self.server.cmd_usage
         if not xpath and name: xpath = '/*[wiki:name=%s]' % name
         else: xpath = xpath or ('/*[%s]' % filter) 
         results = self.server.evalXPath(xpath)
         for item in results:
             name = self.server.evalXPath('string(wiki:name)', node = item)
             assert name
             orginalName = name
             format = self.server.evalXPath('string(wiki:revisions/*[last()]//a:contents/a:ContentTransform/a:transformed-by/wiki:ItemFormat)', node = item)
             ext = os.path.splitext(name)[1]
             if not ext and format:                 
                if self.exts.get(format):
                    name += '.' + self.exts[format]
             content = None
             if static:
                 try:
                     content = kw['__requestor__'].invoke__(orginalName) 
                     #todo: do we need any special link fixup?
                     #todo: what about external files (e.g. images)
                     #todo: change extension based on output mime type
                     #       (use invokeEx but move default mimetype handling out of handleRequest())
                     #       but adding an extension means fixing up links
                 except AttributeError:
                     log.warning('%s is dynamic, can not do static export', name)
                     pass #note: only works with static site (ones with no arguments to pass
             else:
                 #just run the revision action and the contentAction
                 #todo: process patch
                 content = self.server.doActions([self.findRevisionAction, self.findContentAction], kw.copy(), item)             
             if content is None:
                 continue
                
             dir = dir.replace(os.sep, '/')
             path = dir+'/'+ name
             try: os.makedirs(os.path.split(path)[0])
             except os.error: pass 
             itemfile = file(path, 'w+b')
             itemfile.write( content)
             itemfile.close()
             
             lastrevision = self.server.evalXPath('wiki:revisions/*[last()] | wiki:revisions/*[last()]//a:contents/*', node = item)
             lastrevision.insert(0, item)
             metadata = rxml.getRXAsRhizmlFromNode(lastrevision)
             metadatafile = file(path + METADATAEXT, 'w+b')
             metadatafile.write( metadata)
             metadatafile.close()             

    def processPatch(self, contents, kw, result):
        #we assume result is a:ContentTransform/a:transformed-by/*, set context to the parent a:ContentTransform
        patchBaseResource =  self.server.evalXPath('../../a:pydiff-patch-base/*', node = result)
        #print 'r', result
        #print 'b', patchBaseResource
        #print 'c', contents
        #print 'context: ', result
        #print 'pr', patchBaseResource

        #get the contents of the resource which this patch will use as the base to run its patch against
        #todo: issue kw.copy() is not a deep copy -- what to do?
        base = self.server.doActions([self.findContentAction, self.processContentAction], kw.copy(), patchBaseResource)
        patch = pickle.loads(str(contents))
        return utils.patch(base,patch)

    def metadata_save(self, about, contents):
      #print >>sys.stderr, 'about ', about
      if not isinstance(about, ( types.ListType, types.TupleType ) ):
        about = [ about ]
      resources = []
      try:
       for s in self.server.rdfDom.childNodes:
            if not about:
                break
            if s.getAttributeNS(RDF_MS_BASE, 'about') in about:            
                resources.append(s)
                about.remove( s.getAttributeNS(RDF_MS_BASE, 'about') )
       xml = rhizml.rhizmlString2xml(contents)#parse the rxity to rx xml
       self.server.processRxML('<rx:rx>'+ xml+'</rx:rx>', resources)
      except:
        log.exception("metadata save failed")
        raise

    def addItemTuple(self, name, **kw):
        return [(name, self.addItem(name, **kw))]

    def addItem(self, name, loc=None, contents=None, disposition = 'complete', 
                format='binary', doctype='', handlesDoctype='', handlesDisposition='', title=None,
                handlesAction=None, actionType='http://rx4rdf.sf.net/ns/archive#NamedContent',
                baseURI=None, owner='http://rx4rdf.sf.net/site/users-admin',
                accessTokens=['base:write-structure-token'], authorizationGroup=''):
        '''
        Convenience function for adding an item the model. Returns a string of triples.
        '''
        from utils import Res
        Res.nsMap = self.nsMap
        
        if not baseURI:
            baseURI = self.BASE_MODEL_URI
        nameUriRef = Res(baseURI + filter(lambda c: c.isalnum() or c in '_-./', name))
        namebNode = '_:'+ filter(lambda c: c.isalnum(), name) 
        listbNode = Res(namebNode + '1List')
        itembNode = Res(namebNode + '1Item')

        contentbNode = Res(namebNode + '1Content')
        itembNode['a:contents'] = contentbNode
        contentbNode['rdf:type'] = Res('a:ContentTransform')
        
        if format.isalpha(): #if not a URI
           format = 'http://rx4rdf.sf.net/ns/wiki#item-format-' + format        
        contentbNode['a:transformed-by'] = Res(format)

        assert not (loc and contents)
        if loc:
            loc = Res(loc)
            loc['rdf:type'] = Res('a:ContentLocation')
            contentbNode['a:contents'] = loc
        else:
            contentbNode['a:contents'] = contents

        if title is not None:
            itembNode['wiki:title'] = title        
        if doctype:
            if doctype.isalpha(): #if not a URI
               doctype = 'http://rx4rdf.sf.net/ns/wiki#doctype-' + doctype
            itembNode['wiki:doctype'] = Res(doctype)
        if handlesDoctype:
            nameUriRef['wiki:handles-doctype'] = Res('http://rx4rdf.sf.net/ns/wiki#doctype-' + handlesDoctype)
        if handlesDisposition:
            nameUriRef['wiki:handles-disposition'] = Res('http://rx4rdf.sf.net/ns/wiki#item-disposition-' + handlesDisposition)
            
        if handlesAction:                        
            nameUriRef['wiki:handles-action'] = [Res('wiki:action-'+ x) for x in handlesAction]
            if actionType:
                nameUriRef['wiki:action-for-type'] = Res(actionType)

        if accessTokens:
            nameUriRef['auth:needs-token'] = [Res(x) for x in accessTokens]
            
        if authorizationGroup:
            nameUriRef['auth:member-of'] = Res(authorizationGroup)
            
        if owner:
            if owner == 'http://rx4rdf.sf.net/site/users-admin':
                #fix up to be the admin user for this specific site
                owner = self.BASE_MODEL_URI + 'users-admin'
            itembNode['wiki:created-by'] = Res(owner)
                
        nameUriRef['wiki:name'] = name
        nameUriRef['wiki:revisions'] = listbNode
        nameUriRef['rdf:type'] = Res('a:NamedContent')
        
        listbNode['rdf:type'] = Res('rdf:List')
        listbNode['rdf:first'] = itembNode
        listbNode['rdf:rest'] = Res('rdf:nil')
        
        itembNode['rdf:type'] = Res('wiki:Item')
        itembNode['a:created-on'] = "1057919732.750"
        itembNode['wiki:item-disposition'] = Res('http://rx4rdf.sf.net/ns/wiki#item-disposition-' + disposition)

        return nameUriRef.toTriplesDeep()                