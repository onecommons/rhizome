'''
    An XML Dom Implementation that conforms to RxPath.
    Loads and saves the Dom to a RDF model.
    
    Todo:
    * rdf collections aren't implemented as per the spec.
    (currently predicate@listID/<children> instead of predicate/rdf:List/rdf:first@listID/<children>
    * rdf containers aren't implemented (rdf:Seq/rdf:li/<children>) -- currently the default: rdf:Seq/rdf:_<n>/object
    * descendant axes

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
'''
from __future__ import generators

from DomTree import *
from Ft.Xml import SplitQName, XMLNS_NAMESPACE, InputSource
from Ft.Rdf import OBJECT_TYPE_RESOURCE, OBJECT_TYPE_LITERAL, Util, BNODE_BASE, BNODE_BASE_LEN,RDF_MS_BASE
from Ft.Rdf.Statement import Statement
import Ft
from utils import generateBnode
from Ft.Xml import XPath
import types

#from Ft.Rdf import RDF_MS_BASE -- for some reason we need this to be unicode for the xslt engine:
RDF_MS_BASE=u'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
OBJECT_TYPE_XMLLITERAL='http://www.w3.org/1999/02/22-rdf-syntax-ns#XMLLiteral'

def splitUri(uri):
    '''
    Split an URI into a (namespaceURI, name) pair suitable for creating a QName with
    Returns (uri, '') if it can't
    '''
    if uri.startswith(BNODE_BASE):  
        index = BNODE_BASE_LEN-1
    else:
        index = uri.rfind('#')
    if index == -1:        
        index = uri.rfind('/')
        if index == -1:
            index = uri.rfind(':')
            if index == -1:
                return (uri, '')
    if not uri[index+1:].replace('_', '0').replace('.', '0').replace('-', '0').isalnum():
        return (uri, '')
    local = uri[index+1:]
    if local and not local.lstrip('_'): #must be all '_'s
        local += '_' #add one more
    return (uri[:index+1], local)

def elementNamesFromURI(uri, nsMap):
    predNs, predLocal  = splitUri(uri)
    if not predLocal: # no "#" or nothing after the "#" 
        predLocal = u'_'
    if nsMap.has_key(predNs):
        prefix = nsMap[predNs]
    else:
        prefix = u'ns' + str(len(nsMap.keys()))
        nsMap[predNs] = prefix
    return prefix+':'+predLocal, predNs, prefix, predLocal

def getURIFromElementName(elem):
    u = elem.namespaceURI
    local = elem.localName 
    if not local.lstrip('_'): #must be all '_'s
        local = local[:-1] #strip last '_'
    return u + local

class SubjectElement(Element):
    stringValue = ''
    
    def __init__(self):
        Element.__init__(self, u'rdf:Description', RDF_MS_BASE, u'rdf', u'Description')
                
    def setType(self, typeUri, nsMap):
        if self.prefix == 'rdf' and self.localName == 'Description':
            qname, self.namespaceURI, self.prefix, self.localName = elementNamesFromURI(typeUri, nsMap)
            self.nodeName = self.tagName = qname
            return True
        else:
            return False #already set -- probably has multiple types

    def cmpSiblingOrder(self, other):
        return cmp( self.getAttributeNS(RDF_MS_BASE, 'about'), other.getAttributeNS(RDF_MS_BASE, 'about'))

    def preAddHook(self, newChild):
        #todo ensure newChild is a PredicateElement (incl. handling recursive elements)
        if self.parentNode == self.rootNode and self.rootNode.model:
            id = newChild.getAttributeNS(RDF_MS_BASE, 'ID')
            if not id: id = ''
            assert newChild.childNodes[0], "predicate element must have object childNode"
            object, objectType = getObject(newChild.childNodes[0])
            #todo: handle rdf:lists -- check if newChild.hasAttributeNS(rxpath, 'list')
            s = self.stringValue
            p = getURIFromElementName(newChild)
            self.rootNode.model.add( Statement( s, p, object, id, '', objectType))            
        return newChild

    def preRemoveHook(self, newChild):
        assert isinstance(newChild, PredicateElement)
        if self.parentNode == self.rootNode and self.rootNode.model:
            s = self.stringValue
            p = getURIFromElementName(newChild)
            o, objectType = getObject(newChild.childNodes[0]) #todo handle lists
            self.rootNode.model.remove(s, p, o)

    def matchName(self, namespaceURI, local):
        if self.namespaceURI == namespaceURI and self.localName == local:
            return True
        #support for multiple rdf:types:
        types = [ n.childNodes[0] for n in self.childNodes\
                  if n.nodeType == Node.ELEMENT_NODE and n.localName == 'type' and n.namespaceURI == RDF_MS_BASE]
                  #note: doesn't support subproperties of rdf:type
        for type in types:
            if local == '*' and type.startswith(namespaceURI):
                return True
            elif type == namespaceURI + local:
                return True
        return False
        
    def getAttributeNS(self, namespaceURI, localName):
        v = super(SubjectElement,self).getAttributeNS(namespaceURI, localName)
        if not v and (namespaceURI == RDF_MS_BASE and localName == 'about'):
            assert self.rootNode.model
            bNodeUri = unicode(generateBnode())
            self.setAttributeNS(RDF_MS_BASE, u'rdf:about', bNodeUri)
            return bNodeUri
        else:
            return v

    def _set_attribute(self, key, attr):
        if key != (RDF_MS_BASE, 'about'):
            raise 'only can set rdf:about attribute here'
        self.stringValue = attr.nodeValue
        return super(SubjectElement,self)._set_attribute(key,attr)

    def __repr__(self):
        if len(self.attributes):
            about = self.attributes.values()[0]
        else:
            about = '??'
        return "<pResourceElem at %X: %s, <%s>, %d children>" % (
            id(self),
            repr(self.nodeName),
            about,
            len(self.childNodes)
            )
    
