"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

from rx import raccoon, utils, logging, rhizome
import unittest, os, os.path, shutil, glob, time, pprint, sys, repr as Repr

RHIZOMEDIR = '../rhizome'

import gc
class TrackRefs:
    """Object to track reference counts across test runs."""

    def __init__(self):
        self.type2count = {}
        self.type2all = {}
        self.type2ids = {}        

    def update(self, dumpObjects=False):
        obs = sys.getobjects(0)
        type2count = {}
        type2all = {}
        type2o = {}
        for o in obs:
            all = sys.getrefcount(o)
            t = type(o)
            if t in type2count:
                type2count[t] += 1
                type2all[t] += all
                type2o[t].append(o)
            else:
                type2count[t] = 1
                type2all[t] = all
                type2o[t] = [o]

        ct = [(type2count[t] - self.type2count.get(t, 0),
               type2all[t] - self.type2all.get(t, 0),
               t)
              for t in type2count.iterkeys()]
        ct.sort()
        ct.reverse()
        for delta1, delta2, t in ct:
            if delta1 or delta2:
                print "%-55s %8d %8d" % (t, delta1, delta2)
                if not dumpObjects: continue
                oldids = self.type2ids.get(t,[])
                for o in type2o[t]:
                    if id(o) not in oldids:
                        print 'leak?', o

        self.type2count = type2count
        self.type2all = type2all
        self.type2ids = dict([(k, [id(o) for o in olist])
                              for k,olist in type2o.iteritems()])
        

