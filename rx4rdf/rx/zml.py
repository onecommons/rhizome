#! /usr/bin/env python
"""
    ZML to XML/XML to ZML
    
    Copyright (c) 2003-4 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, released under GPL v2, see COPYING for details.
    
    See http://rx4rdf.liminalzone.org/ZML for more info on ZML.    
"""

defaultZMLVersion = 0.7

try:
    from rx.utils import NestedException
except ImportError:
    #copied from rx/utils.py so this file has no dependencies
    class NestedException(Exception):
        def __init__(self, msg = None,useNested = False):
            if not msg is None:
                self.msg = msg
            self.nested_exc_info = sys.exc_info()
            self.useNested = useNested
            if useNested and self.nested_exc_info[0]:
                if self.nested_exc_info[1]:
                    args = getattr(self.nested_exc_info[1], 'args', ())
                else: #nested_exc_info[1] is None, a string must have been raised
                    args = self.nested_exc_info[0]
            else:
                args = msg
            Exception.__init__(self, args)

class ZMLParseError(NestedException):    
    errors = [
    'generic parse error',
    'unexpected token (%s) found outside of attribute list'
    ]
    TOKEN_NOT_IN_ATTRIBUTES = 1
    USER_DEFINED = 100
    
    def __init__(self, msg = None, code=0):
        self.code = code
        if code == self.USER_DEFINED:
            code = 0
        if msg is not None:
            if code:
                msg = self.errors[code] % msg
        else:
            if code:
                msg = self.errors[code]
            else:
                msg = ''

        NestedException.__init__(self, msg)
        self.state = None        
        
    def setState(self, state):
        self.state = state #line, col #, etc.
        if state:
            self.msg = ('ZML syntax error at line %d, column %d: '
                '%s\nline: "%s"' % (state.currentStartPos[0], 
                state.currentStartPos[1],self.msg, state.currentLine.strip()))
            #'cuz this is the way Exception stores its message
            self.args = ( self.msg, ) 
        
######################################################
###begin tokenizer
######################################################
"""
Tokenizer for ZML

This is a modification of Python 2.2's tokenize module and behaves
the same except for:

* NAME tokens also can include '.', ':' and '-' (aligning them with XML's
  NMTOKEN production) (but the trailing ':', if present, is treated as an OP)
* New string tokens are introduced:
  1. STRLINE, which behaves similar to a comment: any characters following a '`'
     to the end of the line are part of the token
  2. the optional FREESTR token, which if true (the default), causes any
  non-indented, non-continued line to be returned whole as a FREESTR token
  Its presence is controlled by the 'useFreestr' keyword parameter added to
  tokenize() (default: True)
  3. WHITESPACE so the tokeneater function gets notified of all the whitespace
  4. IGNORE for lines that begin with '#!'
  5. PI for lines that begin with '#?'
  6. URIREF for token thats look like: {http://blahblah}
* indention whitespace characters can include '<'
* string quote modifiers changed from 'ur' to 'pr'    
"""

import string, re, sys, os
try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO
from token import *

COMMENT = N_TOKENS
tok_name[COMMENT] = 'COMMENT'
NL = N_TOKENS + 1
tok_name[NL] = 'NL'
N_TOKENS += 2
STRLINE = N_TOKENS
tok_name[STRLINE] = 'STRLINE'
N_TOKENS += 1
FREESTR = N_TOKENS
tok_name[FREESTR] = 'FREESTR'
N_TOKENS += 1
WHITESPACE = N_TOKENS
tok_name[WHITESPACE] = 'WHITESPACE'
N_TOKENS += 1
PI = N_TOKENS
tok_name[PI] = 'PI'
N_TOKENS += 1
IGNORE = N_TOKENS
tok_name[IGNORE] = 'IGNORE'
N_TOKENS += 1
URIREF = N_TOKENS
tok_name[URIREF] = 'URIREF'
N_TOKENS += 1

def group(*choices): return '(' + '|'.join(choices) + ')'
def any(*choices): return group(*choices) + '*'
def maybe(*choices): return group(*choices) + '?'

tabsize = 8

class StopTokenizing(Exception): pass

def printtoken(type, token, (srow, scol), (erow, ecol), line, *args):
    # for testing
    print "%d,%d-%d,%d:\t%s\t%s" % \
        (srow, scol, erow, ecol, tok_name[type], repr(token))

def tokenize(readline, parser):
    try:
        tokenize_loop(readline, parser)
    except StopTokenizing, e:        
        pass

def tokenize_loop(readline, parser):
    lnum = parenlev = continued = 0
    namechars, numchars = string.letters + '_', string.digits  
    contstr, needcont = '', 0
    contline = None
    indents = [0]
    literalstr = ''
    pos = 0
    doIndent = True
    
    parseState = parser.parseState
    tokeneater = parseState.tokenHandler
    pseudoprog = parseState.pseudoprog
    endprogs = parseState.endprogs
    nameOrUriProg = parseState.nameOrUriProg
    
    while 1:            # loop over lines in stream        
        line = readline()
        lnum = lnum + 1
        #print 'LN:', line, parenlev

        done = not line
        oldpos = pos
        xmlline = parseState.parseXML(line)
        if not done and not xmlline: #line consumed by the xml parser
            continue
        if xmlline != line: #xml consumed chars
            line = xmlline
            continued = 1
            pos = oldpos
            max = len(line)
            doIndent = False #don't recalculate indentions after consuming xml
            consumedXML = True
        else:
            consumedXML = False
            pos, max = 0, len(line)
            
        parseState.currentLine = line        
        parseState.currentStartPos = lnum, pos
        
        if literalstr: #last line was a FREESTR
            if line and not line.isspace() and line[0].isspace():
                #if this line starts with whitespace (but isn't all whitespace)
                #it's a continuation of the last

                #line continued (previous line should end in newline whitespace)
                literalstr = literalstr.rstrip() + line 
                literalstrstop = (lnum, max)
                literalline = line
                continue
            else: #last line is complete
                tokeneater(FREESTR, literalstr, literalstrstart,
                           literalstrstop, literalline)
                literalstr = ''
                if not line:
                    break

        if not consumedXML:
            doIndent = True

        if not contstr and line[:2] == '#!': #ignore these lines
            tokeneater(IGNORE, line[2:], (lnum, 0), (lnum, max), line)
            continue
        if not contstr and line[:2] == '#?':
            #processing instruction e.g. #?zml1.0 markup
            if line.startswith('#?zml'):
                if line[5:6].isdigit():
                    parseState = parser.setZMLVersion(float(line[5:9]))
                    tokeneater = parseState.tokenHandler
                    pseudoprog = parseState.pseudoprog
                    endprogs = parseState.endprogs
                    nameOrUriProg = parseState.nameOrUriProg
                if line.find('markup') > -1:                    
                    parseState.setMarkupMode(True)
                else:
                    parseState.setMarkupMode(False)
            tokeneater(PI, line[2:], (lnum, 0), (lnum, max), line)
            continue
          
        if (parseState.useFreestr and line and not line.isspace() and
            not continued and parenlev == 0 and not contstr and
            not line[0] == parseState.MARKUPSTARTCHAR):
            #free-form text
            if (line[0] in ("'", '"') or 
                  line[:2] in ("r'", 'r"', "R'", 'R"',"p'", 'p"', "P'", 'P"')
                  or line[:3] in ("pr'", 'pr"', "Pr'", 'Pr"', "pR'", 'pR"',
                               "PR'", 'PR"' )):
                #this is a quoted string but treat like wiki markup (don't dedent)
                doIndent = False 
            else:
                literalstrstart = (lnum, 0)
                literalstrstop = (lnum, max)
                literalline = line
                literalstr = line
                continue

        if contstr:                            # continued string
            if not line:
                #raise ZMLParseError, ("EOF in multi-line string", strstart)
                #don't raise an error, just close the string 
                if contstr[0] in 'pPrR':
                    if contstr[1] in 'rR':
                        delim = contstr[2] * 3
                    else:
                        delim = contstr[1] * 3
                else:
                    delim = contstr[0] * 3
                tokeneater(STRING, contstr+delim, strstart,
                           (lnum -1, endcontline), line)
                break
                
            endmatch = endprog.match(line)
            if endmatch:
                pos = end = endmatch.end(0)
                tokeneater(STRING, contstr + line[:end],
                           strstart, (lnum, end), contline + line)
                contstr, needcont = '', 0
                contline = None
                #if there's only trailing whitespace left on the line
                if not line[pos:].strip(): 
                  tokeneater(NEWLINE, line[pos:],(lnum, pos),
                             (lnum, len(line)), line)
                  continue                
            elif needcont and line[-2:] != '\\\n' and line[-3:] != '\\\r\n':
                tokeneater(ERRORTOKEN, contstr + line,
                           strstart, (lnum, len(line)), contline)
                contstr = ''
                contline = None
                continue
            else:
                contstr = contstr + line
                contline = contline + line
                endcontline = max
                continue

        elif parenlev == 0 and not continued:  # new statement
            if not line: break
            column = 0
            while pos < max:                   # measure leading whitespace
                if line[pos]==' ' or line[pos]==parseState.MARKUPSTARTCHAR:
                    column = column + 1
                elif line[pos] == '\t':
                    column = (column/tabsize + 1)*tabsize
                elif line[pos] == '\f':
                    column = 0
                else: break
                pos = pos + 1
            if pos == max: break            

        if pos >= len(line): 
            if not line:
                tokeneater(ERRORTOKEN, line,
                           (lnum, pos), (lnum, pos), line)
                break
            else:
                #seems to happens when the last line == "'''" and there's no NL
                continue

        if line[pos] in '\r\n':           # skip blank lines            
            tokeneater(NL, line[pos:],(lnum, pos), (lnum, len(line)), line)
            #if the 'whitespace' was not all '<' continue
            if not line[:pos] or line[:pos].strip(parseState.MARKUPSTARTCHAR):
                continue    #but all < treat as an intentional dedent/indent

        #begin redunancy (todo)
        if doIndent and not parenlev:
            # count indents or dedents
            if column > indents[-1]:
                indents.append(column)
                tokeneater(INDENT, line[:column], (lnum, 0), (lnum, pos), line)
            else:
                tokeneater(DEDENT, '', (lnum, pos), (lnum, pos), line)
                while column < indents[-1]:
                    indents = indents[:-1]
                    tokeneater(DEDENT, '', (lnum, pos), (lnum, pos), line)
                tokeneater(INDENT, '', (lnum, pos), (lnum, pos), line)
        doIndent = False
        tokeneater(WHITESPACE, line[:pos], (lnum, 0), (lnum, pos), line)
 
        if line[pos] in '`':    # our new type of string
             tokeneater(STRLINE, line[pos:],
                    (lnum, pos), (lnum, len(line)), line)
             continue
        #end redundancy
        
        if continued:
            if not line:
                raise ZMLParseError(
        "Encountered the end of the file while within a multi-line statement")
            continued = 0

        while pos < max:
            if doIndent:
                # count indents or dedents
                if icolumn > indents[-1]:           
                    indents.append(icolumn)
                    tokeneater(INDENT, line[:pos], (lnum, 0), (lnum, pos), line)
                else:
                    tokeneater(DEDENT, '', (lnum, pos), (lnum, pos), line)
                    while icolumn < indents[-1]:
                        indents = indents[:-1]
                        tokeneater(DEDENT, '', (lnum, pos), (lnum, pos), line)
                    tokeneater(INDENT, '', (lnum, pos), (lnum, pos), line)
                doIndent = False
                                        
            pseudomatch = pseudoprog.match(line, pos)
            if pseudomatch:                                # scan for tokens
                start, end = pseudomatch.span(1)
                spos, epos, pos = (lnum, start), (lnum, end), end
                token, initial = line[start:end], line[start]

                if parseState.want_freestr and initial not in '<#`':
                    ret = tokeneater(FREESTR, line[start:],
                            (lnum, start), (lnum, len(line)), line)
                    if ret is not None:
                        pos = ret
                        continue
                    else:
                        break
                #else:
                #    parseState.want_freestr = 0

                wstart, wend = pseudomatch.span(0)
                if wstart != start:                  
                  assert line[wstart:start].isspace()
                  tokeneater(WHITESPACE, line[wstart:start], (lnum, wstart),
                             (lnum, start), line)
                
                if initial in numchars or \
                   (initial == '.' and token != '.'):      # ordinary number
                    tokeneater(NUMBER, token, spos, epos, line)
                elif initial in '\r\n':
                    tokeneater(parenlev > 0 and NL or NEWLINE,
                               token, spos, epos, line)
                elif initial == parseState.COMMENTCHAR:
                    tokeneater(COMMENT, token, spos, epos, line)                    
                elif initial == '`':                    
                    tokeneater(STRLINE, token, spos, epos, line)
                elif token in ("'''", '"""',               # triple-quoted
                               "r'''", 'r"""', "R'''", 'R"""',
                               "p'''", 'p"""', "P'''", 'P"""',
                               "pr'''", 'pr"""', "Pr'''", 'Pr"""',
                               "pR'''", 'pR"""', "PR'''", 'PR"""'):
                    endprog = endprogs[token]
                    endmatch = endprog.match(line, pos)
                    if endmatch:                           # all on one line
                        pos = endmatch.end(0)
                        token = line[start:pos]
                        tokeneater(STRING, token, spos, (lnum, pos), line)
                    else:
                        strstart = (lnum, start)           # multiple lines
                        contstr = line[start:]
                        contline = line
                        endcontline = max
                        break
                elif initial in ("'", '"') or \
                    token[:2] in ("r'", 'r"', "R'", 'R"',
                                  "p'", 'p"', "P'", 'P"') or \
                    token[:3] in ("pr'", 'pr"', "Pr'", 'Pr"',
                                  "pR'", 'pR"', "PR'", 'PR"' ):
                    if token[-1] == '\n':                  # continued string
                        strstart = (lnum, start)
                        endprog = (endprogs[initial] or endprogs[token[1]] or
                                   endprogs[token[2]])
                        contstr, needcont = line[start:], 1
                        contline = line
                        break
                    else:                                  # ordinary string
                        tokeneater(STRING, token, spos, epos, line)
                elif initial in namechars:                 # ordinary name
                    if token[-1] == ':':
                        tokeneater(NAME, token[:-1], spos, (lnum, pos-1), line)
                        tokeneater(OP, token[-1], epos, epos, line)
                    else:
                        tokeneater(NAME, token, spos, epos, line)
                elif initial == parseState.URIRef[1]:                 # URIRef
                    tokeneater(URIREF, token, spos, epos, line)                    
                elif initial == '\\':                      # continued stmt
                    continued = 1
                else: 
                    if initial in '(':
                        parenlev = parenlev + 1 #removed [{ and }]
                    elif initial in ')':
                        parenlev = parenlev - 1
                    tokeneater(OP, token, spos, epos, line)                    
                    if initial == parseState.NEWSTMTCHAR:
                        startpos = pos
                        countIndention = False
                        while pos < max and (line[pos].isspace() or
                                line[pos] == parseState.MARKUPSTARTCHAR):                            
                            if line[pos] == parseState.MARKUPSTARTCHAR:
                                #only measure the whitespace if it has a '<'
                                countIndention = True
                            pos += 1                            
                        if countIndention:
                            icolumn = column + (pos - startpos)
                        else:
                            #set column to the indention of the beginning
                            #of the physical line
                            icolumn = column
                        tokeneater(WHITESPACE, line[startpos:pos],
                                   (lnum, startpos),(lnum, pos), line)
                        doIndent = True
                    else:
                        rest = line[pos:]
                        remainderline = parseState.parseXML(rest)
                        if remainderline != rest: #xml parser consumed some text
                            line, pos, max =  remainderline, 0, len(remainderline)
            else:
                if parseState.want_freestr:
                    ret = tokeneater(FREESTR, line[pos:],
                            (lnum, pos), (lnum, len(line)), line)
                    if ret is not None:
                        pos = ret
                        continue
                    else:
                        break                
                tokeneater(ERRORTOKEN, line[pos],
                           (lnum, pos), (lnum, pos+1), line)
                pos = pos + 1

    tokeneater(ENDMARKER, '', (lnum, 0), (lnum, 0), '')