#/s/p/o    /p   /o     /p
#/s/p/r(s)/r(p)/r(r(s))/r(r(r(r(p))

#todo note: subject.parentNode will return root(document) not none

class PredicateElement(Element):
    def __init__(self, predicateUri, nsMap):
        qname, self.namespaceURI, self.prefix, self.localName = elementNamesFromURI(predicateUri, nsMap)
        self.nodeName = self.tagName = qname
        self.attributes = {}
        self.childNodes = []

    #work around for a 'bug' in _conversions.c, unlike Conversion.py (and object_to_string),
    #node_descendants() doesn't check for a stringvalue attribute
    def __getattr__(self, name):
        if name == 'stringValue':
            val = ''
            for n in self.childNodes:
                if hasattr(n, 'stringValue'):
                    val += n.stringValue
                else:
                    assert n.nodeType == Node.TEXT_NODE
                    val += n.data
            return val
        else:
            return super(PredicateElement, self).__getattr__(name)

    def cmpSiblingOrder(self, other):
        return cmp( getURIFromElementName(self), getURIFromElementName(other))
                
    def preAddHook(self, newChild):
        #ensure newChild is a RefElement or text        
        if self.rootNode.model:
            #if we're connected to the doc sync with the underlying model:
            #todo: this doesn't work if parentNode is a recursiveElement -- is that possible? 
            if self.parentNode and self.parentNode.parentNode == self.rootNode:
                s = self.parentNode.stringValue
                p = getURIFromElementName(self)
                o, oType = getObject(self.childNodes[0])
                self.rootNode.model.remove(s, p, o)
                
                id = self.getAttributeNS(RDF_MS_BASE, 'ID')
                if not id: id = ''
                object, objectType = getObject(newChild)
                #todo: handle rdf:lists -- check if self.hasAttributeNS(rxpath, 'list')
                self.model.add( Statement( s, p, object, id, '', objectType))
        return newChild
    
    def preRemoveHook(self,oldchild):
        #todo: what about rdf:list and removing just one member?
        raise 'do not remove the object node, you need to remove the whole predicate and add a new one'
            
    def _set_attribute(self, key, attr):
        if key not in [(RDF_MS_BASE, 'ID'), (None, u'listID')]:
            raise 'only can set rdf:ID or listID attribute here'
        return super(PredicateElement,self)._set_attribute(key,attr)
    
class RefAttrDict(dict):
    def __init__(self, parent, attributes):
        self.parent = parent
        self.attributes = attributes

    def __setattr__(self, name, value):
        if name in ['parent', 'attributes']:
            super(RefAttrDict, self).__setattr__(name, value)
        else:
            setattr(self.attributes, name, value) #raise AttributeError('you can not modify a RefElement element')

    def __getattribute__(self, name):
        #print 'attr attr ', name
        if name in ['parent', 'attributes', 'values', 'items','__class__', '__dict__']:
            return super(RefAttrDict, self).__getattribute__(name)
        else:
            return getattr(self.attributes, name)

    #special methods don't seem to work with __getattribute__ -- must be defined
    def __len__(self): return len(self.attributes)
    def __repr__(self): return repr(self.attributes)
    def __cmp__(self, dict): return cmp(self.attributes, dict)
    def __contains__(self, key): return key in self.attributes
    def __setitem__(self, key, item): self.attributes[key] = item
    def __delitem__(self, key): del self.attributes[key]
    
    def values(self):
        return map(lambda x: newRefElement(self.parent, x), self.attributes.values() )

    def items(self):
        return map(lambda x: (x[0], newRefElement(self.parent, x[1])), self.attributes.items() )
            
    def __getitem__(self, key):
        return newRefElement(self.parent, self.attributes.__getitem__(key))
        
    #todo! the rest of the dict methods that can retrieve values: popitem, iteritems, itervalues, (and __iter__?)

