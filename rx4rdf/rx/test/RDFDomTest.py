"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import unittest, os, os.path, glob
from Ft.Xml import XPath, InputSource
from Ft.Rdf import Util
import cStringIO
from Ft.Xml.Lib.Print import PrettyPrint
from pprint import *
        
newRDFDom = 1
if not newRDFDom:
    from rx.RDFDom import *
else:
    from rx.RxPath import *
    RDFDoc = lambda model, nsMap: createDOM(model, nsMap)
    
from rx import utils
import difflib, time

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
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#created-on> "1057790527.921" .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057790527.921" .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/wiki#name> "HomePage" .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://rx4rdf.sf.net/ns/wiki#summary> "l" .
<http://4suite.org/rdf/banonymous/5c79e155-5688-4059-9627-7fee524b7bdf> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#content-length> "13" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#hasContent> "            kkk &nbsp;" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "XPmK/UXVwPzgKryx1EwoHtTMe34=" .
<urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/wiki#name> "test" .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#created-on> "1057790874.703" .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057790874.703" .
<http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6> <http://rx4rdf.sf.net/ns/wiki#summary> "lll" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "jERppQrIlaay2cQJsz36xVNyQUs=" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#hasContent> "        kkkk    &nbsp;" .
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#content-length> "13" .
'''

    model2 = r'''<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "ndKxl8RGTmr3uomnJxVdGnWgXuA=" .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#hasContent> " llll" .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#content-length> "5" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/wiki#name> "HomePage" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#created-on> "1057802436.437" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057802436.437" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/wiki#summary> "ppp" .'''

    loopModel = r'''<http://loop.com> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://loop.com>.
<http://loop.com#2> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://loop.com#3>.
<http://loop.com#3> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://loop.com#2>.'''
    
    model1NsMap = {  'rdf' : RDF_MS_BASE, 
                    'wiki' : "http://rx4rdf.sf.net/ns/wiki#",
                    'a' : "http://rx4rdf.sf.net/ns/archive#" }

    def setUp(self):
        pass

    def loadFtModel(self, source, type='nt'):
        if type == 'rdf':
            model, self.db = Util.DeserializeFromUri(source)
        else:
            model, self.db = utils.DeserializeFromN3File( source )
        return FtModel(model)

    def loadRedlandModel(self, source, type='nt'):        
        if type == 'rdf':
            assert 'Not Supported'
        else:            
            for f in glob.glob('RDFDomTest*.db'):
                if os.path.exists(f):
                    os.unlink(f)            
            return initRedlandHashBdbModel("RDFDomTest", source)
            
    def loadModel(self, source, type='nt'):
        self.model = self.loadFtModel(source, type)
        #self.model = self.loadRedlandModel(source, type)
        self.nsMap = {u'http://rx4rdf.sf.net/ns/archive#':u'arc',
               u'http://www.w3.org/2002/07/owl#':u'owl',
               u'http://purl.org/dc/elements/1.1/#':u'dc',
               }
        self.rdfDom = RDFDoc(self.model, self.nsMap)

    def getModel(self, source, type='nt'):
        model = self.loadFtModel(source, type)
        #self.model = self.loadRedlandModel(source, type)
        self.nsMap = {u'http://rx4rdf.sf.net/ns/archive#':u'arc',
               u'http://www.w3.org/2002/07/owl#':u'owl',
               u'http://purl.org/dc/elements/1.1/#':u'dc',
               }
        return RDFDoc(model, self.nsMap)
       
    def tearDown(self):
        pass

    def testDom(self):
        self.loadModel(cStringIO.StringIO(self.model1) )

        #print self.model.getResources()
        #print self.rdfDom

        #test model -> dom (correct resources created)
        xpath = '/*'
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(len(res1)==6)
        
        #test predicate stringvalue         
        xpath = "string(/*[wiki:name/text()='HomePage']/a:has-expression)"
        res2 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)        

        xpath = "string(/*[wiki:name='HomePage']/a:has-expression/node())"
        res3 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(res2 and res2 == res3)

        #test recursive elements        
        xpath = "/*[wiki:name/text()='HomePage']/a:has-expression/*/a:hasContent/text()"
        res4 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        start = time.time()        
        xpath = "/*[.='urn:sha:XPmK/UXVwPzgKryx1EwoHtTMe34=']/a:hasContent/text()"
        res5 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #print time.time() - start
        #they have the same string value but occupy different positions in the tree
        self.failUnless(res4[0] != res5[0] and res4[0].data == res5[0].data)

    def timeXPath(self):
        self.loadModel(cStringIO.StringIO(self.model1) )
        start = time.time()
        for i in xrange(100):        
            xpath = "/*[wiki:name/text()='HomePage']/a:has-expression/*/a:hasContent/text()"
            self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        print time.time() - start

    def testLoop(self):
        self.loadModel(cStringIO.StringIO(self.loopModel) )
        
        xpath = '/*'
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #print res1
        self.failUnless(len(res1)==3)
                
        xpath = "/*/*/*"        
        res2 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #print res2
        self.failUnless(len(res2)==3)

        #circularity checking only on with descendant axes
        xpath = "/*/*/*/*/*"        
        res3 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #print res3        
        c1 = [x.stringValue for x in res2]
        c1.sort()
        c2 = [x.stringValue for x in res3]
        c2.sort()
        self.failUnless(c1 == c2) #order will be different but should be same resources
                
        xpath = "//rdf:type"        
        res4 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(len(res4)==5) 

        self.rdfDom.globalRecurseCheck = 1
        PrettyPrint(self.rdfDom) #Xml.Lib.Print.Nss.seek() causes infinite regress
        self.rdfDom.globalRecurseCheck = 0
            
    def testDocIndex(self):
        self.loadModel("about.rx.nt")
        xpath = "*/wiki:revisions/*"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
       
        xpath = "(*/wiki:revisions/*/rdf:first/*//a:contents)[last()]"
        res2 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        
        xpath = "(*/wiki:revisions/*/rdf:first/*//a:contents)"
        res3 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
 
        self.failUnless(res2[-1] == res3[-1])        

        #print 'cmp test', res1[0], res2[0]
        self.failUnless(res1[0].docIndex < res2[0].docIndex)

    def testLists(self):
        self.loadModel("about.rx.nt")
        xpath = "*/wiki:revisions/*/rdf:first/@listID='http://4suite.org/rdf/anonymous/xc52aaabe-6b72-42d1-8772-fcb90303c24b_5'"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)        
        self.failUnless( res1 )

        xpath = "*[wiki:name='about']/wiki:revisions/*/rdf:first"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( len(res1)==2 )

        xpath = "*[wiki:name='about']/wiki:revisions/*/rdf:first/*"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( len(res1)==2 )

        xpath = "*[wiki:name='about']/wiki:revisions/*/rdf:rest"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( len(res1)==0 )

        xpath = "*[wiki:name='about']/wiki:revisions/*/rdf:first[2]='http://4suite.org/rdf/anonymous/x467ce421-1a30-4a2f-9208-0a4b01cd0da1_9'"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( res1 )

    def testId(self):
        #use this one because all resources appear as an object at least once
        self.loadModel(cStringIO.StringIO(self.loopModel) )
        #we need to add the predicate filter to force the nodeset in doc order so we can compare it
        xpath = "(id(/*/*/*))[true()]"  
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        res2 = self.rdfDom.evalXPath( '/*',  self.model1NsMap)
        self.failUnless(res1 == res2)
        
    def testDiff(self):
        self.loadModel("about.rx.nt")
        updateDom = self.getModel("about.diff1.nt")
        updateNode = updateDom.findSubject('http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2')
        self.failUnless( updateNode )
        added, removed, reordered = diffResources(self.rdfDom, [updateNode])
        #nothing should have changed
        self.failUnless( not added and not removed and not reordered )

        updateDom = self.getModel("about.diff2.nt")
        updateNode = updateDom.findSubject('http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2')
        self.failUnless( updateNode )
        added, removed, reordered = diffResources(self.rdfDom, [updateNode])
        #print added, removed, reordered
        #we've add and removed one non-list statement and changed the first list item (and so 1 add, 1 remove)
        self.failUnless( len(added) == len(removed) == len(reordered) ==
            len(reordered.values()[0][0]) == len(reordered.values()[0][1]) == 1)

        updateDom = self.getModel("about.diff3.nt")
        updateNode = updateDom.findSubject('http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2')
        self.failUnless( updateNode )
        added, removed, reordered = diffResources(self.rdfDom, [updateNode])
        #with this one we've just re-ordered the list, so no statements should be listed as added or removed
        self.failUnless(reordered and len(reordered.values()[0][0]) == len(reordered.values()[0][1]) == 0)
        
    def _mergeAndUpdate(self, updateDom, resources):
        statements, nodesToRemove = mergeDOM(self.rdfDom, updateDom ,resources)
        #print 'res'; pprint( (statements, nodesToRemove) )
        
        #delete the statements or whole resources from the dom:            
        for node in nodesToRemove:
            node.parentNode.removeChild(node)
        #and add the statements
        addStatements(self.rdfDom, statements)
        return statements, nodesToRemove
    
    def testMerge(self):
        self.loadModel("about.rx.nt")
        updateDom = self.getModel("about.diff1.nt")
        statements, nodesToRemove = mergeDOM(self.rdfDom, updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])                
        #nothing should have changed
        self.failUnless( not statements and not nodesToRemove )

        self.loadModel("about.rx.nt")
        updateDom = self.getModel("about.diff2.nt")
        #we've added and removed one non-list statement and changed the first list item
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])
        self.failUnless( statements and nodesToRemove )
        #merge in the same updateDom in again, this time there should be no changes
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])
        self.failUnless( not statements and not nodesToRemove )

        self.loadModel("about.rx.nt")        
        updateDom = self.getModel("about.diff3.nt")
        #with this one we've just re-ordered the list,
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])
        self.failUnless( statements and nodesToRemove )
        #merge in the same updateDom in again, this time there should be no changes
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])
        self.failUnless( not statements and not nodesToRemove )
        
        
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
        if newRDFDom:
            db = self.db
        else:
            from Ft.Rdf.Drivers import Memory
            db = Memory.CreateDb('', 'default')
            import Ft.Rdf.Model
            outputModel = Ft.Rdf.Model.Model(db)
            treeToModel(self.rdfDom, outputModel)        
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
        currentStmts = db._statements['default']
        currentStmts.sort()
        #print 'XUPDATE ', pprint( currentStmts) 
        expectedStmts = statements['default']
        expectedStmts.sort()
        d = difflib.SequenceMatcher(None,currentStmts, expectedStmts )         
        self.failUnless( currentStmts == expectedStmts , 'statements differ: '+`d.get_opcodes()` )

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

        result = applyXslt(self.rdfDom, xslStylesheet)
        #print result
        #todo assert something!
        #print 'XLST2 ', result
        #PrettyPrint(self.rdfDom)

    def timeXslt(self):
        self.loadModel(cStringIO.StringIO(self.model2) )
        start = time.time()
        for i in xrange(40):
            #'identity stylesheet'
            xslStylesheet=r'''<?xml version="1.0" ?>        
            <xsl:stylesheet version="1.0"
                    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
                <xsl:template match="node()|@*">
            <xsl:copy>
                <xsl:apply-templates select="node()|@*"/>
            </xsl:copy>
            </xsl:template>         
            </xsl:stylesheet>'''
            result = applyXslt(self.rdfDom, xslStylesheet)
        print time.time() - start
    
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
        #open('testXslt1.xml', 'wb').write(result)
        #d = difflib.Differ()
        #print list(d.compare(result,outputXml)) #list of characters, not lines!
        self.failUnless( result == file('testXslt1.xml').read(),'xml output does not match')
    
if __name__ == '__main__':
    import sys    
    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = RDFDomTestCase(test)
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()

