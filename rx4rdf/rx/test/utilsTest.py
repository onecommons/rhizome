"""
    utils unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import unittest
from rx.utils import *

class utilsTestCase(unittest.TestCase):
    def testSingleton(self):
        class single: __metaclass__=Singleton
        s1 = single()
        s2 = single()
        self.failUnless(s1 is s2)
        
    def testVisitExpr(self):
        expr='/*/foo:bar[. = 1 + baz] | "dsfdf"'
        parseExpr = XPath.Compile(expr)
        def test(node): print node        
        parseExpr.visit(test)
        
    def testIterExpr(self):        
        expr='/*/foo:bar[. = 1 + baz] | "dsfdf"'
        parseExpr = XPath.Compile(expr)        
        for term in parseExpr:
            print term
            
    def testDynException(self):
        _defexception = DynaExceptionFactory(__name__)
        _defexception('test dyn error') #defines exception NotFoundError
        try:
            raise TestDynError()
        except (TestDynError), e:
            self.failUnless(e.msg == "test dyn error")
            
        try:
            raise TestDynError("another msg")
        except (TestDynError), e:
            self.failUnless(e.msg == "another msg")
            
if __name__ == '__main__':
    import sys
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = utilsTestCase(test)
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()

