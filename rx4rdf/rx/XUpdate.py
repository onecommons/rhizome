########################################################################
## 
# $Header$
"""
Code below is based on Ft/Xml/XUpdate.py with a few bug fixes and support for the "message" element

Handles XUpdate requests (see http://xmldb.org/xupdate/xupdate-wd.html)

Copyright 2002 Fourthought, Inc. (USA).
Detailed license and copyright information: http://4suite.org/COPYRIGHT
Project home, documentation, distributions: http://4suite.org/
"""

XUPDATE_NS = 'http://www.xmldb.org/xupdate'

import string

from Ft import FtException
from Ft.Xml.FtMiniDom import NonvalReader
from Ft.Xml.XPath import parser
from Ft.Xml.XPath import Context, Conversions
from Ft.Xml.Xslt import NullWriter, DomWriter, AttributeValueTemplate

from Ft.Xml import SplitQName, EMPTY_NAMESPACE, XML_NAMESPACE, Domlette
from xml.dom import Node

class XUpdateException(FtException):

    NO_VERSION = 1
    NO_SELECT = 2
    INVALID_SELECT = 3
    INVALID_CONTENT = 4
    UNABLE_TO_RENAME = 5
    NO_TEST = 6
    NO_TARGET = 7

    def __init__(self, code, *args):
        FtException.__init__(self, code, g_errorMessages, args)

g_errorMessages = {
    XUpdateException.NO_VERSION : 'missing required version attribute',
    XUpdateException.NO_SELECT : 'missing required select attribute',
    XUpdateException.INVALID_SELECT : 'select expression "%s" must return a non-empty node-set',
    XUpdateException.INVALID_CONTENT : 'invalid content',
    XUpdateException.UNABLE_TO_RENAME : 'unable to rename element',
    XUpdateException.NO_TEST : 'missing required test attribute',
    XUpdateException.NO_TARGET : 'missing required target attribute',
    }

class StringWriter(NullWriter.NullWriter):
    def __init__(self):
        self._result = []

    def getResult(self):
        return u''.join(self._result)

    def text(self, data):
        self._result.append(data)
        return


