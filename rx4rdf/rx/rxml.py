"""
    RxML Processor

    todo:
    * support for rdf:dataType and xml:lang on literals
    
    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import sys, re, urllib
from rx import utils, RxPath
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
    returns zml string that can be used as zml representation of a xml infoset text item
    '''
    if '\n' in string or '\r' in string:
        #if odd number of \ before a & or < we need to add an extra \
        #because in zml \& and \< means don't escape the markup character
        string = re.sub(r'((?<=[^\\]\\)\\\\+|(?<=^\\)\\\\+|(?<!\\)\\)(&|<)', r'\1\\\2', string)
        return `string`.lstrip('u')
    else:
        return '`' + string # ` strings in zml are raw (no escape characters)
    
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
            resource = RxPath.generateBnode()
    else:
        #deprecated if the element has an id element treat as the resource URI ref and the element name as the class type
        id = getAttributefromQName(s, rxNSPrefix, 'id')
        if id is not None:
            resource = id
            if not resource:
                resource = RxPath.generateBnode()                            
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
        docFrag = elem.ownerDocument.createDocumentFragment()
        docFrag.childNodes = elem.childNodes
        prettyOutput = StringIO.StringIO()
        import Ft.Xml.Lib.Print
        Ft.Xml.Lib.Print.Print(docFrag, stream=prettyOutput)
        return prettyOutput.getvalue(), RxPath.OBJECT_TYPE_XMLLITERAL 
    else:
        return getResource(elem, rxNSPrefix,nsMap, thisResource)[0], OBJECT_TYPE_RESOURCE

def addList2Model(model, subject, p, listID, scope, getObject = getObject):    
    prevListID = None                
    for child in p.childNodes:
        if child.nodeType == p.COMMENT_NODE:
            continue
        object, objectType = getObject(child)
        if prevListID:
            listID = RxPath.generateBnode()
            model.add( Statement( prevListID, RDF_MS_BASE+'type', RDF_MS_BASE+'List', '', scope, OBJECT_TYPE_RESOURCE))                
            model.add( Statement( prevListID, RDF_MS_BASE+'rest', listID, '', scope, OBJECT_TYPE_RESOURCE))                        
        model.add( Statement( listID, RDF_MS_BASE+'first', object, '', scope, objectType))
        prevListID = listID
    model.add( Statement( listID, RDF_MS_BASE+'type', RDF_MS_BASE+'List', '', scope, OBJECT_TYPE_RESOURCE))                
    model.add( Statement( listID, RDF_MS_BASE+'rest', RDF_MS_BASE+'nil', '', scope, OBJECT_TYPE_RESOURCE))

def addContainer2Model(model, subject, p, listID, scope, getObject, listType):
    assert listType.startsWith('rdf:')
    model.add( Statement( listID, RDF_MS_BASE+'type', RDF_MS_BASE+listType[4:], '', scope, OBJECT_TYPE_RESOURCE))
    ordinal = 1
    for child in p.childNodes:
        if child.nodeType == p.COMMENT_NODE:
            continue
        object, objectType = getObject(child)
        model.add( Statement( listID, RDF_MS_BASE+'_' + str(ordinal), object, '', scope, objectType))
        ordinal += 1
    
def addResource(model, scope, resource, resourceElem, rxNSPrefix,nsMap, thisResource, noStmtIds=False):
    '''
    add the children of a RXML resource element to the model
    '''
    for p in resourceElem.childNodes:
        if p.nodeType != p.ELEMENT_NODE:
            continue
        if matchName(p, rxNSPrefix, 'resource'):
            predicate = p.getAttributeNS(EMPTY_NAMESPACE, 'id')
        elif matchName(p, rxNSPrefix, 'a'): #alias for rdf:type
            predicate = RDF_MS_BASE + 'type'
        else:
            predicate = getURIFromElementName(p, nsMap)
        id = getAttributefromQName(p, rxNSPrefix, RX_STMTID_ATTRIB)
        if not id: id = p.getAttributeNS(EMPTY_NAMESPACE, RX_STMTID_ATTRIB)
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
             or len([c for c in p.childNodes if c.nodeType != p.COMMENT_NODE \
                and c.nodeValue and c.nodeValue.strip()]) > 1:
            #the object of this predicate is a list
            listID = getAttributefromQName(p, rxNSPrefix, 'list')
            if not listID:
                listID = p.getAttributeNS(EMPTY_NAMESPACE, 'list')
            if not listID:
                listID = RxPath.generateBnode()
            model.add( Statement(resource, predicate, listID, id, scope, OBJECT_TYPE_RESOURCE))
            listType = getAttributefromQName(p, rxNSPrefix, 'listType')
            if not listID:
                listType = p.getAttributeNS(EMPTY_NAMESPACE, 'listType')
            getObjectFunc = lambda elem: getObject(elem, rxNSPrefix,nsMap,thisResource)
            if not listType or listType == 'rdf:List':
                addList2Model(model, resource, p, listID, scope, getObjectFunc)
            else:
                addContainer2Model(model, resource, p, listID, scope, getObjectFunc, listType)
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
    '''given a DOM of a RXML document, iterate through it, adding its statements to the specified 4Suite model    
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
                result = rdfdom.evalXPath(s.getAttributeNS(EMPTY_NAMESPACE, 'id'), nsMap)
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
    return nsMap
            
def getRXAsZMLFromNode(resourceNodes, nsMap=None, includeRoot = False,
                         INDENT = '    ', NL = '\n', INITINDENT='', rescomment='',
                          fixUp=None, fixUpPredicate=None):
    '''given a nodeset of RxPathDom nodes, return RXML serialization in ZML markup format'''    
    def getResourceNameFromURI(resNode):
        namespaceURI = resNode.getAttributeNS(RDF_MS_BASE, 'about')
        assert namespaceURI
        prefixURI, rest = RxPath.splitUri(namespaceURI)
        #print >>sys.stderr, 'spl %s %s %s' % (namespaceURI, prefixURI, rest)
        #print revNsMap        
        if not rest:
            printResourceElem = True
        elif revNsMap.has_key(prefixURI):
            printResourceElem = False
        elif resNode.ownerDocument.nsRevMap.has_key(prefixURI):
            prefix = resNode.ownerDocument.nsRevMap[prefixURI]
            nsMap[prefix] = prefixURI
            revNsMap[prefixURI] = prefix
            printResourceElem = False
        else:
            printResourceElem = True
            
        if not printResourceElem: 
            prefix = revNsMap[prefixURI]
            retVal = prefix + ':' + rest
            if fixUp:
                retVal = fixUp % utils.kw2dict(uri=namespaceURI,
                    encodeduri=urllib.quote(namespaceURI), res=retVal)
        else:        
            if fixUp:
                namespaceURI = fixUp % utils.kw2dict(uri=namespaceURI,
                    encodeduri=urllib.quote(namespaceURI), res=namespaceURI)
            retVal = rxPrefix + 'resource id="' + namespaceURI + '"'
        return retVal

    def outputPredicate(predNode, indent):
        if revNsMap.has_key(predNode.namespaceURI):
            prefix = revNsMap[predNode.namespaceURI]
        else:
            prefix = predNode.prefix
            nsMap[prefix] = predNode.namespaceURI
            revNsMap[predNode.namespaceURI] = prefix

        if predNode.namespaceURI == RDF_MS_BASE and predNode.localName == 'type':
            predicateString = rxPrefix + 'a' #use rx:a instead rdf:type
        else:
            predicateString = prefix+':'+predNode.localName

        if fixUpPredicate:
            predURI = RxPath.getURIFromElementName(predNode)
            eu = urllib.quote(predURI)
            predicateString = fixUpPredicate % utils.kw2dict(uri=predURI,
                encodeduri=eu, predicate=predicateString)

        line = indent + predicateString
        
        id = predNode.getAttributeNS(RDF_MS_BASE, 'ID')
        if id:
            line += ' '+rxPrefix+RX_STMTID_ATTRIB+'="' + id + '"'
        
        assert len(predNode.childNodes) == 1        
        if  predNode.childNodes[0].nodeType == predNode.TEXT_NODE:
            line += ': '
            line += doQuote(predNode.childNodes[0].nodeValue) + NL #todo: datatype, xml literal
        else:
            object = predNode.childNodes[0]
            isList = object.isCompound()
            if isList:
                line += ' '+rxPrefix+'list="' + object.getAttributeNS(RDF_MS_BASE, 'about') + '"'
                isList = isList[len(RDF_MS_BASE):]
                if isList != 'List':
                    assert isList in ['Alt', 'Seq', 'Bag'], 'isList should not be ' + isList
                    line += ' '+rxPrefix+'listType="rdf:' + isList + '"'
                    
            line += ': '
            line += NL
            indent += INDENT

            if isList: #is the object a list resource?
                for li in [p.childNodes[0] for p in object.childNodes\
                        if RxPath.getURIFromElementName(p) in [
                            RDF_MS_BASE+'first', RDF_MS_BASE+'li']]:   
                    if li.nodeType == li.TEXT_NODE: #todo: datatype, xml literal
                        line += indent + rxPrefix + RX_LITERALELEM + ':'+ doQuote(li.nodeValue) + NL
                    elif li.nodeType == li.ELEMENT_NODE: 
                        line += indent + getResourceNameFromURI(li) + NL
            else:
                line += indent + getResourceNameFromURI(object) + NL
                
        return line
    if fixUp: #if fixUp we assume we're outputing xml/html not zml
        doQuote = lambda s: '`' + utils.htmlQuote(s)
    else:
        doQuote = quoteString
    if nsMap is None:
      nsMap = { 'bnode': BNODE_BASE,
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
        root + '#?zml markup' + NL
        root += INITINDENT + rxPrefix + 'rx:' + NL        

    if not isinstance(resourceNodes, (type([]), type(()) )):
        resourceNodes = [ resourceNodes ]
    #print resourceNodes
    for resourceNode in resourceNodes:
        #print resourceNode
        line += indent + getResourceNameFromURI(resourceNode) + ':'
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

def rxml2RxPathDOM(path, url=None, debug=0, nsMap = None):
    outputModel, db, nsMap = rx2model(path, url, debug, nsMap)
    #todo: bug! revNsMap doesn't work with 2 prefixes one ns
    revNsMap = dict(map(lambda x: (x[1], x[0]), nsMap.items()) )#uri to prefix namespace map    
    return RxPath.createDOM(RxPath.FtModel(outputModel), revNsMap)

def rx2model(path, url=None, debug=0, nsMap = None):
    '''
    Parse the RxML and returns a 4Suite model containing its statements.
    '''
    from Ft.Lib import Uri
    from Ft.Xml import Domlette

    if url:
        isrc = InputSource.DefaultFactory.fromUri(url)    
    elif isinstance(path, ( type(''), type(u'') )):
        isrc = InputSource.DefaultFactory.fromUri(Uri.OsPathToUri(path))    
    else:
        isrc = InputSource.DefaultFactory.fromStream(path, 'file:')    
    doc = Domlette.NonvalidatingReader.parse(isrc)

    from Ft.Rdf.Drivers import Memory    
    db = Memory.CreateDb('', 'default')
    import Ft.Rdf.Model
    outputModel = Ft.Rdf.Model.Model(db)
    
    nsMap = addRxdom2Model(doc, outputModel, nsMap = nsMap, thisResource='wikiwiki:')
    return outputModel, db, nsMap

def rx2statements(path, url=None, debug=0, nsMap = None):
    '''
    Given a rxml file return a list of tuples like (subject, predicate, object, statement id, scope, objectType)
    '''
    model, db, nsMap = rx2model(path, url, debug, nsMap)
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

def zml2nt(stream=None, contents=None, debug=0, nsMap = None, addRootElement=True):
    from rx import zml
    if stream is not None:
        xml = zml.zml2xml(stream, mixed=False)
    else:
        xml = zml.zmlString2xml(contents, mixed=False)#parse the zml to rx xml
    if addRootElement:
        xml = '<rx:rx>'+ xml+'</rx:rx>'
    return rx2nt(StringIO.StringIO(xml), debug=debug, nsMap = nsMap)

def zml2RDF_XML(stream=None, contents=None, debug=0, nsMap = None, addRootElement=True):
    from rx import zml
    if stream is not None:
        xml = zml.zml2xml(stream, mixed=False)
    else:
        xml = zml.zmlString2xml(contents, mixed=False)#parse the zml to rx xml
    if addRootElement:
        xml = '<rx:rx>'+ xml+'</rx:rx>'

    model, db, nsMap = rx2model(StringIO.StringIO(xml), debug=debug, nsMap = nsMap)

    from Ft.Rdf.Serializers.Dom import Serializer as DomSerializer
    serializer = DomSerializer()
    outdoc = serializer.serialize(model, nsMap = nsMap)
    return outdoc

if __name__ == '__main__':                     
    if '-n' in sys.argv:
        print rx2nt(sys.argv[2])
    elif '-z' in sys.argv:
        print zml2RDF_XML(file(sys.argv[2]))        
    elif '-r' in sys.argv:
        model, db = utils.deserializeRDF( sys.argv[2] )
        nsMap = {
                'bnode': BNODE_BASE,   
               'rx': RX_NS              
            }
        revNsMap = dict( [ (x[1], x[0]) for x in nsMap.items() if x[0] and ':' not in x[0] ])
        rdfDom = RxPath.createDOM(RxPath.FtModel(model), revNsMap)        
        print getRXAsZMLFromNode(rdfDom.childNodes, nsMap)
    else:
        print '''        
usage:
   -n|-r|-z filepath
   -n given an RxML/XML file output RDF in NTriples format
   -z given an RxML/ZML file output RDF in RDF/XML format   
   -r given an RDF file (.rdf, .nt or .mk) convert to RxML/ZML
'''
        sys.exit()