######################################################
###end tokenizer
######################################################

DEFAULT_MARKUPMAP_URI = 'http://rx4rdf.sf.net/zml/mm/default'

class UnknownMarkupMap(ZMLParseError):
    def __init__(self, uri):
        ZMLParseError.__init__(self, "Unknow markup map:" + uri)

class MarkupMapDetectionException(Exception):
    '''raise when detection is done'''

class Handler(object):
    '''
    SAX-like interface 
    '''
    nextHandler = None
    def __init__(self, nextHandler=None):
        self.nextHandler = nextHandler

    def startElement(self, element):
        if self.nextHandler:
            self.nextHandler.startElement(element)

    def attrib(self, name, value):
        if self.nextHandler:
            self.nextHandler.attrib(name, value)

    def endAttribs(self):
        if self.nextHandler:
            self.nextHandler.endAttribs()
        
    def endElement(self,element):
        if self.nextHandler:
            self.nextHandler.endElement(element)
        
    def comment(self, string):
        if self.nextHandler:
            self.nextHandler.comment(string)
        
    def text(self, string):
        if self.nextHandler:
            self.nextHandler.text(string)

    def whitespace(self, string):
        if self.nextHandler:
            self.nextHandler.whitespace(string)
        
    def pi(self, name, value):
        if self.nextHandler:
            self.nextHandler.pi(name, value)
        
    def endDocument(self):
        if self.nextHandler:
            self.nextHandler.endDocument()
        
class OutputHandler(Handler):
    def __init__(self, output):
        self.output = output
        self.element = None

    def __finishElement(self):
        if self.element:
            self.output.write(u'>')
        self.element = None
    
    def startElement(self, element):
        self.__finishElement()
        self.output.write( u'<' + element)                
        self.element = element

    def attrib(self, name, value):
        self.output.write(' ' + name + '=' + value)
        
    def endElement(self, element):
        if self.element:
            assert element == self.element, '%s != %s' % (element, self.element)
            self.output.write(u' />') #empty element
            self.element = None            
        else:
            self.output.write( u'</' + element + '>')        
        
    def comment(self, string):
        self.__finishElement()
        if string.find('--') != -1:
            raise ZMLParseError(' "--" not allowed in comments')
        self.output.write( u'<!--' + string.rstrip('\n') + '-->')
        
    def text(self, string):
        self.__finishElement()
        self.output.write( string ) #no escaping -- allow inline xml markup
        
    def whitespace(self, string):
        pass#self.output.write( string ) #this put whitespace in places you wouldn't expect

    def pi(self, name, value):
        self.__finishElement()
        self.output.write( u'<?' + name + ' ' + value.rstrip('\n') + '?>')
    
    def endDocument(self):
        self.__finishElement()

class Annotation(object):
    '''
    An link annotation is really just a simple representation of an XML element.

    Attributes:
    name is None or a qname or simple name
    attribs is a list of (name, value) pairs (where name may be a qname)
    children can have either (unicode) strings or annotations as children
    '''
    def __init__(self, name=None, parent=None):
        self.name = name
        self.attribs = []
        self.children = []
        self.parent = parent

    def pushAnnotation(self, handler):
        handler.startElement(self.name)
        for name, value in self.attribs:
            handler.attrib(name, value)
        handler.endAttribs()
        for child in self.children:
            if hasattr(child, 'name'):
                child.pushAnnotation(handler)
                handler.endElement(child.name)
            else:
                handler.text(child)                    

class _WikiElemName(str):
    '''
    This marker class indicates that the element named here was
    generated by wiki markup.
    '''

class _WikiSectionElemName(_WikiElemName): 
    level = 0 #the higher the level the better

class _WikiInlineElemName(_WikiElemName): pass