class RhizomeTestCase(unittest.TestCase):
    '''
    Run test "scripts".
    
    Our pathetic little scripting environment works like this:
    
    The Raccoon's -r option records requests sent to it and then pickles
    the list when you use Ctrl-C to shutdown.
    
    The -d [picklefile] option plays back those requests.
    
    Our test-config.py adds a page named "assert" that lets us write Python assertions
    that will get executed when played back.
    '''
    
    def setUp(self):
        logging.BASIC_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"        
        logLevel = DEBUG and logging.DEBUG or logging.INFO
        logging.root.setLevel(logLevel)
        logging.basicConfig()        
        raccoon.DEFAULT_LOGLEVEL = logLevel

    def testNoSpamFixer(self):
        contents='''<?xml version=1.0 standalone=true ?>
        <!doctype asdf>
        <test link='foo' t='1'>
        <a href='http://viagra.com'>spam</a>
        <!-- comment -->
        <![CDATA[some < & > unescaped! ]]>
        some content&#233;more content&amp;dsf<a href='http://viagra.com/next' rel='next' />
        </test>'''
        result = '''<?xml version=1.0 standalone=true ?>
        <!doctype asdf>
        <test link='foo' t='1'>
        <a href='http://viagra.com' rel="nofollow" >spam</a>
        <!-- comment -->
        <![CDATA[some < & > unescaped! ]]>
        some content&#233;more content&amp;dsf<a href='http://viagra.com/next' rel="nofollow" />
        </test>'''
        import utilsTest
        runLinkFixer = utilsTest.utilsTestCase.runLinkFixer.im_func        
        runLinkFixer(self, rhizome.SanitizeHTML, contents, result)

    def executeScript(self, config, histories):
        histories = [os.path.abspath(x) for x in histories]
        config, rhizomedir = [os.path.abspath(x) for x in (config, RHIZOMEDIR)]        
        currpath = os.path.abspath( os.getcwd() )
        tempdir = os.tempnam(None,'rhizometest')
        os.mkdir(tempdir)
        os.chdir(tempdir)
        try:
            for playback in histories:
                print 'playing back', playback
                raccoon.main(['-x','-d', playback, '-a', config,
                #these args are used in the test-configs:
                '--testplayback', '--rhizomedir', rhizomedir,'--includedir', currpath])
        finally:
            os.chdir(currpath)
            if SAVE_WORK:
                print 'work saved at', tempdir
            else:
                shutil.rmtree(tempdir)
    
    def testMinorEdit(self):
        '''
        The script:
        1. logs in as admin
        1. add a page called testminoredit,
        1. modifies it several times with and without the minor edit flag
        1. then asserts that the correct number revisions and checks the expected first
        character of the final revision
        '''
        for configpath in glob.glob('test-config*.py'):
            print 'testing ', configpath
            self.executeScript(configpath, glob.glob('minoredit.*.pkl'))

    def testSmokeTest(self):
        '''
        So far this script only does this:
        1. edit the zmlsandbox
        1. view it
        1. create new html page called "sanitize" using illegal html (e.g. javascript)
        1. view it
        1. create a new user account (foo/foo)
        1. view it
        1. edit it, change password to 'bar'
        '''
        for configpath in glob.glob('test-config*.py'):
            print 'testing ', configpath
            self.executeScript(configpath, glob.glob('smoketest.*.pkl'))

    def testNonAscii(self):
        '''
        This script:
        1. Creates a text page with non-ascii name, title and contents
        1. Previews it
        1. Views it
        1. Re-edits it
        1. Creates a page with binary content (via file upload)
        1. Views it
        '''
        for configpath in glob.glob('test-config*.py'):
            print 'testing ', configpath
            self.executeScript(configpath, glob.glob('nonascii.*.pkl'))

    def doHTTPRequest(self, requestProcessor, kw, url, method='GET'):
        '''
        turns a dictionary into one that looks like an HTTP request 
        and then call handleHTTPRequest    
        '''
        #we need to add this to make this look like a http request
                
        #copied from rhizome.doExport():
        class _dummyRequest:
           def __init__(self):
              self.headerMap = {}
              self.simpleCookie = {}

        request  = _dummyRequest()
        request.method = method
        parts = url.split('/',3)        
        #request needs request.host, request.base, request.browserURL
        request.headerMap['host'] = parts[2]
        request.base = '/'.join(parts[:3])
        request.browserUrl = url
        path = parts[3:] 
        request.path = path and path[0] or '' #path is a list
        if request.path[-1:] == '/':
            request.path = request.path[:-1]
        
                      
        response = _dummyRequest()

        request.paramMap = kw
        request.paramMap['_request']=request
        request.paramMap['_response']=response
        request.paramMap['_session']= {}
           
        import urllib        
        name = urllib.unquote(request.path)
        
        newkw = request.paramMap.copy()
        requestProcessor.log.info(method + ' ' + url)
        return requestProcessor.handleHTTPRequest(name, newkw) 

    def testContentAuthorization(self):
        from rx.transactions import OutsideTransaction
        
        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                                            appVars = { 'useIndex':0} )

        guestAccount = root.evalXPath("/*[foaf:accountName = 'guest']")
        guestKw = { '__account' : guestAccount } 
        vars, extFunMap = root.mapToXPathVars(guestKw)
        guestKw['__accountTokens'] = root.evalXPath(root.rhizome.accountTokens, vars, extFunMap)
        vars, extFunMap = root.mapToXPathVars(guestKw)
            
        xpath=('''wf:process-contents('print 1', 'http://rx4rdf.sf.net/ns/wiki#item-format-python')''')        
        self.failUnlessRaises(raccoon.NotAuthorized, lambda: root.evalXPath(xpath, vars, extFunMap))

        #now don't require a blanket authorization for xupdate 
        xpath=('''wf:process-contents('<foo/>', 'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate')''')                
        self.failUnlessRaises(OutsideTransaction, lambda: root.evalXPath(xpath, vars, extFunMap))  

        adminAccount = root.evalXPath("/*[foaf:accountName = 'admin']")
        adminKw = { '__account' : adminAccount } 
        vars, extFunMap = root.mapToXPathVars(adminKw)
        adminKw['__accountTokens'] = root.evalXPath(root.rhizome.accountTokens, vars, extFunMap)
        vars, extFunMap = root.mapToXPathVars(adminKw)
        
        #even though we're the super-user here this won't succeed because there's no authorization digest
        xpath=('''wf:process-contents('print 1', 'http://rx4rdf.sf.net/ns/wiki#item-format-python')''')                        
        self.failUnlessRaises(raccoon.NotAuthorized, lambda: root.evalXPath(xpath, vars, extFunMap))

        #this XUpdate should be authorized and tries to process the content
        #(but throws an OutsideTransaction exception since we're not inside a request)
        xpath=('''wf:process-contents('<foo/>', 'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate')''')
        self.failUnlessRaises(OutsideTransaction, lambda: root.evalXPath(xpath, vars, extFunMap))                        

    def _fineGrainedCheck(self, root, account, contents, expectNotAuthorized,
                resourcesExp=None, kw=None, exceptionType=raccoon.NotAuthorized,
                xpath=None, xpathValidate=None, more=0, save=False):
        kw = kw or {}
        kw['contents'] = contents
        kw['__account'] = account        
        vars, extFunMap = root.mapToXPathVars(kw)
        kw['__accountTokens'] = root.evalXPath(root.rhizome.accountTokens, vars, extFunMap)

        root.txnSvc.begin()
        root.txnSvc.state.kw = kw

        if xpath is None:
            if resourcesExp:
                #replacing resource -- merge statements with matching bnodes
                xpath='''wf:save-rdf($contents, 'rxml_zml', '', %s)''' % resourcesExp
            else:
                #all new -- matching bnodes labels will be renamed
                xpath='''wf:save-rdf($contents, 'rxml_zml')'''
                
        try:            
            vars, extFunMap = root.mapToXPathVars(kw, doAuth=True)
            root.evalXPath(xpath, vars, extFunMap)
            if save:
                root.txnSvc.commit()
            else:
                root.txnSvc._prepareToVote() #we don't want to actually commit
            if xpathValidate:
                if more:
                    for xp in more:
                        print xp
                        print root.evalXPath(xp, vars, extFunMap)
                self.failUnless( root.evalXPath(xpathValidate, vars, extFunMap) )
        except exceptionType:            
            if not expectNotAuthorized:                
                self.fail('raised %s: %s' % (exceptionType, sys.exc_info()[1])) 
        except:
            raise #unexpected
        else:
            if expectNotAuthorized:
                self.fail('unexpectedly succeeded')
        
        if not save and root.txnSvc.isActive(): #else already aborted
            root.txnSvc.abort()    #we don't want to actually commit this  
        
    def testFineGrainedAuthorization(self):
        def beforeConfigLoad(kw):
            addTestUser = '''                     
        {test:testUser}:
          rdf:type: foaf:OnlineAccount
          foaf:accountName: `test
          auth:has-role: auth:role-default
          auth:can-assign-guard: base:testUserToken
          auth:has-rights-to: base:testUserToken

        base:testUserToken
          rdf:type: auth:AccessToken   
          auth:priority: `1            

        base:anotherToken
          rdf:type: auth:AccessToken   
          auth:priority: `1            
        '''
            kw['__addRxML__'](addTestUser)
        
        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                            model_uri = 'test:', appVars = { 'useIndex':0,
                                        'beforeConfigHook': beforeConfigLoad })

        guestAccount = root.evalXPath("/*[foaf:accountName = 'guest']")
        self.failUnless(guestAccount)
        adminAccount = root.evalXPath("/*[foaf:accountName = 'admin']")
        self.failUnless(adminAccount)
        testAccount = root.evalXPath("/*[foaf:accountName = 'test']")
        self.failUnless(testAccount)

        #test add -- the guest shouldn't have permission to add a role
        contents = '''
        prefixes:        
            auth: `http://rx4rdf.sf.net/ns/auth#
            base: `test:
        
        {base:a-new-resource}:
          auth:has-role: auth:role-superuser
        '''                
        self._fineGrainedCheck(root, guestAccount, contents, True)
        #admin can do anything
        self._fineGrainedCheck(root, adminAccount, contents, False)
        
        #test remove
        #this rxml removes the auth:guarded-by statement and so will raise NotAuthorized
        contents = '''
        prefixes:
            wiki: `http://rx4rdf.sf.net/ns/wiki#
            base: `test:

        base:TextFormattingRules:
            wiki:about: 
                wiki:help
        '''
        self._fineGrainedCheck(root, guestAccount, contents, True,
                               "/*[wiki:name='TextFormattingRules']")

        #should be able to add this innocuous statement about a new resource
        contents = '''
        prefixes:
            wiki: `http://rx4rdf.sf.net/ns/wiki#
            base: `test:

        base:newresource:
            wiki:about: 
                wiki:help
        '''
        self._fineGrainedCheck(root, guestAccount, contents, False)

        #all wiki:DocTypes are protected by a class access token
        #so we can't make any statements about them
        contents = '''
        prefixes:
            wiki: `http://rx4rdf.sf.net/ns/wiki#
            base: `test:

        base:newresource:
            rdf:type: wiki:DocType
            wiki:about: 
                wiki:help
        '''
        self._fineGrainedCheck(root, guestAccount, contents, True)
        self._fineGrainedCheck(root, adminAccount, contents, False)

        #same test, but test remove (removes all but the rdfs:label statement,
        #including the class type
        contents = '''
        prefixes:
            wiki: `http://rx4rdf.sf.net/ns/wiki#
            base: `test:

        {http://rx4rdf.sf.net/ns/wiki#doctype-faq}:
           rdfs:label: `FAQ
        '''
        replaceResourceExp = "/*[.='http://rx4rdf.sf.net/ns/wiki#doctype-faq']"
        self._fineGrainedCheck(root, guestAccount, contents, True,replaceResourceExp)
        self._fineGrainedCheck(root, adminAccount, contents, False,replaceResourceExp)

        #test transitive authorization base:diffrevisions is protected by base:save-only-token
        saveOnlyProtectedcontents = '''
        prefixes:        
            auth: `http://rx4rdf.sf.net/ns/auth#
            base: `test:
        
        {bnode:diffrevisions1Content}:
          base:my-prop: "test"
        '''
        self._fineGrainedCheck(root, guestAccount, saveOnlyProtectedcontents, True, "''")
        
        #test recheckAuthorization:
        #bnode:diffrevisions1Item already exists
        #but because a:contents is a subproperty of auth:requires-authorization-for
        #this adding that will trigger a recheckAuthorization which will transitively 
        #test all statements including the unauthorized statement
        #"bnode:diffrevisions1Content: a:transformed-by: wiki:item-format-python"
        contents = '''
        prefixes:
            wiki: `http://rx4rdf.sf.net/ns/wiki#
            a:    `http://rx4rdf.sf.net/ns/archive#
            base: `test:

        base:newresource:
            rdf:type: a:NamedContent
            a:contents: {bnode:diffrevisions1Item}
        '''
        self._fineGrainedCheck(root, guestAccount, contents, True, "''")
        self._fineGrainedCheck(root, adminAccount, contents, False, "''")

        #test auth:with-value-greater-than -- this will invoke base:limit-priority-guard
        contents = '''
        prefixes:
            auth: `http://rx4rdf.sf.net/ns/auth#
            base: `test:

        base:newresource:
            rdf:type: auth:AccessToken
            auth:priority: %s
        '''
        self._fineGrainedCheck(root, guestAccount, contents % '1', False)
        self._fineGrainedCheck(root, guestAccount, contents % '100', True)
    
        #test extraPrivileges 
        #saveRes auth:grants-rights-to save-only-override-token
        saveRes = root.evalXPath("/*[wiki:name = 'save']")
        assert saveRes
        kw = { '__handlerResource' : saveRes }        
        self._fineGrainedCheck(root, guestAccount, saveOnlyProtectedcontents, False, "''", kw)

        #test auth:with-value-account-has-via-this-property
        contents = '''
        prefixes:
            auth: `http://rx4rdf.sf.net/ns/auth#
            base: `test:

        base:ZMLSandbox:
            auth:guarded-by: %s
        '''
        #should fail because of base:guard-guard:
        self._fineGrainedCheck(root, testAccount, contents % 'base:anotherToken', True)
        #should succeed because of base:change-accesstoken-guard:
        self._fineGrainedCheck(root, testAccount, contents % 'base:testUserToken', False)
        
    def testXPathFuncAuthorization(self):
        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                            model_uri = 'test:', appVars = { 'useIndex':0,} )

        kw = {}        
        kw['__account'] = root.evalXPath("/*[foaf:accountName = 'guest']")       
        vars, extFunMap = root.mapToXPathVars(kw)
        kw['__accountTokens'] = root.evalXPath(root.rhizome.accountTokens, vars, extFunMap)

        vars, extFunMap = root.mapToXPathVars(kw, doAuth=True)        

        #calling this function requires base:execute-function-token
        xpath = "wf:generate-patch('adfadsf')"
        self.failUnlessRaises(raccoon.NotAuthorized, lambda: root.evalXPath(xpath, vars, extFunMap))        

        #try to trick request() into giving us administrator rights
        xpath = '''wf:request('Sandbox', 'action', 'delete', '__account', /*[foaf:accountName = 'admin'],
                    '_noErrorHandling', 1)'''
        self.failUnlessRaises(raccoon.XPathUserError, lambda: root.evalXPath(xpath, vars, extFunMap))

    def testValidation(self):
        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                            model_uri = 'test:', appVars = { 'useIndex':0, })

        guestAccount = root.evalXPath("/*[foaf:accountName = 'guest']")
        self.failUnless(guestAccount)

        import Ft.Xml.Xslt
        #trigger validation error -- wiki:name must be unique for a:NamedContent, and 'index' is already used
        contents = '''
        prefixes:
            wiki: `http://rx4rdf.sf.net/ns/wiki#
            a: `http://rx4rdf.sf.net/ns/archive#
            base: `test:

        base:newresource:
            a: a:NamedContent
            wiki:name: 'index'
        '''
        self._fineGrainedCheck(root, guestAccount, contents, True,exceptionType=
                               Ft.Xml.Xslt.XsltRuntimeException)

        #trigger validation error -- wiki:name must be unique (except a:NamedContent can shadow it)
        contents = '''
        prefixes:
            wiki: `http://rx4rdf.sf.net/ns/wiki#
            a: `http://rx4rdf.sf.net/ns/archive#
            base: `test:

        base:newresource2:
            wiki:name: 'non-unique'

        base:newresource3:
            wiki:name: 'non-unique'
        '''
        self._fineGrainedCheck(root, guestAccount, contents, True,exceptionType=
                               Ft.Xml.Xslt.XsltRuntimeException)
        
    def testLocalLinks(self):
        #the main point of this test is to test virtual hosts
        
        #test-links.py contains links to internal pages
        #if any of those link to pages that are missing this test will fail
        #because hasPage() will fail
        #also, because these uses the default template with the sidebar
        #we also test link generation with content generated through internal link resolution

        appVars = {}#'domStoreFactory': createRedlandDomStore}         
        argsForConfig = ['--rhizomedir', os.path.abspath(RHIZOMEDIR)]
        root = raccoon.HTTPRequestProcessor(a='test-links.py',
                            argsForConfig=argsForConfig, appVars=appVars)

        self.doHTTPRequest(root, {}, 'http://www.foo.com/page1')
        self.doHTTPRequest(root, {}, 'http://www.foo.com/page1/')
        self.doHTTPRequest(root, {}, 'http://www.foo.com/folder/page2')

        self.doHTTPRequest(root, {}, 'http://www.foo.com/')
        self.doHTTPRequest(root, {}, 'http://www.foo.com')

        self.doHTTPRequest(root, {}, 'http://www.foo.com:8000')
        
    def _testRootConfigLocalLinks(self, config, configArgs=None):
        #the main point of this test is to test virtual hosts
        
        argsForConfig = ['--rhizomedir', os.path.abspath(RHIZOMEDIR)
                         ] + (configArgs or [])
        root = raccoon.HTTPRequestProcessor(a=config,
                                argsForConfig=argsForConfig)

        def not_found(kw):
            if raiseWhenNotFound:            
                raise kw['_name'] + ' not found'
            else:
                return 'notfound'
        root.default_not_found = not_found

        raiseWhenNotFound = True
        #self.doHTTPRequest(root, {}, 'http://www.anydomain.com/page1')
        
        self.doHTTPRequest(root, {}, 'http://www.foo.com/page1')
        self.doHTTPRequest(root, {}, 'http://www.foo.com/folder/page2')

        self.doHTTPRequest(root, {}, 'http://foo.org/page1')
        self.doHTTPRequest(root, {}, 'http://foo.org:8000/folder/page2')

        self.doHTTPRequest(root, {}, 'http://foo.bar.org/page1')
        self.doHTTPRequest(root, {}, 'http://foo.bar.org/folder/page2')
        self.doHTTPRequest(root, {}, 'http://foo.bar.org/folder/page2/')

        self.doHTTPRequest(root, {}, 'http://foo.bar.org/')
        self.doHTTPRequest(root, {}, 'http://foo.bar.org')

        self.doHTTPRequest(root, {}, 'http://www.bar.org/bar/page1')
        self.doHTTPRequest(root, {}, 'http://www.bar.org/bar/folder/page2')
        self.doHTTPRequest(root, {}, 'http://www.bar.org/bar/folder/page2/')

        self.doHTTPRequest(root, {}, 'http://www.bar.org/bar/')
        self.doHTTPRequest(root, {}, 'http://www.bar.org/bar')

        raiseWhenNotFound = False
        #result = self.doHTTPRequest(root, {}, 'http://www.foo.com/foo/page1')
        #self.failUnless(result == 'notfound')
        
        #result = self.doHTTPRequest(root, {}, 'http://www.foo.com/foo/folder/page2')
        #self.failUnless(result == 'notfound')
        
        result = self.doHTTPRequest(root, {}, 'http://www.bar.org/page1')
        self.failUnless(result == 'notfound')
        
        #result = self.doHTTPRequest(root, {}, 'http://www.bar.org/folder/page2')
        #self.failUnless(result == 'notfound') 

        result = self.doHTTPRequest(root, {}, 'http://www.anyolddomain.org/page1')
        self.failUnless(result == 'notfound')

    def testLocalLinksRootConfig(self):
        self._testRootConfigLocalLinks('test-root-config.py')

    def testLocalLinksXMLRootConfig(self):
        self._testRootConfigLocalLinks('test-root-config.py', 
            ['-s', 'test-server.xml'])
    
    def _testCaches(self, live):
        argsForConfig = ['--rhizomedir', os.path.abspath(RHIZOMEDIR)]
        root = raccoon.HTTPRequestProcessor(a='test-links.py',
            argsForConfig=argsForConfig, appVars= {'LIVE_ENVIRONMENT': live})

        #root.styleSheetCache.debug = 1
        repr1 = Repr.Repr() 
        repr1.maxtuple = 100
        #import sets
        #comparesets = []
        cacheSizes = []
        for i in range(4):
            start = time.time()
            self.doHTTPRequest(root, {}, 'http://www.foo.com/page1')
            #print time.time() - start
            cacheSizes.append( (root.actionCache.nodeSize, root.styleSheetCache.nodeSize,
             root.queryCache.nodeSize, root.expCache.nodeSize, raccoon.fileCache.nodeSize) )
            #comparesets.append( sets.Set(root.queryCache.nodeDict.keys() ) )
        return cacheSizes 
        #pprint.pprint(list(comparesets[2] - comparesets[1]))
                
    def testCaches(self):        
        cacheSizes = self._testCaches(False)
        #make sure the cache isn't erroneously growing
        self.failUnless(cacheSizes[-1] == cacheSizes[-2])

        #yes, this is quite a fragile test:
        #print cacheSizes[-1]
        self.failUnless(cacheSizes[-1][:-1] == (7, 5, 138, 59))#, 17090L)) 

        cacheSizes = self._testCaches(True)
        #make sure the cache isn't erroneously growing
        self.failUnless(cacheSizes[-1] == cacheSizes[-2])

        #yes, this is quite a fragile test:
        #print cacheSizes[-1]
        self.failUnless(cacheSizes[-1][:-1] == (6, 3, 127, 59))#, 16724L))

    def testShredding(self):
        appVars = { 'useIndex':0,
                    'DEFAULT_URI_SCHEMES':['http','data','file'],
                }
        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                            model_uri = 'test:', appVars = appVars )
        guestAccount = root.evalXPath("/*[foaf:accountName = 'guest']")
        self.failUnless(guestAccount)
        
        xpath = '''wf:shred(/*[wiki:name='ZMLSandbox'],
         'http://rx4rdf.sf.net/ns/wiki#item-format-xml',
            "<testshredder ><a href='foo'/><a href='ZMLSandbox'/></testshredder >")'''

        xpathValidate = '''/*[wiki:name='ZMLSandbox']/wiki:testprop = 'test success!'
        and /*[wiki:name='ZMLSandbox']/wiki:links-to = 'site:///foo'
        and count(/wiki:MissingPage) = 1 and /wiki:MissingPage/wiki:name = 'foo' '''
        m = []#["/*[wiki:name='ZMLSandbox']/wiki:testprop",
            #"f:resolve-url('site:///zmlsandbox', 'foo')",
            # "/*[wiki:name='ZMLSandbox']/wiki:links-to",
            # '/wiki:MissingPage/wiki:name/text()']
        #xml-shred.xsl has a test pattern for matching <testshredder>
        self._fineGrainedCheck(root, guestAccount, '', False, xpath=xpath,
                               xpathValidate=xpathValidate, more=m)

        xpath = '''wf:shred(/*[wiki:name='ZMLSandbox'],
         'http://rx4rdf.sf.net/ns/wiki#item-format-xml', "<faq />")'''

        xpathValidate = '''(/*[wiki:name='ZMLSandbox']/wiki:revisions/*/rdf:first)[last()]/*/wiki:doctype
           = uri('wiki:doctype-faq') and count((/*[wiki:name='ZMLSandbox']/wiki:revisions/*/rdf:first)[last()]/*/wiki:doctype) = 1'''
        #xml-shred.xsl should deduce the proper doctype
        m = []#["(/*[wiki:name='ZMLSandbox']/wiki:revisions/*/rdf:first)[last()]/*/wiki:doctype",
              #  "count((/*[wiki:name='ZMLSandbox']/wiki:revisions/*/rdf:first)[last()]/*/wiki:doctype)"]
        self._fineGrainedCheck(root, guestAccount, '', False, xpath=xpath,
                               xpathValidate=xpathValidate, more=m)
        
        xpath = '''wf:shred(/*[wiki:name='ZMLSandbox'],
         'http://rx4rdf.sf.net/ns/wiki#item-format-xml', $contents)'''
        contents = file('testgrddl.html').read()

        #work around bug in http://www.w3.org/2000/06/dc-extract/dc-extract.xsl: invalid predicate
        xpathValidate = "/*[wiki:name='ZMLSandbox']/*[uri(.)='http://purl.org/dctitle'] = 'Joe Lambda Home page as example of RDF in XHTML'"  
        self._fineGrainedCheck(root, guestAccount, contents, False, xpath=xpath,
                               xpathValidate=xpathValidate)

    def testShreddingContexts(self):
        from rx import RxPath
        appVars = { 'useIndex':0,
                    'modelFactory' : RxPath.TransactionMemModel,
                }
        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                            model_uri = 'test:', appVars = appVars )

        guestAccount = root.evalXPath("/*[foaf:accountName = 'guest']")
        self.failUnless(guestAccount)

        scope = 'context:1'
        #a triple set view of a global quad set
        #you can also manipulate and view a context quad set
        #conceptually:
        #if quad added to context copy to global quadset
        #if quad removed from context remove from global quadset
        #can remove a triple from global, but doesn't remove from context
        #can add a triple to global, doesn't effect context
                
        #1. add prop to context
        #check that its both in the context and the global context
        #2. now remove the prop from the global context
        #check that its still in the context
        #3. now re-add the same statements to the context
        #check its still not in the global context
        #4. now remove it from the context
        #check that's it been removed from the context        
        #5. now re-add it to the context
        #check that's now also in the global context
        #6. now add it to the global context also
        #7. remove it from the context
        #check that its still in the global context

        def _shred(contents, context):
            contentsHeader = '''#?zml0.7 markup
        rx:
          prefixes:
            wiki: `http://rx4rdf.sf.net/ns/wiki#
            a: `http://rx4rdf.sf.net/ns/archive#
            base: `test:
        '''                        
            xupdate = r'''<?xml version="1.0" ?> 
        <xupdate:modifications version="1.0" xmlns:xupdate="http://www.xmldb.org/xupdate"
            xmlns="http://rx4rdf.sf.net/ns/archive#" xmlns:wiki='http://rx4rdf.sf.net/ns/wiki#'            		    
            xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
            xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>    
            <xupdate:remove %s select="get-context('context:1')/*/*" />
            <!-- re-add one of the statements -->
            <xupdate:append select='/' %s>
            <xupdate:variable name='shredded'
            select="wf:shred(/*[wiki:name='ZMLSandbox'],
             'http://rx4rdf.sf.net/ns/wiki#item-format-zml', $contents)"/>
            </xupdate:append>
        </xupdate:modifications>
        ''' % (context, context)
            kw = {}
            kw['contents'] = contentsHeader+contents
            kw['__account'] = guestAccount        
            vars, extFunMap = root.mapToXPathVars(kw)
            kw['__accountTokens'] = root.evalXPath(root.rhizome.accountTokens, vars, extFunMap)

            root.txnSvc.begin()
            root.txnSvc.state.kw = kw
            root.txnSvc.join(root.domStore)
            #print len(root.domStore.dom.childNodes)
            root.xupdateRDFDom(root.domStore.dom, xupdate, kw)
            #print 'a', [n.stmt for n in root.txnSvc.state.additions]
            #print 'r', root.txnSvc.state.removals
            #print len(root.domStore.dom.childNodes), root.domStore.dom.findSubject('test:test1')
            root.txnSvc.commit()
            #print len(root.domStore.dom.childNodes), root.domStore.dom.findSubject('test:test1')

        contents1 = '''
          base:test1:
            base:prop1: `1
            base:prop1: `2        
        '''
        _shred(contents1, "to-graph='context:1'")

        globalProp1Exp = "/*[.='test:test1']/base:prop1"        
        self.failUnless( len(root.evalXPath(globalProp1Exp))==2 )

        contextProp1Exp = "get-context('context:1')/*[.='test:test1']/base:prop1"        
        self.failUnless( len(root.evalXPath(contextProp1Exp))==2 )

        contents2 = '''
          base:test1:
            base:prop1: `1
        '''
        #2. now remove one of the props from the global context
        _shred(contents2, '')             
        #only one predicate in global scope
        self.failUnless( len(root.evalXPath(globalProp1Exp))==1 )
        #context still has two predicates though        
        self.failUnless( len(root.evalXPath(contextProp1Exp))==2 ) 

        #3. now re-add the original statements to the context
        _shred(contents1, "to-graph='context:1'")
        #this should not have changed anything
        #check its still not in the global context
        self.failUnless( len(root.evalXPath(globalProp1Exp))==1 )
        #and that the context still has just the predicates
        self.failUnless( len(root.evalXPath(contextProp1Exp))==2 ) 

        #4. now remove it from the context
        #check that's it been removed from the context
        _shred(contents2, "to-graph='context:1'")             
        #only one predicate in global scope
        self.failUnless( len(root.evalXPath(globalProp1Exp))==1 )
        #context now only has one predicates though        
        self.failUnless( len(root.evalXPath(contextProp1Exp))==1 ) 

        #5. now re-add it to the context        
        _shred(contents1, "to-graph='context:1'")
        #check that's now also in the global context
        self.failUnless( len(root.evalXPath(globalProp1Exp))==2 )
        #context now has two predicates again        
        self.failUnless( len(root.evalXPath(contextProp1Exp))==2 ) 

        #6. now add it to the global context also
        _shred(contents1, '')
        self.failUnless( len(root.evalXPath(globalProp1Exp))==2 )
        #7. remove it from the context
        _shred(contents2, "to-graph='context:1'")
        self.failUnless( len(root.evalXPath(contextProp1Exp))==1 ) 
        #check that its still in the global context
        self.failUnless( len(root.evalXPath(globalProp1Exp))==2 )
        
    def testGRDDLImport(self):
        storepath = os.tempnam(None,'wikistore')
        try:
            appVars = { 'useIndex':0,
                        'DEFAULT_URI_SCHEMES':['http','data','file'],}
            #import testgrddl.html
            root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                                model_uri = 'test:', appVars = appVars,
                    m=storepath, argsForConfig = ['--import', 'testgrddl.html'])
            res = root.evalXPath('/*[wiki:name="testgrddl"]')
            self.failUnless(res)        
            #'get-context(./preceeding::a:from-source/*/a:entails)/*/*'
            extracted = root.evalXPath(
                'get-context(/*[a:from-source = $__context]/a:entails)/*/*',
                node=res[0])
            self.failUnless(extracted)
            testProp = root.evalXPath("/*/*[uri(.)='http://purl.org/dctitle']")
            self.failUnless(testProp)

            adminAccount = root.evalXPath("/*[foaf:accountName = 'admin']")
            self.failUnless(adminAccount)
            xpath = "wf:request('testgrddl', '_noErrorHandling', 1,'action', 'delete')"
            #this extracted property should have been deleted:
            xpathValidate = "not(/*/*[uri(.)='http://purl.org/dctitle'])"
            self._fineGrainedCheck(root, adminAccount, '', False, xpath=xpath,
                                   xpathValidate=xpathValidate)
        finally:            
            if SAVE_WORK:
                print 'saved testGRDDLImport model at ', storepath
            else:
                try:
                    os.unlink(storepath)
                except OSError:
                    pass
                    

        #export testgrddl.html
        #verify 

    def testOptimisticLocking(self):
        from rx import RxPath
        appVars = { 'useIndex':0,
                    #set the next two so we don't save anything to disk
                    'modelFactory' : RxPath.TransactionMemModel,
                    'MAX_MODEL_LITERAL':-1,
                }
        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                            model_uri = 'test:', appVars = appVars)

        #this doesn't work, xhtml is being escaped, but current-transaction isn't set
        #invoke edit-metadata, grep for currentcontext
        #xpath = '''wf:request('index','_noErrorHandling', 1, 'action', 'edit-metadata')'''
        #res = root.evalXPath(xpath)
        #self.failUnless(isinstance(res, unicode) )
        #res = res.encode('utf8')
        #from Ft.Xml import Domlette
        #xmldoc = Domlette.NonvalidatingReader.parseString(res)
        #contexturi = RxPath.XPath.Evaluate("//input[@name='_editContext']/@value", xmldoc)
        #self.failUnless(contexturi)

        guestAccount = root.evalXPath("/*[foaf:accountName = 'guest']")
        self.failUnless(guestAccount)

        #set _editContext to the initial txn context uri
        kw = dict(_editContext="context:txn:test:;1")

        #now modify the store (add a new resource)
        contents = '''
          {test:newResource}:
            {test:prop1}: `1
        '''
        self._fineGrainedCheck(root, guestAccount, contents, False,kw=kw, save=True)

        #modify a resource using the edit context (this should work)
        resourceuri = 'test:ZMLSandbox'
        contents = '''
          {%s}:
            {test:prop1}: `1
        ''' % resourceuri

        self._fineGrainedCheck(root, guestAccount, contents, False,
                               kw=kw, save=True)

        #modify the same resource again using the edit context
        #(this should raise a resource already modified error)
        contents = '''
          {%s}:
            {test:prop2}: `1
        ''' % resourceuri

        self._fineGrainedCheck(root, guestAccount, contents, True,kw=kw, save=True,
                               exceptionType=raccoon.XPathUserError)

        #delete the same resource again using the edit context
        #(this should raise a resource already modified error)
        self._fineGrainedCheck(root, guestAccount, "", True,kw=kw, save=True,
                            resourcesExp="/*[wiki:name='ZMLSandbox']",
                            exceptionType=raccoon.XPathUserError)
        
    def _testMemUse(self):

        def getObjectsByType(oo):
            typeMap = {}
            for o in oo:
                tid = id(type(o))
                ignore, count = typeMap.get(tid, (None, 0))
                typeMap[tid] = (type(o), count + 1)
            return typeMap

        def findMismatchedTypes(newtm, oldtm):
            #cmp typemaps
            for tid, (to, count) in newtm.iteritems():
                if tid not in oldtm or count > oldtm[tid]:
                    print to, count, count - oldtm.get(tid,0)
                    yield to

        appVars = { 'useIndex':0,
                'XPATH_CACHE_SIZE': 3,
                'ACTION_CACHE_SIZE': 3,
                'XPATH_PARSER_CACHE_SIZE':3,
                'STYLESHEET_CACHE_SIZE':2,
                'FILE_CACHE_SIZE': 0 }

        appVars = { 'useIndex':0,
                'XPATH_CACHE_SIZE': 0,
                'ACTION_CACHE_SIZE': 0,
                'XPATH_PARSER_CACHE_SIZE':0,
                'STYLESHEET_CACHE_SIZE':0,
                'FILE_CACHE_SIZE': 0 }

        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                            model_uri = 'test:', appVars = appVars )
        pages = root.evalXPath('/a:NamedContent/wiki:name')
        def getCacheSizes(root):
            return [(len(cache.nodeDict), cache._countNodes()) for cache in 
                [root.expCache, root.styleSheetCache, root.actionCache, 
                root.queryCache, raccoon.fileCache] ]        
        import gc, types, traceback, sys
        gc.collect()        
        #from sets import Set
        #set = Set
        #ids = set([id(o) for o in gc.get_objects()])
        tm1 = getObjectsByType(gc.get_objects())        

        for i in range(20):            
            for page in pages[:10]:
                pagename = raccoon.StringValue(page)                
                #print 'pass', i, len(ids)#gc.collect(), len(gc.get_objects())#getCacheSizes(root)
                print 'pass', i, gc.collect(), len(gc.get_objects())
                try:
                    url = 'http://www.foo.com/'+pagename #ZML' #missing_page' 
                    #kw = dict(search='..', searchType='RxPath')
                     #,_disposition='http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-print')
                    kw = {}#'_noErrorHandling':1}
                    #kw = dict(_originalContext=[], _previousContext=[],
                    #    _prevkw=dict(_template=[], __resource=[]) )
                    try:
                        self.doHTTPRequest(root, kw, url)                        
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        traceback.print_exc()
                        print 'error raised'
                    sys.exc_clear( ) 
                    print 'collected', gc.collect()
                    oo = gc.get_objects()
                    print 'object count', len(oo)                    
                    tm2 = getObjectsByType(oo)
                    typelist = list(findMismatchedTypes(tm2,tm1))
                    for o in oo:
                        break
                        if isinstance(o, types.TracebackType):
                            traceback.print_tb(o, 1) 
                            print [type(r) for r in gc.get_referrers(o)]
                            #pprint.pprint( [repr(r) for r in gc.get_referrers(o)] )
                            #break
                    #print [repr(o) for o in oo
                    #        if id(type(o)) in tids]
                    tm1 = tm2
                    del oo
                    #newids = set([id(o) for o in gc.get_objects()])
                    #leaked = newids - ids
                    #print 'leaked', len(ids), len(newids), len(leaked) #, leaked
                    #ids = newids
                except:
                    raise
                    pass

    def _testMemUse(self):
        import gc
        appVars = { 'useIndex':0,
                'XPATH_CACHE_SIZE': 0,
                'ACTION_CACHE_SIZE': 0,
                'XPATH_PARSER_CACHE_SIZE':0,
                'STYLESHEET_CACHE_SIZE':0,
                'FILE_CACHE_SIZE': 0 }

        root = raccoon.HTTPRequestProcessor(a=RHIZOMEDIR+'/rhizome-config.py',
                            model_uri = 'test:', appVars = appVars )
        print len( root.evalXPath('/a:NamedContent/wiki:name') ), 'pages'        
        gc.collect()        
        REFCOUNT = 1 
        if REFCOUNT:
            rc = sys.gettotalrefcount()
            track = TrackRefs()
        i = 0
        while True:
            i += 1
            #runner(files, test_filter, debug)
            try:
                url = 'http://www.foo.com/basestyles.css' #missing_page' 
                #kw = dict(search='..', searchType='RxPath')
                 #,_disposition='http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-print')
                kw = {}#'_noErrorHandling':1}
                #kw = dict(_originalContext=[], _previousContext=[],
                #    _prevkw=dict(_template=[], __resource=[]) )
                try:
                    self.doHTTPRequest(root, kw, url)                        
                except (KeyboardInterrupt, SystemExit):
                    raise
                except:
                    traceback.print_exc()
                    print 'error raised'
                del kw
                sys.exc_clear( ) 
            except:
                raise
                pass

            gc.collect()
            if gc.garbage:
                print "GARBAGE:", len(gc.garbage), gc.garbage
                return
            if REFCOUNT:
                prev = rc
                rc = sys.gettotalrefcount()
                print "totalrefcount=%-8d change=%-6d" % (rc, rc - prev)
                track.update(i > 1)
        