class Processor:
    def __init__(self, reader=None):
        self.writers = [NullWriter.NullWriter(None)]
        return

    def pushDomResult(self, ownerDocument):
        self.writers.append(DomWriter.DomWriter(ownerDocument))
        return

    def pushStringResult(self):
        self.writers.append(StringWriter())
        return

    def popResult(self):
        return self.writers.pop().getResult()

    def execute(self, node, xupdate, variables=None, extFunctionMap = None):
        variables = variables or {}
        context = Context.Context(node, varBindings=variables, extFunctionMap=extFunctionMap)
        self.visit(context, xupdate, 0)
        #xupdate.instantiate(context, self)
        return node

    def visit(self, context, node, preserveSpace):
        #FIXME: We should improve this function from this ugly-ass
        #switch thingie to dynamic dispatch
        if node.nodeType == Node.ELEMENT_NODE:
            xml_space = node.getAttributeNS(XML_NAMESPACE, 'space')
            if xml_space == 'preserve':
                preserveSpace = 1
            elif xml_space == 'default':
                preserveSpace = 0
            # else, no change

            if node.namespaceURI != XUPDATE_NS:
                self.writers[-1].startElement(node.nodeName, node.namespaceURI)

                # Process the attributes
                for attr in node.attributes.values():
                    self.writers[-1].attribute(attr.nodeName, attr.value,
                                               attr.namespaceURI)

                # Now the children
                for child in node.childNodes:
                    context = self.visit(context, child, preserveSpace)
                self.writers[-1].endElement(node.nodeName)
                return context

            # XUpdate elements
            if node.localName == 'modifications':
                for n in node.childNodes:
                    self.visit(context, n, preserveSpace)
            elif node.localName == 'remove':
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                _select = self.parseExpression(select)
                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)
                nodeset = _select.evaluate(context)
                if nodeset:
                    refnode = nodeset[0]
                    if refnode.nodeType == Node.ATTRIBUTE_NODE:
                        parent = refnode.ownerElement
                        parent.removeAttributeNode(refnode)
                    else:
                        parent = refnode.parentNode
                        if parent is None:
                            parent = refnode.ownerDocument
                        parent.removeChild(nodeset[0])
                context.processorNss = oldNss
            elif node.localName in ['insert-after', 'insert-before']:
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                _select = self.parseExpression(select)
                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)

                nodeset = _select.evaluate(context)
                if not nodeset:
                    raise XUpdateException(XUpdateException.INVALID_SELECT)
                refnode = nodeset[0]

                self.pushDomResult(refnode.ownerDocument)
                try:
                    for child in node.childNodes:
                        context = self.visit(context, child, preserveSpace)
                finally:
                    result = self.popResult()

                if node.localName == 'insert-before':
                    refnode.parentNode.insertBefore(result, refnode)
                elif node.localName == 'insert-after':
                    # if arg 2 is None, insertBefore behaves like appendChild
                    refnode.parentNode.insertBefore(result, refnode.nextSibling)
                context.processorNss = oldNss
            elif node.localName == 'element':
                name = node.getAttributeNS(EMPTY_NAMESPACE, 'name')
                if not name:
                    raise XUpdateException(XUpdateException.NO_NAME)
                _name = self.parseAVT(name)

                namespace = node.getAttributeNS(EMPTY_NAMESPACE, 'namespace')
                _namespace = self.parseAVT(namespace)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)
                name = _name.evaluate(context)

                namespace = _namespace and _namespace.evaluate(context)

                (prefix, local) = SplitQName(name)
                if not namespace:
                    if prefix:
                        namespace = context.processorNss[prefix]
                    else:
                        namespace = EMPTY_NAMESPACE

                self.writers[-1].startElement(name, namespace)
                for child in node.childNodes:
                    context = self.visit(context, child, preserveSpace)
                self.writers[-1].endElement(name)
                context.processorNss = oldNss
            elif node.localName == 'attribute':
                name = node.getAttributeNS(EMPTY_NAMESPACE, 'name')
                if not name:
                    raise XUpdateException(XUpdateException.NO_NAME)
                _name = self.parseAVT(name)

                namespace = node.getAttributeNS(EMPTY_NAMESPACE, 'namespace')
                _namespace = self.parseAVT(namespace)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)
                name = _name.evaluate(context)
                namespace = _namespace and _namespace.evaluate(context)

                (prefix, local) = SplitQName(name)
                if not namespace:
                    if prefix:
                        namespace = context.processorNss[prefix]
                    else:
                        namespace = EMPTY_NAMESPACE
                self.pushStringResult()
                try:
                    for child in node.childNodes:
                        context = self.visit(context, child, preserveSpace)
                finally:
                    result = self.popResult()

                self.writers[-1].attribute(name, result, namespace)
                context.processorNss = oldNss
            elif node.localName == 'append':
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                _select = self.parseExpression(select)

                child = node.getAttributeNS(EMPTY_NAMESPACE, u'child') or u'last()'
                _child = self.parseExpression(child)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)

                nodeset = _select.evaluate(context)
                if not nodeset:
                    raise XUpdateException(
                        XUpdateException.INVALID_SELECT,
                        select
                        )
                refnode = nodeset[0]
                self.pushDomResult(refnode.ownerDocument)
                try:
                    for child in node.childNodes:
                        context = self.visit(context, child, preserveSpace)
                finally:
                    result = self.popResult()
                size = len(refnode.childNodes)
                con = Context.Context(refnode, 1, size,
                                      processorNss={'xupdate': XUPDATE_NS})
                # Python lists is 0-indexed counting, node-sets 1-indexed
                position = int(Conversions.NumberValue(_child.evaluate(con)))
                if position >= size:
                    refnode.appendChild(result)
                else:
                    refnode.insertBefore(result, refnode.childNodes[position])
                context.processorNss = oldNss
            elif node.localName == 'update':
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                try:
                    _select = self.parseExpression(select)
                except SyntaxError, e:
                    raise SyntaxError("Select Expression %s: %s" % (select, str(e)))

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)

                nodeset = _select.evaluate(context)
                if not nodeset:
                    raise XUpdateException(XUpdateException.INVALID_SELECT, node.getAttributeNS(EMPTY_NAMESPACE, u'select'))
                refnode = nodeset[0]

                if refnode.nodeType == Node.ATTRIBUTE_NODE:
                    self.pushStringResult()
                    try:
                        for child in node.childNodes:
                            context = self.visit(context, child, preserveSpace)
                    finally:
                        result = self.popResult()
                    refnode.nodeValue = refnode.value = result
                else:
                    self.pushDomResult(refnode.ownerDocument)
                    try:
                        for child in node.childNodes:
                            context = self.visit(context, child, preserveSpace)
                    finally:
                        result = self.popResult()

                    while refnode.firstChild:
                        #print 'remove', id(refnode), id(refnode.firstChild), len(refnode.childNodes)
                        refnode.removeChild(refnode.firstChild)

                    refnode.appendChild(result)

                context.processorNss = oldNss
            elif node.localName == 'rename':                
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                try:
                    _select = self.parseExpression(select)
                except SyntaxError, e:
                    raise SyntaxError("Select Expression %s: %s" % (select, str(e)))

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)
                nodeset = _select.evaluate(context)

                if not nodeset:
                    raise XUpdateException(XUpdateException.INVALID_SELECT, node.getAttributeNS(EMPTY_NAMESPACE, u'select'))

                Domlette.XmlStrStrip(node.firstChild.data)
                new_name = node.firstChild.data.strip()
                (prefix, local) = SplitQName(new_name)
                if prefix:                    
                    namespace = context.processorNss[prefix]
                else:
                    namespace = EMPTY_NAMESPACE

                for refnode in nodeset:
                    if refnode.nodeType == Node.ATTRIBUTE_NODE:
                        parent = refnode.ownerElement
                        parent.removeAttributeNode(refnode)
                        parent.setAttributeNS(namespace, new_name, refnode.value)
                    else:
                        assert refnode.nodeType == Node.ELEMENT_NODE
                        refnode.nodeName = refnode.tagName = new_name
                        refnode.namespaceURI = namespace
                        refnode.prefix = prefix
                        refnode.localName = local