OLCHAR = '1'
class MarkupMap(object):
    '''
    Derive from this class to wiki markup output.
    Element attributes can either be string (e.g. "TABLE") or a tuple like:
    ('TABLE', (('class','"wiki"'),) ) where the second item is a tuple
    of attribute name value pairs.
    The element method is used as an dictionary keys, so tuples, not lists,
    must be used.
    '''
    #block
    UL, OL, LI, DL, DD, DT = 'UL', 'OL', 'LI', 'DL', 'DD', 'DT', 
    P, HR, PRE, BLOCKQUOTE = 'P', 'HR', 'PRE', 'BLOCKQUOTE'
    DIV, SECTION = _WikiSectionElemName('DIV'), _WikiSectionElemName('DIV')#('DIV', (('class',"'section'"),) )
    blockElems = [ 'UL', 'OL', 'LI', 'DL', 'DD', 'DT', 'P', 'HR', 'PRE',
                   'BLOCKQUOTE', 'SECTION', 'DIV'] 
    #header
    H1, H2, H3, H4, H5, H6 = 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'
    headerElems = [ 'H1', 'H2', 'H3', 'H4', 'H5', 'H6' ]
    #table
    TABLE, TR, TH, TD = 'TABLE', 'TR', 'TH', 'TD'    
    tableElems = [ 'TABLE', 'TR', 'TH', 'TD' ]
    #inline:
    I, B, TT, A, IMG, SPAN, BR = 'EM', 'STRONG', 'TT', 'A', 'IMG', 'SPAN', 'BR'
    inlineElems = [ 'I', 'B', 'TT', 'A', 'IMG', 'SPAN', 'BR']

    INLINE_IMG_EXTS = ['.png', '.jpg', '.gif']

    docType = ''
    
    nameClass = 'rhizomename'
    annotationClass = 'zmlannotation'
        
    def __init__(self):
        #wikistructure maps syntax that correspond to strutural
        #elements that only contain block elements (as opposed to
        #inline elements) create per instance instead of at the class
        #level so the attributes are lazily evaluated, making
        #subclassing less tricky
        self.wikiStructure = { '*' : [self.UL, self.LI ],
                               OLCHAR : [self.OL, self.LI],
                               ':' : [self.DL, self.DD ],
                               '+' : [self.DL, self.DT ],
                               '|' : [self.TABLE, self.TR],
                               '!' : [self.DIV,self.H1]
                               }

        #rough order in which block elements can appear,
        #from outermost to innermost
        self.blockModel=[self.SECTION, self.BLOCKQUOTE, self.UL, self.OL,
                                                 self.DL, self.TABLE, self.P]
        self.innermostSectionalElement = self.BLOCKQUOTE

    def canonizeElem(self, elem):
        '''
        implement if you have elements that might vary from
        instance to instance, e.g. map H4 -> H or (elem, attribs) ->
        elem '''
        return elem

    def getStructureAttribs(self, token, structNames):
        attribs = {}
        for name in structNames:
            if name[0] == '#':
                #todo: if its a (c)URI, add namespace
                attribs['id'] = xmlquote( name[1:] )
                attribs['about'] = xmlquote( name )
            elif ':' in name: #its a (C)URI
                #todo: add namepsace if necessary 
                attribs.setdefault('role', []).append(name) 
            else:
                attribs.setdefault('class', []).append(name) 

        values = attribs.get('class')
        if values:
            attribs['class'] = xmlquote( ' '.join(values) )
        #values = attribs.get('role') #todo
        #if values:
        #    attribs['role'] = Curi( ' '.join(values) )

        return tuple( attribs.iteritems() )                 
                      
    def H(self, level, line):
        '''
        We support two styles of markup
        <h1>one line</h1>
        or 
        <section>
        aribtrary text
            <section>
            aribtrary text
            </section>        
        <section>        
        
        To indicate the latter, add '!' to the wikiStructure dict,
        e.g. self.wikiStructure['!'] = ( self.SECTION, None)
        or
        self.wikiStructure['!'] = ( self.SECTION, self.TITLE)
        '''
        h = getattr(self, self.headerElems[level-1]) #evaluate lazily
        if self.wikiStructure.get('!') and level==1:
            div = _WikiSectionElemName(self.DIV)
            div.level = level
            div = (div,(('class',"'h"+str(level)+"'" ),) )
            if line:
                #only include the line if there's text
                return (div, _WikiInlineElemName(h)) 
            else:
                return (div, None)
        else:
            if not line:
                div = _WikiSectionElemName(self.DIV)
                div.level = level
                return (div,(('class',"'h"+str(level)+"'" ),) ) 
            else:
                return h
        
    def _fixupAnnotations(self, annotation):
        name = annotation.name 
        annotation.name = self.SPAN #todo: support attributes
        annotation.attribs += [('class',xmlquote(self.annotationClass + ' ' + name, False) )]
        #todo:merge class atts
        for child in annotation.children:
            if hasattr(child, 'name'):
                self._fixupAnnotations(child)    
            
    def mapAnnotationsToMarkup(self, annotationsRoot, name):
        #get the first node of the annotation, which can be either an element
        #or a string
        # root: [text | annotation]
        ##type = getattr(annotationsRoot.children[0], 'name',
        ##               annotationsRoot.children[0])
        #always None since we never change the text
        #also don't escape the attribute because the annotation parser
        #already did this
        ##return self.SPAN, [('class',xmlquote(type, False) )], None
        #only support one root annotation now
        root = annotationsRoot.children[0]
        if not hasattr(root, 'name'):
            root = Annotation(root) #treat text as name
        self._fixupAnnotations(root)
        #if there were any other children, just treat them as 
        #a name to add to the class
        index =[i for i, att in enumerate(root.attribs) if att[0] == 'class']
        assert index, 'root must have a class attribute'
        index = index[-1]
        for child in annotationsRoot.children[1:]:
            name = getattr(child, 'name','')
            if name:
                attVal = root.attribs[index][1]
                root.attribs[index] = ('class', 
                    attVal[:-1] + ' ' + name + attVal[0])
        return root

    def mapLinkToMarkup( self, link, name, annotations, isImage, isAnchorName):
        '''
        return (element, attrib list, text)
        '''        
        if name is None:
            if link.startswith('site:///'):
                generatedName = link[len('site:///'):]
            elif link.startswith('#'): #anchor link
                generatedName = link[1:] 
            else:
                generatedName = link
            generatedName = xmlescape(generatedName)
        else:
            generatedName = ''
        #print link, not annotations or [a.name for a in annotations]
        if isImage and (annotations is None or 
                not [annotation for annotation in annotations.children
                    if getattr(annotation, 'name', None) == 'wiki:xlink-replace']):
            attribs = [ ('src', xmlquote(link)),
                        ('alt', xmlquote(name or generatedName)) ]
            return self.IMG, attribs, '' #no link text (IMG is an empty element)
        else:
            if isAnchorName:
                attribs = [('name', xmlquote(link)) ]
            else:
                attribs = [ ('href', xmlquote(link)) ]
            if annotations and annotations.children:
                first = getattr(annotations.children[0], 'name',
                                annotations.children[0])
                if first != 'wiki:xlink-replace':     #todo: handle curi      
                    attribs += [ ('rel', xmlquote(first)) ]
            if generatedName:
                return self.A, attribs, generatedName
            else:
                return self.A, attribs, None #don't override the link text

#create a MarkupMap subclass with lowercase versions of all the elements names
class LowerCaseMarkupMap(MarkupMap):
    def canonizeElem(self, elem):
        elem = MarkupMap.canonizeElem(self, elem)
        if isinstance(elem, tuple):
            return (elem[0].lower(), elem[1])
        else:
            return elem.lower()

for varname in (MarkupMap.blockElems +
        MarkupMap.headerElems + MarkupMap.tableElems + MarkupMap.inlineElems):
    att = getattr(LowerCaseMarkupMap, varname)
    setattr(LowerCaseMarkupMap, varname, att.__class__(att.lower()) )
    
class DefaultMarkupMapFactory(Handler):
    '''
    This class is used to dynamic choose the appropriate MarkupMap
    based on the first element and comments encountered. Any Handler
    method may return a MarkupMap. See MarkupMapFactoryHandler for
    more info.
    '''
    done = False
    
    def getDefault(self):        
        return LowerCaseMarkupMap()

    def getMarkupMap(self, uri):
        if uri == DEFAULT_MARKUPMAP_URI:
            return self.getDefault()
        else:
            raise UnknownMarkupMap(uri)

class MarkupMapFactoryHandler(Handler):
    '''
    Calls MarkupMapFactory.startElement for the first element
    encountered and MarkupMapFactory.attrib, MarkupMapFactory.pi and
    MarkupMapFactory.comment until the second element is encountered

    If the MarkupMapFactory returns a MarkupMap, use that one
    '''    
    terminate = False
    
    def __init__(self, parseState, handler=None):
        super(MarkupMapFactoryHandler, self).__init__(handler)
        self.markupfactory = parseState.mmf
        self.elementCount = 0
        self.st = parseState

    def startElement(self, element):
        #examine first element encountered
        if not self.markupfactory.done and self.elementCount < 1: 
            mm = self.markupfactory.startElement(element)
            if mm:
                self.st.mm = mm
        self.elementCount += 1
        if self.terminate and self.elementCount == 2:
            raise MarkupMapDetectionException()
        super(MarkupMapFactoryHandler, self).startElement(element)
            
    def attrib(self, name, value):        
        if not self.markupfactory.done and self.elementCount < 2:                
            mm = self.markupfactory.attrib(name, value)
            if mm:
                self.st.mm = mm
        #elif self.elementCount == 1 and name == 'xmlns':
        #    self.defaultNSDeclaration = value
        super(MarkupMapFactoryHandler, self).attrib(name, value)

    def text(self, string):
        #note: <!DOCTYPE will should up as text
        if not self.markupfactory.done and self.elementCount < 2:
            mm = self.markupfactory.text(string)
            if mm:
                self.st.mm = mm
        super(MarkupMapFactoryHandler, self).text(string)
                            
    def comment(self, string): 
        if not self.markupfactory.done and self.elementCount < 2:
            mm = self.markupfactory.comment(string)
            if mm:
                self.st.mm = mm      
        super(MarkupMapFactoryHandler, self).comment(string)
        
    def pi(self, name, value): 
        if not self.markupfactory.done and self.elementCount < 2:
            mm = self.markupfactory.pi(name, value)
            if mm:
                self.st.mm = mm
        super(MarkupMapFactoryHandler, self).pi(name, value)

def interWikiMapParser(interwikimap, xmlescape=True, replaceDict=None):
    interWikiMap = {}
    for line in interwikimap:
        line = line.strip()
        if line and not line.startswith('#'):
            prefix, url = line.split()
            if replaceDict:
                url = url % replaceDict
            if xmlescape:
                url = url.replace('&', '&amp;').replace('<', '&lt;')
            interWikiMap[prefix.lower()] = url
    return interWikiMap

def isQName(name):
    parts = name.split(':')
    if len(parts) > 2:
        return False
    return bool( [p for p in parts if isNCName(name)])

_XMLNameChars = re.compile(r'[\w\.\-]+', re.U)
def isNCName(name):
    return re.match(_XMLNameChars, name) and name[0].isalpha()

def stripQuotes(strQuoted, checkEscapeXML=True):    
    if strQuoted[0] == '`':
        if strQuoted[-1].isspace():#normalize trailing whitespace
            return strQuoted[1:].replace('&', '&amp;').replace(
                                      '<', '&lt;').rstrip() + ' '
        else:
            return strQuoted[1:].replace('&', '&amp;').replace('<', '&lt;')

    #we xml escape strings unless raw quote type is specifed        
    escapeXML = checkEscapeXML and not (strQuoted[0] in 'rR'
                or (strQuoted[0] in 'pP' and strQuoted[1] in 'rR'))
        
    #python 2.2 and below won't eval unicode strings while in unicode,
    #so temporarily encode as UTF-8
    if sys.version_info < (2, 3) and isinstance(strUnquoted, unicode):
        strQuoted = strQuoted.encode("utf8")

    #remove p prefix from string
    if strQuoted[0] in 'pP':
        strQuoted = 'u' + strQuoted[1:]
    elif strQuoted[0] in 'rR' and strQuoted[1] in 'pP':
        strQuoted = 'ur' + strQuoted[2:]
    if escapeXML:
        #we need to do this before eval() because eval("'\&'") == eval("'\\&'")
        strQuoted = xmlescape(strQuoted)
    strUnquoted = eval(strQuoted)
    #now handle and \U and \u: replace with character reference
    strUnquoted = re.sub(r'\\U(.{8})', r'&#x\1;', strUnquoted)
    strUnquoted = re.sub(r'\\u(.{4})', r'&#x\1;', strUnquoted)        
    return strUnquoted

