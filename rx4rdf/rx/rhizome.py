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

class DocumentMarkupMap(rhizml.LowerCaseMarkupMap):
    TT = 'code'
    A = 'link'
    
    def __init__(self):
        super(DocumentMarkupMap, self).__init__()
        self.wikiStructure['!'] = ('section', 'title')

    def H(self, level, line):
        return 'section'
        
class TodoMarkupMap(rhizml.LowerCaseMarkupMap):
    pass #todo

class SpecificationMarkupMap(DocumentMarkupMap):
    def __init__(self):
        super(SpecificationMarkupMap, self).__init__()        
        self.wikiStructure['!'] = ('s', None)

    def canonizeElem(self, elem):
        if isinstance(elem, type(()) ) and elem[0][0] == 's':
            return 's' #map sections elems to s
        else:
            return elem
        
    def H(self, level, line):
        return ('s'+`level`, (('title',rhizml.xmlquote(line)),) )

class MarkupMapFactory(rhizml.DefaultMarkupMapFactory):
    map = {
        'faq' : DocumentMarkupMap(),
        'document' : DocumentMarkupMap(),
        'specification' : SpecificationMarkupMap(),
        'todo' : TodoMarkupMap(),
        }
    
    def startElement(self, elem):
        return self.map.get(elem)

METADATAEXT = '.metarx'

