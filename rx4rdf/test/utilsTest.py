"""
    utils unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import unittest
from rx import utils
from rx.utils import *

class TestLinkFixer(utils.HTMLFilter):
    def __init__(self, out):
        utils.HTMLFilter.__init__(self, out)
                    
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
        def test(node, fields): pass
        parseExpr.visit(test)
        class TestVisit(XPathExprVisitor):
            def descend(self, node, fields, *args):
                #print 'ov', node, fields
                return XPathExprVisitor.descend(self, node, fields, *args)

            def ParsedLiteralExpr(self, node):
                parentNode, field = self.ancestors[-1]
                if isinstance(parentNode, XPath.ParsedExpr.ParsedUnionExpr):
                    assert field == '_right'
                    self.ancestors[-1] = parentNode._left

            def ParsedNLiteralExpr(self, node):
                parentNode, field = self.ancestors[-1]
                if self.foundFuncCall:
                    self.ancestors[-1] = parentNode._args[1]

            foundFuncCall = 0
            def FunctionCall(self, node):
                self.foundFuncCall = 1
                return self.DESCEND
                                    
        parseExpr.visit(TestVisit().visit)
        #parseExpr.pprint()
        self.failUnless(parseExpr._left == parseExpr._right)

        parseExpr = XPath.Compile('foo(1, /bar)')
        parseExpr.visit(TestVisit().visit)
        parseExpr.pprint()

    def testIterExpr(self):        
        expr='/*/foo:bar[. = 1 + baz] | "dsfdf"'
        parseExpr = XPath.Compile(expr)        
        for term in parseExpr:
            pass#print term
    
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

    def testThreadlocalAttribute(self):
        class HasThreadLocals(object_with_threadlocals):
            def __init__(self, bar):
                #set values that will initialize across every thread
                self.initThreadLocals(tl1 = 1, tl2 = bar)

        test = HasThreadLocals('a')        
        test.tl1 = 2        
        test2 = HasThreadLocals('b')
        
        self.failUnless(test.tl2 == 'a')    
        self.failUnless(test2.tl2 == 'b')        
                
        def threadMain():
            #make sure the initial value are what we expect
            self.failUnless(test.tl1 == 1)
            self.failUnless(test.tl2 == 'a')
            #change them
            test.tl1 = 3
            test.tl2 = 'b'
            #make they're what we just set
            self.failUnless(test.tl1 == 3)
            self.failUnless(test.tl2 == 'b')

        #make sure the initial values are what we expect
        self.failUnless(test.tl1 == 2)
        self.failUnless(test.tl2 == 'a')
        
        thread1 = threading.Thread(target=threadMain)
        thread1.start()
        thread1.join()

        #make sure there the values haven't been changed by the other thread
        self.failUnless(test.tl1 == 2)
        self.failUnless(test.tl2 == 'a')

    def runLinkFixer(self, fixerFactory, contents, result):
        import StringIO
        out = StringIO.StringIO()
        fixlinks = fixerFactory(out)
        fixlinks.feed(contents)
        fixlinks.close()
        #print out.getvalue()
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
        #self.runLinkFixer(BlackListHTMLSanitizer, contents, result)
        #test malformed entity references
        #see http://weblogs.mozillazine.org/gerv/archives/007538.html
        #todo: still broken inside PCDATA
        #contents = '''<style>background-image: url(&#106ava&#115cript&#58aler&#116&#40&#39Oops&#39&#41&#59)</style>
        contents = '''<img src="&#106ava&#115cript&#58aler&#116&#40&#39Oops&#39&#41&#59" />'''
        #results = '''<style></style>
        result = '''<img src="" />'''
        self.runLinkFixer(BlackListHTMLSanitizer, contents, result)

    def testHTMLTruncator(self):        
        def makeTruncator(out):
            fixer = HTMLTruncator(out)
            fixer.maxWordCount = 3
            return fixer

        contents = '''
        <body>
        <div>
        one two
        three
        four
        </div>
        </body>
        '''

        result = '''
        <body>
        <div>
        one two
        three
        </div></body>'''
        
        self.runLinkFixer(makeTruncator, contents, result)

        contents = '''
        <body>
        <div>
        one two
        three
        </div>
        </body>
        '''
        self.runLinkFixer(makeTruncator, contents, result)
        
        contents = '''
        <html>
        <head>
        <title>text inside the head element should not count</title>
        </head>
        <body>
        <div>
        one two
        three
        four
        </div>
        </body>
        </html>
        '''

        result = '''
        <html>
        <head>
        <title>text inside the head element should not count</title>
        </head>
        <body>
        <div>
        one two
        three
        </div></body></html>'''

        self.runLinkFixer(makeTruncator, contents, result)

        #<div class='summary'> let's the user explicitly declare what to include in the summary
        contents = '''
        <html>
        <head>
        <title>text inside the head element should not count</title>
        </head>
        <body>
        <div class='summary'>
        <div>
        one two
        three
        four
        </div>
        </div>
        </body>
        </html>
        '''

        result = '''
        <html>
        <head>
        <title>text inside the head element should not count</title>
        </head>
        <body>
        <div class='summary'>
        <div>
        one two
        three
        four
        </div>
        </div></body></html>'''

        self.runLinkFixer(makeTruncator, contents, result)
        
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

    def testMonkeyPatcher(self):
        class NeedsPatching(object):
            def buggy(self):
                return 1
            
        class unusedname(NeedsPatching):
            __metaclass__ = MonkeyPatcher

            def buggy(self):                          
               return self.newFunc()
               
            def newFunc(self):
                return 2

            def addedFunc(self):
                return self.__class__.__name__

        test = NeedsPatching()

        self.failUnless(test.buggy() == 2)
        self.failUnless(test.buggy_old_() == 1) 
        self.failUnless(test.addedFunc() == 'NeedsPatching')

import doctest

class DocTestTestCase(unittest.TestCase):
    '''only works in Python 2.4 and higher'''
    
    doctestSuite = doctest.DocTestSuite(utils)

    def run(self, result):
        return self.doctestSuite.run(result)

    def runTest(self):
        '''Just here so this TestCase gets automatically added to the
        default TestSuite'''
        
if __name__ == '__main__':
    import sys
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = utilsTestCase(test)
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()