def xmlquote(quote, escape=True):
    if escape:
        quote = quote.replace('&', '&amp;').replace('<', '&lt;')
    if quote.find('"') == -1:
        return '"' + quote + '"'
    elif quote.find("'") == -1:
        return "'" + quote + "'"
    else:
        return '"' + quote.replace('"', '&quot;') + '"'

def xmlescape(s):
    r'''xml escape & and < unless proceeded by an odd number of \
        e.g. '\&' -> '&' but '\\&' -> '\\&amp;'
    '''            
    def replace(match):
        pos = match.start() #this will point to either \ or the searchChar        
        raw = False        
        while pos > -1 and s[pos] == '\\':
            raw = not raw
            pos -= 1
            
        if raw:
            #print s[match.start():match.end()], searchChar
            return searchChar
        else:            
            if s[match.start()] == '\\':
                #print s[match.start():match.end()], '\\' + replaceStr
                return '\\' + replaceStr
            else:
                #print s[match.start():match.end()], replaceStr
                return replaceStr

    searchChar = '&'
    replaceStr = '&amp;'            
    s = re.sub(r'\\?'+searchChar, replace, s)#&amp sub must go first

    searchChar = '<'
    replaceStr = '&lt;'            
    s = re.sub(r'\\?'+searchChar, replace, s)
    return s
        
def zmlString2xml(strText, markupMapFactory=None, **kw):
    if isinstance(strText, unicode):
        strText = strText.encode("utf8")
    fd = StringIO.StringIO(strText)
    contents = zml2xml(fd, mmf=markupMapFactory, **kw)   
    return contents

def splitURI(uri):
    for i in xrange(len(uri)-1,-1,-1):
        if not (uri[i].isalnum() or uri[i] in '.-_'):
            #the first character can't begin with a number or . or _            
            while not uri[i+1].isalpha() and uri[i+1] != '_':
                i += 1
                if i+1 == len(uri):
                    return uri, '' #can't split                    
            return uri[:i+1], uri[i+1:]
    return uri, ''

def parseLinkType(string, version=None):
    '''
    parse the annotation string e.g.:
    foo:bar attribute='value': foo:child 'sometext'; foo:annotation2; 'plain text annotation';
    returns a list of Annotations
    '''
    class TypeParseHandler(Handler):
        def __init__(self):            
            self.annotation = Annotation() #doc root
            
        def startElement(self, element):
            node = Annotation(element, self.annotation)
            self.annotation.children.append( node )
            self.annotation = node

        def endElement(self, element):
            assert self.annotation.parent
            self.annotation = self.annotation.parent
            
        def attrib(self, name, value):            
            self.annotation.attribs.append( (name, value) )
            
        def text(self, string):
            self.annotation.children.append(string)
            
        def comment(self, string):
            pass #ignore comments
            #anything after the ; is another annotation, if anything
            #if string:
            #    parseLinkType(string, self.annotationList)
        
    handler = TypeParseHandler()
    zmlString2xml(string, handler=handler, mixed=False, zmlVersion=version)
    assert handler.annotation.parent is None
    if version and version < 0.8 and handler.annotation.children:
        handler.annotation.children = handler.annotation.children[:1]
        if hasattr(handler.annotation.children[0], 'attribs'):
            handler.annotation.children[0].attribs = []
    return handler.annotation

def parseAttributes(string):
    '''
    Parses an attribute lists like "((foo=bar, ))((another=list))"
    and returns the pos after the end of the list(s) and a list of 
    attribute lists, each of which contain attribute name value pairs.
    '''
    if not string.lstrip().startswith('(('):
        return 0, [ [] ]    

    #parse until encounter final '))'
    class AttributeHandler(Handler):
        def __init__(self):            
            self.attribs = [] 
                        
        def attrib(self, name, value):            
            self.attribs.append( (name, value) )
        
        def endAttribs(self):
            raise ZMLParseError(code=ZMLParseError.USER_DEFINED)

        def text(self, string):
            raise ZMLParseError('unexpected markup while parsing attributes')            

        def endDocument(self):
            raise ZMLParseError('parsing attributes finished before encountering "))"') 

    try:
        handler = AttributeHandler()
        zmlString2xml('<dummy ' + string, handler=handler, zmlVersion=0.8)
    except ZMLParseError, e:
        if e.code in [ZMLParseError.USER_DEFINED,
                      ZMLParseError.TOKEN_NOT_IN_ATTRIBUTES]:
            pos = e.state.currentStartPos[1] - len('dummy ')
            assert pos > -1
            morePos, moreAttr = parseAttributes(string[pos:])
            return pos+morePos, [ handler.attribs ] + moreAttr
        else:
            raise        
    assert False, 'parseAttributes did not complete successfully'
    
class Parser(object):
    parseState = None
    parseStateFactory = None
    
    def __init__(self, mixedMode = True, mmf=None, wantVersion=1.0,
                 parseStateFactory=None):
        self.mmf = mmf or DefaultMarkupMapFactory()
        self.markupMode = not mixedMode
        #a bit of a hack, used by zml07.copyZML
        self.parseStateFactory = parseStateFactory
        self.parseState = self.setZMLVersion(wantVersion)

    def setZMLVersion(self, version):
        if self.parseState and self.parseState.handlesVersion(version):
            return self.parseState
        else:            
            mixed = not self.markupMode
            if self.parseStateFactory:
                self.parseState = self.parseStateFactory(mixed)
                return self.parseState

            if version == 0.8 or version == 1.0:
                parser = ParseState(mixed, self.mmf)
            elif version == 0.9 or version == 0.7:
                from rx import zml07                
                parser = zml07.OldParseState(mixed, self.mmf)
            else:
                raise ZMLParseError("unknown ZML version: " + str(version))
            if self.parseState:
                #parser.mm = self.parseState.mm
                parser.URIAdjust = self.parseState.URIAdjust
                parser.namespaceStack = self.parseState.namespaceStack
                parser.debug = self.parseState.debug
                parser.handler = self.parseState.handler
            self.parseState = parser
            return parser
        
