########################################################################
## 
# $Header$
"""
Code below is based on Ft/Xml/XUpdate.py with a few bug fixes
and added support for the following elements/instructions:
"message", "variable", "replace", "copy-of", and "value-of" and more

Handles XUpdate requests (see http://xmldb.org/xupdate/xupdate-wd.html)

Copyright 2002 Fourthought, Inc. (USA).
Detailed license and copyright information: http://4suite.org/COPYRIGHT
Project home, documentation, distributions: http://4suite.org/
"""

XUPDATE_NS = 'http://www.xmldb.org/xupdate'

import string, sys

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
    STYLESHEET_REQUESTED_TERMINATION=8
    NO_NAME=9
    UNDEFINED_TEMPLATE=10
    NO_HREF=11
    

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
    XUpdateException.STYLESHEET_REQUESTED_TERMINATION: '%s',
    XUpdateException.NO_NAME : 'missing required name attribute',
    XUpdateException.UNDEFINED_TEMPLATE : 'template %s undefined',
    XUpdateException.NO_NAME : 'missing required href attribute',
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
        import sys
        self._msgout = sys.stderr
        self.templates = {}

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


                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)                
                
                for attr in node.attributes.values():
                    value = self.parseAVT(attr.value)
                    value = value.evaluate(context)
                    self.writers[-1].attribute(attr.nodeName, value,
                                               attr.namespaceURI)
                    
                context.processorNss = oldNss
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
                #import sys
                #print >>sys.stderr, 'removing', select
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                _select = self.parseExpression(select)
                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)
                nodeset = _select.evaluate(context)
                if nodeset:
                    #change from 4Suite -- why did it only delete the first node in the nodeset?
                    #that's not in the spec or very intuitive
                    #refnode = nodeset[0]
                    for refnode in nodeset:
                        if refnode.nodeType == Node.ATTRIBUTE_NODE:
                            parent = refnode.ownerElement
                            parent.removeAttributeNode(refnode)
                        else:
                            parent = refnode.parentNode
                            if parent is None:
                                parent = refnode.ownerDocument
                            parent.removeChild(refnode)
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
            elif node.localName == 'replace':
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

                self.pushDomResult(refnode.ownerDocument)
                try:
                    for child in node.childNodes:
                        context = self.visit(context, child, preserveSpace)
                finally:
                    result = self.popResult()

                if refnode.nodeType == Node.ATTRIBUTE_NODE:
                    owner = refnode.parentNode
                    owner.removeAttributeNode(refnode)
                    owner.setAttributeNodeNS(result)
                else:
                    refnode.parentNode.replaceChild(result, refnode)

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
                #moved XUpdate draft's semantics to xupdate:copy-of
                #now has semantics to equivalent to XSLT's value-of
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                _select = self.parseExpression(select)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)

                result = _select.evaluate(context)
                if type(result) is not type(u''):
                    result = Conversions.StringValue(result)
                self.writers[-1].text(result)
                context.processorNss = oldNss
            elif node.localName == 'copy-of':
                #equivalent XUpdate draft's semantics for xupdate:value-of
                #and XSLT's copy-of                
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    raise XUpdateException(XUpdateException.NO_SELECT)
                _select = self.parseExpression(select)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)

                result = _select.evaluate(context)
                #fixed 4suite bug CopyNode and processor undefined
                from Ft.Xml.Xslt.CopyOfElement import CopyNode
                processor = self #CopyNode just accesses writers[-1]        
                if type(result) is type([]): # a node-set                    
                    for node in result:
                        CopyNode(processor, node) 
                else:
                    # a string, number or boolean
                    if type(result) is not type(u''):
                        result = Conversions.StringValue(result)
                    self.writers[-1].text(result)
                context.processorNss = oldNss
            elif node.localName == 'define-template':
                name = node.getAttributeNS(EMPTY_NAMESPACE, u'name')
                if not name:
                    raise XUpdateException(XUpdateException.NO_NAME)
                
                self.templates[name] = (Domlette.GetAllNs(node), node, preserveSpace)
            elif node.localName == 'call-template':
                name = node.getAttributeNS(EMPTY_NAMESPACE, u'name')
                if not name:
                    raise XUpdateException(XUpdateException.NO_NAME)

                if not self.templates.get(name):
                    raise XUpdateException(XUpdateException.UNDEFINED_TEMPLATE, name)
                
                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if not select:
                    templateNode = context.node
                else:                    
                    _select = self.parseExpression(select)
                    oldNss = context.processorNss
                    context.processorNss = Domlette.GetAllNs(node)

                    nodeset = _select.evaluate(context)
                    if not nodeset:
                        raise XUpdateException(XUpdateException.INVALID_SELECT, select)
                    templateNode = nodeset[0]
                    context.processorNss = oldNss

                t_nss, t_node, t_preserveSpace = self.templates[name]
                t_context = Context.Context(templateNode, varBindings=context.varBindings,
                                    extFunctionMap=context.functions, processorNss = t_nss)
                for n in t_node.childNodes:
                    self.visit(t_context, n, t_preserveSpace)
            elif node.localName == 'for-each':
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

                #support nested for-each:
                oldCurrent = context.varBindings.get((EMPTY_NAMESPACE, 'current'), []) 
                for refnode in nodeset:
                    for child in node.childNodes:
                        context.varBindings[(EMPTY_NAMESPACE, 'current')] = [refnode]
                        context = self.visit(context, child, preserveSpace)
                context.varBindings[(EMPTY_NAMESPACE, 'current')] = oldCurrent

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
                #print >>sys.stderr, 'test', test
                test = self.parseExpression(test)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)
                
                if Conversions.BooleanValue(test.evaluate(context)):
                    for n in node.childNodes:
                        self.visit(context, n, preserveSpace)

                context.processorNss = oldNss
            elif node.localName == 'variable':
                name = node.getAttributeNS(EMPTY_NAMESPACE, 'name')
                if not name:
                    raise XUpdateException(XUpdateException.NO_NAME)
                _name = self.parseAVT(name)

                oldNss = context.processorNss
                context.processorNss = Domlette.GetAllNs(node)
                name = _name.evaluate(context)

                (prefix, local) = SplitQName(name)                
                if prefix:
                    namespace = context.processorNss[prefix]
                else:
                    namespace = EMPTY_NAMESPACE

                select = node.getAttributeNS(EMPTY_NAMESPACE, u'select')
                if select:                                        
                    _select = self.parseExpression(select)
                    result = _select.evaluate(context)                    
                else:
                    self.pushDomResult(context.node.ownerDocument)
                    try:
                        for child in node.childNodes:
                            context = self.visit(context, child, preserveSpace)
                    finally:
                        #result will be a documentfragment
                        result = self.popResult().childNodes
                        
                context.varBindings[(namespace, local)] = result
                #print >>sys.stderr, local, result
                
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
                    raise XUpdateException(
                        XUpdateException.STYLESHEET_REQUESTED_TERMINATION, msg) 
                else:
                    self.xupdateMessage(msg)
            elif node.localName == 'include':
                href = node.getAttributeNS(EMPTY_NAMESPACE, u'href')
                if not href:
                    raise XUpdateException(XUpdateException.NO_HREF)
                
                reader = Domlette.NonvalidatingReader
                xupdate = reader.parseUri(href)
                for n in xupdate:
                    self.visit(context, n, preserveSpace)                                    
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
        #import sys; print >>sys.stderr, 'exp', expression
        return parser.new().parse(expression)

    def parseAVT(self, avt):
        if avt is None: return None
        return AttributeValueTemplate.AttributeValueTemplate(avt)

    #next 2 functions copied from Xslt.Processor
    # FIXME: l10n
    def xupdateMessage(self, msg):
        if self._msgout:
            self._msgout.write(msg+'\n')

    def messageControl(self, msgout):
        '''
        File-like object to write message to (default: sys.stderr)
        '''
        self._msgout = msgout
    
# -- XUpdate user API -------------------------------------------------

def ApplyXupdate(doc, xup):
    """
    Takes 2 InputSources, one for the source document and one for the
    XUpdate instructions.  It returns a DOM node representing the result
    of applying the XUpdate to the source doc
    """
    from Ft.Xml import Domlette
    reader = Domlette.NonvalidatingReader
    processor = Processor()
    source = reader.parse(doc)
    xupdate = reader.parse(xup)
    processor.execute(source, xupdate)
    #The source has been updated in place
    return source