from UserList import UserList
class RefList(UserList, object): #RefList(UserList, list) doesn't work for some reason
    '''
    wraps an Element's childnode list, making it appear to have RefElements
    as children but allowing the underlying list list to be modified.
    '''
    def __init__(self, parent, aliaslist):
        self.parent = parent
        self.data = aliaslist
        
    def __getitem__(self, i): return _wrap(self.data[i], self.parent)
    
    def __getslice__(self, i, j):
        return map(lambda x: _wrap(x, self.parent), self.data.__getslice__(i,j) )
        
    def pop(self, i=-1): return _wrap(self.data.pop(i), self.parent)

    def index(self, item):
        return [_wrap(x, self.parent) for x in self.data].index(item)
            
    def remove(self, item):
         del self.data[self.index(item)]
        
    def count(self, item):
        return [_wrap(x, self.parent) for x in self.data].count(item)
    
    def __contains__(self, item):
        return item in [_wrap(x, self.parent) for x in self.data]
            
class RefElement(object):
    def __init__(self, parent, aliasElement):
        self.parentNode = parent
        self.alias = aliasElement

    def __setattr__(self, name, value):
        if name in ['parentNode', 'alias']:
            super(RefElement, self).__setattr__(name, value)
        elif name in  ['nextSibling', 'previousSibling'] and isinstance(self.alias, SubjectElement):
            super(RefElement, self).__setattr__(name, value)
        else:
            setattr(self.alias, name, value) #raise AttributeError('you can not modify a RefElement element')

    def __repr__(self):
        return '<R! ' + repr(self.alias) + ' >'

    def __eq__(self, other):        
        if isinstance(other, RefElement):
#            print>>sys.stderr, 'eq ', self.parentNode, other.parentNode, self.alias, other.alias 
            return self.parentNode == other.parentNode and self.alias == other.alias 
#        elif isinstance(other, Node):
#            print>>sys.stderr, 'eq ', self.alias, other
#            return self.parentNode == other.parentNode and self.alias == other            
        else:
#            if self.alias == other:
#                print>>sys.stderr, 'eq ', self, other 
#            return self.alias == other
            return False

    def __hash__(self):
        return hash(self.parentNode) ^ hash(self.alias)
    
    def getSafeChildNodes(self, stopNode):
        alias = self.alias
        parent = self.parentNode
        while parent and parent != stopNode:
            if parent == alias: #circular reference! -- stop
                return []
            parent = parent.parentNode
        return RefList(self, alias.childNodes)
                    
    def __getattribute__(self, name):
        if name in ['parentNode', '__repr__','__eq__', 'docIndex', 'getSafeChildNodes']:
            return super(RefElement, self).__getattribute__(name)        
        if name == 'alias':            
            alias = super(RefElement, self).__getattribute__(name)
            if isinstance(alias, RefElement):
                return alias.alias
            else:
                return alias

        if name == 'ownerElement': #for when our alias is an Attr
            return self.parentNode

        alias = super(RefElement, self).__getattribute__('alias')
                    
        if name == 'childNodes':
            #return map(lambda x: _wrap(x, self), alias.childNodes)
            if alias.ownerDocument.globalRecurseCheck:
                return self.getSafeChildNodes(alias.rootNode)
            else:
                return RefList(self, alias.childNodes)
        elif name == 'firstChild' or name == 'lastChild':
            return _wrap(getattr(alias, name), self)
        elif name == 'nextSibling' or name == 'previousSibling':
            if isinstance(alias, SubjectElement):
                return super(RefElement, self).__getattribute__(name)
            else:
                return _wrap(getattr(alias, name), self.parentNode)
        elif name == 'attributes':
            return RefAttrDict(self, alias.attributes)
        else:
            attr = getattr(alias, name)
            if isinstance(attr, types.MethodType) and attr.im_self is alias: #attr is a method, return ours  
                return super(RefElement, self).__getattribute__(name)
            else:
                return attr