class ParseState(object):
    forVersion = [0.8, 1.0]
    in_xml = None
    escapeXML = False

    defexp =  r'\='
    tableexp= r'\|' 
    bold= r'__'
    italics= r'(?<!:)//' #ignore cases like http://
    monospace= r'\^\^'
    brexp= r'\~\~'
    linkexp = r'\[\[.*?\]\]'
    nameexp = r"''.*?''" 
    #match any of the above unless proceeded by an odd number of \
    inlineprog = re.compile(r'(((?<!\\)(\\\\)+)|[^\\]|^)'+
        group('<',defexp,tableexp,bold,monospace,italics,linkexp,brexp,nameexp))
    
    def __init__(st, mixedMode = True, mmf=None):
        mmf = mmf or DefaultMarkupMapFactory()
        st.mmf = mmf
        st.mm = mmf.getDefault()
        
        st.in_attribs = 0
        st.in_elemchild = 0

        st.attribs = []
        st.currentLine = ''
        st.currentStartPos = (0, 0)
        st.nextGeneratedPrefixCounter = 0    
        st.elementStack = [ [] ]
        st.namespaceStack = [ ]

        st.markupMode = not mixedMode
        st.want_freestr = mixedMode
        st.pendingElements = []

        st.MARKUPSTARTCHAR = 'disable'
        
        #not used anymore
        st.wikiStack = []    
        st.in_freeform = 0 #are we in wikimarkup?
        st.nlcount = 0 #how many blank lines following wikimarkup        
        st.useFreestr = False
        st.pseudoprog,st.endprogs,st.nameOrUriProg = st.makeTokenizer()
        curiMatch = group(st.Name, st.URIRef)
        structNameMatch = '(#X|X)(,\s*(#X|X))*'.replace('X',curiMatch)
        st.structNameProg = re.compile(structNameMatch)
        
    def setMarkupMode(self, mode):
        self.markupMode = mode
        self.want_freestr = not mode

    def handlesVersion(self, version):
        return version in self.forVersion

    COMMENTCHAR = '#' 
    NEWSTMTCHAR = ';'

    #define name as a very loose URI match: start with alpha char followed 
    #by any number of the acceptable URI characters with some restrictions on
    #the acceptable characters (')[];: and more for the last character
    Name =  r"[a-zA-Z_]([\w:.\-\]\[/?@&+$,!~*%#]*[\w.\-\/?@&+$!~*%#])?"
    #rough URI match in brackets (todo: support IP6 addresses with []) 
    URIRef =  r"\[[a-zA-Z_][\w:.\-\]\[;/?@&=+$,!~*'()%#]*\]"
    
    def makeTokenizer(self):
        Whitespace = r'[ \f\t]*'
        Comment = self.COMMENTCHAR + r'[^\r\n]*' 
        StrLine = r'`[^\r\n]*'
        Ignore=Whitespace+any(r'\\\r?\n'+Whitespace)+maybe(Comment)+maybe(StrLine)
        Name, URIRef = self.Name, self.URIRef
        Hexnumber = r'0[xX][\da-fA-F]*[lL]?'
        Octnumber = r'0[0-7]*[lL]?'
        Decnumber = r'[1-9]\d*[lL]?'
        Intnumber = group(Hexnumber, Octnumber, Decnumber)
        Exponent = r'[eE][-+]?\d+'
        Pointfloat = group(r'\d+\.\d*', r'\.\d+') + maybe(Exponent)
        Expfloat = r'[1-9]\d*' + Exponent
        Floatnumber = group(Pointfloat, Expfloat)
        Imagnumber = group(r'0[jJ]', r'[1-9]\d*[jJ]', Floatnumber + r'[jJ]')
        Number = group(Imagnumber, Floatnumber, Intnumber)
    
        # Tail end of ' string.
        Single = r"[^'\\]*(?:\\.[^'\\]*)*'"
        # Tail end of " string.
        Double = r'[^"\\]*(?:\\.[^"\\]*)*"'
        # Tail end of ''' string.
        Single3 = r"[^'\\]*(?:(?:\\.|'(?!''))[^'\\]*)*'''"
        # Tail end of """ string.
        Double3 = r'[^"\\]*(?:(?:\\.|"(?!""))[^"\\]*)*"""'
        Triple = group("[pP]?[rR]?'''", '[pP]?[rR]?"""')
        # Single-line ' or " string.
        String = group(r"[pP]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*'",
                       r'[pP]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*"')
    
        # Because of leftmost-then-longest match semantics, be sure to put the
        # longest operators first (e.g., if = came before ==, == would get
        # recognized as two instances of =).
        Operator = group(r"\*\*=?", r">>=?", r"<<=?", r"<>", r"!=",
                         r"[+\-*/%&|^=<>]=?",
                         r"~")
    
        Bracket = '[()]' #remove ][{}
        Special = group(r'\r?\n', r'[:;,]') #removed `.
        Funny = group(Operator, Bracket, Special)
    
        PlainToken = group(Funny, String, Name, Number) 
        Token = Ignore + PlainToken
    
        # First (or only) line of ' or " string.
        ContStr = group(r"[pP]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*" +
                        group("'", r'\\\r?\n'),
                        r'[pP]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*' +
                        group('"', r'\\\r?\n'))
        PseudoExtras = group(r'\\\r?\n', Comment, Triple, StrLine)
        PseudoToken = Whitespace + group(PseudoExtras, Funny, ContStr,
                                         Name, URIRef, Number) #added URIRef 
    
        tokenprog, pseudoprog, single3prog, double3prog = map(
            re.compile, (Token, PseudoToken, Single3, Double3))
        endprogs = {"'": re.compile(Single), '"': re.compile(Double),
                    "'''": single3prog, '"""': double3prog,
                    "r'''": single3prog, 'r"""': double3prog,
                    "p'''": single3prog, 'p"""': double3prog,
                    "pr'''": single3prog, 'pr"""': double3prog,
                    "R'''": single3prog, 'R"""': double3prog,
                    "P'''": single3prog, 'P"""': double3prog,
                    "pR'''": single3prog, 'pR"""': double3prog,
                    "Pr'''": single3prog, 'Pr"""': double3prog,
                    "PR'''": single3prog, 'PR"""': double3prog,
                    'r': None, 'R': None, 'p': None, 'p': None}
        return pseudoprog, endprogs, re.compile(group(Name, URIRef))

    def parseXML(parseState, line):
        if parseState.in_xml:
            if not line:
                parseState.in_xml.close()            
            else:
                try:
                    parseState.in_xml.feed(line)
                    line = '' #all consumed by the xml parser                
                except StopTokenizing:
                    #what the parser didn't consume
                    line = parseState.in_xml.rawdata 
                    parseState.in_xml = None
        return line
        
    def inlineTokenMap(st):
        return { '/' : st.mm.I, '_' : st.mm.B, '^' : st.mm.TT}

    def processInlineToken(st, elem, inlineTokens=None, userAttribs=() ):
        if isinstance(elem, tuple):
            name = elem[0]
        else:
            name = elem
            
        open = st.elementStack[-1].count(name)
        #todo: open = [ st.mm.canonizeElem(x) for x in
        #   st.elementStack[-1] ].count( st.mm.canonizeElem(name) )
        if open: #if the elem is open, close it
            st.popWikiStack(elem) #pop all elements until we reach this one
        else: 
            st.pushWikiStack(elem, userAttribs, _WikiInlineElemName)
     
    def handleInlineWiki(st, string, wantTokenMap=None, userTextHandler=None):
        inlineTokens = st.inlineTokenMap()
        if wantTokenMap is None:
            wantTokenMap = inlineTokens
        if userTextHandler is None:
            userTextHandler = lambda s: st.handler.text(s)
            
        if st.escapeXML:
            #xmlescape then strip out \ (but not \\) 
            textHandler = lambda s: userTextHandler(re.sub(r'\\(.)',r'\1',
                                                           xmlescape(s)) )
        else:
            textHandler = userTextHandler
            
        pos = 0
        while 1:
            #we can't do search(string, pos) because of ^ in our regular expression
            match = st.inlineprog.search(string[pos:]) 
            if match:
                start, end = match.span(4) #0
                start += pos
                end += pos
                token = string[start]
                if token == '<':
                    st.nlcount = 0
                    textHandler(string[pos:start])
                    return start
                if st.nlcount:
                    st.pushWikiStack(st.mm.P)
                    st.nlcount = 0

                elem = wantTokenMap.get(token)
                if elem or token in "~'[":
                    textHandler(string[pos:start])
                    if st.forVersion[0] >= 0.8:
                        newpos, customAttributes = parseAttributes(
                            string[start:])
                        assert customAttributes
                        start += newpos
                    else:
                        customAttributes = (None,)                        
  
                elem = wantTokenMap.get(token)
                if elem:                
                    if token == '=':
                        del wantTokenMap['='] #only do this once per line
                    elif token == '|':
                        #if || its a TH
                        if len(string) > start+1 and string[start+1] == '|': 
                            cell = st.mm.TH
                            end += 1 #skip second |
                        else:
                            cell = st.mm.TD
                        #user may have switched from || to | or from || to |
                        #(not sure if this is valid html though)
                        wantTokenMap['|'] = cell 

                    if token in inlineTokens.keys():
                        st.processInlineToken(elem, inlineTokens, 
                            customAttributes[0])
                    else:
                        st.popWikiStack() #pop the DT or last TD or TH
                        #push the DD or TD or TH
                        st.pushWikiStack(elem,customAttributes[0]) 
                    pos = end
                elif token == '~': #<BR>
                    st.pushWikiStack(st.mm.BR, customAttributes[0])
                    st.popWikiStack()
                    pos = end
                elif token in "['": #its a link
                    #handle special case of "[]" -- just print it 
                    if string[start+1] == ']':                        
                        textHandler( string[start:start+1] )
                        pos = start+1 
                        continue
                                        
                    pos = end
                    if st.forVersion[0] < 0.8:
                        delimLen = 1
                    else:
                        delimLen = 2
                    #strip [[ and ]] 
                    linkToken = string[start+delimLen:end-delimLen] 

                    nameAndLink = linkToken.split('|', 1)
                    if len(nameAndLink) == 1:
                        name = None
                    else:
                        name = nameAndLink[0].strip()                    
                        namechunks = []
                        #parse out any wiki markup in the name
                        #(using a dummy handler)
                        #use __class__ so subclasses create the right type of ParseState
                        dummyState = st.__class__() 
                        dummyState.handler = Handler()
                        dummyState.mm = st.mm
                        dummyState.handleInlineWiki(name, None,
                                        lambda s: namechunks.append(s))
                        name = ''.join(namechunks)                    
                    linkinfo = nameAndLink[-1].strip() #the right side of the |
                    
                    words = linkinfo.split()
                    if not words:
                        raise ZMLParseError('link missing URL: ['+linkToken+']')

                    #last character is the annotation delineator,
                    #so there's no link
                    if words[-1][-1] == ';': 
                        #todo: actually, a valid URL could end in a ';'
                        #but that is an extremely rare case we don't support
                        link = None
                        type = ' '.join(words)
                    elif len(words) > 1 and words[-2][-1] == ';':
                        #annotation preceeding link
                        link = words[-1]
                        type = ' '.join(words[:-1])
                    else: 
                        if len(words) > 1:
                            #must be a link like [this is also a link]
                            if name is not None:                                
                                raise ZMLParseError(
                        'link URL can not contain spaces: ' + ''.join(words))
                            if [word for word in words if not word.isalnum()]:
                                #error: one of the words has punctuation, etc.
                                raise ZMLParseError('invalid link: ' + linkToken)
                            link = ''
                            #[this is also a link] creates a hyperlink to an
                            #internal WikiPage called 'ThisIsAlsoALink'.
                            for word in words:
                                #can't use capitalize(),
                                #it makes other characters lower
                                link += word[0].upper() + word[1:] 
                            name = ' '.join(words)
                        else:
                            link = words[0]
                        type = None
                        
                    if type:
                        #type is a list of Annotations 
                        type = parseLinkType(type, st.forVersion[0])
                    if token == "'":
                        if not type:
                            type = Annotation()
                        type.children.append( Annotation(st.mm.nameClass, type) )
                                                            
                    if link:                                                          
                        isInlineIMG = (link[link.rfind('.'):].lower()
                                       in st.mm.INLINE_IMG_EXTS)
                        isFootNote = link[0] == '#'
                        isAnchor = link[0] == '&'
                        if isAnchor:
                            link = link[1:] #strip &
                        element, attribs, text = st.mm.mapLinkToMarkup(
                                link, name, type, isInlineIMG, isAnchor)

                        st.handler.startElement(element)
                        for name, value in attribs:
                            st.handler.attrib(name, value)
                        st.handler.endAttribs()                    
                        if text is not None: 
                            st.handler.text( text )
                        else:
                            st.handleInlineWiki(nameAndLink[0].strip(), None)
                        st.handler.endElement(element)
                    else: #no link, just a type
                        assert(type)
                        #element, attribs, text = 
                        annotation = st.mm.mapAnnotationsToMarkup(type, name)
                        annotation.pushAnnotation(st.handler)
                        st.handleInlineWiki(nameAndLink[0].strip(), None)
                        assert annotation.name
                        st.handler.endElement(annotation.name) 
                else:
                    textHandler( string[pos:start+1] )                
                    pos = start+1 #skip one of the brackets                
                    continue
            else:
                if st.nlcount and string[pos:]:
                    st.pushWikiStack(st.mm.P)
                    st.nlcount = 0                
                break            
        textHandler( string[pos:] )

    def normalizeAttribs(st, attribs):
        '''
        returns list of (name, value) tuples (use list to preserve order)
        '''
        cleanAttribs = []
        i = 0
        while i+1 <= len(attribs):
            #last item or next item != '=' : assume attribute minimalization
            if i+1 == len(attribs) or attribs[i+1] != '=': 
                cleanAttribs.append( (attribs[i], '"' + attribs[i] + '"') )
                i+=1
            else:
                val = attribs[i+2]
                if val[0] not in '\'"':
                    val = '"'+val+'"'
                cleanAttribs.append( (attribs[i], val) )
                i+=3    

        return cleanAttribs
    
    def uriToQName(st, token):
        if token[0] == st.URIRef[1]:
            uri = token[1:-1] #strip {}
        else:
            uri = token
        if not uri:
            raise ZMLParseError('syntax error: empty URI element')        
        if not uri[-1].isalnum() and uri[-1] not in '.-':
            if not st.URIAdjust: 
                if uri[-1] != '_': #trailing _ is ok in this case
                    raise ZMLParseError('invalid URI as element name: %s'
                                        % repr(uri))
            else:
                #add another _ to assure we can split the URI into a qname
                uri += '_'
                
        prefix, local = '',''    
        addNSMapping = True
        namespaces = []
        inScope = {}
        #find the namespaces in scope
        for i in range(len(st.namespaceStack)-1,-1,-1): #reverse order            
            namespaceDict = st.namespaceStack[i] 
            for prefixCandidate, namespace in namespaceDict.items():                        
                if prefixCandidate not in inScope:
                    #hasn't been overridden
                    inScope[prefixCandidate] = namespace
                    namespaces.append((prefixCandidate, namespace))

        #first check if URI is a CURI
        namespaceURI = ''
        uri_parts = uri.split(':', 1)
        namespace = inScope.get( uri_parts[0] )
        if namespace:
            uri = namespace + uri_parts[1]
            if isNCName(uri_parts[1]):
                prefix = uri_parts[0]
                addNSMapping = False 
        #todo: check given nsmapping
        #elif uri_parts[0] in nsmapping:
        #    #we need to add this ns mapping to the doc 
        #    namespaceURI, local = nsmapping[ uri_parts[0] ],  uri_parts[1]
        #    uri = namespaceURI + local
        #    prefix = uri_parts[0]
        
        if not prefix:
            #look for a namespace mapping that can be used
            for (prefixCandidate, nsuri) in namespaces:
                if uri.startswith(nsuri):
                    local = uri[len(nsuri):]
                    if isNCName(local):
                        prefix = prefixCandidate
                        addNSMapping = False
                        break            
                
        if addNSMapping: #add a namespace mapping  
            if not prefix:                 
                while 1:
                    #make sure the generated prefix doesn't override 
                    #an in-scope user declared prefix
                    st.nextGeneratedPrefixCounter += 1
                    prefix = 'ns' + str(st.nextGeneratedPrefixCounter)
                    if prefix not in inScope:
                        break
                    
            if not namespaceURI:
                namespaceURI, local = splitURI(uri)
            if not local: #uri ended in a non-alphabetic character
                local = u'_'                
            assert prefix and namespaceURI and local, "%s %s %s" % (
                                        prefix, namespaceURI, local)
            st.namespaceStack[-1][prefix] = namespaceURI

            newNS = ('xmlns:'+ prefix, "'"+namespaceURI+"'")
        else:
            newNS = None
        assert local
        return prefix + ':' + local, newNS
        
    def startElement(st):
        st.in_attribs = 0        

        cleanAttribs = st.normalizeAttribs(st.attribs)

        #first pass: check for any explicit namespace declarations
        for name, value in cleanAttribs:
            #add namespace to map
            if name.startswith('xmlns:'):                
                #note: we don't care about the default namespace                
                st.namespaceStack[-1][name[len('xmlns:'):] ] = value[1:-1]
            elif name.startswith('xml:base'):
                pass#st.docbase.append( value ) #todo

        name = st.elementStack[-1][-1]

        if not isQName(name): #its a URIRef
            name, newNS = st.uriToQName(name)
            if newNS:
                cleanAttribs.append( newNS )
            st.elementStack[-1][-1] = name
             
        st.handler.startElement( name )
    
        for name, value in cleanAttribs:
            #check for URIRefs and add namespaces declarations if necessary
            if not isQName(name):
                name, newNS = st.uriToQName(name)
                if newNS:
                    st.handler.attrib(newNS[0],newNS[1])
            
            #skip: don't treat values as URIRefs
            #if value and value[0] == '{':
            #    #note: this code results in a URIRef as an attribute value
            #    #being converted to a qname
            #    value, newNS = st.uriToQName(value)
            #    if newNS:
            #        st.handler.attrib(name, value)
            #if isinstance(value, curis):
            #    for curi in curis.split():
                    #check if its a curi not a uri
                    #if so, check if the prefix namespace declaration
                    #hasn't been handled yet if not add it
            #        pass
            st.handler.attrib(name, value)            
        st.attribs = []
        st.handler.endAttribs()

    def addWikiElem(st, wikiElem, userAttribs=()):
        if isinstance(wikiElem, tuple):
            attribs = wikiElem[1]
            elem = wikiElem[0]
        else:
            attribs = []
            elem = wikiElem

        st.handler.startElement(elem)
        userAttribDict = dict(userAttribs)
        for name, value in attribs:
            if name in userAttribDict:
                value = userAttribDict[name]
                userAttribs.remove( (name,value) )
            st.handler.attrib(name, value)
        for name, value in userAttribs:
            st.handler.attrib(name, value)
        st.handler.endAttribs()
        return elem
            
    def pushWikiStack(st,wikiElem, userAttribs=(),
        defaultElemClass=_WikiElemName):
        name = st.addWikiElem(wikiElem, userAttribs)
        if not isinstance(name, _WikiElemName):
            name = defaultElemClass(name)
        st.pushElementStack(name)
        
    def popWikiStack(st, untilElem = None):
        if isinstance(untilElem, tuple):
            name = untilElem[0]
        else:
            name = untilElem

        elements = st.elementStack[-1]        
        while elements:
            wikiElem = elements.pop()
            st.handler.endElement( wikiElem )
            st.namespaceStack.pop()
            if not untilElem or untilElem == wikiElem:
                return wikiElem

    def getParentElem(self):
        for i in range(len(self.elementStack)-1, -1, -1):            
            elements = self.elementStack[i]
            if elements:
                return elements[-1]
        return ''
            
    def stringToText(st, token):
        preformatted = token[0] in 'Pp' or (token[0] in 'rR' and token[1] in 'pP')
        string = stripQuotes(token)
        if preformatted:
            st.addWikiElem(st.mm.PRE)            
        st.handler.text(string)
        if preformatted:
            if isinstance(st.mm.PRE, tuple):
                st.handler.endElement(st.mm.PRE[0])
            else:
                st.handler.endElement(st.mm.PRE)
             
    def handleWikiML(st, string):            
        if len(string.strip()) > 2 and not len(string.strip().strip(':')):
            st.nlcount = 0
            #all characters are ':' so treat as blockquote (instead of indent)
            #not exactly inline but the logic is the same
            st.processInlineToken(st.mm.BLOCKQUOTE)            
            return
            
        if string.startswith('----'):
            st.nlcount = 0
            newpos,userAttribsList = parseAttributes(string[4:])
            st.pushWikiStack(st.mm.HR,userAttribsList[0])
            st.popWikiStack() #empty element pop the HR
            return

        lead = string[0]
        pos = 0                                
        if lead in '*:!+|'+OLCHAR:
            st.nlcount = 0
            while string[pos] == lead:
                pos += 1
            startpos = pos
            if lead == '1' and string[pos] == '.': #skip past the dot .
                pos += 1

            nameMatch = st.structNameProg.match(string, pos)
            if nameMatch:
                nameStart, pos = nameMatch.span()
                structName = string[nameStart:pos]
                #todo: bug: doesn't support URIs containing a ','
                structNames = structName.split(',')         
                structNames = [name.strip() 
                    for name in structNames if name.strip()]        
                idNames = [name for name in structNames if name.startswith('#')]
                if idNames:
                    if len(idNames) > 1:
                        raise ZMLParseError(
                        'more than one id defined (%s)' % structName)
                    structNames.remove(idNames[0])
                structName = ' '.join(structNames) 
            newpos,userAttribsList = parseAttributes(string[pos:])
            pos += newpos
            if nameMatch:
                attribs = []
                if structNames:
                    attribs.extend(st.mm.getStructureAttribs(lead,structNames) )
                for attrib in attribs:
                    if attrib[0] not in dict(userAttribsList[0]):                        
                        userAttribsList[0].append( attrib )
            
            done = False
            parent, lineElem = st.mm.wikiStructure.get(lead, (None, None))
            structureElem = parent
            if lead == '!':
                hlevel = startpos
                #this is conceptual cleaner (the more !! the bigger the header)
                #but too hard to use: requires the user to know
                #how many !! to type to get to H1
                #hlevel = 7 - pos #h1 thru h6
                #if hlevel < 1:
                #    hlevel = 1
                htext = string[pos:].strip()
                helem = st.mm.H(hlevel, htext)
                #if not in wikiStructure its not structural
                #(not like <section>), just a line element (like <H1>)
                if not parent or startpos != 1: #todo: fix this hack! 
                    st.pushWikiStack(helem, userAttribsList.pop(0))
                    done = True
                else:                    
                    #use helem instead of parent, lineElem
                    if lineElem: #assume its a pair
                        structureElem, lineElem = helem
                    else:
                        structureElem = helem

            if not done and parent in [
                st.mm.SECTION, st.mm.DIV, st.mm.BLOCKQUOTE]:
                st.processOpenWikiElements(parent,popAndStop=True)
                st.pushWikiStack(structureElem,
                            userAttribsList and userAttribsList.pop(0) or ())                    
                if lineElem:
                    st.pushWikiStack(lineElem,
                            userAttribsList and userAttribsList.pop(0) or ())
                done = True
                    
            if not done:
                if lead == '|': #tables don't nest
                    level = 1
                else:
                    level = startpos
                #close or deepen the outline structure till it matches the level
                currentLevel = st.processOpenWikiElements(parent)

                #when we encounter a nestable element close and
                #restart the same level
                #closeSameLevel = parent in [st.mm.SECTION]
                while level < currentLevel:
                    st.processOpenWikiElements(parent,popAndStop=True)
                    currentLevel -= 1
                while level > currentLevel:                    
                    st.pushWikiStack(structureElem,
                            userAttribsList and userAttribsList.pop(0) or ())
                    currentLevel += 1
                    
                if lineElem:
                    st.pushWikiStack(lineElem,
                            userAttribsList and userAttribsList.pop(0) or ())
        else:                        
            if lead == '\\' and string[1] in '*:-!+| ' + OLCHAR:
                #handle escape 
                pos += 1
                
        wantTokenMap = st.inlineTokenMap()
        if lead == '+':
            wantTokenMap['='] = st.mm.DD
        elif lead == '|':
            if startpos == 2: #||
                cell = st.mm.TH
            else:
                cell = st.mm.TD
            wantTokenMap['|'] = cell
            st.pushWikiStack(cell, userAttribsList.pop(0) )
            
        remainder = st.handleInlineWiki(string[pos:], wantTokenMap)
        if remainder is not None:
            return pos + remainder
        return

    def processOpenWikiElements(st, parent, popAndStop=False):
        '''
        Pop all the pending elements
        until we reach an element that matches the parent or        
        find one that's above it in the block content model.

        If we find the parent, either pop it or count how many appear.        
        '''
        currentLevel = 0
        if parent:
            if isinstance(parent, tuple):
                parentname = parent[0]
            else:
                parentname = parent
            parentOrder = st.mm.blockModel.index(parentname)
        else:
            parentOrder = -1
            parentname = ''
            
        currentlyOpenElements = st.elementStack[-1]
        while currentlyOpenElements:
            currElem = currentlyOpenElements[-1]
            if st.mm.canonizeElem(currElem) == parentname:
                currentLevel = 1
                if popAndStop:
                    st.handler.endElement( currentlyOpenElements.pop() )
                    st.namespaceStack.pop() 
                else:                    
                    reversedList = currentlyOpenElements[:-1]
                    reversedList.reverse()
                    for currElem in reversedList:
                        if st.mm.canonizeElem(currElem) == parentname:
                            currentLevel += 1
                        else:
                            break
                return currentLevel
            else:                
                try:
                    index = st.mm.blockModel.index(currElem)
                except ValueError:
                    index = 0xFFFFF
                if parentOrder < index:
                    #the current element is contained by the parent
                    #in the block model so pop it
                    st.handler.endElement( currentlyOpenElements.pop() )
                    st.namespaceStack.pop() 
                else:
                    #we've reached a element that's above
                    #the parent in the block model so stop
                    break
        return currentLevel

    def pushElementStack(st, name):
        st.elementStack[-1].append( name )
        st.namespaceStack.append( {} ) 
    
    def popElementStack(st):
        #we're dedenting so
        #close any pending element that haven't be handled yet
        while st.pendingElements:
            st.handler.endElement( st.pendingElements.pop() )
            st.namespaceStack.pop() 

        #this will be empty when the top level elements are indented
        #and then we dedent
        if st.elementStack: 
            elements = st.elementStack.pop() #pop this indention level
            while elements:
                #stop closing the elements when we encounter one
                #that may need to stay open
                if isinstance(elements[-1], _WikiElemName):
                    st.pendingElements = elements
                    break
                st.handler.endElement( elements.pop() )
                st.namespaceStack.pop() 
        
    def tokenHandler(st, type, token, (srow, scol), (erow, ecol), line):        
        if st.debug:                
            print >>sys.stderr, "STATE: A %d, Ch %d Fr %d NL %d" % (
                st.in_attribs, st.in_elemchild, st.in_freeform
                or st.want_freestr, st.nlcount)
            print >>sys.stderr, "TOKEN: %d,%d-%d,%d:\t%s\t%s" % (
                srow, scol, erow, ecol, tok_name[type], repr(token))
        st.currentStartPos = (srow, scol)
        if type == IGNORE:
            return
        
        handler = st.handler
        
        if type == WHITESPACE:
            if not st.in_attribs and not st.in_elemchild:
                handler.whitespace(token.replace(st.MARKUPSTARTCHAR, ' '))
            return

        if st.forVersion[0] < 0.8:    
            if type == FREESTR:            
                st.in_freeform = 1
                
                while st.nlcount:
                    st.nlcount -= 1            
                return st.handleWikiML(token) #handle wikiml         
            elif st.in_freeform:
                if type == NL:
                    #NL == a blank line - close the P:
                    while st.wikiStack:
                        st.popWikiStack()                
                    handler.whitespace(token)
                    #used to be += 1 but we disabled this "feature"
                    st.nlcount = 1
                                        
                    #if the 'whitespace' is all '<'s continue
                    if not line[:scol] or line[:scol].strip(st.MARKUPSTARTCHAR):
                        return
                elif type in [STRLINE, STRING]:
                    #encounting a string with no indention immediately
                    #after a FREESTR:
                    #just write out the string at the same markup level
                    st.stringToText(token)
                    st.nlcount = 0
                    return
                elif type == NEWLINE:
                    handler.whitespace(token)
                    return 
                else:
                    st.in_freeform = 0
                    st.nlcount = 0
            while st.wikiStack: st.popWikiStack()
            assert st.toClose == 0
        elif type == FREESTR:
            ret = st.handleWikiML(token) #handle wikiml
            st.nlcount = 0
            if ret is not None:
                st.want_freestr = 0
                return ret + scol
            else:
                return
        
        if type == NL:
            if not st.in_attribs: #this can happen when parenlev > 0
                st.want_freestr = 1
                #close any pending (wiki markup) element
                #that haven't be handled yet
                st.nlcount = 1
                
            #if the 'whitespace' is all '<'s continue
            if not line[:scol] or line[:scol].strip(st.MARKUPSTARTCHAR):
                return
        elif type not in [DEDENT, INDENT, COMMENT, PI]:
            #we're about to encount markup so close all the wiki elements
            #at the current indention level
            assert not st.pendingElements
            if st.elementStack:
                elements = st.elementStack[-1]
                while elements:
                    if isinstance(elements[-1], _WikiElemName):
                        st.handler.endElement( elements.pop() )
                        st.namespaceStack.pop()
                    else:
                        break

        #note:
        #NEWLINE or NEWSTMTCHAR always come before IN/DE/NO/DENT
        #which are followed by a markup token or a FREESTR
        if type == INDENT:
            assert not st.in_attribs                        
            #pop any pending elements if we've encounters a NL
            elements = st.pendingElements
            while elements:
                #assert isinstance(elements[-1], _WikiElemName)                    
                if st.nlcount:#we've encountered a NL, close all up to section level
                    if isinstance(elements[-1], _WikiSectionElemName):
                        break
                elif not len(token):
                    #no indention implies a new line at the same level
                    #close all line level elements
                    if not isinstance(elements[-1], _WikiInlineElemName):
                        break
                else: #we're indenting, keep the elements open
                    break
                st.handler.endElement( elements.pop() )
                st.namespaceStack.pop()
            #re-add any pending elements to this indention level
            st.elementStack.append( st.pendingElements )
            st.pendingElements = []
        elif type == DEDENT:
            assert not st.in_attribs
            st.popElementStack()
            #handler.whitespace('\t')
        elif type == NEWLINE or (type == OP and token == st.NEWSTMTCHAR):
            if st.in_attribs: #never encountered the :
                st.startElement()
                assert not st.in_attribs
                if not st.markupMode:
                    st.want_freestr = 1
            st.in_elemchild = 0
            handler.whitespace(token)
        elif type == NAME or type == URIREF:
            name = token                
            if st.in_attribs:
                st.attribs.append(name)
            #elif st.in_elemchild:
            #    handler.text(token)              
            else:
                st.pushElementStack( name )
                st.in_attribs = 1
        elif type == STRLINE: #`a string
            if st.in_attribs:
                #in attribs but never encountered the :
                st.startElement()
            st.stringToText(token)
        elif type == STRING:            
            if not st.in_attribs:
                st.stringToText(token)                
            else:        
                string = stripQuotes(token)
                st.attribs.append(xmlquote(string))
        elif type == OP and token != st.NEWSTMTCHAR:
            if token in ':<':
                if st.in_attribs and st.elementStack[-1]:
                    st.startElement()
                else:
                    assert token == '<'
                st.in_elemchild = 1
                if token == ':':
                    st.want_freestr = not st.markupMode
                else:                    
                    st.want_freestr = 0
                #assert len(st.attribs) % 2 == 0 #is even
                #no dict, we want to preserve order
                #attribDict = dict([ ( attribs[i], attribs[i+1])
                #            for i in range( 0, len(attribs), 2)])
            else:
                if not st.in_attribs:
                    raise ZMLParseError(token,
                            code=ZMLParseError.TOKEN_NOT_IN_ATTRIBUTES)
                if token == '>' and st.forVersion[0] >= 0.8:
                    #the tag has closed, enter xml parse mode
                    empty = line[:scol].strip().endswith('/')
                    if empty:
                        #encountered an empty xml element
                        st.startElement()
                        st.popElementStack()
                    else:
                        st.in_attribs = 0
                        cleanAttribs = st.normalizeAttribs(st.attribs)
                        xmlstart = '<' + st.elementStack[-1].pop()
                        if cleanAttribs:
                            xmlstart += ' ' + ' '.join(
                                [n + '=' + v for n,v in cleanAttribs]) + '>'
                        else:
                            xmlstart += '>'
                        st.attribs = []            
                        st.in_xml= XMLParser(st)
                        st.in_xml.feed(xmlstart)
                    if not st.markupMode: 
                        st.want_freestr = 1 #restore flag
                elif token not in '=(),/':
                    raise ZMLParseError('invalid token: ' + repr(token))
                if token == '=':
                    st.attribs.append(token)
                else:
                    if token == ')' and scol and line[scol-1] == ')':                        
                        st.startElement() #)) closes attributes
        elif type == NUMBER:
            if st.in_attribs:
                st.attribs.append(token)
            elif st.in_elemchild:
                handler.text(token)
            else:
                raise ZMLParseError(
                    'encountered a number in an illegal location: ' + token)
        elif type == ENDMARKER:
            if st.in_attribs: #never encountered the :
                st.startElement()            

            while st.wikiStack: st.popWikiStack()
            while st.elementStack:
                elements = st.elementStack.pop()
                while elements:
                    handler.endElement( elements.pop() )
            while st.namespaceStack:
                st.namespaceStack.pop()
        elif type == COMMENT:
            if st.in_attribs:
                #in attribs but never encountered the :
                st.startElement()
            handler.comment( token[1:] )
        elif type == PI:
            split = token.split(None, 1)
            name = split[0]
            if name.lower().startswith('zml'):
                if len(split) > 1:
                    #look at each word in the PI for a URI
                    uris = [x for x in split[1].split() if x.find(':') > -1]
                    if uris:
                        if len(uris) != 1:
                            raise ZMLParseError('malformed zml prologue')
                        st.mm = st.mmf.getMarkupMap(uris[0])
                        st.mmf.done = True
            else:
                if len(split) > 1:
                    value = split[1]
                else:
                    value = ''
                handler.pi(name, value)                
        elif type == ERRORTOKEN and not token.isspace():
            #not sure why this happens
            raise ZMLParseError("unexpected token: " + repr(token))