def createRedlandDomStore():
  from rx import RxPath,DomStore
  return DomStore.RxPathDomStore(RxPath.initRedlandHashBdbModel)

def createMemStore():
  from rx import RxPath,DomStore
  def initModel(location, defaultModel):
    if os.path.exists(location):
        source = location
    else:
        source = defaultModel
    return RxPath.MemModel(source)
  return DomStore.RxPathDomStore(initModel, RxPath.BaseSchema)
    
SAVE_WORK=False
DEBUG = False

def profilerRun(testname, testfunc):
    import hotshot, hotshot.stats
    prof = hotshot.Profile(testname+".prof")
    prof.runcall(testfunc)
    prof.close()

    stats = hotshot.stats.load(testname+".prof")
    stats.strip_dirs()
    stats.sort_stats('cumulative','time')
    stats.print_stats(100)            

if __name__ == '__main__':
    import sys    
    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))
    if sys.argv.count("--save"):
        SAVE_WORK=True
        del sys.argv[sys.argv.index('--save')]
    DEBUG = sys.argv.count('--debug')
    if DEBUG:
        del sys.argv[sys.argv.index('--debug')]
    profile = sys.argv.count('--prof')
    if profile:
        del sys.argv[sys.argv.index('--prof')]

    try:
        test=sys.argv[sys.argv.index("-r")+1]
    except (IndexError, ValueError):
        if profile:
            name, ext = os.path.splitext(
                os.path.split(sys.modules[__name__ ].__file__)[1])
            profilerRun(name, unittest.main)
        else:
            unittest.main()
    else:
        tc = RhizomeTestCase(test)
        tc.setUp()
        testfunc = getattr(tc, test)
        if profile:
            profilerRun(test, testfunc)
        else:
            testfunc() #run test