##                        parent = refnode.parentNode
##                        if parent is None:
##                            parent = refnode.ownerDocument
##                        self.pushDomResult(refnode.ownerDocument)
##                        self.writers[-1].startElement(new_name, namespace)
##                        self.writers[-1].endElement(new_name)
##                        result = self.popResult()
##                        parent.replaceChild(result, refnode)

                context.processorNss = oldNss
            elif node.localName == 'value-of':
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                _select = self.parseExpression(select)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)

                result = _select.evaluate(context)
                #4suite bug CopyNode and processor undefined
                #instead let's convert everything to string like XSLT
                #if type(result) is type([]):
                #    # a node-set
                #    for node in result:
                #        CopyNode(processor, node) 
                #else:
                    # a string, number or boolean
                if type(result) is not type(u''):
                    result = Conversions.StringValue(result)
                self.writers[-1].text(result)
                context.processorNss = oldNss
            elif node.localName == 'text':
                for child in node.childNodes:
                    context = self.visit(context, child, 1)
            #Conditional statements are not part of the XUpdate spec,
            #though it has provisions for them because the spec is
            #not so much use without them
            #xupdate:if is a common-sense 4Suite extension
            elif node.localName == 'if':
                test = node.getAttributeNS(EMPTY_NAMESPACE, u'test')
                if not test:
                    raise XUpdateException(XUpdateException.NO_TEST)
                test = self.parseExpression(test)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)
                
                if Conversions.BooleanValue(test.evaluate(context)):
                    for n in node.childNodes:
                        self.visit(context, n, preserveSpace)

                context.processorNss = oldNss
            elif node.localName == 'message':                
                msg = node.getAttributeNS(EMPTY_NAMESPACE, u'text')
                if msg:
                    msg = self.parseAVT(msg)
                    oldNss = context.processorNss
                    context.processorNss = Domlette.GetAllNs(node)
                    msg = msg.evaluate(context)
                    context.processorNss = oldNss
                else:
                    msg = "encountered <xupdate:message> (no message)"
                isError = node.getAttributeNS(EMPTY_NAMESPACE, u'terminate')
                if isError == 'yes':                
                    raise 'XUpdate aborted. Reason: ' + str(msg) #todo
                else:
                    print msg #todo
            else:
                raise Exception("Unknown xupdate element: %s.  This may just be an implementation gap" % node.localName)
        elif node.nodeType == Node.DOCUMENT_NODE:
            self.visit(context, node.documentElement, preserveSpace)
        elif node.nodeType == Node.TEXT_NODE:
            if preserveSpace or Domlette.XmlStrStrip(node.data):
                self.writers[-1].text(node.data)
        elif node.nodeType == Node.COMMENT_NODE: #abs 7/10/03
            pass #ignore comments
        else:
            raise "Finish: %s" % repr(node)
        return context

    def parseExpression(self, expression):
        if expression is None: return None
        return parser.new().parse(expression)

    def parseAVT(self, avt):
        if avt is None: return None
        return AttributeValueTemplate.AttributeValueTemplate(avt)

