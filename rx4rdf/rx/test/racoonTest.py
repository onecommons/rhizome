"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

from rx import racoon, utils
import unittest


class RacoonTestCase(unittest.TestCase):
    def testAuth(self):
        root = racoon.Root(['-a', 'testAuthAction.py'])
        unauthorized = root.rdfDom.findSubject( 'http://rx4rdf.sf.net/ns/auth#Unauthorized' )
        #the guest user has no rights
        user = root.rdfDom.findSubject( root.BASE_MODEL_URI+'users/guest' )
        start = root.rdfDom.findSubject( root.BASE_MODEL_URI+'test-resource1' )        
        assert user
        result = root.runActions('test', utils.kw2dict(__user=[user], start=[start]))
        print result, unauthorized 
        self.failUnless( unauthorized == result)
        #the super user always get in
        user = root.rdfDom.findSubject( root.BASE_MODEL_URI+'users/admin' )
        assert user
        result = root.runActions('test', utils.kw2dict(__user=[user], start=[start]))
        print result, unauthorized 
        self.failUnless( start == result)
        
    def testXPathSecurity(self):
        '''
        test that we can't access insecure 4Suite extension functions
        after importing racoon
        '''
        from rx import RxPath
        from Ft.Xml import XPath
        node = None
        context = XPath.Context.Context(node, processorNss = racoon.DefaultNsMap)
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
        tc = RacoonTestCase(test)
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()
