"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

from rx import raccoon, utils, logging
import unittest

class RaccoonTestCase(unittest.TestCase):
    def setUp(self):
        logging.BASIC_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"
        logging.root.setLevel(logging.INFO)
        logging.basicConfig()

    def testAuth(self):
        root = raccoon.RequestProcessor(a='testAuthAction.py')
        unauthorized = root.rdfDom.findSubject( 'http://rx4rdf.sf.net/ns/auth#Unauthorized' )
        #the guest user has no rights
        user = root.rdfDom.findSubject( root.BASE_MODEL_URI+'users/guest' )
        start = root.rdfDom.findSubject( root.BASE_MODEL_URI+'test-resource1' )        
        assert user
        result = root.runActions('test', utils.kw2dict(__user=[user], start=[start]))
        #print result, unauthorized 
        self.failUnless( unauthorized == result)
        #the super user always get in
        user = root.rdfDom.findSubject( root.BASE_MODEL_URI+'users/admin' )
        assert user
        result = root.runActions('test', utils.kw2dict(__user=[user], start=[start]))
        #print result, start 
        self.failUnless( start == result)

    def testMinimalApp(self):
        root = raccoon.RequestProcessor(a='testMinimalApp.py')
        result = root.runActions('http-request', utils.kw2dict(_name='foo'))
        #print type(result), result
        response = "<html><body>page content.</body></html>"
        self.failUnless(response == result)
        
        result = raccoon.InputSource.DefaultFactory.fromUri('site:///foo').read()    
        #print type(result), repr(result), result
        self.failUnless(response == result)
        
        result = root.runActions('http-request', utils.kw2dict(_name='jj'))
        #print type(result), result
        self.failUnless( '<html><body>not found!</body></html>' == result)
                
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

if __name__ == '__main__':
    import sys    
    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = RaccoonTestCase(test)
        tc.setUp()
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()