def _wrap(x, parent):
    if isinstance(x, RefElement):
        if x.parentNode is parent:
            return x
        else:
            return newRefElement(parent, x.alias)
    elif isinstance(x, Element):
        return newRefElement(parent, x)
    else:
        return x

classCache = {}
def newRefElement(parent, aliasElement):    
    global classCache
    klass = type(aliasElement)
    refClass = classCache.get(klass)
    if not refClass:
        class x(RefElement, klass):
            pass
        classCache[klass] = x
        refClass = x
    return refClass(parent, aliasElement)
    
class RDFDoc(Document):
    def __init__(self, model, nsMap):
        Document.__init__(self, model.uri)
        self.ownerDocument = self #bug in dom implementation?
        nsMap[RDF_MS_BASE] = u'rdf'
        self.model = None
        self.modelToTree(model, nsMap)
        self.model = model
        self.globalRecurseCheck = False
    
    def preAddHook(self, newChild):
        #ensure newChild subject is not already a child (if so, make sure element names match and merge children instead)
        #if the subject doesn't have an rdf:about or has a rdf:bNode attribute generate a bNode uri
        #if self.model: add child statements to model
        if not isinstance(newChild, SubjectElement):
            if isinstance(newChild, RefElement):
                newChild = newChild.alias
                assert isinstance(newChild, SubjectElement)
                return newChild
            else:
                assert type(newChild)==Element
                s = SubjectElement()
                s.nodeName = s.tagName = newChild.nodeName
                s.namespaceURI = newChild.namespaceURI
                s.prefix = newChild.prefix
                s.localName = newChild.localName    
                self.__finishCreatingElement(s)
                assert newChild.getAttributeNS(RDF_MS_BASE, 'about') is not None
                s.setAttributeNS(RDF_MS_BASE, u'rdf:about', newChild.getAttributeNS(RDF_MS_BASE, 'about'))
                return s            
        else:
            return newChild

    def preRemoveHook(self, newChild):
        assert isinstance(newChild, SubjectElement)
        if not self.model:
            return 
        s = newChild.stringValue
        for pred in newChild.childNodes:
            p = getURIFromElementName(pred)
            o, objectType = getObject(pred.childNodes[0]) #todo handle lists
            self.model.remove(s, p, o)
                        
    def createPredicateElement(self, predicateUri, object, objectType, statementUri, nsMap, scope=''):        
        element = PredicateElement(predicateUri, nsMap)
        self.__finishCreatingElement(element)
        if statementUri:
            element.setAttributeNS(RDF_MS_BASE, u'rdf:ID', statementUri )
        if objectType != OBJECT_TYPE_RESOURCE:
            element.appendChild(self.createTextNode(object) ) 
        else:
            element.object = object
        element.scope = scope
        return element
        
    def createSubjectElement(self, subjectUri):
        element = SubjectElement()
        self.__finishCreatingElement(element)
        element.setAttributeNS(RDF_MS_BASE, u'rdf:about', subjectUri)
        return element
        
    def __finishCreatingElement(self, element):
        element.ownerDocument = element.rootNode = self
        element.baseURI = self.baseURI
        #element.docIndex = self.nextIndex
        self.nextIndex += 3  # room for namespace and attribute nodes
        return element
    
    def modelToTree(self, model, nsMap):
        
        def addList(id, first, firstType, next):
            tpl = listResources.setdefault( id, [None, None, None] )        
            tpl[0] = tpl[0] or first
            tpl[1] = tpl[1] or firstType
            tpl[2] = tpl[2] or next
                
        def getlist(start):
            list = []
            next = start
            while 1:
                object, objectType, next = listResources[next]
                if object is not None: #this will be true in the case of an empty list
                    list.append( (object, objectType, next) )
                if next == RDF_MS_BASE+'nil':
                    break
            return list

        def addObjectResource(p, o):
           element = resources.get(o)
           if not element:                            
               element = self.createSubjectElement( o )
               resources[o] = element
           p.appendChild( newRefElement(None, element) )
        
        stmts = model.complete(None, None, None)
        stmts = map(lambda s: (unicode(s.subject), unicode(s.predicate), unicode(s.object), s.objectType, unicode(s.uri), s.scope ), stmts)
        stmts.sort() #todo: this doesn't handle lists correctly 
        resources = {}
        listResources = {}
        lastResource = None
        lastUri = ""
        for i in stmts:
            #special handling for rdf:List resources (rdf:parseType='Collection')
            if i[1] == RDF_MS_BASE+'first':
                addList(i[0], i[2], i[3], None)
                continue
            elif i[1] == RDF_MS_BASE+'rest':
                addList(i[0], None, None, i[2])                     
                continue            
            elif i[1] == RDF_MS_BASE+'type' and i[2] == RDF_MS_BASE+'List':                
                continue

            if i[0] != lastUri:
                lastUri = i[0]
                lastResource = self.createSubjectElement(lastUri)
                resources[ lastUri ] = lastResource
            if i[1] == RDF_MS_BASE+'type': #note we don't handle equivalent properties or subproperties of rdf:type
                lastResource.setType(i[2], nsMap) 
            lastResource.appendChild( self.createPredicateElement(i[1], i[2], i[3], i[4], nsMap, i[5]) )
            #todo place rdf:ID URI in the tree and add reified statements
            
        #now iterate through all the predicates
        #   1. replacing its object with the subject element if found, or
        #   2. looking for orphan object resources that need to be added
        #   3. also, if the object is a rdf:List add multiple children (in the proper order), following the rules above
        for s in resources.values():
            for p in s.childNodes:                
                if hasattr(p,'object'):
                   o = p.object
                   if listResources.get(o):
                       p.setAttributeNS(None, u'listID', o)
                       for object, objectType, next in getlist(o):
                           if objectType != OBJECT_TYPE_RESOURCE:
                               p.appendChild(self.createTextNode(object) )
                           else:
                               addObjectResource(p, object)
                   else:
                       addObjectResource(p, o)
                   del p.object 
        #sort by uri and add subject elements to root in that order
        #print resources
        resourceUris = resources.keys()
        resourceUris.sort()
        for u in resourceUris:                        
            self.appendChild( resources[u] )