from rx.htmlfilter import HTMLFilter #todo: rx package dependency
from HTMLParser import HTMLParseError

class XMLParser(HTMLFilter):
    class HandlerStream:
        def __init__(self, handler):
            self.handler = handler
            
        def write(self, data):
            self.handler.text(data)

    completed = False

    def __init__(self, parseState):    
        super(XMLParser,self).__init__(self.HandlerStream(parseState.handler))
        self.parseState = parseState

    def feed(self, data):
        try:
            super(XMLParser,self).feed(data)
        except HTMLParseError, e:
            lineno, col = self.parseState.currentStartPos
            if e.lineno is not None and e.offset is not None:                
                lineno += e.lineno-1
                if e.lineno-1:                
                    col = e.offset
                else:
                    #error on the same line as the start of the xml
                    col += e.offset
                self.parseState.currentStartPos = (lineno, col)
            raise ZMLParseError('error parsing embedded XML: ' + e.msg)
                
    def handle_endtag(self, tag):
        super(XMLParser,self).handle_endtag(tag)
        if not self.tagStack:
            self.completed = True

    def parse_endtag(self, i):
        k = super(XMLParser, self).parse_endtag(i)
        if self.completed:        
            self.rawdata = self.rawdata[k:]
            #print 'rd', self.rawdata
            raise StopTokenizing        
        return k