class Reader(Domlette.NonvalidatingReaderBase):
    fromSrc = Domlette.NonvalidatingReaderBase.parse

##class Reader(NonvalReader.NonvalReader):

##    def fromSrc(self,src):
##        res = NonvalReader.NonvalReader.fromSrc(self,src)
##        res.setup()
##        return res

##    # Handler node creation overrides

##    def Element(self, qname, namespace, prefix, local):
##        if namespace == XUPDATE_NS:
##            return XUPDATE_ELEMENT_MAPPING[local](self._namespaces[-1], qname,
##                                                  namespace, prefix, local)
##        else:
##            return LiteralElement(self._namespaces[-1], qname,
##                                  namespace, prefix, local)

##    def Document(self):
##        return XUpdateDocument()

##    def Text(self, data):
##        return LiteralText(data)

##    def comment(self, data):
##        pass
##    def processingInstruction(self, target, data):
##        pass


##class XUpdateDocument(Nodes.Document):
##    def instantiate(self, context, processor):
##        self.documentElement.instantiate(context, processor)
##        return

##    def setup(self):
##        self.documentElement.setup()
##        return

##class XUpdateElement(Nodes.Element):

##    def __init__(self, namespaces, qname, namespace, prefix, local):
##        self._namespaces = namespaces
##        Nodes.Element.__init__(self, qname, namespace, prefix, local)
##        return

##    def parseExpression(self, expression):
##        if expression is None: return None
##        return parser.new().parse(expression)

##    def parseAVT(self, avt):
##        if avt is None: return None
##        return AttributeValueTemplate.AttributeValueTemplate(avt)

##    def splitQName(self, qualifiedName):
##        index = qualifiedName.find(':')
##        if index != -1:
##            prefix, local = qualifiedName[:index], qualifiedName[index+1:]
##        else:
##            prefix, local = None, qualifiedName
##        return prefix, local

##    def setup(self):
##        for child in self.childNodes:
##            child.setup()

##    def instantiate(self, context, processor):
##        return context


##class ModificationsElement(XUpdateElement):
##    """
##    An update is represented by an xupdate:modifications element in an XML
##    document. An xupdate:modifications element must have a version attribute,
##    indicating the version of XUpdate that the update requires. For this
##    version of XUpdate, the value should be 1.0.
##    """

##    def setup(self):
##        self._version = self.getAttributeNS(EMPTY_NAMESPACE,u'version')
##        if not self._version:
##            raise XUpdateException(XUpdateException.NO_VERSION)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces
##        for child in self.childNodes:
##            context = child.instantiate(context, processor)
##        return context


##class InsertElement(XUpdateElement):

##    PRECEDING = 0
##    FOLLOWING = 1

##    def setup(self):

##        select = self.getAttributeNS(EMPTY_NAMESPACE, u'select')
##        if not select:
##            raise XUpdateException(XUpdateException.NO_SELECT)
##        self._select = self.parseExpression(select)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces

