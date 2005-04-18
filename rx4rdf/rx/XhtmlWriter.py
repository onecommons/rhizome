'''
Implements the serialization rules for XSLT 2.0's xhtml
output method (see
http://www.w3.org/TR/2005/WD-xslt-xquery-serialization-20050404/#xhtml-output).

Proper xhtml usage requires that unqualified XML names must either be
not associated with any namespace or associated with the
"http://www.w3.org/1999/xhtml" namespace using a default namespace declaration
in the root html element.
'''

from Ft.Xml import XPath, Xslt, Lib, EMPTY_NAMESPACE
import Ft.Xml.Lib.XmlPrinter, Ft.Xml.Lib.XmlPrettyPrinter
try:
    #new 4Suite
    from Ft.Xml.Lib import cStreamWriter
    StreamWriter = cStreamWriter    
except ImportError:
    #old 4Suite
    from Ft.Xml.Lib import StreamWriter 
import Ft.Xml.Xslt.HtmlWriter, Ft.Xml.Xslt.OutputHandler

import StringIO
#this attribute was removed when these interfaces changed:
_oldPrinterInterface = getattr(Lib.XmlPrinter.XmlPrinter(StringIO.StringIO(),'ascii'), '_isInline', None)

class XhtmlPrinter(Lib.XmlPrinter.XmlPrinter):
    emptyContentModel = ['base', 'meta', 'link', 'br', 'basefont', 
        'frame', 'area', 'param', 'img', 'input', 'isindex', 'col', 'hr']
    
    attrEntitiesApos = StreamWriter.EntityMap({'<' : '&lt;',
                                           '&' : '&amp;',
                                           '\t' : '&#9;',
                                           '\n' : '&#10;',
                                           '\r' : '&#13;',
                                           "'" : '&#39;', # &apos; not recognized by old browsers
                                           })

    def _endElement(self, namespaceUri, tagName):
        """
        Handles an endElement event.

        Writes the closing tag for an element to the stream, or, if the
        element had no content, finishes writing the empty element tag.
        """
        if self._inElement:
            # No element content, use minimized form
            if ((not namespaceUri or namespaceUri == "http://www.w3.org/1999/xhtml")
                and tagName not in self.emptyContentModel):
                self.writeAscii(' >')
                self.writeAscii('</')
                self.writeEncode(tagName, 'end-tag name')
                self.writeAscii('>')
            else:
                self.writeAscii(' />') #for xhtml add space
            self._inElement = 0
        else:
            self.writeAscii('</')
            self.writeEncode(tagName, 'end-tag name')
            self.writeAscii('>')
        return

    if _oldPrinterInterface:
        def endElement(self, tagName):
            return self._endElement(None, tagName)
    else:
        def endElement(self, namespaceUri, tagName):
            return self._endElement(namespaceUri, tagName)

class XhtmlPrettyPrinter(Lib.XmlPrettyPrinter.XmlPrettyPrinter):
    emptyContentModel = XhtmlPrinter.emptyContentModel
    attrEntitiesApos = XhtmlPrinter.attrEntitiesApos

    if _oldPrinterInterface:
        def endElement(self, tagName):
            self._level -= 1
            # Do not break short tag form (<tag/>)
            if not self._indentForbidden and not self._inElement:
                self.writeAscii('\n' + (self.indent * self._level))
            XhtmlPrinter.endElement(self, tagName)
            # Allow indenting after endtags
            self._indentForbidden = 0
            return
    else:
        def endElement(self, namespaceUri, tagName):
            self._level -= 1
            # Do not break short tag form (<tag/>)
            if self._canIndent and not self._inElement:
                self.writeAscii('\n' + (self.indent * self._level))
            XmlPrinter.endElement(self, namespaceUri, tagName)
            # Allow indenting after endtags
            self._canIndent = True
            return

class XhtmlWriter(Xslt.HtmlWriter.HtmlWriter):
    def startDocument(self):
        self._outputParams.setDefault('version', '1.0') #XML not HTML version
        self._outputParams.setDefault('encoding', 'iso-8859-1')
        self._outputParams.setDefault('indent', 1)
        self._outputParams.setDefault('mediaType', 'text/html')

        encoding = self._outputParams.encoding.encode('ascii')
        version = self._outputParams.version.encode('ascii')
        
        if self._outputParams.indent:
            printer = XhtmlPrettyPrinter
        else:
            printer = XhtmlPrinter

        self._printer = printer(self._stream,
                                encoding)
        
        #for older versions of 4Suite:
        if hasattr(self, '_printerstack'):
            #create these now so we don't create an XmlPrinter in startElement
            self._printerstack.append(0)
            self._htmlprinter = self._printer

            self._xmlprinter = XhtmlPrinter(self._stream,
                                encoding)
            self._xmlprettyprinter = XhtmlPrettyPrinter(
                                      self._stream,
                                      encoding)

        if not self._outputParams.omitXmlDeclaration:
            self._printer.startDocument(version,
                  self._outputParams.standalone)
        return   

Xslt.OutputHandler.OutputHandler._methods[(EMPTY_NAMESPACE, 'xhtml')] = XhtmlWriter
