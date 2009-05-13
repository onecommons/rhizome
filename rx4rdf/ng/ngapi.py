'''
    Top level apis for ng
    
 * implement minimal API for note archiving app, implement refactor just for this API
   * (re)addContent(source, shreddedRDF)
   * updateMetadata(add, remove)
   * sync (should just be a special case of readdContent? or anti-entropy algorithm?)
   * search/query (over context?) - sparql for prototype, return sjson (extend Res class?)
   * serve - wsgi implements endpoints

TODO: refactor with no dependency on (in order)
 * RxPath/RxSLT expressions
 * raccoon
 * FT 
RxDom OK for small documents (e.g. shredding)

* Ft dependencies:
 * RxPath (create FTStub with NumberValue, StringValue, XPath.Context, etc.)? 
 * RxPathUtils.parseRDFFromURI (Uri, ImportSource)
 * RxPathUtils._sessionBNodeUUID (fixed using uuid.uuid4() -- only for >= 2.5)
 * RxPathGraph: RxPath.Id, String/NumberValue, xpath extension functions
 * RxPathDOM: SplitQName, XML_NAMESPACE [x;]
 * DOMStore: applyXslt, applyXPath (subclass)
 * UriResolver: UriResolver
* RxDom dependencies:
 * RxPathDom.__init__: graphManager.setDoc()
   * doc.findSubject(stmt.subject)
   * subjectNode.findPredicate(stmt)
   * subjectNode.removeChild(predicateNode)
   * doc.getKey()
   * docTemplate.nsRevMap, docTemplate.modelUri, docTemplate.schemaClass

 * references to DomStore.dom:
   * raccoon.updateDom, updateStoreWithRDF
     * RxPath.addStatements(doc, stmts)
       * rdfDom.findSubject(stmt.subject) or rdfDom.addResource(stmt.subject)
       * subject.addStatement(stmt, listid)

   * OK: __store in mapToXPathVars
   * transactions.py: RaccoonTransactionService
   
       
    Copyright (c) 2009 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
'''

class api(object):

    def load(self):
        '''
        Load the database
        '''

    def updateMetadata(self, add, remove):
        '''
        add/remove statements
        '''

    def serve(self):
        '''
        wsgi endpoint
        '''
    
def test():
    pass