##        nodeset = self._select.evaluate(context)
##        if not nodeset:
##            raise XUpdateException(XUpdateException.INVALID_SELECT)
##        refnode = nodeset[0]

##        processor.pushDomResult(refnode.ownerDocument)
##        try:
##            for child in self.childNodes:
##                context = child.instantiate(context, processor)
##        finally:
##            result = processor.popResult()

##        if self.direction == InsertElement.PRECEDING:
##            refnode.parentNode.insertBefore(result, refnode)
##        elif self.direction == InsertElement.FOLLOWING:
##            # if arg 2 is None, insertBefore behaves like appendChild
##            refnode.parentNode.insertBefore(result, refnode.nextSibling)

##        return context


##class InsertBeforeElement(InsertElement):
##    direction = InsertElement.PRECEDING


##class InsertAfterElement(InsertElement):
##    direction = InsertElement.FOLLOWING


##class AppendElement(XUpdateElement):

##    def setup(self):
##        select = self.getAttributeNS(EMPTY_NAMESPACE, u'select')
##        if not select:
##            raise XUpdateException(XUpdateException.NO_SELECT)
##        self._select = self.parseExpression(select)

##        child = self.getAttributeNS(EMPTY_NAMESPACE, u'child') or u'last()'
##        self._child = self.parseExpression(child)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces

##        nodeset = self._select.evaluate(context)
##        if not nodeset:
##            raise XUpdateException(XUpdateException.INVALID_SELECT,self.getAttributeNS(EMPTY_NAMESPACE, u'select'))
##        refnode = nodeset[0]

##        processor.pushDomResult(refnode.ownerDocument)
##        try:
##            for child in self.childNodes:
##                context = child.instantiate(context, processor)
##        finally:
##            result = processor.popResult()

##        size = len(refnode.childNodes)
##        con = Context.Context(refnode, 1, size,
##                              processorNss={'xupdate': XUPDATE_NS})
##        # Python lists is 0-indexed counting, node-sets 1-indexed
##        position = int(Conversions.NumberValue(self._child.evaluate(con)))
##        if position >= size:
##            refnode.appendChild(result)
##        else:
##            refnode.insertBefore(result, refnode.childNodes[position])
##        return context


##class UpdateElement(XUpdateElement):

##    def setup(self):
##        select = self.getAttributeNS(EMPTY_NAMESPACE, u'select')
##        if not select:
##            raise XUpdateException(XUpdateException.NO_SELECT)
##        try:
##            self._select = self.parseExpression(select)
##        except SyntaxError, e:
##            raise SyntaxError("Select Expression %s: %s" % (select,str(e)))
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces

##        nodeset = self._select.evaluate(context)
##        if not nodeset:
##            raise XUpdateException(XUpdateException.INVALID_SELECT,self.getAttributeNS(EMPTY_NAMESPACE, u'select'))
##        refnode = nodeset[0]

##        if refnode.nodeType == Node.ATTRIBUTE_NODE:
##            processor.pushStringResult()
##            try:
##                for child in self.childNodes:
##                    context = child.instantiate(context, processor)
##            finally:
##                result = processor.popResult()
##            refnode.value = result
##        else:
##            processor.pushDomResult(refnode.ownerDocument)
##            try:
##                for child in self.childNodes:
##                    context = child.instantiate(context, processor)
##            finally:
##                result = processor.popResult()

##            while refnode.firstChild:
##                refnode.removeChild(refnode.firstChild)

##            refnode.appendChild(result)

##        return context


##class RemoveElement(XUpdateElement):

##    def setup(self):
##        select = self.getAttributeNS(EMPTY_NAMESPACE, u'select')
##        if not select:
##            raise XUpdateException(XUpdateException.NO_SELECT)
##        self._select = self.parseExpression(select)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces
##        nodeset = self._select.evaluate(context)
##        if nodeset:
##            nodeset[0].parentNode.removeChild(nodeset[0])
##        return context


##class RenameElement(XUpdateElement):

