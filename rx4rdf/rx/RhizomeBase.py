"""
    Helper classes for Rhizome
    This classes includes functionality dependent on the Rhizome schemas
    and so aren't included in the Raccoon module.

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx import zml, rxml, raccoon, utils, RxPath
from rx.transactions import TxnFileFactory
import Ft
from Ft.Lib import Uri
from RxPath import RDF_MS_BASE,OBJECT_TYPE_RESOURCE,RDF_SCHEMA_BASE
from Ft.Xml import InputSource
import os, os.path, sys, types, base64, traceback, re, copy
try:
    import cPickle
    pickle = cPickle
except ImportError:
    import pickle
from rx import logging #for python 2.2 compatibility
log = logging.getLogger("rhizome")

def kw2vars(**kw):
    return dict([((None, x[0]), x[1]) for x in kw.items()])
                 
class RhizomeBase(object):
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
    log = log
    defaultPassword = 'admin'
    defaultSecureHashSeed = 'YOU SHOULD CHANGE THIS!'
                                          
    def configHook(self, kw):
        self.log = logging.getLogger("rhizome." + self.server.appName)
        
        def initConstants(varlist, default):
            return raccoon.assignVars(self, kw, varlist, default)
        
        initConstants( ['MAX_MODEL_LITERAL'], -1)        
        
        self.SAVE_DIR = kw.get('SAVE_DIR', 'content/.rzvs')
        if not os.path.isabs(self.SAVE_DIR):
            self.SAVE_DIR = os.path.join(self.server.baseDir, self.SAVE_DIR)
                                               
        altsaveSetting = kw.get('ALTSAVE_DIR', 'content')
        if altsaveSetting:
            self.ALTSAVE_DIR = os.path.join(self.server.baseDir, altsaveSetting)
        else:
            self.ALTSAVE_DIR = ''
        self.THEME_DIR = kw.get('THEME_DIR', 'themes/default')
            
        if not kw.has_key('PATH'): 
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
        self.log.debug('path is %s' % self.server.PATH)
        
        if self.MAX_MODEL_LITERAL > -1:
            if self.ALTSAVE_DIR:
                assert [prefix for prefix in self.server.PATH
                 if self.ALTSAVE_DIR.startswith(os.path.abspath(prefix)) ],\
                    'ALT_SAVE_DIR must be on the PATH'
                
            #SAVE_DIR should be a sub-dir of one of the PATH
            #directories so that 'path:' URLs to files there include
            #the subfolder to make them distinctive.
            #(Because you don't want to be able override them)
            saveDirPrefix = [prefix for prefix in self.server.PATH
                if self.SAVE_DIR.startswith(os.path.abspath(prefix)) ]
            assert saveDirPrefix and self.SAVE_DIR[len(saveDirPrefix[0]):],\
                  'SAVE_DIR must be a distinct sub-directory of a directory on the PATH'
                
        self.interWikiMapURL = kw.get('interWikiMapURL', 'site:///intermap.txt')
        initConstants( ['useIndex'], 1)
        initConstants( ['RHIZOME_APP_ID'], '')
        initConstants( ['akismetKey','akismetUrl'], '')
        
        self.passwordHashProperty = kw.get('passwordHashProperty',
                                          self.BASE_MODEL_URI+'password-hash')
        self.secureHashSeed = kw.get('SECURE_HASH_SEED', self.defaultSecureHashSeed)
        if self.secureHashSeed == self.defaultSecureHashSeed:
            self.log.warning("SECURE_HASH_SEED using default seed"
                             " -- set your own private value.")
        self.secureHashMap = kw.get('secureHashMap',        
            { self.passwordHashProperty :  self.secureHashSeed })
        #make this available as an XPath variable
        self.resourceAuthorizationAction.assign("__passwordHashProperty",
                        "'"+self.passwordHashProperty+"'")

        if not kw.get('ADMIN_PASSWORD_HASH') and not kw.get('ADMIN_PASSWORD'):
            self.log.warning("neither ADMIN_PASSWORD nor ADMIN_PASSWORD_HASH "
                             "was set; using default admin password.")
        elif kw.get('ADMIN_PASSWORD') == self.defaultPassword:
            self.log.warning("ADMIN_PASSWORD set is to the default admin password.")

        self.authorizedExtFunctions = kw.get('authorizedExtFunctions', {})

        #this is just like findResourceAction except we don't assign the 'not found' resource
        #used by hasPage
        self.checkForResourceAction = copy.deepcopy(self.findResourceAction)        
        self.checkForResourceAction.queries.pop()
                
        self.indexDir = kw.get('INDEX_DIR',
                            os.path.join(self.server.baseDir, 'contentindex'))
        self.indexableFormats = kw.get('indexableFormats', self.defaultIndexableFormats)

        xmlContentProcessor = self.server.contentProcessors[
                                'http://rx4rdf.sf.net/ns/wiki#item-format-xml']
        xmlContentProcessor.blacklistedElements = kw.get('blacklistedElements',
                              utils.BlackListHTMLSanitizer.blacklistedElements)
        for name in [ 'blacklistedContent', 'blacklistedAttributes']:
            setting = kw.get(name)
            if setting is not None:
                value = dict([(re.compile(x), re.compile(y))
                               for x, y in setting.items()])
                setattr(xmlContentProcessor, name, value)

        #apply settings to the zmlContentProcessor
        zmlContentProcessor = self.server.contentProcessors[
                        'http://rx4rdf.sf.net/ns/wiki#item-format-zml']
        raccoon.assignVars(zmlContentProcessor, kw, ['undefinedPageIndicator',
                        'externalLinkIndicator', 'interWikiLinkIndicator'], 1)
        raccoon.assignVars(zmlContentProcessor, kw, ['ZMLDefaultVersion'],
                                                       zml.defaultZMLVersion)
                                                     
        self.shredders = dict([ (x.uri, x) for x in kw.get('shredders', [])])

        self.uninitialized = False
                                 
    ######XPath extension functions#####        
    def getZML(self, context, resultset = None):        
        if resultset is None:
            resultset = context.node
        contents = raccoon.StringValue(resultset)
        return zml.zmlString2xml(contents,self.mmf )

    def getSecureHash(self, context, plaintext, secureProperty=None):
        if not secureProperty:
            secureProperty = self.passwordHashProperty
        import sha
        return sha.sha(plaintext + self.secureHashMap[secureProperty] ).hexdigest()    

    def _getContents(self, node, kw=None):
        kw = kw or {}
        kw.setdefault('action', 'view-source')
        #run last 3 actions: findContentAction, processContentAction, templateAction:
        return self.server.doActions(self.handleRequestSequence[-3:], kw, node)
                
    def getContents(self, context, node=None):
        '''
        Given a node, find the contents associated with it.
        '''
        if node is None:
            node = context.node
        elif not node:
            return ''#empty nodeset
        return self._getContents(node, {})
        
    def truncateContents(self, context, node=None, maxwords=0, maxlines=0):
        '''
        Get the contents of the given revision resource,
        truncating it when maxwords is reached. Returns either a
        string of the contents or a number if the contents can't be
        represented in HTML (e.g. if it binary or if it contains HTML
        that can be embedded).
        '''
        #if maxwords is None: #todo
        #    maxwords = self.maxSummaryWords
        if node is None:
            node = context.node
        elif not node:
            return ''#empty nodeset
        
        kw = {'action':'view',
              'maxwords':maxwords,
              'maxlines':maxlines,
              '_disposition': 'http://rx4rdf.sf.net/ns/wiki#item-disposition-complete'
              }
        try:
            text = self._getContents(node, kw)            
        except raccoon.DoNotHandleException:
            return 1
        if kw['__lastFormat'] == 'http://rx4rdf.sf.net/ns/wiki#item-format-text':            
            text, wordCount, lineCount, noMore = utils.truncateText(
                text, maxwords, maxlines or -1)
        elif kw['__lastFormat'] == 'http://rx4rdf.sf.net/ns/wiki#item-format-binary':
            return 1 
        return text

    def makeRequest(self, context, name, *args):        
        #we have this instead of a more general run-actions function
        #because only the http-request trigger is secure
        kw = self.server._xpathArgs2kw(args)
        result, kw = self.server.requestDispatcher.invokeEx__(name, kw)        
        if hasattr(result, 'read'): #if result is a stream
            result = result.read()
        if not isinstance(result, unicode):
            item = unicode(str(result), 'utf8')
        return result

    def nameFromURL(self, context, resultset):
        '''
        return true if the page has been defined
        '''
        url = raccoon.StringValue(resultset)

        #if the URL has already been converted from a site: url to an http: url
        #convert it back to an internal name
        if url.startswith( self.server.appBase):
            url = url[len(self.server.appBase):]
        elif url[:5] == 'site:':
            url = url[5:]
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
        
        schemePos = url.find('://')
        if schemePos > -1:
            return u'' #it's an absolute URL, skip it
        else:
            return url                

    def hasPage(self, context, resultset):
        '''
        return true if the page has been defined
        '''
        url = raccoon.StringValue(resultset)
        
        kw = { '_name' : url }
        self.server.doActions([self.checkForResourceAction], kw)
        if (kw['__resource'] and kw['__resource'] != [self.server.domStore.dom]
           or kw.get('externalfile')):            
            return raccoon.XTrue
        else:
            return raccoon.XFalse
        
    def getNameURI(self, context, wikiname):
        #note filter: URI fragment might not match wikiname
        #python 2.2 bug: filter() on a unicode returns a list not unicode
        #todo I8N (return a IRI?)
        return self.BASE_MODEL_URI + \
               filter(lambda c: c.isalnum() or c in '_-./', str(wikiname))
            
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
                        self.log.warning("aborting creation of patch: %s unexpectedly exists" % filepath)
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
                self.log.warning("while saving content: %s unexpectedly exists, trying %s" % (filepath, newfilepath) )
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

            ff = TxnFileFactory(filepath)
            self.server.txnSvc.join(ff)
            f = ff.create('b')
            #f = file(filepath, 'wb')
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

                    ff = TxnFileFactory(altfilepath)
                    self.server.txnSvc.join(ff)
                    f = ff.create('b')
                    #f = file(altfilepath, 'wb')
                    f.write(contents)
                    f.close()
                elif conflict:
                    self.log.warning("conflict trying to save revision to ALTSAVE_DIR: "
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
                encodedURI = RxPath.generateBnode()
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

    def isSpam(self, context, user_ip, user_agent, contents):        
        if not (self.akismetKey or self.akismetUrl):
            return raccoon.XFalse #no check

        from rx import akismet, __version__
        try:
            akismet.USERAGENT = "Rhizome/" + str(__version__)
            
            real_key = akismet.verify_key(self.akismetKey,self.akismetUrl)
            if real_key:
                user_ip, user_agent, contents = (raccoon.StringValue(user_ip),
                    raccoon.StringValue(user_agent), raccoon.StringValue(contents))
                
                is_spam = akismet.comment_check(self.akismetKey,self.akismetUrl,                    
                  user_ip, user_agent, comment_content=contents)
                if is_spam:
                    return raccoon.XTrue
                else:
                    return raccoon.XFalse
            else:
                self.log.warning('akismet.verify_key failed')
                return raccoon.XFalse
        except akismet.AkismetError, e:            
            self.log.warning('error invoking akismet API: %s %s' % (e.response, e.statuscode))
            return raccoon.XFalse

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
                self.log.info('creating lupy index in %s' % self.indexDir)
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
                            self.log.debug('adding resource %s to index', resource)
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
            return [self.server.domStore.dom.findSubject(x)
                      for x in self.findInIndex(query)
                         if self.server.domStore.dom.findSubject(x)]
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
        from rx.RxPathUtils import Res
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
        #this function is a confusing hack -- only should be used by rhizome-config.py
        if keywords:
            #only add 'built-in' when other keywords are specified
            if 'built-in' not in keywords:
                keywords = keywords + ['built-in']
        else:
            keywords = ()

        if kw['format'] == 'zml' and 'zmlVersion' not in kw:
            kw['zmlVersion'] = '0.7' #todo upgrade built-in content to latest zml
        return (name, self.addItem(name, keywords=keywords,
                                   accessTokens=accessTokens, **kw))

    def addItem(self, name, loc=None, contents=None, disposition = 'complete', 
                format='binary', doctype='', handlesDoctype='', handlesDisposition='',
                title=None, label='http://rx4rdf.sf.net/ns/wiki#label-released',
                handlesAction=None, actionType='http://rx4rdf.sf.net/ns/archive#NamedContent',
                baseURI=None, owner='http://rx4rdf.sf.net/site/accounts/admin',
                accessTokens=None, authorizationGroup='', keywords=None,
                contentLength = None, digest = None, createdOn = "1057919732.750",
                extraProps=None, zmlVersion=None):
        '''
        Convenience function for adding an item the model. Returns a string of triples.
        '''
        def kw2uri(kw, default):
            if kw.find(':') == -1: #if not a URI
                return default + kw
            else:
                return kw

        from rx.RxPathUtils import Res
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
        if zmlVersion:
            contentbNode['wiki:zml-version'] = zmlVersion

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

        if extraProps:
            for (p, v) in extraProps:
                nameUriRef[p] = Res(v)
                
        if accessTokens:
            nameUriRef['auth:guarded-by'] = [Res(x) for x in accessTokens]
            
        if authorizationGroup:
            nameUriRef['auth:uses-template'] = Res(authorizationGroup)
            
        if owner:
            if owner == 'http://rx4rdf.sf.net/site/accounts/admin':
                #fix up to be the admin user for this specific site
                owner = self.BASE_MODEL_URI + 'accounts/admin'
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
        
        itembNode['a:created-on'] = createdOn
        
        if disposition:
            itembNode['wiki:item-disposition'] = Res(kw2uri(disposition, 'wiki:item-disposition-'))

        if keywords:
            nameUriRef['wiki:about'] = [Res(kw2uri(x,'wiki:')) for x in keywords]
            
        if rootFolder:
            return rootFolder.toTriplesDeep()
        else:
            return nameUriRef.toTriplesDeep()        