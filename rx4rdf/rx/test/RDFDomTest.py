"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import unittest
from Ft.Xml import XPath, InputSource
from Ft.Rdf import Util
import cStringIO
from Ft.Xml.Lib.Print import PrettyPrint

from rx.RDFDom import *
from rx import utils
import difflib

class RDFDomTestCase(unittest.TestCase):
    ''' tests rdfdom, rxpath, rxslt, and xupdate on a rdfdom
        tests models with:
            bNodes
            literals: empty (done for xupdate), xml, text with invalid xml characters, binary
            advanced rdf: rdf:list, datatypes, xml:lang
            circularity 
            empty element names (_)
            multiple rdf:type
    '''

    model1 = r'''#test
<http://4suite.org/rdf/anonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#created-on> "1057790527.921" .
<http://4suite.org/rdf/anonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> .
<http://4suite.org/rdf/anonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057790527.921" .
<http://4suite.org/rdf/anonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/wiki#name> "HomePage" .
<http://4suite.org/rdf/anonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/wiki#summary> "l" .
<http://4suite.org/rdf/anonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#content-length> "13" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#hasContent> "            kkk &nbsp;" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "XPmK/UXVwPzgKryx1EwoHtTMe34=" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<http://4suite.org/rdf/anonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<http://4suite.org/rdf/anonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/wiki#name> "test" .
<http://4suite.org/rdf/anonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#created-on> "1057790874.703" .
<http://4suite.org/rdf/anonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> .
<http://4suite.org/rdf/anonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057790874.703" .
<http://4suite.org/rdf/anonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/wiki#summary> "lll" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "jERppQrIlaay2cQJsz36xVNyQUs=" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#hasContent> "        kkkk    &nbsp;" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#content-length> "13" .
'''

    model2 = r'''<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "ndKxl8RGTmr3uomnJxVdGnWgXuA=" .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#hasContent> " llll" .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#content-length> "5" .
<http://4suite.org/rdf/anonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<http://4suite.org/rdf/anonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/wiki#name> "HomePage" .
<http://4suite.org/rdf/anonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#created-on> "1057802436.437" .
<http://4suite.org/rdf/anonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> .
<http://4suite.org/rdf/anonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057802436.437" .
<http://4suite.org/rdf/anonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/wiki#summary> "ppp" .'''
    
    model1NsMap = { 'wiki' : "http://rx4rdf.sf.net/ns/wiki#", 'a' : "http://rx4rdf.sf.net/ns/archive#" }

    def setUp(self):
        pass

    def loadModel(self, source, type='nt'):
        if type == 'rdf':
            self.model, self.db = Util.DeserializeFromUri(source)
        else:
            self.model, self.db = utils.DeserializeFromN3File( source ) 
        self.nsMap = {u'http://rx4rdf.sf.net/ns/archive#':u'arc',
               u'http://www.w3.org/2002/07/owl#':u'owl',
               u'http://purl.org/dc/elements/1.1/#':u'dc',
               }
        self.rdfDom = RDFDoc(self.model, self.nsMap)
       
    def tearDown(self):
        pass

    def testDom(self):
        self.loadModel(cStringIO.StringIO(self.model1) )

        #print self.db._statements
        #print self.rdfDom

        #test model -> dom (correct resources created)
        xpath = '/*'
        res1 = evalXPath(self.rdfDom, xpath,  self.model1NsMap)
        self.failUnless(len(res1)==6)

        #test predicate stringvalue         
        xpath = "string(/*[wiki:name/text()='HomePage']/a:has-expression)"
        res2 = evalXPath(self.rdfDom, xpath,  self.model1NsMap)        

        xpath = "string(/*[wiki:name='HomePage']/a:has-expression/node())"
        res3 = evalXPath(self.rdfDom, xpath,  self.model1NsMap)
        self.failUnless(res2 and res2 == res3)

        #test virtual reference elements
        xpath = "/*[wiki:name/text()='HomePage']/a:has-expression/*/a:hasContent/text()"
        res4 = evalXPath(self.rdfDom, xpath,  self.model1NsMap)

        xpath = "/*[.='urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=']/a:hasContent/text()"
        res5 = evalXPath(self.rdfDom, xpath,  self.model1NsMap)                
        self.failUnless(res4 == res5)

    def testDocIndex(self):
        self.loadModel("about.rx.nt")
        xpath = "*/wiki:revisions/*"
        res1 = evalXPath(self.rdfDom, xpath,  self.model1NsMap)
        xpath = "(*/wiki:revisions/*//a:contents)[last()]"
        res2 = evalXPath(self.rdfDom, xpath,  self.model1NsMap)
        
        xpath = "(*/wiki:revisions/*//a:contents)"
        res3 = evalXPath(self.rdfDom, xpath,  self.model1NsMap)
        self.failUnless(res2[-1] == res3[-1])        

        #print 'cmp test', res1[0], res2[0]
        self.failUnless(res1[0].docIndex < res2[0].docIndex)

    def testXUpdate(self):       
        '''test xupdate'''
        self.loadModel("rdfdomtest1.rdf",'rdf')
        xupdate=r'''<?xml version="1.0" ?> 
        <xupdate:modifications version="1.0" xmlns:xupdate="http://www.xmldb.org/xupdate" 
        xmlns="http://rx4rdf.sf.net/ns/archive#" 
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:owl='http://www.w3.org/2002/07/owl#'
        >
            <xupdate:append select='/'>
                <Contents rdf:about='urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk='>
                <content-length>0</content-length>
                <hasContent />
                </Contents>        
            </xupdate:append>        
        </xupdate:modifications>
        '''               
        applyXUpdate(self.rdfDom,xupdate)
        from Ft.Rdf.Drivers import Memory
        db = Memory.CreateDb('', 'default')
        outputModel = Ft.Rdf.Model.Model(db)
        treeToModel(self.rdfDom, outputModel)
        #print 'XUPDATE ', db._statements        
        statements = {'default': [(u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/creator', u'Adam Souzis', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/date', u'2003-04-10', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/identifier', u'http://rx4rdf.sf.net/ns/archive', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/language', u'en', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/title', u'archive instance', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://rx4rdf.sf.net/ns/archive#imports', u'http://rx4rdf.sf.net/ns/archive', u'', u'', u'R'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', u'http://www.w3.org/2002/07/owl#Ontology', u'', u'', u'R'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://www.w3.org/2002/07/owl#versionInfo', u'v0.1 April 20, 2003', u'', u'', u'L'),
                                  (u'urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk=', u'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', u'http://rx4rdf.sf.net/ns/archive#Contents', u'', u'', u'R'),
                                  (u'urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk=', u'http://rx4rdf.sf.net/ns/archive#content-length', u'0', u'', u'', u'L'),
                                  (u'urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk=', u'http://rx4rdf.sf.net/ns/archive#hasContent', u'', u'', u'', u'L')]}
        d = difflib.SequenceMatcher(None,db._statements['default'], statements['default'])         
        self.failUnless( db._statements == statements, 'statements differ: '+`d.get_opcodes()` )

    def testXslt2(self):
        self.loadModel(cStringIO.StringIO(self.model2) )
        xslStylesheet=r'''<x:stylesheet version="1.0"
                            xmlns:a="http://rx4rdf.sf.net/ns/archive#"
                            xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
                            xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
                            xmlns:x="http://www.w3.org/1999/XSL/Transform"
                            exclude-result-prefixes = "a wiki rdf" 
                            >
                    <x:output method="html" />
                    <x:template match="/*[wiki:name/text()='HomePage']">
                    <div class="summary"><x:value-of select="./wiki:summary/text()" /></div>
                    <br/>
                    <div class="body"><x:value-of select="/*[wiki:name/text()='HomePage']/a:has-expression/*/a:hasContent/text()" /></div> <!-- /a:has-expression/*/a:hasContent/text() -->
                    <hr />
                    <div class="details">Last Modifed: <x:value-of select="./a:last-modified/text()" />
                    <br />Created On: <x:value-of select="./a:created-on/text()" />
                    <!-- todo "by: user" -->
                    </div>
                    <a href="edit?name=HomePage">Edit</a>
                    </x:template>
                    <x:template match="text()|@*" />
                    </x:stylesheet>'''

        xslStylesheet2=r'''<?xml version="1.0" ?>        
        <xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
            <xsl:template match="node()|@*">
	    <xsl:copy>
	        <xsl:apply-templates select="node()|@*"/>
	    </xsl:copy>
	    </xsl:template>         
        </xsl:stylesheet>'''
        result = applyXslt(self.rdfDom, xslStylesheet)
        #todo assert something!
        #print 'XLST2 ', result
        #PrettyPrint(self.rdfDom)
    
    def testXslt(self):       
        '''test rxslt'''
        self.loadModel(cStringIO.StringIO(self.model1) )
        todoxslStylesheet=r'''<?xml version="1.0" ?>        
        <xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
        <xsl:template match="/contents">                
        <xsl:if select="./hasContents">
            return hasContents/text()
        <xsl:otherwise>
            for-each has-instance/content-source
               if ext:url-accessible(.)
                    return ext:url-as-text(.)              
        </xsl:otherwise>
        </xsl:if> 
        '''
       
        xslStylesheet=r'''<?xml version="1.0" ?>        
        <xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
        <xsl:template match="/">  
        <rdfdom>
        <xsl:apply-templates />
        </rdfdom>
        </xsl:template>
        
        <xsl:template match="node()|@*">
	    <xsl:copy>
	        <xsl:apply-templates select="node()|@*"/>
	    </xsl:copy>
	    </xsl:template>
         
        </xsl:stylesheet>
        '''
      
        result = applyXslt(self.rdfDom, xslStylesheet)
        #d = difflib.Differ()
        #print list(d.compare(result,outputXml)) #list of characters, not lines!
        self.failUnless( result == file('testXslt1.xml').read(),'xml output does not match')
       
if __name__ == '__main__':
    import sys
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = RDFDomTestCase(test)
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()