##    def setup(self):
##        select = self.getAttributeNS(EMPTY_NAMESPACE, u'select')
##        if not select:
##            raise XUpdateException(XUpdateException.NO_SELECT)
##        self._select = self.parseExpression(select)
##        try:
##            qname = self.childNodes[0].data
##        except:
##            raise XUpdateException(XUpdateException.INVALID_CONTENT)
##        # we don't need to worry about XML specific whitespace, all whitespace
##        # is invalid in a qualified name
##        self._new_name = qname.strip()
##        index = self._new_name.find(':')
##        if index != -1:
##            self._new_ns = self._namespaces[self._new_name[:index]]
##        else:
##            self._new_ns = self._namespaces[EMPTY_NAMESPACE]
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces
##        nodeset = self._select.evaluate(context)
##        if nodeset:
##            node = nodeset[0]
##            if node.nodeType == Node.ELEMENT_NODE:
##                element = node.ownerDocument.createElementNS(self._new_ns,
##                                                             self._new_name)
##                # transfer existing children to this new element
##                while node.firstChild:
##                    element.appendChild(node.firstChild)
##                node.parentNode.replaceChild(element, node)
##            elif node.nodeType == Node.ATTRIBUTE_NODE:
##                node.ownerElement.setAttributeNS(self._new_ns, self._new_name, node.value)
##                node.ownerElement.removeAttributeNode(node)
##            else:
##                raise XUpdateException(XUpdateException.UNABLE_TO_RENAME)
##        return context


##class VariableElement(XUpdateElement):

##    def setup(self):
##        name = self.getAttributeNS(EMPTY_NAMESPACE, 'name')
##        self._name = self.expandQName(name)
##        select = self.getAttributeNS(EMPTY_NAMESPACE, u'select')
##        if select:
##            self._select = self.parseExpression(select)
##        else:
##            self._select = None
##            self._string = Conversions.StringValue(self.childNodes)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        if self._select:
##            context.processorNss = self._namespaces
##            result = self._select.evaluate(context)
##        else:
##            result = self._string
##        context.varBindings[self._name] = result
##        return context


##class ValueOfElement(XUpdateElement):

##    def setup(self):
##        select = self.getAttributeNS(EMPTY_NAMESPACE, u'select')
##        if not select:
##            raise XUpdateException(XUpdateException.NO_SELECT)
##        self._select = self.parseExpression(select)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces
##        result = self._select.evaluate(context)
##        if type(result) is type([]):
##            # a node-set
##            for node in result:
##                CopyNode(processor, node)
##        else:
##            # a string, number or boolean
##            if type(result) is not type(u''):
##                result = Conversions.StringValue(result)
##            processor.writers[-1].text(result)
##        return context


##class IfElement(XUpdateElement):

##    def setup(self):
##        test = self.getAttributeNS(EMPTY_NAMESPACE, u'test')
##        if not test:
##            raise XUpdateException(XUpdateException.NO_TEST)
##        self._test = self.parseExpression(test)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces
##        if Conversions.BooleanValue(self._test.evaluate(context)):
##            for child in self.childNodes:
##                context = child.instantiate(context, processor)
##        return context


##class LiteralText(Nodes.Text):
##    def setup(self): pass
##    def instantiate(self, context, processor):
##        processor.writers[-1].text(self.data)
##        return context


##class LiteralElement(XUpdateElement):

##    def instantiate(self, context, processor):
##        processor.writers[-1].startElement(self.nodeName, self.namespaceURI)

##        # Due the attributes
##        for attr in self.attributes.values():
##            processor.writers[-1].attribute(attr.nodeName, attr.value, attr.namespaceURI)

##        # then the children
##        for child in self.childNodes:
##            context = child.instantiate(context, processor)

##        processor.writers[-1].endElement(self.nodeName)
##        return context

##### instructions ###

##class ElementElement(XUpdateElement):

##    def setup(self):
##        name = self.getAttributeNS(EMPTY_NAMESPACE, 'name')
##        if not name:
##            raise XUpdateException(XUpdateException.NO_NAME)
##        self._name = self.parseAVT(name)