def getObject(elem):
    if elem.nodeType == Node.TEXT_NODE:
        return elem.nodeValue, OBJECT_TYPE_LITERAL
    else:
        assert elem.getAttributeNS(RDF_MS_BASE, 'about')
        return elem.getAttributeNS(RDF_MS_BASE, 'about'), OBJECT_TYPE_RESOURCE

def addList2Model(model, subject, p, listID, id, scope, getObject = getObject):    
    prevListID = None                
    for child in p.childNodes:
        if child.nodeType == Node.COMMENT_NODE:
            continue
        object, objectType = getObject(child)
        if prevListID:
            listID = generateBnode()
            model.add( Statement( prevListID, RDF_MS_BASE+'type', RDF_MS_BASE+'List', '', scope, OBJECT_TYPE_RESOURCE))                
            model.add( Statement( prevListID, RDF_MS_BASE+'rest', listID, '', scope, OBJECT_TYPE_RESOURCE))                        
        model.add( Statement( listID, RDF_MS_BASE+'first', object, '', scope, objectType))
        prevListID = listID
    model.add( Statement( listID, RDF_MS_BASE+'type', RDF_MS_BASE+'List', '', scope, OBJECT_TYPE_RESOURCE))                
    model.add( Statement( listID, RDF_MS_BASE+'rest', RDF_MS_BASE+'nil', '', scope, OBJECT_TYPE_RESOURCE))
    
def treeToModel(rootNode, model, scopeFilter=None):
    '''Convert an arbitrary xml tree that conforms to our rdf mapping.
    For example, a RDFDoc that has been modified by XUpdate.
    '''
    for s in rootNode.childNodes:        
        subject = s.getAttributeNS(RDF_MS_BASE, 'about')
        #for the case where the rdfdom has been manually modified:
        if not subject:
            print "warning no rdf:about", s
            subject = generateBnode()
        if not isinstance(s, SubjectElement) and not (s.namespaceURI == RDF_MS_BASE and s.localName == 'Description'):
            implicitType = getURIFromElementName(s)
            model.add( Statement( subject, RDF_MS_BASE + 'type', implicitType, '', scopeFilter or '', OBJECT_TYPE_RESOURCE))
        else:
            implicitType = None
            
        for p in s.childNodes:
            scope = getattr(p, 'scope', '') #use default scope for the case where the rdfdom has been manually modified 
            if scopeFilter is not None and scope != scopeFilter:
                continue
            id = p.getAttributeNS(RDF_MS_BASE, 'ID')
            if not id: id = ''

            resourceID = p.getAttributeNS(RDF_MS_BASE, 'resource')
            if resourceID:
                assert not isinstance(p, PredicateElement) #this can only happen if the DOM was manually modified
                model.add( Statement( subject, getURIFromElementName(p), resourceID, id, scope, OBJECT_TYPE_RESOURCE))
                continue
            
            listID = p.getAttributeNS(None, 'listID')
            if listID:
                model.add( Statement( subject, getURIFromElementName(p), listID, id, scope, OBJECT_TYPE_RESOURCE))
                addList2Model(model, subject, p, listID, id, scope)
            else:
                if not p.childNodes: #if no child we assume its an empty literal
                    object, objectType = "", OBJECT_TYPE_LITERAL            
                else:
                    object, objectType = getObject(p.childNodes[0])
                #print object, objectType 
                #todo: bug: xpudate with an anonymous node as an object doesn't work
                if implicitType == object and getURIFromElementName(p) == RDF_MS_BASE + 'type':
                    continue #don't add redundant rdf:type
                model.add( Statement( subject, getURIFromElementName(p), object, id, scope, objectType))

