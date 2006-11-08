"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

from rx import raccoon, utils, logging
import unittest, glob, os, os.path

class RaccoonTestCase(unittest.TestCase):
    def setUp(self):
        logging.BASIC_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"
        logging.root.setLevel(logging.INFO)
        logging.basicConfig()

    def testFileCache(self):        
        raccoon.fileCache.capacity = 20000
        #raccoon.fileCache.maxFileSize = 2000
        #raccoon.fileCache.hashValue = lambda path: getFileCacheKey(path, fileCache.maxFileSize)
        fileList = [path for path in glob.glob('*') if os.path.isfile(path)]
        #make sure we'll exceed the cache
        assert sum( [os.stat(x).st_size for x in fileList] ) > raccoon.fileCache.capacity
        #add them to the cache
        for path in fileList:
            raccoon.fileCache.getValue(path)
        #retrieve them from the cache
        for path in fileList:        
            raccoon.fileCache.getValue(path)        
        
    def testAuth(self):
        root = raccoon.RequestProcessor(a='testAuthAction.py', model_uri = 'test:')
        unauthorized = root.domStore.dom.findSubject( 'http://rx4rdf.sf.net/ns/auth#Unauthorized' )
        #the guest user has no rights
        user = root.domStore.dom.findSubject( root.BASE_MODEL_URI+'users/guest' )
        start = root.domStore.dom.findSubject( root.BASE_MODEL_URI+'test-resource1' )        
        assert user
        result = root.runActions('test', utils.kw2dict(__user=[user], start=[start]))
        #print result, unauthorized 
        self.failUnless( unauthorized == result)
        #the super user always get in
        user = root.domStore.dom.findSubject( root.BASE_MODEL_URI+'users/admin' )
        assert user
        result = root.runActions('test', utils.kw2dict(__user=[user], start=[start]))
        #print result, start 
        self.failUnless( start == result)

    def testMinimalApp(self):
        root = raccoon.RequestProcessor(a='testMinimalApp.py',model_uri = 'test:')
        result = root.runActions('http-request', utils.kw2dict(_name='foo'))
        #print type(result), result
        response = "<html><body>page content.</body></html>"
        self.failUnless(response == result)
        
        result = raccoon.InputSource.DefaultFactory.fromUri(
            'site:///foo', resolver=root.resolver).read()    
        #print type(result), repr(result), result
        self.failUnless(response == result)
        
        result = root.runActions('http-request', utils.kw2dict(_name='jj'))
        #print type(result), result
        self.failUnless( '<html><body>not found!</body></html>' == result)

    def testErrorHandling(self):
        root = raccoon.RequestProcessor(a='testErrorHandling-config.py',model_uri = 'test:')
        result = root.runActions('test-error-request', utils.kw2dict(_name='foo'))
        
        response = "404 not found"
        self.failUnless(response == result)

    def testIncrementalLoad(self):
        appVars = { 'useIndex':0,
                    'STORAGE_TEMPLATE':
r'''#!graph context:add:context:txn:test:;1;;context:extracted:bnode:xeec53da980d74a0289dacd125017fbc8x2
_:xeec53da980d74a0289dacd125017fbc8x4 <http://rx4rdf.sf.net/ns/wiki#question> "<p>1What does ZML stand for? blah\n</p>" .
#!remove context:add:context:txn:test:;1;;context:extracted:bnode:xeec53da980d74a0289dacd125017fbc8x2
#!graph context:add:context:txn:test:;1;;context:extracted:bnode:xeec53da980d74a0289dacd125017fbc8x2
_:xeec53da980d74a0289dacd125017fbc8x4 <http://rx4rdf.sf.net/ns/wiki#question> "<p>1What does ZML stand for? blah\n</p>" .
#!graph context:add:context:txn:test:;2;;context:extracted:bnode:xeec53da980d74a0289dacd125017fbc8x8
<test:testctxtentail#1> <http://rx4rdf.sf.net/ns/wiki#question> "<p>1What does ZML stand for? blah\n</p>" .
#!remove context:add:context:txn:test:;2;;context:extracted:bnode:xeec53da980d74a0289dacd125017fbc8x8
#!graph context:add:context:txn:test:;2;;context:extracted:bnode:xeec53da980d74a0289dacd125017fbc8x8
<test:testctxtentail#1> <http://rx4rdf.sf.net/ns/wiki#question> "<p>1What does ZML stand for? blah\n</p>" .
#!graph context:add:context:txn:test:;3;;context:extracted:bnode:xeec53da980d74a0289dacd125017fbc8x14
<test:testctxtentail#1> <http://rx4rdf.sf.net/ns/wiki#question> "<p>2What does ZML stand for? blah2\n</p>" .'''
                }
        root = raccoon.HTTPRequestProcessor(a='testAuthAction.py', model_uri = 'test:', appVars = appVars )
        self.failUnless( len(root.evalXPath('/*[.="test:testctxtentail#1"]/*/node()')) == 1)
        
    def testContentProcessing(self):
        root = raccoon.RequestProcessor(a='testContentProcessor.py',
                                        model_uri='test:')

        result = root.runActions('http-request', utils.kw2dict(_name='authorized'))
        self.failUnless( result == 'authorized code executed\n')

        self.failUnlessRaises(raccoon.NotAuthorized,lambda: root.runActions(
                'http-request', utils.kw2dict(_name='unauthorized')) )

        self.failUnlessRaises(raccoon.NotAuthorized,lambda: root.runActions(
                'http-request', utils.kw2dict(_name='dynamic unauthorized')) )
        
    def testStreaming(self):
        '''
        test an action pipeline whose retVal is a file-like object
        '''
        from StringIO import StringIO
        testString = "a stream of text"
        
        root = raccoon.RequestProcessor(a='testMinimalApp.py',model_uri='test:')        
        root.actions={ 'test' : [
            raccoon.Action(action=lambda *args: StringIO(testString)),
            #assume the content is text
            raccoon.Action(["'http://rx4rdf.sf.net/ns/wiki#item-format-text'"],
                   root.processContents, canReceiveStreams=True),
            ]}
        result = root.runActions('test', {})
        self.failUnless( result.read() == testString )
        
    def testXPathSecurity(self):
        '''
        test that we can't access insecure 4Suite extension functions
        after importing raccoon
        '''
        from rx import RxPath
        from Ft.Xml import XPath
        node = None
        context = XPath.Context.Context(node, processorNss = raccoon.DefaultNsMap)
        from Ft.Xml.XPath import BuiltInExtFunctions
        #print BuiltInExtFunctions.ExtFunctions[(XPath.FT_EXT_NAMESPACE, 'env-var')]
        try:
            RxPath.evalXPath('xf:env-var("foo")', context)
        except (XPath.RuntimeException), e:
            pass
        else:
            self.fail("should have thrown exception")
            
    def testXPathExtFuncs(self):
        root = raccoon.RequestProcessor(a='testAuthAction.py',model_uri='test:')

        self.failUnless( root.evalXPath("""/* = wf:map(/*, ".")""") )
        self.failUnless( root.evalXPath("""count(/*) = count(wf:map(/*, "."))""") )

    def testResolvers(self):
        from Ft.Xml import InputSource
        from Ft.Lib import UriException
        root = raccoon.RequestProcessor(a='testMinimalApp.py',model_uri='test:')
        InputSource.DefaultFactory.resolver = root.resolver
        
        test = lambda: InputSource.DefaultFactory.fromUri('http://www.google.com')        
        self.failUnlessRaises(UriException, test)

        appVars = dict(DEFAULT_URI_SCHEMES=['http'],
                       uriResolveBlacklist=[r'.*yahoo\.com.*'])
        root = raccoon.RequestProcessor(a='testMinimalApp.py',model_uri='test:',
            appVars=appVars)
        InputSource.DefaultFactory.resolver = root.resolver
        
        test = lambda: InputSource.DefaultFactory.fromUri('http://www.yahoo.com/')        
        self.failUnlessRaises(UriException, test)

        self.failUnless(InputSource.DefaultFactory.fromUri('http://www.google.com'))

    def testCaching(self):
        root = raccoon.RequestProcessor(a='testMinimalApp.py',model_uri='test:')
        from rx import RxPath
        from Ft.Xml import XPath
        node = root.domStore.dom
        kw = { 'url': 'foo:', '__server__': root}
        vars, extFunMap = root.mapToXPathVars(kw)        
        context = XPath.Context.Context(node, varBindings=vars,
                                        extFunctionMap = extFunMap,
                                        processorNss = raccoon.DefaultNsMap) 
        xpath = "wf:get-metadata('url')"        
        compExpr = RxPath._compileXPath(xpath, context)
        key = raccoon.getKeyFromXPathExp(compExpr, context, root.NOT_CACHEABLE_FUNCTIONS)        
        self.failUnless(key == ('wf:get-metadata("url")', (None, u'url'),
                                'foo:', node.getKey()) )

        styleSheetContents = '''
        <x:stylesheet version="1.0" xmlns:x="http://www.w3.org/1999/XSL/Transform"
                 xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'>
        <x:template match='/'>
        <x:variable name='url' select='wf:get-metadata("url")' />
        </x:template></x:stylesheet>
        '''
        
        styleSheetKey = raccoon.getXsltCacheKeyPredicate(
                        root.styleSheetCache,
                        root.NOT_CACHEABLE_FUNCTIONS,
                        styleSheetContents,
                        '<root />', kw, node,
                        styleSheetUri='test:')

        self.failUnless(styleSheetKey == (styleSheetContents,
                'test:', '<root />', node.getKey(),((None, u'url'),False), ((None, u'url'),'foo:')) )
        

if __name__ == '__main__':
    import sys    
    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))
    try:
        test=sys.argv[sys.argv.index("-r")+1]
    except (IndexError, ValueError):
        unittest.main()
    else:
        tc = RaccoonTestCase(test)
        tc.setUp()
        getattr(tc, test)() #run test