##        namespace = self.getAttributeNS(EMPTY_NAMESPACE, 'namespace')
##        self._namespace = self.parseAVT(namespace)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces
##        name = self._name.evaluate(context)
##        namespace = self._namespace and self._namespace.evaluate(context)

##        (prefix, local) = self.splitQName(name)
##        if not namespace:
##            if prefix:
##                namespace = context.processorNss[prefix]
##            else:
##                namespace = EMPTY_NAMESPACE

##        processor.writers[-1].startElement(name, namespace)
##        for child in self.childNodes:
##            context = child.instantiate(context, processor)
##        processor.writers[-1].endElement(name)
##        return context


##class AttributeElement(XUpdateElement):

##    def setup(self):
##        name = self.getAttributeNS(EMPTY_NAMESPACE, u'name')
##        if not name:
##            raise XUpdateException(XUpdateException.NO_NAME)
##        self._name = self.parseAVT(name)

##        namespace = self.getAttributeNS(EMPTY_NAMESPACE, u'namespace')
##        self._namespace = self.parseAVT(namespace)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces
##        name = self._name.evaluate(context)
##        namespace = self._namespace and self._namespace.evaluate(context)

##        prefix, local = self.splitQName(name)
##        if not namespace:
##            if prefix:
##                namespace = context.processorNss[prefix]
##            else:
##                namespace = EMPTY_NAMESPACE

##        processor.pushStringResult()
##        try:
##            for child in self.childNodes:
##                context = child.instantiate(context, processor)
##        finally:
##            result = processor.popResult()

##        processor.writers[-1].attribute(name, result, namespace)
##        return context


##class TextElement(XUpdateElement):

##    def setup(self):
##        try:
##            self._data = self.childNodes[0].data
##        except:
##            self._data = u''
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        self._data and processor.writers[-1].text(self._data)
##        return context


##class ProcessingInstructionElement(XUpdateElement):

##    def setup(self):
##        target = self.getAttributeNS(EMPTY_NAMESPACE, u'target')
##        if not name:
##            raise XUpdateException(XUpdateException.NO_TARGET)
##        self._target = self.parseAVT(target)
##        XUpdateElement.setup(self)
##        return

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces
##        target = self._target.evaluate(context)

##        processor.pushStringResult()
##        try:
##            for child in self.childNodes:
##                context = child.instantiate(context, processor)
##        finally:
##            result = processor.popResult()

##        processor.writers[-1].processingInstruction(target, result)
##        return context


##class CommentElement(XUpdateElement):

##    def instantiate(self, context, processor):
##        context.processorNss = self._namespaces

##        processor.pushStringResult()
##        try:
##            for child in self.childNodes:
##                context = child.instantiate(context, processor)
##        finally:
##            result = processor.popResult()

##        processor.writers[-1].comment(result)
##        return context


##XUPDATE_ELEMENT_MAPPING = {
##    'modifications': ModificationsElement,
##    'insert-before': InsertBeforeElement,
##    'insert-after': InsertAfterElement,
##    'element': ElementElement,
##    'attribute': AttributeElement,
##    'text': TextElement,
##    'processing-instruction' : ProcessingInstructionElement,
##    'comment' : CommentElement,
##    'append': AppendElement,
##    'update': UpdateElement,
##    'remove': RemoveElement,
##    'rename': RenameElement,
##    'variable': VariableElement,
##    'value-of' : ValueOfElement,
##    'if': IfElement,
##    }


# -- XUpdate user API -------------------------------------------------

def ApplyXupdate(doc, xup):
    """
    Takes 2 InputSources, one for the source document and one for the
    XUpdate instructions.  It returns a DOM node representing the result
    of applying the XUpdate to the source doc
    """
    from Ft.Xml import Domlette, InputSource
    reader = Domlette.NonvalidatingReader
    xureader = Reader()
    processor = Processor()
    source = reader.parse(doc)
    xupdate = xureader.fromSrc(xup)
    processor.execute(source, xupdate)
    #The source has been updated in place
    return source
