"""
    ZML unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

from rx import zml
import unittest, os, os.path, glob, StringIO, difflib

class TestMarkupMapFactory(zml.DefaultMarkupMapFactory):
    mmMap = {}

    def getMarkupMap(self, uri):
        mm = self.mmMap.get(uri)
        if not mm:
            return zml.DefaultMarkupMapFactory(self, uri)
    
class ZMLTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def generateZ2X(self):
        for f in glob.glob('z2x-test*.zml'):
            resultpath = os.path.splitext(f)[0]+'.xml'            
            result = zml.zml2xml(file(f), mmf=TestMarkupMapFactory())
            print 'writing to', resultpath, result[:30]
            expected = file(resultpath, 'w')
            expected.write(result)
            expected.close()
        
    def testZ2X(self):
        for f in glob.glob('z2x-test*.zml'):
            resultpath = os.path.splitext(f)[0]+'.xml'
            self.failUnless(os.path.exists(resultpath), resultpath + ' does not exist')
            print f
            result = zml.zml2xml(file(f,'rU'), mmf=TestMarkupMapFactory())
            expected = file(resultpath,'rU').read()
            #print repr(result), '\n', repr(expected)
            #strip trailing LFs
            self.failUnless(result.rstrip() == expected.rstrip(), f + ':\n' +
                    '\n'.join(difflib.ndiff(result.rstrip().splitlines(), expected.rstrip().splitlines())) ) 

    def testCopyZML(self):
        for f in glob.glob('z2x-test*.zml'):                        
            result = zml.copyZML(file(f,'rb')).rstrip()
            orginal = open(f,'rb').read().rstrip()
            print f, len(result), len(orginal)
            self.failUnless(orginal == result, 'copy does not match orginal: '+f)

    def generateX2Z(self):
        for f in glob.glob('x2z-test*.xml'):
            resultpath = os.path.splitext(f)[0]+'.zml'
            print 'writing to', resultpath
            expected = file(resultpath, 'w')
            zml.xml2zml(file(f).read(), expected, '\n')    
            expected.close()
                    
    def testX2Z(self):
        for f in glob.glob('x2z-test*.xml'):
            resultpath = os.path.splitext(f)[0]+'.zml'
            self.failUnless(os.path.exists(resultpath), resultpath + ' does not exist')
            out = StringIO.StringIO()
            zml.xml2zml(file(f).read(), out, '\n')
            result = out.getvalue()
            #print repr(result)
            expected = file(resultpath,'rU').read()
            #print repr(expected)
            #print difflib.SequenceMatcher(None,result, expected).get_opcodes()
            self.failUnless(result.rstrip() == expected.rstrip(), f + ':\n' + 
                    '\n'.join(difflib.ndiff(result.rstrip().splitlines(), expected.rstrip().splitlines())) ) 

    def testEscaping(self):
        self.failUnless(zml.xmlescape(r'<<<<')=='&lt;&lt;&lt;&lt;')
        self.failUnless(zml.xmlescape(r'<\<<\\<')==r'&lt;<&lt;\\&lt;')
        self.failUnless(zml.xmlescape(r'<\\\<') == r'&lt;\\<')
        self.failUnless(zml.xmlescape(r'<\\\\<') == r'&lt;\\\\&lt;')
        
if __name__ == '__main__':
    import sys    
    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = ZMLTestCase(test)
        tc.setUp()
        getattr(tc, test)() #run test
    except (IndexError, ValueError):        
        unittest.main()