##########################################################################
## RxPath extension functions
##########################################################################                
#todo: return true if all in nodeset?
#isSubject is a little murky.. why would use it
##def isSubject(context, nodeset=None):
##    if nodeset is None:
##        nodeset = [ context.node ]
##    return nodeset[0].nodeType == Node.ELEMENT_NODE and nodeset[0].parentNode == nodeset[0].ownerDocument 
##
##def isObject(context, nodeset=None):
##    if nodeset is None:
##        nodeset = [ context.node ]
##    return nodeset[0].parentNode and isPredicate(context, nodeset[0].parentNode)

def isPredicate(context, nodeset=None):
    if nodeset is None:
        nodeset = [ context.node ]
        
    if nodeset and nodeset[0].nodeType == Node.ELEMENT_NODE and nodeset[0].parentNode and isResource(context, nodeset[0].parentNode):
        if nodeset[1:]:
            return isPredicate(context, nodeset[1:])
        else:
            return True #we made it to the end 
    else:
        return False

def isResource(context, nodeset=None):
    if nodeset is None:
        nodeset = [ context.node ]
        
    if nodeset and nodeset[0].nodeType == Node.ELEMENT_NODE and nodeset[0].getAttributeNS(RDF_MS_BASE, 'about'):#or instead use: and not isPredicate(context, nodeset[0])
        if nodeset[1:]:
            return isResource(context, nodeset[1:])
        else:
            return True #we made it to the end 
    else:
        return False

def getResource(context, nodeset=None):
    '''
    map each node in the nodeset to its "nearest resource":
    if we're a resource return '.'
    if we're a predicate return '..'
    if we're a literal return '../..'
    otherwise empty nodeset
    '''    
    if nodeset is None:
        nodeset = [ context.node ]
        
    def getResourceFromNode(node):
        if node.nodeType == Node.ATTRIBUTE_NODE:
            node = node.ownerElement
        if isResource(context, [node]):
            return node
        else:
            return getResourceFromNode(node.parentNode)
    return [getResourceFromNode(node) for node in nodeset if node.nodeType in [Node.ELEMENT_NODE, Node.TEXT_NODE, Node.ATTRIBUTE_NODE] ]

RFDOM_XPATH_EXT_NS = None #todo: put these in an extension namespace?
BuiltInExtFunctions = {
(RFDOM_XPATH_EXT_NS, 'isPredicate'): isPredicate,
(RFDOM_XPATH_EXT_NS, 'isResource'): isResource,
(RFDOM_XPATH_EXT_NS, 'getResource'): getResource,
}

##########################################################################
## "patches" to Ft.XPath
##########################################################################                
def descendants(self, context, nodeTest, node, nodeSet, startNode=None):
    """Select all of the descendants from the context node"""
    startNode = startNode or context.node
    if context.node.nodeType != Node.ATTRIBUTE_NODE:
        childNodeFunc = getattr(node, 'getSafeChildNodes', None)
        if childNodeFunc:
            childNodes = childNodeFunc(startNode)
        else:
            childNodes = node.childNodes
        for child in childNodes:
            childNodeFunc = getattr(child, 'getSafeChildNodes', None)
            
            if nodeTest(context, child, self.principalType):
                nodeSet.append(child)
            elif childNodeFunc:
                 continue#we're a RxPath dom and the nodetest didn't match, don't examine the node's descendants
             
            if childNodeFunc:
                childNodes = childNodeFunc(startNode)
            else:
                childNodes = child.childNodes                
            if childNodes:
                self.descendants(context, nodeTest, child, nodeSet, startNode)
    return (nodeSet, 0)
XPath.ParsedAxisSpecifier.AxisSpecifier.descendents = descendants

