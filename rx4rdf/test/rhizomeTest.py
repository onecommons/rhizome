"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

from rx import raccoon, utils, logging, rhizome
import unittest, os, os.path, shutil, glob, time, pprint, repr as Repr

RHIZOMEDIR = '../../rhizome'

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
        1. create a new user account
        1. view it
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

    def testLocalLinks(self):
        #the main point of this test is to test virtual hosts
        
        #test-links.py contains links to internal pages
        #if any of those link to pages that are missing this test will fail
        #because hasPage() will fail
        #also, because these uses the default template with the sidebar
        #we also test link generation with content generated through internal link resolution
        
        argsForConfig = ['--rhizomedir', os.path.abspath(RHIZOMEDIR)]
        root = raccoon.HTTPRequestProcessor(a='test-links.py',
                                argsForConfig=argsForConfig)

        self.doHTTPRequest(root, {}, 'http://www.foo.com/page1')
        self.doHTTPRequest(root, {}, 'http://www.foo.com/page1/')
        self.doHTTPRequest(root, {}, 'http://www.foo.com/folder/page2')

        self.doHTTPRequest(root, {}, 'http://www.foo.com/')
        self.doHTTPRequest(root, {}, 'http://www.foo.com')

        self.doHTTPRequest(root, {}, 'http://www.foo.com:8000')
        
    def _testRootConfigLocalLinks(self, config):
        #the main point of this test is to test virtual hosts
        
        argsForConfig = ['--rhizomedir', os.path.abspath(RHIZOMEDIR)]
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
        self._testRootConfigLocalLinks('test-xml-root-config.py')
    
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
        self.failUnless(cacheSizes[-1][:-1] == (6, 3, 107, 57))#, 13523L)) #14695

        cacheSizes = self._testCaches(True)
        #make sure the cache isn't erroneously growing
        self.failUnless(cacheSizes[-1] == cacheSizes[-2])
        #yes, this is quite a fragile test:
        self.failUnless(cacheSizes[-1][:-1] == (5, 1, 97, 57))#, 13523L))
        
SAVE_WORK=False
DEBUG = False

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

    try:
        test=sys.argv[sys.argv.index("-r")+1]
    except (IndexError, ValueError):
        unittest.main()
    else:
        tc = RhizomeTestCase(test)
        tc.setUp()
        getattr(tc, test)() #run test