def detectMarkupMap(fd, mmf=None, mixed=True, URIAdjust=False):
    '''
    Start parsing until the markup map is figured out and then
    return the MarkupMap.
    '''    
    parser = Parser(mixed, mmf)
    st = parser.parseState
    st.URIAdjust = URIAdjust
    st.debug = False

    st.handler = MarkupMapFactoryHandler(st)
    st.handler.terminate = True

    try:                    
        tokenize(fd.readline, parser)
    except MarkupMapDetectionException:
        pass
    
    return st.mm

class DebugHandler(Handler):
    '''
    SAX-like interface 
    '''
    out = sys.stderr
    
    def startElement(self, element):
        print >> self.out, 'startElement', element
        if self.nextHandler:
            self.nextHandler.startElement(element)

    def attrib(self, name, value):
        print >> self.out,'attrib', name, value
        if self.nextHandler:
            self.nextHandler.attrib(name, value)

    def endAttribs(self):
        print >> self.out,'endAttribs'
        if self.nextHandler:
            self.nextHandler.endAttribs()
        
    def endElement(self,element):
        print >> self.out,'endElement', element
        if self.nextHandler:
            self.nextHandler.endElement(element)
        
    def comment(self, string):
        print >> self.out,'comment', string
        if self.nextHandler:
            self.nextHandler.comment(string)
        
    def text(self, string):
        print >> self.out,'text', string
        if self.nextHandler:
            self.nextHandler.text(string)

    def whitespace(self, string):
        print >> self.out,'whitespace', string
        if self.nextHandler:
            self.nextHandler.whitespace(string)
        
    def pi(self, name, value):
        print >> self.out,'pi', name, value
        if self.nextHandler:
            self.nextHandler.pi(name, value)
        
    def endDocument(self):
        print >> self.out,'endDocument'
        if self.nextHandler:
            self.nextHandler.endDocument()
        