def findNextStep(parsed):
    #currently only works in the context of a ParsedAbbreviatedAbsoluteLocationPath
    if isinstance(parsed, (XPath.ParsedStep.ParsedStep, XPath.ParsedStep.ParsedAbbreviatedStep)):
        return parsed
    elif isinstance(parsed, (XPath.ParsedRelativeLocationPath.ParsedRelativeLocationPath, XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath)):
        return findNextStep(parsed._left)
    else:
        return None

def isChildAxisSpecifier(step):    
    axis = getattr(step, '_axis', None)
    if isinstance(axis, XPath.ParsedChildAxisSpecifier):
        return True
    else:
        return False
            
def _descendants(self, context, nodeset, startNode=None):
    startNode = startNode or context.node
    childNodeFunc = getattr(context.node, 'getSafeChildNodes', None)
    if childNodeFunc:
        childNodes = childNodeFunc(startNode)
    else:
        childNodes = context.node.childNodes
    
    for child in childNodes:
        context.node = child

        #skip for now: nodetest is always node() since we're an ParsedAbbreviatedAbsoluteLocationPath
        #if childNodeFunc and isPredictate(context):
        #    step = findNextStep(self._rel)
        #    if isChildAxisSpecifier(step):
        #       nodetest = getattr(step, '_nodeTest', XPathParsedNodeTest.NodeTest())
        #       if not nodetest.match(context, context.node, ??):
        #           continue
        #        results = self._rel.select(context)
                 # Ensure no duplicates
        #        nodeset.extend(filter(lambda n, s=nodeset: n not in s, results))
        
        results = self._rel.select(context)
        # Ensure no duplicates
        nodeset.extend(filter(lambda n, s=nodeset: n not in s, results))
                    
        if child.nodeType == Node.ELEMENT_NODE:
            self._descendants(context, nodeset, startNode)
XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath._descendents = _descendants

#patch XPath.ParsedNodeTest.QualifiedNameTest:
_QualifiedNameTest_oldMatch = XPath.ParsedNodeTest.QualifiedNameTest.match.im_func
def _QualifiedNameTest_match(self, context, node, principalType=Node.ELEMENT_NODE):
    if not hasattr(node, 'matchName'):
        return _QualifiedNameTest_oldMatch(self, context, node, principalType)
    else:
        try:
            return node.nodeType == principalType and node.matchName(context.processorNss[self._prefix], self._localName)
        except KeyError:
            raise XPath.RuntimeException(RuntimeException.UNDEFINED_PREFIX, self._prefix)        
    
XPath.ParsedNodeTest.QualifiedNameTest.match = _QualifiedNameTest_match

_NamespaceTest_oldMatch = XPath.ParsedNodeTest.NamespaceTest.match.im_func
def _NamespaceTest_match(self, context, node, principalType=Node.ELEMENT_NODE):
    if not hasattr(node, 'matchName'):
        return _NamespaceTest_oldMatch(self, context, node, principalType)
    else:
        try:
            return node.nodeType == principalType and node.matchName(context.processorNss[self._prefix], '*')
        except KeyError:
            raise XPath.RuntimeException(RuntimeException.UNDEFINED_PREFIX, self._prefix)        
        
XPath.ParsedNodeTest.NamespaceTest.match = _NamespaceTest_match


from Ft.Xml.Xslt import XsltRuntimeException, Error,XsltFunctions
def GenerateId(context, nodeSet=None):
    """
    Implementation of generate-id().

    Returns a string that uniquely identifies the node in the argument
    node-set that is first in document order. If the argument node-set
    is empty, the empty string is returned. If the argument is omitted,
    it defaults to the context node.
    """
    if nodeSet is not None and type(nodeSet) != type([]):
        raise XsltRuntimeException(Error.WRONG_ARGUMENT_TYPE,
                                   context.currentInstruction)
    if nodeSet is None:
        # If no argument is given, use the context node
        return u'id' + `hash(context.node)` #hash instead of id
    elif nodeSet:
        # first node in nodeset
        node = XPath.Util.SortDocOrder(context, nodeSet)[0]
        return u'id' + `hash(node)`
    else:
        # When the nodeset is empty, return an empty string
        return u''
XsltFunctions.GenerateId = GenerateId

