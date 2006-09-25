"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import unittest, os, os.path, glob, tempfile
from Ft.Xml import XPath, InputSource
import cStringIO
from Ft.Xml.Lib.Print import PrettyPrint
from pprint import *
   
from rx.RxPath import *
def RDFDoc(model, nsMap):
    from rx import RxPathGraph
    graphManager = RxPathGraph.NamedGraphManager(model, None,None)
    graphManager.createCtxResource = False
    return createDOM(model, nsMap, graphManager=graphManager)

import difflib, time

try:
    from Ft.Rdf import Util
    from rx.RxPathUtils import _parseTriples as parseTriples
    from Ft.Rdf.Statement import Statement as FtStatement
    from Ft.Rdf.Model import Model as Model4Suite
    #this function is no longer used by RxPath
    def DeserializeFromN3File(n3filepath, driver=Memory, dbName='', create=0, defaultScope='',
                            modelName='default', model=None):
        if not model:
            if create:
                db = driver.CreateDb(dbName, modelName)
            else:
                db = driver.GetDb(dbName, modelName)
            db.begin()
            model = Model4Suite(db)
        else:
            db = model._driver
            
        if isinstance(n3filepath, ( type(''), type(u'') )):
            stream = file(n3filepath, 'r+')
        else:
            stream = n3filepath
            
        #bNodeMap = {}
        #makebNode = lambda bNode: bNodeMap.setdefault(bNode, generateBnode(bNode))
        makebNode = lambda bNode: BNODE_BASE + bNode
        for stmt in parseTriples(stream,  makebNode):
            if stmt[0] is Removed:            
                stmt = stmt[1]
                scope = stmt[4] or defaultScope
                model.remove( FtStatement(stmt[0], stmt[1], stmt[2], '', scope, stmt[3]) )
            else:
                scope = stmt[4] or defaultScope
                model.add( FtStatement(stmt[0], stmt[1], stmt[2], '', scope, stmt[3]) )                
        #db.commit()
        return model, db
except ImportError:
    print 'package Ft.Rdf not available, some tests will be disabled'
    
