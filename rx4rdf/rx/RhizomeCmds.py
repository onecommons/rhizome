"""
    Rhizome commands.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx.RhizomeBase import *
import os, os.path, sys, types, fnmatch, traceback
try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO

METADATAEXT = '.metarx'

class RhizomeCmds(RhizomeBase):

    ###command line handlers####
    def doImport(self, path, recurse=False, r=False, disposition='',
                 filenameonly=False, xupdate="path:import.xml",
                 doctype='', format='', dest=None, folder=None, token = None,
                 label=None, keyword=None, keepext=False, noindex=False,
                 noshred=False, save=True, fixedBaseURI=None, **kw):
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
-noindex Don't add the content to the index.
-noshred Don't shred content on import.

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
        self.log.info('beginning import of ' + rootPath)
        triplesDict = {}

        if fixedBaseURI:
            assert not (recurse or r),(
              'this combination of options is not supported yet')
        else:
            if dest:
                prefixlen = len(InputSource.DefaultFactory.
                                resolver.getPrefix(dest))  
            else:
                prefixlen = len(InputSource.DefaultFactory.
                                resolver.getPrefix(rootPath))
              
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
            elif prefixlen:
                #if the destination is on the raccoon path use a path: URL
                loc = raccoon.SiteUriResolver.OsPathToPathUri(
                    os.path.abspath(destpath)[prefixlen+1:])
            else: #use a file:// URL 
                loc = Uri.OsPathToUri(os.path.abspath(destpath),
                                        attemptAbsolute=False)
                
            if os.path.exists(path + METADATAEXT):
                #parse the rzml to rxml then load it into a RxPath DOM
                xml = zml.zml2xml(open(path + METADATAEXT), URIAdjust=True)
                rdfDom = rxml.rxml2RxPathDOM(
                    StringIO.StringIO('<rx:rx>'+ xml+'</rx:rx>'))
                #Ft.Xml.Lib.Print.PrettyPrint(rdfDom, asHtml=1,
                #stream=file('rdfdom1.xml','w')) #asHtml to suppress <?xml ...>
                
                #check to see if the page already exists in the site                  
                wikiname = rdfDom.evalXPath('string(/*/wiki:name)',
                                            nsMap = self.server.nsMap)
                assert wikiname, (
                    'could not find a wikiname when importing %s'
                                                      % path + METADATAEXT)
                if save and self.server.evalXPath("/*[wiki:name='%s']"%wikiname):
                    self.log.warning('there is already an item named '
                                     + wikiname +', skipping import')
                    return #hack for now skip if item already exists
                else:                      
                    self.log.info('importing ' +filename)
                                  
                #update the page's metadata using the xupdate script
                self.server.xupdateRDFDom(rdfDom, uri=xupdate,
                      kw={ 'loc' : loc, 'name' : wikiname,
                           'base-uri' : self.BASE_MODEL_URI,
                           'resource-uri' : self.getNameURI(None,wikiname) })

                #write out the model as nt triples
                moreTriples = StringIO.StringIO()                  
                stmts = rdfDom.model.getStatements() 
                RxPath.writeTriples(stmts, moreTriples)        
                triples = moreTriples.getvalue()
                triplesDict[wikiname] = triples

                #get the resource's uri (it might have changed)
                resourceURI = rdfDom.evalXPath('string(/*[wiki:name])',
                                               nsMap = self.server.nsMap)
                assert resourceURI
                
                #create folder resources if necessary
                pathSegments = wikiname.split('/')
                rootFolder, parentFolder = self.addFolders(pathSegments[:-1])
                if parentFolder:
                    parentFolder['wiki:has-child'] = resourceURI
                if rootFolder:
                    triples += rootFolder.toTriplesDeep()
                    triplesDict['@importedfolders'] = triplesDict.get(
                      '@importedfolders','') + rootFolder.toTriplesDeep()
                    
                format = rdfDom.evalXPath(
                '''string((/*[wiki:name]/wiki:revisions/*/rdf:first)[last()]/
                   wiki:Item/a:contents/a:ContentTransform/a:transformed-by/
                   wiki:ItemFormat)''',
                   nsMap = self.server.nsMap)
                contentTransform = rdfDom.evalXPath(
                '''string((/*[wiki:name]/wiki:revisions/*/rdf:first)[last()]/
                   wiki:Item/a:contents/a:ContentTransform)''',
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
                wikiname = filter(lambda c: c.isalnum() or c in '_-./',
                                  wikiname)
                if save and self.server.evalXPath("/*[wiki:name='%s']"% wikiname):
                    self.log.warning('there is already an item named '
                                     + wikiname +', skipping import')
                    return #hack for now skip if item already exists
                else:
                    self.log.info('importing ' +filepath+ ' as ' + wikiname)
                if not defaultFormat:
                    exts = {
                    '.zml' : 'http://rx4rdf.sf.net/ns/wiki#item-format-zml',
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
                pathStat = os.stat(path)
                triples = self.addItem(wikiname,
                                  loc=loc,format=format,
                                  disposition=disposition, doctype=defaultDoctype,
                                  contentLength = str(pathStat.st_size),
                                  digest = utils.shaDigest(path),
                                  keywords=keywords,
                                  label=label, accessTokens=accessTokens,
                                  createdOn='%.3f' % pathStat.st_mtime)
                triplesDict[wikiname] = triples
                title = ''
                resourceURI = self.getNameURI(None, wikiname)
                contentTransform = 'bnode:' + wikiname + '1Content'
                            
            if dest:
                import shutil
                try: 
                    os.makedirs(dest)
                except OSError: pass #dir might already exist
                shutil.copy2(path, dest)

            contentsFile = file(path, 'r')
            contents = contentsFile.read()
            contentsFile.close()

            if save:
                #replace resourceURI (if it exists) with imported
                self.server.updateStoreWithRDF(triples,'ntriples',
                                               resourceURI, [resourceURI])
            
            if save and not noshred:
                contextURI = 'context:'+contentTransform
                self.server.domStore.dom.pushContext(contextURI)
                try:
                    xpath = '''wf:shred(/*[.='%s'],'%s', $contents)
                            ''' % (resourceURI, format)
                    self.server.evalXPath(xpath,
                                          vars={(None,'contents'):contents})
                    from rx.RxPathUtils import Res
                    Res.nsMap = self.nsMap
                    rdfSource = Res()
                    rdfSource['rdf:type'] = Res('a:RDFSource')                       
                    rdfSource['a:from-source']=Res(contentTransform)
                    rdfSource['a:entails'] = Res(contextURI)
                    self.server.updateStoreWithRDF(rdfSource.toTriplesDeep(),
                                                   'ntriples',resourceURI)
                finally:
                    self.server.domStore.dom.popContext()
                                
            if save and self.index and not noindex:
                if format in self.indexableFormats:
                    self.addToIndex(resourceURI,contents, title)
                
        if os.path.isdir(rootPath):
            if recurse or r:
                recurse = 0xFFFF
            utils.walkDir(rootPath, fileFunc, recurse = recurse)
        else:
            fileFunc(rootPath, os.path.split(rootPath)[1])                    
                    
        return triplesDict

    def doExport(self, dir, kw):
        if kw.get('static'):
            #we need to modify the kw dict, not the copy made by **kw
            kw['__readOnly'] = 1
        return self._doExport(dir, **kw)
          
    def _doExport(self, dir, xpath=None, filter='wiki:name', name=None,
                 static=False, noalias=False, astriples=None, base=None, **kw):
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
-base    Base URL for links (use with -static only)
-label Name of revision label
-astriples filepath Export the selected resources as an NTriples file.
                    External content is inserted in the file as string literals.
'''
        assert not (xpath and name), self.server.cmd_usage
        if not xpath and name:
            xpath = '/a:NamedContent[wiki:name="%s"]' % name
        else:
            xpath = xpath or ('/a:NamedContent[%s]' % filter) 
         
        results = self.server.evalXPath(xpath)
        if astriples:
            stmts = []
        if base is None:
            baseURI = Uri.OsPathToUri(os.path.abspath(dir),
                                      attemptAbsolute=False)
        else:
            baseURI = base

        for item in results:
            name = self.server.evalXPath('string(wiki:name)', node = item)
            assert name
            orginalName = name
            content = None
            self.log.info('exporting %s ' % name)
            if static:                 
                try:
                    if kw.get('label'):
                        rc['label'] = kw['label']
                     
                    rc = { '_static' : static,
                            '_noErrorHandling': 1,
                            '_APP_BASE' : baseURI,
                        }
                    #todo: what about adding user context
                    #(default to administrator?)
                    content = self._invokeRequest(name, rc)                     
                    
                    #todo: copy embedded external links (e.g. images)
                    #todo: change extension based on output mime type                     
                except:
                    #traceback.print_exc()
                    #note: only works with static pages (ones with no required parameters)
                    self.log.warning('%s is dynamic, can not do static export' % name)
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
                     pass 
                 itemfile = file(path, 'w+b')
                 itemfile.write( content)
                 itemfile.close()

            if static:
                 if not noalias:
                    #todo: handle aliases better (only generate if referenced)
                    aliases = self.server.evalXPath('wiki:alias/text()',
                                                    node = item)
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
                 from rx.RxPathUtils import Res

                 resources = self.server.evalXPath(
                     '''. | (wiki:revisions/*/rdf:first)[last()]/wiki:Item |
                       ((wiki:revisions/*/rdf:first)[last()]/
                       wiki:Item//a:contents/node())''',
                     node = item)[:-1] #skip final text() or ContentLocation                 
                 
                 #should be the last contents, i.e. a ContentTransform
                 lastContents = resources[-1]
                 assert self.server.evalXPath('self::a:ContentTransform',
                                              node = lastContents), resources

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
             RxPath.writeTriples(stmts,stream)
             stream.close()

    def _invokeRequest(self, name, kw):
        try:
            #we need this to store the mimetype:
            class _dummyRequest:
                def __init__(self):
                    self.headerMap = {}
                    self.simpleCookie = {}
            
            #add these to the requestContext so invocation know its intent
            self.server.requestContext.append(kw)
            return self.server.requestDispatcher.invoke__(name,
                                     _response=_dummyRequest() ) 
        finally:
            self.server.requestContext.pop()
