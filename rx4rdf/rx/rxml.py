"""
    RxML Processor

    todo:
    * support for lists other than rdf:List
    * support for rdf:dataType and xml:lang on literals
    
    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import sys, re
import utils
import RDFDom
from Ft.Xml import EMPTY_NAMESPACE,InputSource,SplitQName
from Ft.Rdf import OBJECT_TYPE_RESOURCE, OBJECT_TYPE_LITERAL, RDF_MS_BASE, BNODE_BASE
from Ft.Rdf.Statement import Statement
try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO
    
RX_NS = 'http://rx4rdf.sf.net/ns/rxml#'
RX_META_DEFAULT = 'default-ns'
RX_BASE_DEFAULT = 'base-default-ns'
RX_LITERALELEM = 'l'
RX_XMLLITERALELEM = 'xml'
RX_STMTID_ATTRIB = 'stmtID'

def getAttributefromQName(elem, prefixes, local):
    for attr in elem.attributes.values():
        if matchName(attr, prefixes, local):
            #support for html style minimalization: return '' instead of value
            if attr.nodeValue == local:
                return ''
            if attr.nodeValue in [prefix + ':' + local for prefix in prefixes if prefix]: 
                return ''
            else:
                return attr.nodeValue
    return None

def getURIFromElementName(elem, nsMap):
    if elem.prefix is None:
        prefix, localName = SplitQName(elem.localName)
    else:
        prefix, localName = elem.prefix, elem.localName
    #print 'pf', prefix
    #print nsMap
    if elem.namespaceURI: #namespace aware node
        u = elem.namespaceURI
        assert u == nsMap.get(prefix, u), 'namespace URI for ' + prefix + ' mismatch xmlns declaration ' + u + ' with rx:prefix ' + nsMap[prefix]
    else:
        u = nsMap[prefix]
        
    if not localName.lstrip('_'): #if empty, must be all '_'s
        localName = localName[:-1] #strip last '_'
    return u + localName

def quoteString(string):
    '''
    returns rhizml string that can be used as rhizml representation of a xml infoset text item
    '''
    if '\n' in string or '\r' in string:
        #if odd number of \ before a & or < we need to add an extra \
        #because in rhizml \& and \< means don't escape the markup character
        string = re.sub(r'((?<=[^\\]\\)\\\\+|(?<=^\\)\\\\+|(?<!\\)\\)(&|<)', r'\1\\\2', string)
        return `string`.lstrip('u')
    else:
        return '`' + string # ` strings in rhizml are raw (no escape characters)
    
def matchName(node, prefixes, local):
    if node.namespaceURI: #namespace aware node 
        return node.namespaceURI in prefixes.values() and node.localName == local
    
    if node.prefix is None:
        prefix, localName = SplitQName(node.localName)
    else:
        prefix, localName = node.prefix, node.localName
    return prefix in prefixes and localName == local
    
def getResource(s, rxNSPrefix, nsMap, thisResource):
    typeName = None
    if matchName(s, rxNSPrefix, 'this-resource'):
        assert thisResource
        resource = thisResource
    elif matchName(s, rxNSPrefix, 'resource'):
        id = s.getAttributeNS(EMPTY_NAMESPACE, 'id')
        resource = id 
        if not id:
            resource = RDFDom.generateBnode()
    else:
        #deprecated if the element has an id element treat as the resource URI ref and the element name as the class type
        id = getAttributefromQName(s, rxNSPrefix, 'id')
        if id is not None:
            resource = id
            if not resource:
                resource = RDFDom.generateBnode()                            
            typeName = getURIFromElementName(s, nsMap)
        else:
            resource = getURIFromElementName(s, nsMap)
    return resource, typeName 
    
def getObject(elem, rxNSPrefix,nsMap, thisResource):
    if elem.nodeType == elem.TEXT_NODE:       
        return elem.nodeValue, OBJECT_TYPE_LITERAL
    elif matchName(elem, rxNSPrefix, RX_LITERALELEM):
        if elem.childNodes:
            literal = elem.childNodes[0].nodeValue
        else:
            literal = ""#if no child we assume its an empty literal
        #todo: support for xml:lang and rdf:datatype
        return literal, OBJECT_TYPE_LITERAL
    elif matchName(elem, rxNSPrefix, RX_XMLLITERALELEM): #xmlliteral #todo: test and fix!! 
        docFrag = RDFDom.DocumentFragment() 
        docFrag.childNodes = elem.childNodes
        prettyOutput = StringIO.StringIO()
        import Ft.Xml.Lib.Print
        Ft.Xml.Lib.Print.Print(docFrag, stream=prettyOutput)
        return prettyOutput.getvalue(), RDFDom.OBJECT_TYPE_XMLLITERAL 
    else:
        return getResource(elem, rxNSPrefix,nsMap, thisResource)[0], OBJECT_TYPE_RESOURCE

def addList2Model(model, subject, p, listID, id, scope, getObject = getObject):    
    prevListID = None                
    for child in p.childNodes:
        if child.nodeType == p.COMMENT_NODE:
            continue
        object, objectType = getObject(child)
        if prevListID:
            listID = RDFDom.generateBnode()
            model.add( Statement( prevListID, RDF_MS_BASE+'type', RDF_MS_BASE+'List', '', scope, OBJECT_TYPE_RESOURCE))                
            model.add( Statement( prevListID, RDF_MS_BASE+'rest', listID, '', scope, OBJECT_TYPE_RESOURCE))                        
        model.add( Statement( listID, RDF_MS_BASE+'first', object, '', scope, objectType))
        prevListID = listID
    model.add( Statement( listID, RDF_MS_BASE+'type', RDF_MS_BASE+'List', '', scope, OBJECT_TYPE_RESOURCE))                
    model.add( Statement( listID, RDF_MS_BASE+'rest', RDF_MS_BASE+'nil', '', scope, OBJECT_TYPE_RESOURCE))
    
def addResource(model, scope, resource, resourceElem, rxNSPrefix,nsMap, thisResource, noStmtIds=False):
    '''
    add the children of a RXML element to the model
    '''
    for p in resourceElem.childNodes:
        if p.nodeType != p.ELEMENT_NODE:
            continue
        if matchName(p, rxNSPrefix, 'resource'):
            predicate = p.getAttributeNS(EMPTY_NAMESPACE, 'id')
        else:
            predicate = getURIFromElementName(p, nsMap)
        id = getAttributefromQName(p, rxNSPrefix, RX_STMTID_ATTRIB)
        if not id: id = getAttributefromQName(p, rxNSPrefix, RX_STMTID_ATTRIB)
        if id and noStmtIds:
            raise RX_STMTID_ATTRIB + ' attribute found at illegal location'
        if not id: id = ''
        object = getAttributefromQName(p, rxNSPrefix, 'res') #this is depreciated
        if object:
            objectType = OBJECT_TYPE_RESOURCE
        elif getAttributefromQName(p, rxNSPrefix, 'list') is not None\
             or getAttributefromQName(p, {'': EMPTY_NAMESPACE}, 'list') is not None\
             or getAttributefromQName(p, rxNSPrefix, 'listType') is not None\
             or getAttributefromQName(p, {'': EMPTY_NAMESPACE}, 'listType') is not None\
             or len([c for c in p.childNodes if c.nodeType != p.COMMENT_NODE and c.nodeValue and c.nodeValue.strip()]) > 1:
            listID = getAttributefromQName(p, rxNSPrefix, 'list')
            if not listID:
                listID = p.getAttributeNS(EMPTY_NAMESPACE, 'list')
            if not listID:
                listID = RDFDom.generateBnode()
            model.add( Statement(resource, predicate, listID, id, scope, OBJECT_TYPE_RESOURCE))
            addList2Model(model, resource, p, listID, id, scope,
                          lambda elem: getObject(elem, rxNSPrefix,nsMap,thisResource))
            #todo support container listTypes (bag, etc.)
            continue
        elif not p.childNodes: #if no child we assume its an empty literal
            object, objectType = "", OBJECT_TYPE_LITERAL            
        else: #object is a a literal 
            object, objectType = getObject(p.childNodes[0],rxNSPrefix,nsMap, thisResource)
        #print >>sys.stderr, 'adding ', repr(resource), repr(predicate), object, 
        model.add( Statement( resource, predicate, object, id, scope, objectType))
        #for o, oElem in objectResources: #add striping? ok, except for typename -- will add over and over
        #    addResources(model, scope, o, oElem, rxNSPrefix,nsMap,thisResource)

#todo special handling for bNode prefix (either in or out or both)
def addRxdom2Model(rootNode, model, nsMap = None, rdfdom = None, thisResource = None,  scope = ''):
    '''given a DOM of a RXML document, iterate through it, adding its statements to the specified output RDF model    
    Note: no checks if the statement is already in the model
    '''
    if nsMap is None:
        nsMap = { None : RX_NS, 'rx' : RX_NS }
    #todo: bug! revNsMap doesn't work with 2 prefixes one ns
    #revNsMap = dict(map(lambda x: (x[1], x[0]), nsMap.items()) )#reverse namespace map
    #rxNSPrefix = revNsMap[RX_NS]
    rxNSPrefix = [x[0] for x in nsMap.items() if x[1] == RX_NS]
    if not rxNSPrefix: #if RX_NS is missing from the nsMap add the 'rx' prefix if not already specified
        if not nsMap.get('rx'):
            nsMap['rx'] = RX_NS
            rxNSPrefix = ['rx']
    if not nsMap.get('rdf'):
        nsMap['rdf'] = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
    if not nsMap.get('rdfs'):
        nsMap['rdfs'] = 'http://www.w3.org/2000/01/rdf-schema#'

    for s in rootNode.childNodes:
        if s.nodeType != s.ELEMENT_NODE:
            continue
        if matchName(s, rxNSPrefix, 'rx'): #optional root element
            rootNode = s
        else:
            break
        
    for s in rootNode.childNodes:
        if s.nodeType != s.ELEMENT_NODE:
            continue
        if matchName(s, rxNSPrefix, 'prefixes'):
            for nsElem in s.childNodes:
                if nsElem.nodeType != nsElem.ELEMENT_NODE:
                    continue                
                if matchName(nsElem, rxNSPrefix, RX_META_DEFAULT):
                    ns = None#'' 
                else:
                    ns = nsElem.localName
                from Ft.Xml.XPath.Conversions import StringValue
                nsMap[ns] = StringValue(nsElem).strip()
                #revNsMap[nsElem.stringValue] = ns
            continue
        elif matchName(s, rxNSPrefix, 'res-query'):
            assert rdfdom
            if rdfdom:
                result = RDFDom.evalXPath(rdfdom, s.getAttributeNS(EMPTY_NAMESPACE, 'id'), nsMap)
                if isinstance(result, ( type(''), type(u'')) ):
                    resources = [ result ]
                else:
                    resources = map(lambda x: x.getAttributeNS(RDF_MS_BASE, 'about'), result)
            else:                
                resources = []
        else:
            resource, typeName = getResource(s, rxNSPrefix, nsMap, thisResource)
            if typeName:
                model.add( Statement( resource, RDF_MS_BASE + 'type', typeName, '', scope, OBJECT_TYPE_RESOURCE))                
            resources = [ resource ]
        for resource in resources:
            addResource(model, scope, resource, s, rxNSPrefix,nsMap,thisResource, len(resources) > 1)        
        
def getResourceNameFromURI(namespaceURI, revNsMap, rxPrefix):
    prefixURI, rest = RDFDom.splitUri(namespaceURI)
    #print 'spl %s %s %s' % (namespaceURI, prefixURI, rest)
    #print revNsMap
    if rest and revNsMap.has_key(prefixURI): 
        prefix = revNsMap[prefixURI]
        return prefix + ':' + rest
    else:
        return rxPrefix + 'resource id="' + namespaceURI + '"'

def getRXAsRhizmlFromNode(resourceNodes, nsMap=None, includeRoot = False,
                         INDENT = '    ', NL = '\n', INITINDENT=' ', rescomment=''):
    '''given a nodeset of RDFDom nodes, return RXML serialization in Rhizml markup format'''    
    def outputPredicate(predNode, indent):
        if revNsMap.has_key(predNode.namespaceURI):
            prefix = revNsMap[predNode.namespaceURI]
        else:
            prefix = predNode.prefix
            nsMap[prefix] = predNode.namespaceURI
            revNsMap[predNode.namespaceURI] = prefix

        line = indent + prefix+':'+predNode.localName
        
        id = predNode.getAttributeNS(RDF_MS_BASE, 'ID')
        if id:
            line += ' '+rxPrefix+RX_STMTID_ATTRIB+'="' + id + '"'
        listID = predNode.getAttributeNS(None, 'listID')
        if listID:
            line += ' '+rxPrefix+'list="' + listID + '"'
        line += ': '
        if not predNode.childNodes:
            return line
        if predNode.childNodes[0].nodeType == predNode.COMMENT_NODE:
            line += ';' + predNode.childNodes[0].nodeValue + NL
        elif len(predNode.childNodes) == 1 and predNode.childNodes[0].nodeType == predNode.TEXT_NODE:
            line += quoteString(predNode.childNodes[0].nodeValue) + NL #todo: datatype, xml literal
        else:
            line += NL
            indent += INDENT
            for c in predNode.childNodes:
                if c.nodeType == c.TEXT_NODE: #todo: datatype, xml literal
                    line += indent + rxPrefix + RX_LITERALELEM + ':'+ quoteString(c.nodeValue) + NL
                elif c.nodeType == c.COMMENT_NODE:
                    line += indent + ';' + c.nodeValue + NL
                elif c.nodeType == c.ELEMENT_NODE: 
                    line += indent + getResourceNameFromURI(c.getAttributeNS(RDF_MS_BASE, 'about'),revNsMap,rxPrefix) + NL
        return line

    if nsMap is None:
      nsMap = { 'bNode': BNODE_BASE,
                RX_META_DEFAULT : RX_NS
                }
    revNsMap = dict( [ (x[1], x[0]) for x in nsMap.items() if x[0] and ':' not in x[0] and x[0] not in [RX_META_DEFAULT, RX_BASE_DEFAULT] ])
    if nsMap.has_key(RX_META_DEFAULT):
        revNsMap[ nsMap[RX_META_DEFAULT] ] = ''
        
    rxPrefix = revNsMap.get(RX_NS, 'rx')
    if rxPrefix: rxPrefix+=':'
    
    indent = INITINDENT    
    line = prefixes = root = ''
    
    if includeRoot:
        indent += INDENT
        root = INITINDENT + rxPrefix + 'rx:' + NL        

    #if not isinstance(resourceNodes, type([])):
    #    resourceNodes = [ resourceNodes ]
    #print resourceNodes
    for resourceNode in resourceNodes:
        #print resourceNode
        line += indent + getResourceNameFromURI(
            resourceNode.getAttributeNS(RDF_MS_BASE, 'about'),revNsMap,rxPrefix) + ':'
        if rescomment:
            line += ' ;'+ rescomment
        line += NL
        for p in resourceNode.childNodes:
            line += outputPredicate(p, indent + INDENT)
        line += NL

    if nsMap:
        prefixes = indent + rxPrefix + 'prefixes:' + NL
        for prefix, ns in nsMap.items():
            prefixes += indent + INDENT + prefix + ': `' + ns + NL
        prefixes += NL

    return root + prefixes + line

def rx2model(path, url=None, debug=0, nsMap = None):    
    from Ft.Lib import Uri
    from Ft.Xml import Domlette

    if url:
        isrc = InputSource.DefaultFactory.fromUri(url)    
    elif isinstance(path, ( type(''), type(u'') )):
        isrc = InputSource.DefaultFactory.fromUri(Uri.OsPathToUri(path))    
    else:
        isrc = InputSource.DefaultFactory.fromStream(path)    
    doc = Domlette.NonvalidatingReader.parse(isrc)

    from Ft.Rdf.Drivers import Memory    
    db = Memory.CreateDb('', 'default')
    import Ft.Rdf.Model
    outputModel = Ft.Rdf.Model.Model(db)
    
    addRxdom2Model(doc, outputModel, nsMap = nsMap, thisResource='wikiwiki:')
    return outputModel, db

def rx2statements(path, url=None, debug=0, nsMap = None):
    '''
    given a rxml file return a list of tuples like (subject, predicate, object, statement id, scope, objectType)
    '''
    model, db = rx2model(path, url, debug, nsMap)
    stmts = db._statements['default'] #get statements directly, avoid copying list
    return stmts
    
def rx2nt(path, url=None, debug=0, nsMap = None):
    '''
    given a rxml file return a string of N-triples
    path is either a stream-like object or a string that is file path
    '''
    stmts = rx2statements(path, url, debug,nsMap)
    outputfile = StringIO.StringIO()
    utils.writeTriples(stmts, outputfile)
    return outputfile.getvalue()

def rhizml2nt(stream=None, contents=None, debug=0, nsMap = None, addRootElement=True):
    import rhizml
    if stream is not None:
        xml = rhizml.rhizml2xml(stream)
    else:
        xml = rhizml.rhizmlString2xml(contents)#parse the rxity to rx xml
    if addRootElement:
        xml = '<rx:rx>'+ xml+'</rx:rx>'
    return rx2nt(StringIO.StringIO(xml), debug=debug, nsMap = nsMap)
            
if __name__ == '__main__':                     
    if len(sys.argv) < 2:
        print '''usage:
   -n|-r filepath
   -n given an RxML/XML file output RDF in NTriples format
   -r given an RDF file (.rdf, .nt or .mk) convert to RxML/RhizML
'''
        sys.exit()
    toNT = '-n' in sys.argv
    if toNT: sys.argv.remove('-n')    
    if not toNT:
        print rx2nt(sys.argv[1])
    else:
        model, db = utils.deserializeRDF( sys.argv[1] )
        nsMap = {
                'bNode': BNODE_BASE,   
               'rx': RX_NS              
            }
        revNsMap = dict( [ (x[1], x[0]) for x in nsMap.items() if x[0] and ':' not in x[0] ])
        rdfDom = RDFDom.RDFDoc(model, revNsMap)        
        print getRXAsRhizmlFromNode(rdfDom.childNodes, nsMap)
        