class RDFDomTestCase(unittest.TestCase):
    ''' tests rdfdom, rxpath, rxslt, and xupdate on a rdfdom
        tests models with:
            bNodes
            literals: empty (done for xupdate), xml, text with invalid xml characters, binary
            advanced rdf: rdf:list, containers, datatypes, xml:lang
            circularity 
            empty element names (_)
            multiple rdf:type
            RDF Schema support
        diffing and merging models
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
<urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=> <http://rx4rdf.sf.net/ns/archive#content-length> "20" .
'''

    model2 = r'''<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#Contents> .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#sha1-digest> "ndKxl8RGTmr3uomnJxVdGnWgXuA=" .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#hasContent> " llll"@en-US .
<urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> <http://rx4rdf.sf.net/ns/archive#content-length> "5"^^http://www.w3.org/2001/XMLSchema#int .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://rx4rdf.sf.net/ns/archive#NamedContent> .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/wiki#name> "HomePage" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#created-on> "1057802436.437" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#has-expression> <urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=> .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/archive#last-modified> "1057802436.437" .
<http://4suite.org/rdf/banonymous/cc0c6ff3-e8a7-4327-8cf1-5e84fc4d1198> <http://rx4rdf.sf.net/ns/wiki#summary> "ppp" .'''

    loopModel = r'''<http://loop.com#r1> <http://loop.com#prop> <http://loop.com#r1>.
<http://loop.com#r2> <http://loop.com#prop> <http://loop.com#r3>.
<http://loop.com#r3> <http://loop.com#prop> <http://loop.com#r2>.'''
    
    model1NsMap = { 'rdf' : RDF_MS_BASE, 
                    'rdfs' : RDF_SCHEMA_BASE,
                    'bnode' : "bnode:",
                    'wiki' : "http://rx4rdf.sf.net/ns/wiki#",
                    'a' : "http://rx4rdf.sf.net/ns/archive#" }

    def setUp(self):        
        if DRIVER == '4Suite':
            self.loadModel = self.loadFtModel
        elif DRIVER == 'RDFLib':
            self.loadModel = self.loadRdflibModel
        elif DRIVER == 'Redland':
            self.loadModel = self.loadRedlandModel
        elif DRIVER == 'Mem':
            self.loadModel = self.loadMemModel
        else:
            raise "unrecognized driver: " + DRIVER
        #from rx import RxPath
        #RxPath.useQueryEngine = True

    def loadFtModel(self, source, type='nt'):
        if type == 'rdf':
            #assume relative file
            model, self.db = Util.DeserializeFromUri('file:'+source, scope='')
        else:
            model, self.db = DeserializeFromN3File( source )
        #use TransactionFtModel because we're using 4Suite's Memory
        #driver, which doesn't support transactions
        return TransactionFtModel(model)

    def loadRedlandModel(self, source, type='nt'):
        #ugh can't figure out how to close an open store!
        #if hasattr(self,'rdfDom'):
        #    del self.rdfDom.model.model._storage
        #    import gc; gc.collect()             

        if type == 'rdf':
            assert False, 'Not Supported'
        else:            
            for f in glob.glob('RDFDomTest*.db'):
                if os.path.exists(f):
                    os.unlink(f)
            if isinstance(source, (str, unicode)):
                stream = file(source, 'r+')
            else:
                stream = source
            stmts = NTriples2Statements(stream)
            return RedlandHashMemModel("RDFDomTest", stmts)
            #return RedlandHashBdbModel("RDFDomTest", stmts)

    def loadRdflibModel(self, source, type='nt'):
        dest = tempfile.mktemp()
        if type == 'rdf':
            type = 'xml'
        return initRDFLibModel(dest, source, type)

    def loadMemModel(self, source, type='nt'):
        if type == 'nt':
            type = 'ntriples'
        elif type == 'rdf':
            type = 'rdfxml'        
        if isinstance(source, (str, unicode)):
            return TransactionMemModel(parseRDFFromURI('file:'+source,type))
        else:
            return TransactionMemModel(parseRDFFromString(source.read(),'test:', type))
        
    def getModel(self, source, type='nt'):
        model = self.loadModel(source, type)
        self.nsMap = {u'http://rx4rdf.sf.net/ns/archive#':u'arc',
               u'http://www.w3.org/2002/07/owl#':u'owl',
               u'http://purl.org/dc/elements/1.1/#':u'dc',
               }
        return RDFDoc(model, self.nsMap)
       
    def tearDown(self):
        pass

    def testNtriples(self):
        #we don't include scope as part of the Statements key
        st1 = Statement('test:s', 'test:p', 'test:o', 'R', 'test:c')
        st2 = Statement('test:s', 'test:p', 'test:o', 'R', '')
        self.failUnless(st2 in [st1] and [st2].index(st1) == 0)
        self.failUnless(st1 in {st2:1}  )
        
        #test character escaping 
        s1 = r'''bug: File "g:\_dev\rx4rdf\rx\Server.py", '''
        n1 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents> "bug: File \"g:\\_dev\\rx4rdf\\rx\\Server.py\", ".'''
        [(subject, predicate, object, objectType, scope)] = [x for x in parseTriples([n1])]
        self.failUnless(s1 == object)
        #test xml:lang support
        n2 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents> "english"@en-US.'''
        [(subject, predicate, object, objectType, scope)] = [x for x in parseTriples([n2])]
        self.failUnless(object=="english" and objectType == 'en-US')
        #test datatype support
        n3 = r'''_:x1f6051811c7546e0a91a09aacb664f56x142 <http://rx4rdf.sf.net/ns/archive#contents>'''\
        ''' "1"^^http://www.w3.org/2001/XMLSchema#int.'''
        [(subject, predicate, object, objectType, scope)] = [x for x in parseTriples([n3])]
        self.failUnless(object=="1" and objectType == 'http://www.w3.org/2001/XMLSchema#int')

        sio = cStrin`gIO.StringIO()
        writeTriples( [Statement('test:s', 'test:p', u'\x10\x0a\\\u56be',
                                 OBJECT_TYPE_LITERAL)], sio, 'ascii')
        self.failUnless(sio.getvalue() == r'<test:s> <test:p> "\u0010\n\\\u56BE" .'
                        '\n')                      

        #test URI validation when writing triples
        out = cStringIO.StringIO()
        self.failUnlessRaises(RuntimeError, lambda:
            writeTriples( [Statement(BNODE_BASE+'foo bar', 'http://foo bar', 
                'http://foo bar')], out) )
        writeTriples( [Statement(BNODE_BASE+'foobar', 'http://foo', 
                'http://foo bar')], out)         
        self.failUnlessRaises(RuntimeError, lambda:
            writeTriples( [Statement(BNODE_BASE+'foobar', 'http://foo', 
                'http://foo bar',OBJECT_TYPE_RESOURCE)], out) )

    def testDom(self):
        self.rdfDom = self.getModel(cStringIO.StringIO(self.model1) )

        #print self.model.getResources()
        #print self.rdfDom

        #test model -> dom (correct resources created)
        xpath = '/*[not(starts-with(., "http://www.w3.org/"))]'
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #pprint( ( len(res1), res1 ) )
        self.failUnless(len(res1)== 14) #6 resource + 8 properties
        
        #test predicate stringvalue         
        xpath = "string(/*[wiki:name/text()='HomePage']/a:has-expression)"
        res2 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)        

        xpath = "string(/*[wiki:name='HomePage']/a:has-expression/node())"
        res3 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #print ( (res2, res3) )
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

    def testLangAndDatatype(self):
        self.rdfDom = self.getModel(cStringIO.StringIO(self.model2) )
        
        xpath = "/*[.='urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=']/a:hasContent"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        xpath = "/*[.='urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=']/a:hasContent[@xml:lang='en-US']"
        res2 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        xpath = "/*[.='urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=']/a:hasContent[@xml:lang='de']"
        res3 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(res1 == res2 and res2 and not res3)

        xpath = "/*[.='urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=']/a:content-length[@rdf:datatype='http://www.w3.org/2001/XMLSchema#int']"
        res4 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        xpath = "/*[.='urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=']/a:content-length[@rdf:datatype='http://www.w3.org/2001/XMLSchema#int']"
        res5 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)        
        xpath = "/*[.='urn:sha:ndKxl8RGTmr3uomnJxVdGnWgXuA=']/a:content-length[@rdf:datatype='http://www.w3.org/2001/XMLSchema#anyURI']"
        res6 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)

        self.failUnless(res4 == res5 and res4 and not res6)
        
    def testSubtype(self):        
        model = '''_:C <http://www.w3.org/2000/01/rdf-schema#subClassOf> _:D.
_:C <http://www.w3.org/2000/01/rdf-schema#subClassOf> _:F.
_:B <http://www.w3.org/2000/01/rdf-schema#subClassOf> _:D.
_:B <http://www.w3.org/2000/01/rdf-schema#subClassOf> _:E.
_:A <http://www.w3.org/2000/01/rdf-schema#subClassOf> _:B.
_:A <http://www.w3.org/2000/01/rdf-schema#subClassOf> _:C.
_:O1 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> _:C.
_:O2 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> _:B.
_:O2 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> _:F.
_:O3 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> _:B.
_:O4 <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> _:A.
_:O4 <http://rx4rdf.sf.net/ns/archive#contents> "".
'''
        self.rdfDom = self.getModel(cStringIO.StringIO(model) )

        xpath = "/bnode:A" 
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(len(res1) == 1)

        xpath = "/bnode:D" 
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(len(res1) == 4)

        xpath = "/bnode:F" 
        res2 = self.rdfDom.evalXPath(xpath,  self.model1NsMap)
        self.failUnless(len(res2) == 3)

        xpath = "is-instance-of(/bnode:A, uri('bnode:B'))"
        xpath = "/bnode:A/rdf:type/*//rdfs:subClassOf[.=uri('bnode:B')]"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(res1 )

        xpath = "is-instance-of(/bnode:nomatch, uri('bnode:B'))"        
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(not res1)

        xpath = "is-instance-of(/*/*/bnode:D, uri('bnode:A'))"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(not res1)

        xpath = "/bnode:D/rdf:type/*//rdfs:subClassOf[.=uri('bnode:A')]"
        #only some nodes match, return false
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(not res1)

        #xpath = "is-instance-of(/*/*/text(), uri('rdfs:Literal'))" 
        #res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #self.failUnless(not res1 )
            
        #find all the statements with a property
        xpath='/*/rdf:type'
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
                
        xpath = "/*/*[is-subproperty-of(@uri,'http://www.w3.org/1999/02/22-rdf-syntax-ns#type')]"        
        res2 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #print len(res1), [n.parentNode for n in res1]
        #print len(res2), [n.parentNode for n in res2]
        self.failUnless(res1 == res2)
        
        
    def testSubproperty(self):        
        model = '''<http://rx4rdf.sf.net/ns/archive#C> <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://rx4rdf.sf.net/ns/archive#D>.
<http://rx4rdf.sf.net/ns/archive#C> <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://rx4rdf.sf.net/ns/archive#F>.
<http://rx4rdf.sf.net/ns/archive#B> <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://rx4rdf.sf.net/ns/archive#D>.
<http://rx4rdf.sf.net/ns/archive#B> <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://rx4rdf.sf.net/ns/archive#E>.
<http://rx4rdf.sf.net/ns/archive#A> <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://rx4rdf.sf.net/ns/archive#B>.
<http://rx4rdf.sf.net/ns/archive#A> <http://www.w3.org/2000/01/rdf-schema#subPropertyOf> <http://rx4rdf.sf.net/ns/archive#C>.
_:O1 <http://rx4rdf.sf.net/ns/archive#C> "".
_:O2 <http://rx4rdf.sf.net/ns/archive#B> "".
_:O2 <http://rx4rdf.sf.net/ns/archive#F> "".
_:O3 <http://rx4rdf.sf.net/ns/archive#B> "".
_:O4 <http://rx4rdf.sf.net/ns/archive#A> "".
'''
        self.rdfDom = self.getModel(cStringIO.StringIO(model) )

        xpath = "/*/a:A" 
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(len(res1) == 1)

        xpath = "/*/a:D" 
        res2 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(len(res2) == 4)

        xpath3 = "/*/a:F" 
        res3 = self.rdfDom.evalXPath(xpath3,  self.model1NsMap)
        self.failUnless(len(res3) == 3)        

        xpath = "(.)/self::a:D"
        res = self.rdfDom.evalXPath( xpath,  self.model1NsMap, node=res1[0])
        self.failUnless(len(res) == 1)
        
        xpath = "is-subproperty-of(/*/a:A/@uri, uri('a:B'))"
        res4 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(res4 )

        xpath = "is-subproperty-of(/*/a:nomatch, uri('a:B'))" 
        res5 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(not res5)

        xpath = "is-subproperty-of(/*/a:D/@uri, uri('a:A'))"
        #only some nodes match, but since we follow
        #nodeset equality semantics we still return true
        res6 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(res6)

        #modify the DOM and make sure the schema is updated properly
        self.rdfDom.commit()

        xpath = "/*/rdfs:subPropertyOf[.=uri('a:C')]"
        res7 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        #remove the statement that A is a subproperty of C
        res7[0].parentNode.removeChild(res7[0])

        res8 = self.rdfDom.evalXPath(xpath3,  self.model1NsMap)
        self.failUnless(len(res8) == 2)        

        stmt = Statement("http://rx4rdf.sf.net/ns/archive#E", "http://www.w3.org/2000/01/rdf-schema#subPropertyOf",
                         "http://rx4rdf.sf.net/ns/archive#F", objectType=OBJECT_TYPE_RESOURCE)
        addStatements(self.rdfDom, [stmt])

        res9 = self.rdfDom.evalXPath(xpath3,  self.model1NsMap)
        self.failUnless(len(res9) == 5)        
        
        #now let rollback those changes and redo the queries --
        #the results should now be the same as the first time we ran them
        self.rdfDom.rollback()
        
        res10 = self.rdfDom.evalXPath(xpath3,  self.model1NsMap)
        self.failUnless(res10 == res3)                

    def printPlan(self, xpath):
        from rx import RxPathQuery
        from Ft.Xml.XPath.Context import Context 

        compExpr = XPath.Compile(xpath)
        print compExpr.pprint()
        context = Context(self.rdfDom,
                    extFunctionMap = BuiltInExtFunctions,
                    processorNss = self.model1NsMap)            
        newExpVisitor = RxPathQuery.ReplaceRxPathSubExpr(context, compExpr)
        print xpath
        #print repr(newExpVisitor.resultExpr)
        newExpVisitor.resultExpr.pprint()
        
        newExpVisitor.explain = True
        res = newExpVisitor.resultExpr.evaluate(context)
        if isinstance(res, Tupleset):            
            res.explain(sys.stdout)
        newExpVisitor.explain = False                        
    
    def testTimeXPath(self):        
        self.rdfDom = self.getModel(cStringIO.StringIO(self.model1) )
        return self._timeXPath(self.rdfDom, 1, 0)

    def timeXPathBig(self):        
        source = cStringIO.StringIO(self.model1)
        model = MemModel()
        count = 0
        for stmt in parseRDFFromString(source.read(),'test:', 'ntriples'):            
            for i in xrange(2000):
                modStmt = MutableStatement(*stmt)
                if i > 0:
                    modStmt[0] += str(i)
                count += 1                
                model.addStatement(modStmt)

        print count, model.size()
        self.nsMap = {u'http://rx4rdf.sf.net/ns/archive#':u'arc',
               u'http://www.w3.org/2002/07/owl#':u'owl',
               u'http://purl.org/dc/elements/1.1/#':u'dc',
               }
        rdfDom = RDFDoc(model, self.nsMap)
        
        return self._timeXPath(rdfDom, 1, 1)

    def _timeXPath(self, rdfDom, count, printLevel=2):
        from rx import RxPathQuery
        from Ft.Xml.XPath.Context import Context 

        queries = [
        ("/*/*", 0.12),
        ("/*[a:content-length > 15]", 0),
        ("/*/*", 0.12),
        ("/*[wiki:name='ZMLSandbox']/*[uri(.)='http://purl.org/dctitle']",0),        
        #('/*[.=$subjects]', 0),
        ('/*[.=$test]', 0),
        ('/*[not(starts-with(., "http://www.w3.org/"))]', 0),        
        ("/*/a:D/@uri", 0),
        ("/*[wiki:name='HomePage']/a:has-expression/*/a:hasContent/text()", 79),
        ("/*/a:has-expression", 7.6),
        ("/*[wiki:name='HomePage']/a:has-expression/*", 77.5),
        ("/*[wiki:name='HomePage']", 12),
        ("/*/*", 0.12),
        ("/*/baz", 966),                
        ("/*/*[node()]", 0.5),
        ("/a:NamedContent", 1.25),
        ("/a:NamedContent[wiki:name='HomePage']", 0.35),
        ("/*[.='http://nonexistent']", 1),
        ("/*[.='http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6']", 1),
        ("/a:NamedContent[.='http://4suite.org/rdf/banonymous/5e3bc305-0fbb-4b67-b56f-b7d3f775dde6']", 1),
        ]

        timer = time.clock #some platform time() has precision than clock()
        
        for xpath, expectRatio in queries:
            compExpr = XPath.Compile(xpath)
            context = Context(rdfDom,
                    extFunctionMap = BuiltInExtFunctions,
                    varBindings = { 
                    (None, 'test') : [rdfDom.firstChild],
                    (None, 'subjects') : rdfDom.childNodes,
                     },
                    processorNss = self.model1NsMap)            
            newExpVisitor = RxPathQuery.ReplaceRxPathSubExpr(context, compExpr)
            if printLevel > 1:
                print xpath
                print repr(newExpVisitor.resultExpr)

            #if profile:
            #    for i in xrange(2): 
            #        res = newExpVisitor.resultExpr.evaluate(context)
            #    return
        
            compExpr0 = XPath.Compile(xpath)

            res = compExpr0.evaluate(context)        
            start = timer()
            for i in xrange(count):
                #print 'orig', self.rdfDom.evalXPath( xpath,  self.model1NsMap)
                res = compExpr0.evaluate(context)
                            
            xpathClock = timer() - start
            if printLevel > 1: print xpathClock, len(res), res and res[0] or []

            newExpVisitor.explain = True
            res2 = newExpVisitor.resultExpr.evaluate(context)            
            if printLevel > 1: res2.explain(sys.stdout)
            newExpVisitor.explain = False                        

            start = timer()                
            for i in xrange(count):                            
                #print 'orig', self.rdfDom.evalXPath( xpath,  self.model1NsMap)            
                def tst():
                    return newExpVisitor.resultExpr.evaluate(context)
                if profile:
                    res2 = prof.runcall(tst)
                    break
                else:
                    res2 = tst()
                
            rxpathClock = timer() - start
            if printLevel > 0:
                if printLevel < 2: print xpath
                print rxpathClock, len(res2),
                if printLevel > 1: print res2 and res2[0] or []
                print 'RATIO', xpathClock / rxpathClock
                print '\n'
            self.failUnless((not res and not res2) or res[0:] == res2[0:])

            #skip next test as the non-query engine run sometime has duplicate
            #resource nodes somehow e.g. urn:sha:jERppQrIlaay2cQJsz36xVNyQUs=            
            #self.failUnless(len(res) == len(res2))

            #skip the next test since varies too much from config to config 
            #self.failUnless( rxpathClock / xpathClock < expectRatio)
            
    def testLoop(self):
        loopNsMap = {'loop': 'http://loop.com#'}
        loopNsMap.update(self.model1NsMap)
        self.rdfDom = self.getModel(cStringIO.StringIO(self.loopModel) )
        from rx import RxPath
        RxPath.useQueryEngine = 1
        context = RxPath.XPath.Context.Context(self.rdfDom,processorNss = loopNsMap)
                
        xpath = '/*[starts-with(.,"http://loop.com#r")]'
        res1 = self.rdfDom.evalXPath( xpath,  loopNsMap)
        #print len(res1), res1
        self.failUnless(res1)
                
        xpath = "/*/loop:*/*"        
        res2 = self.rdfDom.evalXPath( xpath,  loopNsMap)
        #print len(res1), len(res2), [ x.parentNode for x in res2]
        self.failUnless(len(res2)==len(res1))
        
        #circularity checking only on with descendant axes
        xpath = "/*/loop:*/*/loop:*/*"        
        res3 = self.rdfDom.evalXPath( xpath,  loopNsMap)

        #xpath = "$r1/*/*[.=uri('loop:r1')]/*/*/*/*"
        #node = self.rdfDom.findSubject('http://loop.com#r1')
        #print self.rdfDom.evalXPath( xpath,  loopNsMap, vars = { (None,'r1'): [node]})
        
        c1 = [x.stringValue for x in res2]
        c1.sort()
        c2 = [x.stringValue for x in res3]
        c2.sort()
        self.failUnless(c1 == c2) #order will be different but should be same resources

        xpath = "//loop:*"        
        res4 = self.rdfDom.evalXPath( xpath,  loopNsMap)
        #print len(res4), res4
        self.failUnless(len(res4)==5)
        
        xpath = "//loop:*/*"        
        res5 = self.rdfDom.evalXPath( xpath,  loopNsMap)        
        #print len(res4), res4
        #results should be r1; r3, r2; r2, r3
        self.failUnless(len(res5)==5) 

        xpath = "/*[.=uri('loop:r1')]//loop:*/*"
        #RxPath._compileXPath(xpath,context).pprint()
        res4 = self.rdfDom.evalXPath( xpath,  loopNsMap)
        #print len(res4), res4
        #results should be r1, r1
        self.failUnless(len([n for n in res4 if RxPath.isResource(context, [n])])==2)

        xpath = "/*[.=uri('loop:r2')]//loop:*/*"         
        res4 = self.rdfDom.evalXPath( xpath,  loopNsMap)
        #print len(res4), res4
        self.failUnless(len(res4)==3) 
        
        #self.rdfDom.globalRecurseCheck = 1
        #Xml.Lib.Print.Nss.seek() causes infinite regress, plus C implementation in CVS trunk doesn't work
        #todo: add a RxPath.PrettyPrint
        #PrettyPrint(self.rdfDom) 
        #self.rdfDom.globalRecurseCheck = 0
            
    def testDocIndex(self):
        self.rdfDom = self.getModel("about.rx.nt")
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
        self.rdfDom = self.getModel("about.rx.nt")
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

        xpath = "*[wiki:name='about']/wiki:revisions/*"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless(res1 and res1[0].isCompound() )

    def testContainers(self):
        self.rdfDom = self.getModel("about.containertest.nt")
        xpath = "*/wiki:revisions/*/rdfs:member/@listID='http://www.w3.org/1999/02/22-rdf-syntax-ns#_1'"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)        
        self.failUnless( res1 )

        xpath = "*[wiki:name='about']/wiki:revisions/*/rdfs:member"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( len(res1)==2 )

        xpath = "*[wiki:name='about']/wiki:revisions/rdf:Seq/rdfs:member/*"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( len(res1)==2 )

        xpath = "*[wiki:name='about']/wiki:revisions/*/rdf:_1"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( len(res1)==0 )

        xpath = "*[wiki:name='about']/wiki:revisions/*/rdfs:member[1]='http://4suite.org/rdf/anonymous/xc52aaabe-6b72-42d1-8772-fcb90303c24b_4'"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( res1 )

        xpath = "*[wiki:name='about']/wiki:revisions/*/rdfs:member[2]='http://4suite.org/rdf/anonymous/x467ce421-1a30-4a2f-9208-0a4b01cd0da1_9'"
        res1 = self.rdfDom.evalXPath( xpath,  self.model1NsMap)
        self.failUnless( res1 )

        self.rdfDom = self.getModel("about.rx.nt")
        triples = '''<test:testrmxml1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#_1> <http://rx4rdf.sf.net/ns/rxml#first> .
        <test:testrmxml1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#_2> <http://rx4rdf.sf.net/ns/rxml#second> .
        <test:testrmxml1> <http://www.w3.org/2000/01/rdf-schema#label> "test containers" .
        '''
        rdfns = u'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        subject = u'test:testrmxml1'
        stmts = [Statement(subject, rdfns+'_1', 'first'),
            Statement(subject, rdfns+'_2', 'second'),
            Statement(subject, u'http://www.w3.org/2000/01/rdf-schema#label',
                'test')]
        self.rdfDom.pushContext('context:test')
        addStatements(self.rdfDom, stmts)
        self.rdfDom.popContext()
        self.failUnless( self.rdfDom.findSubject(subject) )
        
    def testId(self):
        #use this model because all resources appear as an object at least once]
        self.rdfDom = self.getModel(cStringIO.StringIO(self.loopModel) )
        
        loopNsMap = {'loop': 'http://loop.com#'}
        loopNsMap.update(self.model1NsMap)
        
        #we need to add the predicate filter to force the nodeset in doc order so we can compare it
        xpath = "(id(/*/*/loop:*))[true()]"
        res1 = self.rdfDom.evalXPath( xpath, loopNsMap)
        
        res2 = self.rdfDom.evalXPath('/loop:*',  loopNsMap)
        #pprint(( len(res1), len(res2), res1, '2', res2 ))
        self.failUnless(res1 == res2)

    def testrdfdocument(self):
        dataurl = '<RDF:RDF>'
        source = '<foo/>'
        xslStylesheet=r'''<?xml version="1.0" ?>        
        <xsl:stylesheet version="1.0" xmlns:wiki='http://rx4rdf.sf.net/ns/wiki#'
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
        <xsl:output method='text' />
        <xsl:template match="/">
            <xsl:value-of select="rdfdocument('test/about.rx.nt', 'unknown')/*/wiki:name" />
	    </xsl:template>         
        </xsl:stylesheet>
        ''' 
        from Ft.Lib.Uri import OsPathToUri
        from Ft.Xml import InputSource
        from Ft.Xml.Xslt import Processor

        uri = OsPathToUri(os.getcwd())
        STY = InputSource.DefaultFactory.fromString(xslStylesheet,uri)
        SRC = InputSource.DefaultFactory.fromString(source, uri)
        proc = Processor.Processor()
        proc.appendStylesheet(STY)
        result = proc.run(SRC)
        self.failUnless(result == 'about')

    def testDiff(self):
        self.rdfDom = self.getModel("about.rx.nt")
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
        #we've added one non-list statement and changed the first list item (and so 1 add, 1 remove)
        self.failUnless( len(added) == len(reordered) ==
            len(reordered.values()[0][0]) == len(reordered.values()[0][1]) == 1 
            and not len(removed))

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

    def testStatement(self):
        self.failUnless(Statement('s', 'o', 'p') == Statement('s', 'o', 'p'))
        self.failUnless(Statement('s', 'o', 'p','L') == Statement('s', 'o', 'p'))        
        self.failUnless(Statement('s', 'o', 'p',scope='C1') == Statement('s', 'o', 'p', scope='C2'))
        self.failUnless(Statement('s', 'o', 'p','L','C') == Statement('s', 'o', 'p'))
        self.failUnless(not Statement('s', 'o', 'p','L','C') != Statement('s', 'o', 'p'))
        self.failUnless(Statement('s', 'p', 'a') < Statement('s', 'p', 'b'))
    
    def testMerge(self):        
        self.rdfDom = self.getModel("about.rx.nt")
        updateDom = self.getModel("about.diff1.nt")
            
        statements, nodesToRemove = mergeDOM(self.rdfDom, updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])                
        #nothing should have changed
        #pprint((statements, nodesToRemove))
        self.failUnless( not statements and not nodesToRemove )

        self.rdfDom = self.getModel("about.rx.nt")
        updateDom = self.getModel("about.diff2.nt")
        def nr(node): print 'new', node.uri
        updateDom.newResourceTrigger = nr

        #we've added and removed one non-list statement and changed the first list item
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])
        self.failUnless( statements and nodesToRemove )
        #merge in the same updateDom in again, this time there should be no changes
        statements, nodesToRemove = self._mergeAndUpdate(updateDom ,
            ['http://4suite.org/rdf/anonymous/xde614713-e364-4c6c-b37b-62571407221b_2'])

        self.failUnless( not statements and not nodesToRemove )

        self.rdfDom = self.getModel("about.rx.nt")        
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
        '''test RxUpdate (and addTriggers)'''
        self.loadModel = self.loadFtModel #for now this test requires the 4Suite driver
        from rx import RxPathDom
        adds = []    
        def addTrigger(node):
            #we only expect predicate, not resource nodes
            self.failUnless( RxPathDom.looksLikePredicate(node) )
            adds.append(node)
        self.rdfDom = self.getModel("rdfdomtest1.rdf",'rdf')
        self.rdfDom.addTrigger = addTrigger
        
        xupdate=r'''<?xml version="1.0" ?> 
        <xupdate:modifications version="1.0" xmlns:xupdate="http://www.xmldb.org/xupdate" 
        xmlns="http://rx4rdf.sf.net/ns/archive#" 
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:owl='http://www.w3.org/2002/07/owl#'
        >
            <xupdate:append select='/' to-graph='context:1'>
                <Contents rdf:about='urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk='>
                    <content-length>0</content-length>
                    <hasContent />
                </Contents>        
            </xupdate:append>        
        </xupdate:modifications>
        '''               
        applyXUpdate(self.rdfDom,xupdate)
        self.rdfDom.commit()
        #print 'adds', len(adds)
        #pprint([a.stmt for a in adds])
        #2 statements plus type statement and 4 entailments
        self.failUnless(len(adds) == 6) #3

        res1 = self.rdfDom.evalXPath( "get-context('context:1')/*/*")
        #print len(res1)
        #pprint([a.stmt for a in res1])
        self.failUnless(len(res1) == 5) #3
        
        db = self.db
        #pprint( self.db._statements['default'] )
        statements = {'default': [(u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/creator', u'Adam Souzis', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/date', u'2003-04-10', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/identifier', u'http://rx4rdf.sf.net/ns/archive', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/language', u'en', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://purl.org/dc/elements/1.1/title', u'archive instance', u'', u'', u'L'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://rx4rdf.sf.net/ns/archive#imports', u'http://rx4rdf.sf.net/ns/archive', u'', u'', u'R'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', u'http://www.w3.org/2002/07/owl#Ontology', u'', u'', u'R'),
                                  (u'http://rx4rdf.sf.net/ns/archive/archive-example.rdf', u'http://www.w3.org/2002/07/owl#versionInfo', u'v0.1 April 20, 2003', u'', u'', u'L'),
                                  (u'urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk=', u'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', u'http://rx4rdf.sf.net/ns/archive#Contents', u'', u'context:1', u'R'),
                                  (u'urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk=', u'http://rx4rdf.sf.net/ns/archive#content-length', u'0', u'', u'context:1', u'L'),
                                  (u'urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk=', u'http://rx4rdf.sf.net/ns/archive#hasContent', u'', u'', u'context:1', u'L')]}
        currentStmts = [s for s in db._statements['default']
            if not s[4].startswith('context:add') and not s[4].startswith('context:txn')]
        currentStmts.sort()
        print 'XUPDATE ', pprint( currentStmts) 
        expectedStmts = statements['default']
        expectedStmts.sort()
        d = difflib.SequenceMatcher(None,currentStmts, expectedStmts )
        #expectStmts + 2 type Property entailments
        self.failUnless( currentStmts == expectedStmts , 'statements differ: '+`d.get_opcodes()` )

        removes = []    
        def removeTrigger(node):
            #we only expect predicate, not resource nodes
            self.failUnless( RxPathDom.looksLikePredicate(node) )
            removes.append(node)
            
        self.rdfDom.removeTrigger = removeTrigger
        xupdate=r'''<?xml version="1.0" ?> 
        <xupdate:modifications version="1.0" xmlns:xupdate="http://www.xmldb.org/xupdate"
            xmlns="http://rx4rdf.sf.net/ns/archive#" 
            xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>    
            <xupdate:remove to-graph='context:1' select="get-context('context:1')/*/*" />
            <!-- re-add one of the statements -->
            <xupdate:append select='/' to-graph='context:1'>
            <Contents rdf:about='urn:sha:2jmj7l5rSw0yVb/vlWAYkK/YBwk=' />
            </xupdate:append>
        </xupdate:modifications>
        '''               
        applyXUpdate(self.rdfDom,xupdate)
        self.rdfDom.commit()

        #print 'removes', len(removes), [p.stmt for p in removes]        
        self.failUnless(len(removes) == 5) #3 + 2 type Property entailments

        changedStmts = [s for s in db._statements['default']
                        if not s[4].startswith('context:') or s[4].startswith('context:1')]        
        #pprint(changedStmts)
        #print len(changedStmts), len(currentStmts)
        self.failUnless(len(changedStmts) == len(currentStmts) - 2)

    def testXslt2(self):
        self.rdfDom = self.getModel(cStringIO.StringIO(self.model2) )
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
        self.rdfDom = self.getModel(cStringIO.StringIO(self.model2) )
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
        self.rdfDom = self.getModel(cStringIO.StringIO(self.model1) )
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
        #open('testXslt1new.xml', 'wb').write(result)
        #d = difflib.Differ()
        #list(d.compare(result,file('testXslt1.xml').read())) #list of characters, not lines!
        self.failUnless( result == file('testXslt1.xml').read(),'xml output does not match')        

    def testXPathRewrite(self):
        from rx import RxPathQuery
        from Ft.Xml.XPath.Context import Context 

        tests = { '/*' : 'evalRxPathQuery("select 0 from -1 where()")',
                  'foo(/*)' : 'foo(evalRxPathQuery("select 0 from -1 where()"))',
                  '/baz/foo[bar][1=2][0][foo]' : 
                    '''evalRxPathQuery("select 0 from -1 where(select 2 from 0 where((select 1 from 1 where() = u'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'), select 2 from 2 where() in (u'baz')), select 1 from 1 where() in (u'foo'), select 1 from 1 where() with child::bar and (1.0 = 2.0)) with ./child::foo[child::bar][1 = 2][0][child::foo]")''',
                  '/*/*[foo/bar]': 'evalRxPathQuery("select 1 from -1 where(select 1 from 1 where() with child::foo/child::bar)")',                  
                }

        domNode = createDOM(MemModel() )        
        for exp, expected in tests.items():            
            visitor = RxPathQuery.ReplaceRxPathSubExpr(
                        Context(domNode),XPath.Compile(exp))
            #print 'xpw', exp, expected, repr(visitor.resultExpr)
            self.failUnless(repr(visitor.resultExpr) == expected)
            
        
DRIVER = 'Mem'

def profilerRun(testname, testfunc):
    import hotshot, hotshot.stats
    global prof
    prof = hotshot.Profile(testname+".prof")
    try:
        testfunc() #prof.runcall(testfunc)
    except:
        import traceback; traceback.print_exc()
    prof.close()

    stats = hotshot.stats.load(testname+".prof")
    stats.strip_dirs()
    stats.sort_stats('cumulative','time')
    #stats.sort_stats('time','calls')
    stats.print_stats(100)            

if __name__ == '__main__':
    import sys
    from rx import logging
    logging.root.setLevel(logging.DEBUG)
    logging.basicConfig()

    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))    
    if sys.argv.count('--driver'):
        arg = sys.argv.index('--driver')
        DRIVER = sys.argv[arg+1]
        del sys.argv[arg:arg+2]

    profile = sys.argv.count('--prof')
    if profile:
        del sys.argv[sys.argv.index('--prof')]

    try:
        test=sys.argv[sys.argv.index("-r")+1]
    except (IndexError, ValueError):
        unittest.main()
    else:
        tc = RDFDomTestCase(test)
        tc.setUp()
        testfunc = getattr(tc, test)
        if profile:
            profilerRun(test, testfunc)
        else:
            testfunc() #run test