##########################################################################
## public user functions
##########################################################################                
def applyXslt(rdfDom, xslStylesheet, topLevelParams = None, extFunctionMap = None, baseUri='file:'):
    if extFunctionMap is None: extFunctionMap = {}
    #ExtFunctions = { (FT_EXT_NAMESPACE, 'base-uri'): BaseUri,
    #processor.registerExtensionModules( [__name__] )
    #or processor.registerExtensionFunction(namespace, localName, function) #function just need context as first arg
    if extFunctionMap:
        extFunctionMap.update(BuiltInExtFunctions)
    else:
        extFunctionMap = BuiltInExtFunctions
    
    from Ft.Xml.Xslt.Processor import Processor
    processor = Processor()
    processor.appendStylesheet( InputSource.DefaultFactory.fromString(xslStylesheet, baseUri)) #todo: fix this
    for (k, v) in extFunctionMap.items():
        namespace, localName = k
        processor.registerExtensionFunction(namespace, localName, v)
        
    oldVal = rdfDom.globalRecurseCheck
    rdfDom.globalRecurseCheck=True #todo remove this when we implement RxSLT
    try:
        return processor.runNode(rdfDom, None, 0, topLevelParams) 
    finally:
        rdfDom.globalRecurseCheck=oldVal

def applyXUpdate(rdfdom, xup = None, vars = None, extFunctionMap = None, uri='file:'):
    """
    Takes 2 InputSources, one for the source document and one for the
    XUpdate instructions.  It returns a DOM node representing the result
    of applying the XUpdate to the source doc
    """
    #from Ft.Xml import XUpdate #buggy -- use our patched version
    import XUpdate
    xureader = XUpdate.Reader()
    processor = XUpdate.Processor()
    if xup is None:
        xupInput = InputSource.DefaultFactory.fromUri(uri)
    else:
        xupInput = InputSource.DefaultFactory.fromString(xup, uri) 
    xupdate = xureader.fromSrc(xupInput)
    if extFunctionMap:
        extFunctionMap.update(BuiltInExtFunctions)
    else:
        extFunctionMap = BuiltInExtFunctions    
    processor.execute(rdfdom, xupdate, vars, extFunctionMap = extFunctionMap)

def evalXPath(rdfDom, xpath, nsMap = None, vars=None, extFunctionMap = None, node = None):
    node = node or rdfDom
    #print node
    #print xpath
    if extFunctionMap:
        extFunctionMap.update(BuiltInExtFunctions)
    else:
        extFunctionMap = BuiltInExtFunctions
    context = XPath.Context.Context(node, varBindings = vars, extFunctionMap = extFunctionMap, processorNss = nsMap)
    #extModuleList = os.environ.get("EXTMODULES","").split(":"))
    compExpr = XPath.Compile(xpath)
    res = compExpr.evaluate(context)
    return res
                           
import traceback, sys

def main():
    def doQuery():
        try:
            compExpr = XPath.Compile(query)
            compExpr.pprint()
            res = evalXPath(rdfDom, query, vars = vars, nsMap = processorNss)            
            #compExpr = XPath.Compile(query)
            #res = XPath.Evaluate(compExpr, rdfDom, context)
        except:
            print "Unexpected error:", sys.exc_info()[0]
            traceback.print_exc(file=sys.stdout)            
        else:
            print repr(res)
            if res:
                vname = 'v'+`len(vars)`
                vars[(None, vname)] =  res
                print 'set ' + vname

            #for n in res:
            #    Ft.Xml.Lib.Print.PrettyPrint(n)

    if len(sys.argv) > 1:
        import utils
        model, db = utils.deserializeRDF( sys.argv[1] )
    else:
        model, db = Util.DeserializeFromUri("./archive-template.rdf")
    ns =[ ('http://rx4rdf.sf.net/ns/archive#', u'a'),
          ('http://rx4rdf.sf.net/ns/wiki#', u'wiki'),
           ('http://www.w3.org/2002/07/owl#', u'owl'),
           ('http://purl.org/dc/elements/1.1/#', u'dc'),
           ( RDF_MS_BASE, u'rdf')
        ]
    nsMap = dict( ns )
    processorNss = dict( map(lambda x: (x[1], x[0]), ns) )
    rdfDom = RDFDoc(model, nsMap)
    context = XPath.Context.Context(rdfDom, processorNss = processorNss)

    if len(sys.argv) > 2:    
        query = sys.argv[2]
    else:
        query = None
        
    vars = {}
    if not query:
        while 1:
            sys.stderr.write("Enter Query: ")
            query = sys.stdin.readline()
            sys.stderr.write("\n")                
            #raise SystemExit("You must either specify a query on the command line our use the --file option")            
            doQuery()            
    else:
        doQuery()

if __name__  == "__main__":
    main()