class Rhizome:        
    def __init__(self, server):
        self.server = server

    def getResourceAction(self, resultNodeset, kw, contextNode, retVal): 
        kw['_contents'] = retVal            
        kw['_prevnode'] = [ contextNode ] #nodeset containing current resource
        if kw.has_key('revision'):
            del kw['revision'] #don't apply this to the template resource
        return self.server.doActions(self.handleRequestSequence[1:], kw, resultNodeset) #the resultNodeset is the contextNode so skip the find resource step
    
    def doImport(self, path, recurse=False, r=False, disposition='entry', xupdate="path:import.xml", format='', dest=None, **kw):
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
                  wikiname = RDFDom.evalXPath(rdfDom, 'string(/*/wiki:name)', nsMap = self.server.nsMap)
                  assert wikiname
                  if self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                      print 'warning: there is already an item named',wikiname, 'skipping import'
                      return #hack for now skip if item already exists
                  else:                    
                      print 'importing ', filename
                  moreTriples = StringIO.StringIO()                  
                  self.server.xupdateRDFDom(rdfDom,moreTriples, uri=xupdate,
                                    kw={ 'loc' : loc, 'name' : wikiname,
                                         'resource-uri' : self.BASE_MODEL_URI + wikiname })
                  #print moreTriples.getvalue()
                  triples.append( moreTriples.getvalue() )
              else:
                  #try to guess the wikiname
                  wikiname = filter(lambda c: c.isalnum() or c in '_-./', os.path.splitext(filename)[0])
                  if self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                      print 'warning: there is already an item named', wikiname, 'skipping import'
                      return #hack for now skip if item already exists
                  else:
                      print 'importing ', filename
                  if not defaultFormat:
                      exts = { '.rz' : 'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml',
                      '.xsl' : 'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt',
                      '.py' : 'http://rx4rdf.sf.net/ns/wiki#item-format-python',
                      '.txt' : 'http://rx4rdf.sf.net/ns/wiki#item-format-text',
                      }                  
                      format = exts.get(os.path.splitext(path)[1], 'http://rx4rdf.sf.net/ns/wiki#item-format-binary')
                  else:
                      format = defaultFormat
                  triples.append( self.addItem(filename,loc=loc,format=format, disposition=disposition) )
              if dest:
                  import shutil
                  try: 
                    os.makedirs(dest)
                  except OSError: pass #dir might already exist                    
                  shutil.copy2(path, dest)                  

          if os.path.isdir(path):
                utils.walkDir(path, fileFunc, recurse = (recurse or r))
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
                    exts = { 'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate': 'xml',
                    'http://rx4rdf.sf.net/ns/wiki#item-format-python' : 'py',
                    'http://www.w3.org/1999/XSL/Transform' : 'xsl',
                    'http://rx4rdf.sf.net/ns/wiki#item-format-rxslt' : 'xsl',
                    'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml' : 'rz',
                    'http://rx4rdf.sf.net/ns/wiki#item-format-text': 'txt',
                    }
                    if exts.get(format):
                        name += '.' + exts[format]
             content = None
             if static:
                 try:
                     content = kw['__requestor__'].invoke(orginalName) 
                     #todo: do we need any special link fixup?
                     #todo: what about external files (e.g. images)
                     #todo: change extension based on output mime type
                     #       (use invokeEx but move default mimetype handling out of handleRequest())
                     #       but adding an extension means fixing up links
                 except AttributeError:
                     print 'warning: ', name, 'is dynamic, can not do static export'
                     pass #note: only works with static site (ones with no arguments to pass
             else:                              #just run the revision action and the contentAction
                  content = self.server.doActions([self.getRevisionAction, self.getContentAction], kw.copy(), item)             
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
        print 'r', result
        print 'b', patchBaseResource
        print 'c', contents
        #print 'context: ', result
        #print 'pr', patchBaseResource

        #get the contents of the resource which this patch will use as the base to run its patch against
        #todo: issue kw.copy() is not a deep copy -- what to do?
        base = self.server.doActions([self.getContentAction, self.processContentAction], kw.copy(), patchBaseResource)
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
        import traceback
        traceback.print_exc(None, sys.stderr)
        raise

    def addItemTuple(self, name, **kw):
        return [(name, self.addItem(name, **kw))]

    def addItem(self, name, loc=None, contents=None, disposition = 'complete',
                format='binary', doctype='', handlesDoctype='', handlesDisposition='',
                baseURI=None, owner='http://rx4rdf.sf.net/ns/wiki#owner-system'):
        if format.isalpha(): #if not a URI
           format = 'http://rx4rdf.sf.net/ns/wiki#item-format-' + format
        if not baseURI:
            baseURI = self.BASE_MODEL_URI
        nameUriRef = baseURI + filter(lambda c: c.isalnum() or c in '_-./', name)
        namebNode = filter(lambda c: c.isalnum(), name)
        listbNode = namebNode + '1List'
        itembNode = namebNode + '1Item'
        assert not (loc and contents)
        if loc:
            contentTriples = ''' <http://rx4rdf.sf.net/ns/archive#contents> <%(loc)s> .
    <%(loc)s> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#ContentLocation> .''' % locals()
        else:
            contentTriples = ''' <http://rx4rdf.sf.net/ns/archive#contents> "%(contents)s" .''' % locals()

        if format == 'http://rx4rdf.sf.net/ns/wiki#item-format-binary': 
            contentTriples = '_:' + itembNode + contentTriples
        else:
            contentbNode = namebNode + '1Content'
            contentTriples = '''_:%(itembNode)s <http://rx4rdf.sf.net/ns/archive#contents> _:%(contentbNode)s .
    _:%(contentbNode)s <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#ContentTransform> .
    _:%(contentbNode)s <http://rx4rdf.sf.net/ns/archive#transformed-by> <%(format)s> .
    _:%(contentbNode)s %(contentTriples)s''' % locals()

        if doctype:    
            doctype = "_:%(itembNode)s <http://rx4rdf.sf.net/ns/wiki#doctype> <http://rx4rdf.sf.net/ns/wiki#doctype-%(doctype)s>.\n" % locals()
        if handlesDoctype:    
            handlesDoctype = "<%(nameUriRef)s> <http://rx4rdf.sf.net/ns/wiki#handles-doctype> <http://rx4rdf.sf.net/ns/wiki#doctype-%(handlesDoctype)s>.\n" % locals()
        if handlesDisposition:    
            handlesDisposition = "<%(nameUriRef)s> <http://rx4rdf.sf.net/ns/wiki#handles-disposition> <http://rx4rdf.sf.net/ns/wiki#item-disposition-%(handlesDisposition)s>.\n" % locals()
        if owner:    
            owner = "<%(nameUriRef)s> <http://rx4rdf.sf.net/ns/wiki#owned_by> <%(owner)s>.\n" % locals()
        else:
            owner = ''
            
        return '''<%(nameUriRef)s> <http://rx4rdf.sf.net/ns/wiki#name> "%(name)s" .
    <%(nameUriRef)s> <http://rx4rdf.sf.net/ns/wiki#revisions> _:%(listbNode)s .
    <%(nameUriRef)s> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
    _:%(listbNode)s <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/1999/02/22-rdf-syntax-ns#List> .
    _:%(listbNode)s <http://www.w3.org/1999/02/22-rdf-syntax-ns#first> _:%(itembNode)s .
    _:%(listbNode)s <http://www.w3.org/1999/02/22-rdf-syntax-ns#rest> <http://www.w3.org/1999/02/22-rdf-syntax-ns#nil>.
    _:%(itembNode)s <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/wiki#Item> .
    _:%(itembNode)s <http://rx4rdf.sf.net/ns/archive#created-on> "1057919732.750" .
    _:%(itembNode)s <http://rx4rdf.sf.net/ns/wiki#item-disposition> <http://rx4rdf.sf.net/ns/wiki#item-disposition-%(disposition)s> .
    %(doctype)s%(handlesDoctype)s%(handlesDisposition)s%(owner)s%(contentTriples)s\n'''% locals() 