def zml2xml(fd, mmf=None, debug = 0, handler=None, prettyprint=False,
            rootElement = None, mixed=True, URIAdjust=False, zmlVersion=None):
    """
    given a string of zml, return a string of xml
    """
    zmlVersion = zmlVersion or defaultZMLVersion
    parser = Parser(mixed, mmf, zmlVersion)
    st = parser.parseState
    st.URIAdjust = URIAdjust
    st.debug = debug

    output = StringIO.StringIO()
    outputHandler = handler or OutputHandler(output)
    if debug:
        outputHandler = DebugHandler(outputHandler)
    st.handler = handler = MarkupMapFactoryHandler(st, outputHandler)
    del st
    try:                    
        tokenize(fd.readline, parser)
    except ZMLParseError, e:        
        e.setState(parser.parseState)
        raise 
    except Exception, e:
        #unexpected error
        import traceback, sys        
        zpe = ZMLParseError("Unhandled error:\n"
            +''.join(traceback.format_exception(
                sys.exc_type, sys.exc_value, sys.exc_traceback, 100) ))
        zpe.setState(parser.parseState)
        raise zpe

    handler.endDocument()
    
    if rootElement: 
      xml = "<%s>%s</%s>" % (rootElement, output.getvalue(), rootElement)
    else:
      xml = output.getvalue()

    if prettyprint:
        try:
            import Ft.Xml.InputSource, Ft.Xml.Domlette, Ft.Xml.Lib.Print
            xmlInputSrc = Ft.Xml.InputSource.DefaultFactory.fromString(xml)
            prettyOutput = StringIO.StringIO()
            reader = Ft.Xml.Domlette.NoExtDtdReader
            xmlDom = reader.parse(xmlInputSrc)        
            Ft.Xml.Lib.Print.PrettyPrint(xmlDom, stream=prettyOutput)
            return prettyOutput.getvalue()
        except ImportError:
            print >>sys.stderr, 'Error. You need 4Suite installed to pretty print.'
            return xml
    else:
        return xml

##################################################################
##  XML to ZML converter
##################################################################    
import HTMLParser
    
class XML2ZML(HTMLParser.HTMLParser):
    def __init__(self, out, indentwidth = 4, nl = '\n'):
        HTMLParser.HTMLParser.__init__(self)
        self.out = out
        self.tagStack = []
        self.indent = ''
        self.indentwidth = indentwidth
        self.nl = nl
        self.preservespace = False
    
    def handle_starttag(self, tag, attrs):
        self.tagStack.append(tag)        
        self.out.write(self.indent+tag)
        
        for name, value in attrs:
            if value is None: #'compact' attribute in HTML
                self.out.write(' '+name)
            else:
                self.out.write(' '+name +'='+ repr(value))
            
        self.out.write(':'+self.nl)
        self.indent += ' ' * self.indentwidth
                
    def handle_endtag(self, tag):
        #weak handling of the minimized end tags found in html
        while self.tagStack: 
           lastTag = self.tagStack.pop()
           self.indent = self.indent[:-self.indentwidth]
           if lastTag == tag:
               break        

    def handle_charref(self, name):
        #name should be a number
        if name[0] == 'x':
            num = int(name[1:],16)
        else:
            num = int(name)
        self.out.write(self.indent + '"\\U%08x"'%num +self.nl)

    def handle_entityref(self, name):
        builtin = {'lt': '<', 'gt':'>', 'amp':'&'}
        char = builtin.get(name)
        if char:
            self.out.write(self.indent + '`'+char+self.nl)
        else:
            self.out.write(self.indent + '"\&'+name+';"'+self.nl)    

    def handle_data(self, data):
        if not data.isspace() or self.preservespace:
            lines = data.split('\n')
            for data in lines:
                if data or self.preservespace:
                    self.out.write(self.indent + '`'+data+self.nl)         

    def handle_comment(self, data):
        lines = data.split('\n')
        for data in lines:
            self.out.write(self.indent + '#' +data+self.nl)  

    def handle_decl(self, data):        
        self.out.write(self.indent + "r'''<!"+data+">'''"+self.nl)

    def handle_pi(self, data):
        self.out.write(self.indent + '#?' + data.rstrip('?')+self.nl)         

    # we need to override these internal functions
    #because xml needs to preserve the case of tags and attributes
    
    # Internal -- handle starttag, return end or -1 if not terminated
    def parse_starttag(self, i):
        self.__starttag_text = None
        endpos = self.check_for_whole_start_tag(i)
        if endpos < 0:
            return endpos
        rawdata = self.rawdata
        self.__starttag_text = rawdata[i:endpos]

        # Now parse the data between i+1 and j into a tag and attrs
        attrs = []
        match = HTMLParser.tagfind.match(rawdata, i+1)
        assert match, 'unexpected call to parse_starttag()'
        k = match.end()
        self.lasttag = tag = rawdata[i+1:k]

        while k < endpos:
            m = HTMLParser.attrfind.match(rawdata, k)
            if not m:
                break
            attrname, rest, attrvalue = m.group(1, 2, 3)
            if not rest:
                attrvalue = None
            elif attrvalue[:1] == '\'' == attrvalue[-1:] or \
                 attrvalue[:1] == '"' == attrvalue[-1:]:
                attrvalue = attrvalue[1:-1]
                attrvalue = self.unescape(attrvalue)
            attrs.append((attrname, attrvalue))
            k = m.end()

        end = rawdata[k:endpos].strip()
        if end not in (">", "/>"):
            lineno, offset = self.getpos()
            if "\n" in self.__starttag_text:
                lineno = lineno + self.__starttag_text.count("\n")
                offset = len(self.__starttag_text) \
                         - self.__starttag_text.rfind("\n")
            else:
                offset = offset + len(self.__starttag_text)
            self.error("junk characters in start tag: %s"
                       % `rawdata[k:endpos][:20]`)
        if end.endswith('/>'):
            # XHTML-style empty tag: <span attr="value" />
            self.handle_startendtag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
            if tag in self.CDATA_CONTENT_ELEMENTS:
                self.set_cdata_mode()
        return endpos

    #Internal -- parse endtag, return end or -1 if incomplete
    def parse_endtag(self, i):
        rawdata = self.rawdata
        assert rawdata[i:i+2] == "</", "unexpected call to parse_endtag"
        match = HTMLParser.endendtag.search(rawdata, i+1) # >
        if not match:
            return -1
        j = match.end()
        match = HTMLParser.endtagfind.match(rawdata, i) # </ + tag + >
        if not match:
            self.error("bad end tag: %s" % `rawdata[i:j]`)
        self.endtag_text = match.string[match.start():match.end()]
        tag = match.group(1)        
        self.handle_endtag(tag)
        if sys.version_info[:2] > (2,2):
            #this line is in the 2.3 version of HTMLParser.parse_endtag
            self.clear_cdata_mode()
        return j

    in_cdata_section = False
    def updatepos(self, i, j):
        #htmlparser doesn't support CDATA sections hence this terrible hack
        #which rely on the fact that this will be called right after
        #parse_declaration (which calls unknown_decl)
        if self.in_cdata_section:
            self.handle_data(self.rawdata[i:j])
            self.in_cdata_section = False
        return HTMLParser.HTMLParser.updatepos(self, i, j)
        
    def unknown_decl(self, data):
        if data.startswith('CDATA['):
            self.in_cdata_section = True
        else:
            return HTMLParser.HTMLParser.unknown_decl(self, data)

def xml2zml(input, out, NL = os.linesep):
    zml = XML2ZML(out, nl=NL)
    out.write('#?zml0.9 markup'+ NL)
    zml.feed( input )
    zml.close()

def main():
    if len(sys.argv) < 2 or (sys.argv[-1][0] == '-' and sys.argv[-1] != '-'):        
        cmd_usage = '''usage: %s [options] (file | -)

final argument is a file path or - for standard input

-z convert from XML to ZML (if omitted: ZML to XML)
-p pretty print
-d show debug output

ZML to XML options:
-m               assume ZML source is in markup mode
-r [rootelement] wrap in root element (default: "zml")
-mm markupmap    Python class to use as markup map
-v version       treat ZML as version
        ''' % sys.argv[0]
        print cmd_usage
        sys.exit(0)
        
    def opt(opt, default):
        value = False
        try:
            i = sys.argv.index(opt)
            value = default

            if i+1 < len(sys.argv)-1 and sys.argv[i+1][0] != '-':
                value = sys.argv[i+1]
            
        except:
            pass
        return value
    
    def switch(*args):
        for opt in args:
            if opt in sys.argv:
                return True
        return False

    toZml = switch('-z')
    if toZml:
        if sys.argv[-1] == '-':
            text = sys.stdin.read()
        else:
            text = open(sys.argv[-1]).read()
        xml2zml(text, sys.stdout)
        sys.exit(0)
        
    debug = switch('-d', '--debug')
    prettyprint = switch('-p', '--pretty')
    rootElement = opt('-r', 'zml')
    markupOnly = switch('-m')
    version = float( opt('-v', defaultZMLVersion) )
    
    klass = opt('-mm', '')
    if klass:
        qualifiers = klass.split('.')
        qualifiers, klass = qualifiers[:-1], qualifiers[-1:][0]

        if qualifiers:
            mod = __import__('.'.join(qualifiers))
            for comp in qualifiers[1:]:
                mod = getattr(mod, comp)
            localdict = { '_' : mod }
            klass = '_.' + klass
        else:
            localdict = {}

        if klass.find('(') == -1:
            klass += '()'
        mmf= eval(klass, globals(), localdict)
    else:
        mmf = None
            
    if sys.argv[-1] == '-':
        file = sys.stdin
    else:
        file = open(sys.argv[-1])
        
    enc = getattr(file, 'encoding', None) 
    if enc or sys.platform == 'win32':
        import codecs
        #use the OS codepage
        file = codecs.EncodedFile(file, 'utf8',enc or 'mbcs')
    if debug:
        print 
    print zml2xml(file, mmf, debug, prettyprint=prettyprint,
        rootElement = rootElement, mixed=not markupOnly, 
        zmlVersion = version)    

if __name__ == '__main__':
    main()
