"""
    utils unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import unittest
from rx import utils
from rx.utils import *

class TestLinkFixer(utils.LinkFixer):
    def __init__(self, out):
        utils.LinkFixer.__init__(self, out)
                    
    def needsFixup(self, tag, name, value):
        return value and value.startswith('foo')

    def doFixup(self, tag, name, value, hint):
        return 'bar'
    
class utilsTestCase(unittest.TestCase):
    def testSingleton(self):
        class single: __metaclass__=Singleton
        s1 = single()
        s2 = single()
        self.failUnless(s1 is s2)
        
    def testVisitExpr(self):
        expr='/*/foo:bar[. = 1 + baz] | "dsfdf"'
        parseExpr = XPath.Compile(expr)
        def test(node): pass#print node        
        parseExpr.visit(test)
        
    def testIterExpr(self):        
        expr='/*/foo:bar[. = 1 + baz] | "dsfdf"'
        parseExpr = XPath.Compile(expr)        
        for term in parseExpr:
            pass#print term

    def testNtriples(self):
        #test character escaping 
        s1 = r'''bug: File "g:\_dev\rx4rdf\rx\Server.py", '''
        n1 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents> "bug: File \"g:\\_dev\\rx4rdf\\rx\\Server.py\", ".'''
        [(subject, predicate, object, objectType)] = [x for x in parseTriples([n1])]
        self.failUnless(s1 == object)
        #test xml:lang support
        n2 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents> "english"@en-US.'''
        [(subject, predicate, object, objectType)] = [x for x in parseTriples([n2])]
        self.failUnless(object=="english" and objectType == 'en-US')
        #test datatype support
        n3 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents>'''\
        ''' "1"^^http://www.w3.org/2001/XMLSchema#int.'''
        [(subject, predicate, object, objectType)] = [x for x in parseTriples([n3])]
        self.failUnless(object=="1" and objectType == 'http://www.w3.org/2001/XMLSchema#int')
    
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

    def runLinkFixer(self, fixerFactory, contents, result):
        import StringIO
        out = StringIO.StringIO()
        fixlinks = fixerFactory(out)
        fixlinks.feed(contents)
        fixlinks.close()
        self.failUnless(result == out.getvalue())

    def testLinkFixer(self):
        contents='''<?xml version=1.0 standalone=true ?>
        <!doctype asdf>
        <test link='foo' t='1'>        
        <!-- comment -->
        <![CDATA[some < & > unescaped! ]]>
        some content&#233;more content&amp;dsf<a href='foo'/>
        </test>'''
        result = '''<?xml version=1.0 standalone=true ?>
        <!doctype asdf>
        <test link='bar' t='1'>        
        <!-- comment -->
        <![CDATA[some < & > unescaped! ]]>
        some content&#233;more content&amp;dsf<a href='bar'/>
        </test>'''
        self.runLinkFixer(TestLinkFixer, contents, result)

    def testBlackListHTMLSanitizer(self):        
        contents = '''<html>
        <head>
        <style>
        #test {
            border: 1px solid #000000;
            padding: 10px;
            background-image: url('javascript:alert("foo");')
        }
        </style>
        </head>
        <body id='test'>
        <span onmouseover="dobadthings()">
        <a href="javascript:alert('foo')">alert</a>
        </span>
        </body>
        </html>'''
        result = '''<html>
        <head>
        <style></style>
        </head>
        <body id='test'>
        <span onmouseover="">
        <a href="">alert</a>
        </span>
        </body>
        </html>'''
        self.runLinkFixer(BlackListHTMLSanitizer, contents, result)        

    def testDiffPatch(self):
        orig = "A B C D E"
        new = "A C E D"
        self.failUnless(new == patch(orig, diff(orig, new, 0, ' '), ' ') )

        orig = "A B B B E"
        new = "A C C C"
        self.failUnless(new == patch(orig, diff(orig, new, 0, ' '), ' ') )

        orig = ""
        new = "A C C C"
        self.failUnless(new == patch(orig, diff(orig, new, 0, ' '), ' ') )

        orig = "A B B B E"
        new = ""
        self.failUnless(new == patch(orig, diff(orig, new, 0, ' '), ' ') )

        orig = ""
        new = ""
        self.failUnless(new == patch(orig, diff(orig, new, 0, ' '), ' ') )

        orig = "A B B B E"
        new = "A B B B E"
        self.failUnless(new == patch(orig, diff(orig, new, 0, ' '), ' ') )

    def _testSortedDiff(self, old, new):
        #print old, 'to', new
        changes = diffSortedList(old, new)
        #print changes
        patch = opcodes2Patch(old, new, changes)        
        #print patch
        patchList(old, patch)
        #print old
        self.failUnless(new == old)        

    def testSortedDiff(self):
        old = [1, 2, 6]
        new = [0, 2, 4, 9]
        self._testSortedDiff(old,new)

        old = []
        new = [0, 2, 4, 9]
        self._testSortedDiff(old,new)
        
        old = [1, 2, 6]
        new = []
        self._testSortedDiff(old,new)
        
        old = [1, 2, 6]
        new = [0, 2]
        self._testSortedDiff(old,new)
        
        old = [1, 2]
        new = [0, 2, 3]
        self._testSortedDiff(old,new)
        
        old = []
        new = []
        self._testSortedDiff(old,new)

        old = [0, 2, 3]
        new = [0, 2, 3]
        self._testSortedDiff(old,new)
        
if __name__ == '__main__':
    import sys
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = utilsTestCase(test)
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()

