#! /usr/bin/env python
"""
    ZML to XML/XML to ZML
    
    Copyright (c) 2003-4 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, released under GPL v2, see COPYING for details.
    
    See http://rx4rdf.liminalzone.org/ZML for more info on ZML.    
"""

try:
    from rx.utils import InterfaceDelegator, NestedException
except ImportError:
    #copied from rx/utils.py so this file has no dependencies
    class InterfaceDelegator:
        '''assumes only methods will be called on this object and the methods always return None'''
        def __init__(self, handlers):
            self.handlers = handlers
        
        def call(self, name, args, kw):
            for h in self.handlers:
                getattr(h, name)(*args, **kw)
            
        def __getattr__(self, name):
            return lambda *args, **kw: self.call(name, args, kw)

    class NestedException(Exception):
        def __init__(self, msg = None,useNested = False):
            if not msg is None:
                self.msg = msg
            self.nested_exc_info = sys.exc_info()
            self.useNested = useNested
            Exception.__init__(self, msg)

class ZMLParseError(NestedException):
    def __init__(self, msg = ''):                
        NestedException.__init__(self, msg)
        self.state = None
        
    def setState(self, state):
        self.state = state #line, col #, etc.
        if state:
            self.msg = 'ZML syntax error at line %d, column %d: %s\nline: "%s"' % (
                state.currentStartPos[0], state.currentStartPos[1], self.msg, state.currentLine.strip())
            self.args = ( self.msg, ) #'cuz that's the way Exception stores its message
        
######################################################
###begin tokenizer
######################################################
"""
    Tokenizer for ZML

    This is a modification of Python 2.2's tokenize module and behaves
    the same except for:

    * NAME tokens also can include '.', ':' and '-' (aligning them with XML's NMTOKEN production)
      (but the trailing ':', if present, is treated as a OP)
    * New string tokens are introduced:
      1. STRLINE, which behaves similar to a comment: any characters following a '`'
         to the end of the line are part of the token
      2. the optional FREESTR token, which if true (the default),
    causes any non-indented, non-continued line to be returned whole as a FREESTR token
        Its presence is controlled by the 'useFreestr' keyword parameter added to tokenize() (default: True)
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
def any(*choices): return apply(group, choices) + '*'
def maybe(*choices): return apply(group, choices) + '?'

COMMENTCHAR = '#'
NEWSTMTCHAR = ';'

def makeTokenizer():
    Whitespace = r'[ \f\t]*'
    Comment = COMMENTCHAR + r'[^\r\n]*' 
    StrLine = r'`[^\r\n]*'
    Ignore = Whitespace + any(r'\\\r?\n' + Whitespace) + maybe(Comment) + maybe(StrLine)
    Name = r'[a-zA-Z_][\w:.-]*' #added _:.-
    URIRef =  r"\{[a-zA-Z_][\w:.\-\]\[;/?@&=+$,!~*'()%#]*\}" #very loose URI match: start with alpha char followed by any number of the acceptable URI characters
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

    Bracket = '[][()]' #remove {}
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
    PseudoToken = Whitespace + group(PseudoExtras, Funny, ContStr, Name, URIRef, Number) #added URIRef

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
    return pseudoprog, endprogs

pseudoprog, endprogs = makeTokenizer()

tabsize = 8

class StopTokenizing(Exception): pass

def printtoken(type, token, (srow, scol), (erow, ecol), line, *args): # for testing
    print "%d,%d-%d,%d:\t%s\t%s" % \
        (srow, scol, erow, ecol, tok_name[type], repr(token))

def tokenize(readline, tokeneater=printtoken, useFreestr = True, counter = None):
    try:
        tokenize_loop(readline, tokeneater, useFreestr, counter)
    except StopTokenizing:
        pass

def tokenize_loop(readline, tokeneater, useFreestr = True, counter = None):
    lnum = parenlev = continued = 0
    namechars, numchars = string.letters + '_', string.digits  
    contstr, needcont = '', 0
    contline = None
    indents = [0]
    literalstr = ''

    while 1:                                   # loop over lines in stream        
        line = readline()
        lnum = lnum + 1
        pos, max = 0, len(line)
        #print 'LN:', pos, line, parenlev
        if counter:
            counter.currentLine = line
            counter.currentStartPos = lnum, pos
        
        if literalstr: #last line was a FREESTR
            if line and not line.isspace() and line[0].isspace():
                #if this line starts with whitespace (but isn't all whitespace) it's a continuation of the last
                literalstr = literalstr.rstrip() + line #line continued (previous line should end in newline whitespace)
                literalstrstop = (lnum, max)
                literalline = line
                continue
            else: #last line is complete
                tokeneater(FREESTR, literalstr, literalstrstart, literalstrstop, literalline, indents)
                literalstr = ''
                if not line:
                    break
                
        doIndent = True

        if not contstr and line[:2] == '#!': #ignore these lines
            tokeneater(IGNORE, line[2:], (lnum, 0), (lnum, max), line)
            continue
        if not contstr and line[:2] == '#?': #processor instruction #?zml1.0 markup
            if line.startswith('#?zml'):
                if line.find('markup') != -1:
                    useFreestr = False
                else:
                    useFreestr = True
            tokeneater(PI, line[2:], (lnum, 0), (lnum, max), line)
            continue
          
        if useFreestr and line and not line.isspace() and not continued and \
                 parenlev == 0 and not contstr and not line[0] == '<': #free-form text
            if line[0] in ("'", '"') or \
                  line[:2] in ("r'", 'r"', "R'", 'R"',"p'", 'p"', "P'", 'P"') or \
                  line[:3] in ("pr'", 'pr"', "Pr'", 'Pr"', "pR'", 'pR"', "PR'", 'PR"' ):
                doIndent = False #this is a quoted string but treat like wiki markup (don't dedent)
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
                tokeneater(STRING, contstr+delim, strstart, (lnum -1, endcontline), line)
                break
                
            endmatch = endprog.match(line)
            if endmatch:
                pos = end = endmatch.end(0)
                tokeneater(STRING, contstr + line[:end],
                           strstart, (lnum, end), contline + line)
                contstr, needcont = '', 0
                contline = None
                if pos < len(line) and line[pos] in '\r\n':         
                  tokeneater(NEWLINE, line[pos:],(lnum, pos), (lnum, len(line)), line)
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
                if line[pos] == ' ' or line[pos] == '<': column = column + 1
                elif line[pos] == '\t': column = (column/tabsize + 1)*tabsize
                elif line[pos] == '\f': column = 0
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
            if not line[:pos] or line[:pos].strip('<'): #if the 'whitespace' was not all '<' continue
                continue              #but all < treat as an intentional dedent/indent

        #begin redunancy (todo)
        if doIndent:
          if column > indents[-1]:           # count indents or dedents
              indents.append(column)
              tokeneater(INDENT, line[:column], (lnum, 0), (lnum, pos), line)
          while column < indents[-1]:
              indents = indents[:-1]
              tokeneater(DEDENT, '', (lnum, pos), (lnum, pos), line)
          doIndent = False
        tokeneater(WHITESPACE, line[:pos], (lnum, 0), (lnum, pos), line)

        if line[pos] in COMMENTCHAR:           # skip comments 
            tokeneater(COMMENT, line[pos:],
                    (lnum, pos), (lnum, len(line)), line)
            continue
 
        if line[pos] in '`':           # our new type of string
             tokeneater(STRLINE, line[pos:],
                    (lnum, pos), (lnum, len(line)), line)
             continue
        else: #end redundancy
             if not line:
                 raise ZMLParseError("Encountered the end of the file while within a multi-line statement")
             continued = 0

        while pos < max:
            if doIndent:
              if icolumn > indents[-1]:           # count indents or dedents
                  indents.append(icolumn)
                  tokeneater(INDENT, line[:pos], (lnum, 0), (lnum, pos), line)
              while icolumn < indents[-1]:
                  indents = indents[:-1]
                  tokeneater(DEDENT, '', (lnum, pos), (lnum, pos), line)
              doIndent = False
            
            pseudomatch = pseudoprog.match(line, pos)
            if pseudomatch:                                # scan for tokens
                start, end = pseudomatch.span(1)
                spos, epos, pos = (lnum, start), (lnum, end), end
                token, initial = line[start:end], line[start]

                wstart, wend = pseudomatch.span(0)
                if wstart != start:                  
                  assert line[wstart:start].isspace()
                  tokeneater(WHITESPACE, line[wstart:start], (lnum, wstart), (lnum, start), line)
                
                if initial in numchars or \
                   (initial == '.' and token != '.'):      # ordinary number
                    tokeneater(NUMBER, token, spos, epos, line)
                elif initial in '\r\n':
                    tokeneater(parenlev > 0 and NL or NEWLINE,
                               token, spos, epos, line)
                elif initial == COMMENTCHAR:
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
                elif initial == '{':                 # URIRef
                    tokeneater(URIREF, token, spos, epos, line)                    
                elif initial == '\\':                      # continued stmt
                    continued = 1
                else: 
                    if initial in '[(':
                        parenlev = parenlev + 1 #removed { and }
                    elif initial in ')]':
                        parenlev = parenlev - 1
                    tokeneater(OP, token, spos, epos, line)
                    if initial == NEWSTMTCHAR:
                        spos = pos
                        countIndention = False
                        while pos < max and (line[pos].isspace() or line[pos] == '<'):                            
                            if line[pos] == '<': #only measure the whitespace if it has a '<'
                                countIndention = True
                            pos += 1                            
                        if countIndention:
                            icolumn = column + (pos - spos)
                        else:
                            #set column to the indention of the beginning of the physical line
                            icolumn = column
                        doIndent = True
                        tokeneater(WHITESPACE, line[spos:pos], (lnum, spos), (lnum, pos), line)
            else:
                tokeneater(ERRORTOKEN, line[pos],
                           (lnum, pos), (lnum, pos+1), line)
                pos = pos + 1

    for indent in indents[1:]:                 # pop remaining indent levels
        tokeneater(DEDENT, '', (lnum, 0), (lnum, 0), '')
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
    def startElement(self, element): pass
    def attrib(self, name, value): pass
    def endElement(self,element): pass
    def comment(self, string): pass
    def text(self, string): pass
    def whitespace(self, string): pass
    def pi(self, name, value): pass
    def endDocument(self): pass

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

OLCHAR = '1'
class MarkupMap(object):
    '''
    Derive from this class to wiki markup output.
    Element attributes can either be string (e.g. "TABLE") or a tuple like:
    ('TABLE', (('class','"wiki"'),) ) where the second item is a tuple of attribute name value pairs.
    The element method is used as an dictionary keys, so tuples, not lists, must be used.
    '''
    #block
    UL, OL, LI, DL, DD, DT, P, HR, PRE, BLOCKQUOTE, SECTION = 'UL', 'OL', 'LI', 'DL', 'DD', 'DT', 'P', 'HR', 'PRE', 'BLOCKQUOTE', 'SECTION'
    blockElems = [ 'UL', 'OL', 'LI', 'DL', 'DD', 'DT', 'P', 'HR', 'PRE', 'BLOCKQUOTE', 'SECTION'] 
    #header
    H1, H2, H3, H4, H5, H6 = 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'
    headerElems = [ 'H1', 'H2', 'H3', 'H4', 'H5', 'H6' ]
    #table
    TABLE, TR, TH, TD = 'TABLE', 'TR', 'TH', 'TD' # this is valid too: ('TABLE', (('class','"wiki"'),) ) (but attributes must be in a tuple not a list)
    tableElems = [ 'TABLE', 'TR', 'TH', 'TD' ]
    #inline:
    I, B, TT, A, IMG, SPAN, BR = 'EM', 'STRONG', 'TT', 'A', 'IMG', 'SPAN', 'BR'
    inlineElems = [ 'I', 'B', 'TT', 'A', 'IMG', 'SPAN', 'BR']

    INLINE_IMG_EXTS = ['.png', '.jpg', '.gif']

    docType = ''
        
    def __init__(self):
        #wikistructure maps syntax that correspond to strutural elements that only contain block elements (as opposed to inline elements)
        #create per instance instead of at the class level so the attributes are lazily evaluated, making subclassing less tricky
        self.wikiStructure = { '*' : [self.UL, self.LI ], OLCHAR : [self.OL, self.LI],
                               ':' : [self.DL, self.DD ], '+' : [self.DL, self.DT ],'|' : [self.TABLE, self.TR] }

    def canonizeElem(self, elem):
        '''        
        implement if you have elements that might vary from instance to instance, e.g. map H4 -> H or (elem, attribs) -> elem
        '''
        return elem
    
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
        return getattr(self, self.headerElems[level-1]) #evaluate lazily
                
    def mapAnnotationsToMarkup(self, annotationsRoot, name):
        #get the first node of the annotation, which can be either an element or a string
        type = getattr(annotationsRoot.children[0], 'name', annotationsRoot.children[0])
        #always None since we never change the text
        #also don't escape the attribute because the annotation parser already did this
        return self.SPAN, [('class',xmlquote(type, False) )], None 

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
            attribs = [ ('src', xmlquote(link)), ('alt', xmlquote(name or generatedName)) ]
            return self.IMG, attribs, '' #no link text (IMG is an empty element)
        else:
            if isAnchorName:
                attribs = [('name', xmlquote(link)) ]
            else:
                attribs = [ ('href', xmlquote(link)) ]
            if annotations and annotations.children:
                first = getattr(annotations.children[0], 'name', annotations.children[0])
                if first != 'wiki:xlink-replace':                
                    attribs += [ ('rel', xmlquote(first)) ]
            if generatedName:
                return self.A, attribs, generatedName
            else:
                return self.A, attribs, None #don't override the link text

#create a MarkupMap subclass with lowercase versions of all the elements names
class LowerCaseMarkupMap(MarkupMap): pass
for varname in MarkupMap.blockElems +\
        MarkupMap.headerElems + MarkupMap.tableElems + MarkupMap.inlineElems:
    setattr(LowerCaseMarkupMap, varname, getattr(LowerCaseMarkupMap, varname).lower() )
    
class DefaultMarkupMapFactory(Handler):
    '''
    This class is used to dynamic choose the appropriate MarkupMap based on the first element and comments encountered.
    Any Handler method may return a MarkupMap. See MarkupMapFactoryHandler for more info.
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
    Calls MarkupMapFactory.startElement for the first element encountered
    and MarkupMapFactory.attrib, MarkupMapFactory.pi and MarkupMapFactory.comment until the second element is encountered

    If the MarkupMapFactory returns a MarkupMap, use that one
    '''
    terminate = False
    
    def __init__(self, st, markupfactory=None):        
        self.markupfactory = markupfactory or DefaultMarkupMapFactory()
        self.elementCount = 0
        self.st = st

    def startElement(self, element):
        #examine first element encountered
        if not self.markupfactory.done and self.elementCount < 1: 
            mm = self.markupfactory.startElement(element)
            if mm:
                self.st.mm = mm
        self.elementCount += 1
        if self.terminate and self.elementCount == 2:
            raise MarkupMapDetectionException()
            
    def attrib(self, name, value):
        if not self.markupfactory.done and self.elementCount < 2:
            mm = self.markupfactory.attrib(name, value)
            if mm:
                self.st.mm = mm            
                            
    def comment(self, string): 
         if not self.markupfactory.done and self.elementCount < 2:
            mm = self.markupfactory.comment(string)
            if mm:
                self.st.mm = mm      

    def pi(self, name, value): 
         if not self.markupfactory.done and self.elementCount < 2:
            mm = self.markupfactory.pi(name, value)
            if mm:
                self.st.mm = mm      

def interWikiMapParser(interwikimap):
    interWikiMap = {}
    for line in interwikimap:
        line = line.strip()
        if line and not line.startswith('#'):
            prefix, url = line.split()
            interWikiMap[prefix.lower()] = url
    return interWikiMap

def stripQuotes(strQuoted, checkEscapeXML=True):    
    if strQuoted[0] == '`':
        if strQuoted[-1].isspace():#normalize trailing whitespace
            return strQuoted[1:].replace('&', '&amp;').replace('<', '&lt;').rstrip() + ' '  
        else:
            return strQuoted[1:].replace('&', '&amp;').replace('<', '&lt;')
    #we xml escape strings unless raw quote type is specifed        
    escapeXML = checkEscapeXML and not (strQuoted[0] in 'rR' or (strQuoted[0] in 'pP' and strQuoted[1] in 'rR'))
        
    #python 2.2 and below won't eval unicode strings while in unicode, so temporarily encode as UTF-8
    #NOTE: may cause some problems, but good enough for now
    strUTF8 = strQuoted.encode("utf-8")
    #remove p prefix from string
    if strUTF8[0] in 'pP':
        strUTF8 = 'u' + strUTF8[1:]
    elif strUTF8[0] in 'rR' and strUTF8[1] in 'pP':
        strUTF8 = 'ur' + strUTF8[2:]
    if escapeXML:
        #we need to do this before eval() because eval("'\&'") == eval("'\\&'")
        strUTF8 = xmlescape(strUTF8)
    strUnquoted = eval(strUTF8)
    #now handle and \U and \u: replace with character reference
    strUnquoted = re.sub(r'\\U(.{8})', r'&#x\1;', strUnquoted)
    strUnquoted = re.sub(r'\\u(.{4})', r'&#x\1;', strUnquoted)        
    if type(strUnquoted) != type(u''):
        strUnquoted = unicode(strUnquoted, "utf-8")
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
    if type(strText) == type(u''):
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

def _group(*choices): return '(' + '|'.join(choices) + ')'
defexp =  r'\='
tableexp= r'\|' 
bold= r'__'
italics= r'(?<!:)//' #ignore cases like http://
monospace= r'\^\^'
brexp= r'\~\~' 
linkexp = r'\[.*?\]' #todo linkexp doesn't handle ] in annotation strings or IP6 hostnames in URIs
#match any of the above unless proceeded by an odd number of \
inlineprog = re.compile(r'(((?<!\\)(\\\\)+)|[^\\]|^)'+_group(defexp,tableexp,bold,monospace,italics,linkexp,brexp))

def parseLinkType(string):
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
    zmlString2xml(string, handler=handler, mixed=False)
    assert handler.annotation.parent is None
    return handler.annotation

class ParseState:
    def __init__(st):    
        st.in_attribs = 0
        st.in_wikicont = 0 #not implemented
        st.in_elemchild = 0
        st.wantIndent = 0
        st.lineElems = 0 
        st.in_freeform = 0 #are we in wikimarkup?
        st.nlcount = 0 #how many blank lines following wikimarkup
        st.toClose = 0 #how many inline elements need to be closed at the end of the wikimarkup line
        st.attribs = []
        st.currentLine = ''
        st.currentStartPos = (0, 0)
        st.nextGeneratedPrefixCounter = 0    
        st.elementStack = []
        #the stack of elements created by wiki markup that has yet to be closed
        #should maintain this order: nestable block elements (e.g. section, blockquote)*, block elements (e.g. p, ol/li, table/tr)+, inline elements*
        st.wikiStack = []    
        st.wikiStructureStack = {}

    def inlineTokenMap(st):
        return { '/' : st.mm.I, '_' : st.mm.B, '^' : st.mm.TT}
     
    def _handleInlineWiki(st, string, wantTokenMap=None, userTextHandler=None):
        inlineTokens = st.inlineTokenMap()
        if wantTokenMap is None:
            wantTokenMap = inlineTokens
        if userTextHandler is None:
            userTextHandler = lambda s: st.handler.text(s)
        textHandler = lambda s: userTextHandler(re.sub(r'\\(.)',r'\1', xmlescape(s)) ) #xmlescape then strip out \ (but not \\) 
        pos = 0
        while 1:
            match = inlineprog.search(string[pos:]) #we can't do search(string, pos) because of ^ in our regular expression
            if match:
                start, end = match.span(4) #0
                start += pos
                end += pos
                token = string[start]
                elem = wantTokenMap.get(token)
                if elem:                
                    textHandler(string[pos:start])
                    if token == '=':
                        del wantTokenMap['='] #only do this once per line
                    elif token == '|':
                        if len(string) > start+1 and string[start+1] == '|': #|| = header                    
                            cell = st.mm.TH
                            end += 1 #skip second |
                        else:
                            cell = st.mm.TD
                        wantTokenMap['|'] = cell #user may have switched from || to | or from || to | (not sure if this is valid html though)

                    if token in inlineTokens.keys(): 
                        if st.wikiStack.count(elem): #if the elem is open 
                            while st.wikiStack[-1] != elem: #close it
                                wikiElem = st.popWikiStack()
                                if wikiElem in inlineTokens.values(): #these elements need st.toClose to be decremented
                                    st.toClose -= 1
                            st.popWikiStack()
                            st.toClose -= 1
                        else: #open the elem
                            st.pushWikiStack(elem)
                            st.toClose += 1 #update this so we pop the right amount below
                    else:
                        st.popWikiStack() #pop the DT or last TD or TH
                        st.pushWikiStack(elem) #push the DD or TD or TH
                    pos = end
                elif token == '~': #<BR>
                    textHandler(string[pos:start])
                    st.pushWikiStack(st.mm.BR)
                    st.popWikiStack()
                    pos = end
                elif token == '[': #its a link
                    #print 'link ', string[start:end]
                    if string[start+1] == ']':  #handle special case of "[]" -- just print it 
                        textHandler( string[pos:start+1] )
                        pos = start+1 
                        continue
                    
                    textHandler( string[pos:start] )
                    pos = end
                    linkToken = string[start+1:end-1] #strip [ and ] 

                    nameAndLink = linkToken.split('|', 1)
                    if len(nameAndLink) == 1:
                        name = None
                    else:
                        name = nameAndLink[0].strip()                    
                        namechunks = [] 
                        dummyState = ParseState()#parse out any wiki markup in the name (using a dummy handler)
                        dummyState.handler = Handler()
                        dummyState.mm = st.mm
                        dummyState._handleInlineWiki(name, None, lambda s: namechunks.append(s))
                        name = ''.join(namechunks)                    
                    linkinfo = nameAndLink[-1].strip() #the right side of the |
                    
                    words = linkinfo.split()

                    #print 'word ', words
                    if words[-1][-1] == ';': #last character is the annotation delineator, so there's no link
                        #todo: actually, a valid URL could end in a ';' but that is an extremely rare case we don't support
                        link = None
                        type = ' '.join(words)
                    elif len(words) > 1 and words[-2][-1] == ';': #annotation preceeding link
                        link = words[-1]
                        type = ' '.join(words[:-1])
                    else: 
                        if len(words) > 1:
                            #must be a link like [this is also a link]
                            if name is not None:                                
                                raise ZMLParseError('link URL can not contain spaces: ' + ''.join(words))
                            if [word for word in words if not word.isalnum()]:
                                #error: one of the words has punctuation, etc.
                                raise ZMLParseError('invalid link: ' + linkToken)
                            link = ''
                            #[this is also a link] creates a hyperlink to an internal WikiPage called 'ThisIsAlsoALink'.
                            for word in words:
                                link += word[0].upper() + word[1:] #can't use capitalize(), it makes other characters lower
                            name = ' '.join(words)
                        else:
                            link = words[0]
                        type = None
                        
                    if type:
                        type = parseLinkType(type) #type is a list of Annotations
                                                            
                    if link:                                                          
                        isInlineIMG = link[link.rfind('.'):].lower() in st.mm.INLINE_IMG_EXTS
                        isFootNote = link[0] == '#'
                        isAnchor = link[0] == '&'
                        if isAnchor:
                            link = link[1:] #strip &
                        element, attribs, text = st.mm.mapLinkToMarkup(link, name, type, isInlineIMG, isAnchor)
                    else: #no link, just a type
                        assert(type)
                        element, attribs, text = st.mm.mapAnnotationsToMarkup(type, name)
                    
                    st.handler.startElement(element)
                    for name, value in attribs:
                        st.handler.attrib(name, value)                    
                    if text is not None: 
                        st.handler.text( text )
                    else:
                        st._handleInlineWiki(nameAndLink[0].strip(), None)
                    st.handler.endElement(element)
                else:
                    textHandler( string[pos:start+1] )                
                    pos = start+1 #skip one of the brackets                
                    continue
            else:
                break            
        textHandler( string[pos:] )    

    def normalizeAttribs(st, attribs):
        '''
        returns list of (name, value) tuples (use list to preserve order)
        '''
        cleanAttribs = []
        i = 0
        while i+1 <= len(attribs):
            if i+1 == len(attribs) or attribs[i+1] != '=': #last item or next item != '=' : assume attribute minimalization
                cleanAttribs.append( (attribs[i], '"' + attribs[i] + '"') )
                i+=1
            else:
                val = attribs[i+2]
                if val[0] not in '\'"':
                    val = '"'+val+'"'
                cleanAttribs.append( (attribs[i], val) )
                i+=3    

        #add namespace to map
        for name, value in cleanAttribs:
            if name.startswith('xmlns:'):
                #note: we don't care about the default namespace                
                st.namespaceStack[-1][name[len('xmlns:'):] ] = value[1:-1]
            elif name.startswith('xml:base'):
                pass#st.docbase.append( value ) #todo

        return cleanAttribs
    
    def handleInlineWiki(st, string, wantTokenMap ):
        #if markup appears on the line following a wiki line (that ends in ::) this markup will be a child of the wiki element
        #nope too complicated!!!
        if 0:#string[-2:] == '::': 
            return st._handleInlineWiki(string[:-2], wantTokenMap)
            st.in_wikicont = 1
        else:
            return st._handleInlineWiki(string, wantTokenMap)
            st.in_wikicont = 0

    def uriToQName(st, token):
        uri = token[1:-1] #strip {}
        if not uri:
            raise ZMLParseError('syntax error: empty URI element')
        if not uri[-1].isalnum() and uri[-1] not in '.-':
            if not st.URIAdjust: 
                if uri[-1] != '_': #trailing _ is ok in this case
                    raise ZMLParseError('invalid URI as element name: %s' % repr(uri))
            else:                                    
                uri += '_' #add another _ to assure we can split the URI into a qname
        prefix, local = '',''
        inScope = {} #find the namespaces in scope

        for i in range(len(st.namespaceStack)-1,-1,-1): #reverse order            
            namespaceDict = st.namespaceStack[i] 
            for prefixCandidate, namespace in namespaceDict.items():                        
                if prefixCandidate not in inScope:
                    #hasn't been overridden
                    if uri.startswith(namespace):
                        local = uri[len(namespace):]
                        if local and (local[0].isalnum() or local[0] == '_'):
                            prefix = prefixCandidate
                            break
                inScope[prefixCandidate] = namespace
                
        if not prefix:                 
            while 1:
                #make sure the generated prefix doesn't override 
                #an in-scope user declared prefix
                st.nextGeneratedPrefixCounter += 1
                prefix = 'ns' + str(st.nextGeneratedPrefixCounter)
                if prefix not in inScope:
                    break
            
            namespaceURI, local = splitURI(uri)                    
            assert prefix and namespaceURI and local
            st.namespaceStack[-1][prefix] = namespaceURI

            newNS = ('xmlns:'+ prefix, "'"+namespaceURI+"'")
        else:
            newNS = None
        assert local
        return prefix + ':' + local, newNS
        
    def startElement(st):
        st.in_attribs = 0
        cleanAttribs = st.normalizeAttribs(st.attribs)
        name = st.elementStack[-1][0]

        if name[0] == '{': #its a URIRef
             name, newNS = st.uriToQName(name)
             if newNS:
                 cleanAttribs.append( newNS )
             st.elementStack[-1][0] = name
             
        st.handler.startElement( name )
                
        for name, value in cleanAttribs:
            if name[0] == '{':
                name, newNS = st.uriToQName(name)
                if newNS:
                    st.handler.attrib(name, value)
            if value and value[0] == '{':
                #note: this code results in a URIRef as an attribute value being converted to a qname
                value, newNS = st.uriToQName(value)
                if newNS:
                    st.handler.attrib(name, value)            
            st.handler.attrib(name, value)
        st.attribs = []            

    def addWikiElem(st, wikiElem):
        if isinstance(wikiElem, type( () )):
            attribs = wikiElem[1]
            elem = wikiElem[0]
        else:
            attribs = []
            elem = wikiElem
        st.handler.startElement(elem)
        for name, value in attribs:
            st.handler.attrib(name, value)
            
    def pushWikiStack(st,wikiElem):
        st.addWikiElem(wikiElem)
        st.wikiStack.append(wikiElem)
        
    def popWikiStack(st, untilElem = None):        
        while st.wikiStack:
            wikiElem = st.wikiStack.pop()
            if isinstance(wikiElem, type( () )):
                st.handler.endElement(wikiElem[0])
            else:
                st.handler.endElement(wikiElem)
            if st.wikiStructureStack.get(st.mm.canonizeElem(wikiElem)):
                st.wikiStructureStack[st.mm.canonizeElem(wikiElem)]-= 1
            if not untilElem or untilElem == wikiElem:
                return wikiElem
        raise IndexError('pop from empty list')
            
    def stringToText(st, token):
        preformatted = token[0] in 'Pp' or (token[0] in 'rR' and token[1] in 'pP')
        string = stripQuotes(token)
        if preformatted:
            st.addWikiElem(st.mm.PRE)            
        st.handler.text(string)
        if preformatted:
            if isinstance(st.mm.PRE, type( () )):
                st.handler.endElement(st.mm.PRE[0])
            else:
                st.handler.endElement(st.mm.PRE)
             
    def handleWikiML(st, string):
        handler = st.handler
        wikiStructureStack = st.wikiStructureStack
        
        lead = string[0]
        if lead == '`': #treat just like STRLINE token
            handler.text( stripQuotes(string) ) 
            return

        if lead == COMMENTCHAR: #treat just like COMMENT token
            handler.comment( string[1:] )
            return
        
        if not len(string.strip().strip(':')): #all characters are ':' so treat as blockquote (instead of indent)
            newStructureElem = st.mm.BLOCKQUOTE
        else:
            newStructureElem = st.mm.wikiStructure.get(lead, [None])[0]
        #if we're change to a new structure: e.g. from OL to TABLE or UL to None (inline markup)
        #close the current parent elements until we encounter nestable block element or P (latter only in the case going from inline to inline)
        if st.wikiStack and st.wikiStack[-1] != newStructureElem: 
            while st.wikiStack and st.mm.canonizeElem(st.wikiStack[-1]) not in \
                  [st.mm.SECTION, st.mm.BLOCKQUOTE, st.mm.P, newStructureElem]:
               st.popWikiStack()

        if newStructureElem == st.mm.BLOCKQUOTE: #note: too difficult to allow blockquotes to nest
            inBlockQuote = wikiStructureStack.get(st.mm.BLOCKQUOTE, 0)
            if inBlockQuote: #close block quote
                while wikiStructureStack.get(st.mm.BLOCKQUOTE, 0):
                    st.popWikiStack() #will decrement wikiStructureStack
            else: #open block quote
                st.pushWikiStack(st.mm.BLOCKQUOTE)
                wikiStructureStack[st.mm.BLOCKQUOTE] = 1
            return
            
        if string.startswith('----'):
            st.pushWikiStack(st.mm.HR)
            st.popWikiStack() #empty element pop the HR
            return

        pos = 0                                
        if lead in '*:-!+|'+OLCHAR:
            while string[pos] == lead:
                pos += 1
            done = False
            parent, lineElem = st.mm.wikiStructure.get(lead, (None, None))
            structureElem = parent
            if lead == '!':
                hlevel = pos
                #this is conceptual cleaner (the more !! the bigger the header)
                #but too hard to use: requires the user to know how many !! to type to get to H1
                #hlevel = 7 - pos #h1 thru h6
                #if hlevel < 1:
                #    hlevel = 1
                helem = st.mm.H(hlevel, string[pos:]) 
                if not parent: #wasn't in wikiStructure so its not structural (like <section>), just a line element (like <H1>)
                    st.pushWikiStack(helem)
                    st.toClose += 1
                    done = True
                else:
                    structureElem = helem #use helem instead of parent
            if not done:
                if lead == '|': #tables don't nest
                    level = 1
                else:
                    level = pos
                if lead == '1' and string[pos] == '.': #skip past the dot .
                    pos += 1
                #print 'pos wss ', pos, wikiStructureStack
                #close or deepen the outline structure till it matches the level
                closeSameLevel = parent in [st.mm.SECTION] #when we encounter a nestable element close and restart the same level
                while level-closeSameLevel < wikiStructureStack.get(parent, 0):
                    st.popWikiStack() #will decrement wikiStructureStack                
                currlevel = wikiStructureStack.get(parent, 0)
                while level > currlevel:
                    st.pushWikiStack(structureElem)
                    currlevel += 1
                wikiStructureStack[parent] = level
                if lineElem:
                    st.pushWikiStack(lineElem)
                    st.toClose += 1
        else:
            #if no structural element is specfied and the wikistack is empty (eg. we're starting out)
            #or only contains elements that require block elem children, start a P
            if not st.wikiStack or st.mm.canonizeElem(st.wikiStack[-1]) in [st.mm.SECTION, st.mm.BLOCKQUOTE]:
               st.pushWikiStack(st.mm.P) 
            if lead == '\\' and string[1] in '*:-!+| ' + OLCHAR: #handle escape 
                pos += 1

        wantTokenMap = st.inlineTokenMap()
        if lead == '+':
            wantTokenMap['='] = st.mm.DD
        elif lead == '|':
            if pos == 2: #||
                cell = st.mm.TH
            else:
                cell = st.mm.TD
            wantTokenMap['|'] = cell
            st.pushWikiStack(cell)
            st.toClose += 1
        st.handleInlineWiki(string[pos:], wantTokenMap) 
        if st.in_wikicont:
            return
        while st.toClose: #close the line elements: e.g. LI, H1, DD, TR
            st.popWikiStack()
            st.toClose -= 1
        
    def tokenHandler(st, type, token, (srow, scol), (erow, ecol), line, indents=None):        
        if st.debug:                
            print >>sys.stderr, "STATE: A %d, Ch %d nI %d Fr %d NL %d" % (st.in_attribs, st.in_elemchild, st.wantIndent, st.in_freeform, st.nlcount)
            print >>sys.stderr, "TOKEN: %d,%d-%d,%d:\t%s\t%s" % (srow, scol, erow, ecol, tok_name[type], repr(token))
        st.currentStartPos = (srow, scol)
        if type == IGNORE:
            return
        
        handler = st.handler
        
        if type == WHITESPACE:
            if not st.in_attribs and not st.in_elemchild:
                handler.whitespace(token.replace('<', ' '))
            return 
        if type == FREESTR:            
            st.in_freeform = 1
            
            while st.nlcount:
                #this can never happen now:
                #if  st.nlcount > 1 and st.elementStack:
                #    #each extra blank line __between__ wiki paragraphs closes one markup element
                #    handler.endElement( st.elementStack.pop() )
                #    indents.pop()
                st.nlcount -= 1            
            st.handleWikiML(token) #handle wikiml 
            return
        elif st.in_freeform:
            if type == NL:
                if st.in_wikicont: 
                    return #skip blank lines after a wiki line ending in \
                #NL == a blank line - close the P:
                while st.wikiStack:
                    st.popWikiStack()                
                handler.whitespace(token)
                st.nlcount = 1 #used to be += 1 but we disabled this "feature"
                if not line[:scol] or line[:scol].strip('<'):#if the 'whitespace' is all '<'s continue
                    return
            elif type in [STRLINE, STRING]:
                #encounting a string with no indention immediately after a FREESTR:
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

        if not st.in_wikicont: 
            while st.wikiStack: st.popWikiStack()
            assert st.toClose == 0

        if type == NL: #skip blank lines
            if not line[:scol] or line[:scol].strip('<'):#if the 'whitespace' is all '<'s continue
                return
        
        if st.wantIndent and type != ENDMARKER: #newline, check for indention
            if type == INDENT:
                #where becoming a new 
                #handler.whitespace('\n' + token)
                st.lineElems = 0#-= 1
            else:
                #if we don't see an indent and we just encountered an element
                #(e.g. elem:) then pop that elem from the stack
                elementInfo = st.elementStack[-1]                
                while st.lineElems: #support multiple elements per line e.g. elem1: elem2: 'OK!'
                    handler.endElement( st.elementStack.pop()[0] )
                    st.namespaceStack.pop()
                    st.lineElems -= 1
            st.wantIndent = 0
        
        if type == NAME or type == URIREF:                    
            name = token                
            if st.in_attribs:
                st.attribs.append(name)
            #elif st.in_elemchild:
            #    handler.text(token)              
            else:
                st.elementStack.append( [name, 1])
                st.namespaceStack.append( {} )
                st.in_attribs = 1
                st.lineElems += 1
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
        elif type == OP and token != NEWSTMTCHAR:
            if token == ':':
                st.startElement()
                st.in_elemchild = 1
                #assert len(st.attribs) % 2 == 0 #is even
                #attribDict = dict([ ( attribs[i], attribs[i+1]) for i in range( 0, len(attribs), 2)]) #no dict, we want to preserve order
            else:
                if token not in '=(),':
                    raise ZMLParseError('invalid token: ' + repr(token))
                assert st.in_attribs
                if token == '=':
                    st.attribs.append(token)
        elif type == NUMBER:
            if st.in_attribs:
                st.attribs.append(token)
            elif st.in_elemchild:
                handler.text(token)
            else:
                raise ZMLParseError('encountered a number in an illegal location: ' + token)
        elif type == DEDENT:
            if st.in_attribs: #never encountered the :
                st.startElement()            
            if st.elementStack: #this will be empty when the top level elements are indented and then we dedent
                elementInfo = st.elementStack[-1]
                while elementInfo[1]: #element maybe the end of a multi-element line                    
                    handler.endElement( st.elementStack.pop()[0] )
                    st.namespaceStack.pop()
                    elementInfo[1] -= 1
            #handler.whitespace('\t')
        elif type == NEWLINE or type == ENDMARKER or (
                    type == OP and token == NEWSTMTCHAR):
            if st.in_attribs: #never encountered the :
                st.startElement()            
            st.in_elemchild = 0

            if type == ENDMARKER:
                while st.wikiStack: st.popWikiStack()
                while st.elementStack:
                    handler.endElement( st.elementStack.pop()[0] )
                while st.namespaceStack:
                    st.namespaceStack.pop()
            else:
                if st.lineElems: #don't set wantIndent if the line just had a string or comment 
                    st.wantIndent = 1
                    #remember the # of elements on this line so we can pop the right number
                    st.elementStack[-1][1] = st.lineElems                
                handler.whitespace(token)
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
                        st.mm = mmf.getMarkupMap(uris[0])
                        mmf.done = True
            else:
                if len(split) > 1:
                    value = split[1]
                else:
                    value = ''
                handler.pi(name, value)                
        elif type == ERRORTOKEN and not token.isspace(): #not sure why this happens
            raise ZMLParseError("unexpected token: " + repr(token))

def makeOldParser():
    '''
    Globally sets the ZML parser compatible with the ZML syntax prior to Rhizome 0.3.1    
    '''
    global OLCHAR, COMMENTCHAR, NEWSTMTCHAR, pseudoprog, endprogs
    OLCHAR = '#'
    COMMENTCHAR = ';'
    NEWSTMTCHAR = ''
    pseudoprog, endprogs = makeTokenizer()
#makeOldParser()

def detectMarkupMap(fd, mmf=None, mixed=True, URIAdjust=False):
    '''
    Start parsing until the markup map is figured out and then
    return the MarkupMap.
    '''
    mmf = mmf or DefaultMarkupMapFactory()
    
    st = ParseState()    
    st.mm = mmf.getDefault()
    st.URIAdjust = URIAdjust
    st.namespaceStack = [ ]
    st.URIAdjust = URIAdjust
    st.debug = False

    st.handler = MarkupMapFactoryHandler(st, mmf)
    st.handler.terminate = True

    try:                    
        tokenize(fd.readline, tokeneater = st.tokenHandler, useFreestr=mixed, counter=st)
    except MarkupMapDetectionException:
        pass
    
    return st.mm
        
def zml2xml(fd, mmf=None, debug = 0, handler=None, prettyprint=False,
               rootElement = None, mixed=True, URIAdjust=False):
    """
    given a string of zml, return a string of xml
    """
    mmf = mmf or DefaultMarkupMapFactory()
    
    st = ParseState()    
    st.mm = mmf.getDefault()
    st.namespaceStack = [ ]
    st.URIAdjust = URIAdjust
    st.debug = debug

    output = StringIO.StringIO()
    outputHandler = handler or OutputHandler(output)
    st.handler = InterfaceDelegator( [ outputHandler, MarkupMapFactoryHandler(st, mmf) ] )
        
    try:                    
        tokenize(fd.readline, tokeneater = st.tokenHandler, useFreestr=mixed, counter=st)
    except ZMLParseError, e:
        e.setState(st)
        raise 
    except Exception, e:
        #unexpected error
        import traceback, sys        
        zpe = ZMLParseError("Unhandled error:\n"
            +''.join(traceback.format_exception( sys.exc_type, sys.exc_value, sys.exc_traceback, 100) ))
        zpe.setState(st)
        raise zpe

    st.handler.endDocument()
    
    if rootElement: 
      xml = "<%s>%s</%s>" % (rootElement, output.getvalue(), rootElement)
    else:
      xml = output.getvalue()

    if prettyprint:
        try:
            import Ft.Xml.InputSource, Ft.Xml.Domlette, Ft.Xml.Lib.Print
            xmlInputSrc = Ft.Xml.InputSource.DefaultFactory.fromString(xml)
            prettyOutput = StringIO.StringIO()
            reader = Ft.Xml.Domlette.NonvalidatingReader
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
            self.out.write(self.indent + COMMENTCHAR +data+self.nl)  

    def handle_decl(self, data):        
        self.out.write(self.indent + "r'''<!"+data+">'''"+self.nl)

    def handle_pi(self, data):
        self.out.write(self.indent + '#?' + data.rstrip('?')+self.nl)         

    # we need to override these internal functions because xml needs to preserve the case of tags and attributes
    
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
            self.clear_cdata_mode() #this line is in the 2.3 version of HTMLParser.parse_endtag        
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

def copyZML(stream, markupOnly = False, upgrade = False):
    if upgrade:
        makeOldParser()
    tokens = []
    class Counter:
        def __init__(self):            
            self.lines = []

        def __setattr__(self, name, value):
            if name == 'currentLine':
                #print 'c',value
                self.lines.append(value)                
            else:
                self.__dict__[name] = value

        def getLines(self, (srow, scol), (erow, ecol) ):
            lines = self.lines[srow:erow+1]
            #print (srow, scol), (erow, ecol), lines
            lines[0] = lines[0][scol:]
            lines[-1] = lines[-1][:ecol]
            return lines

    counter = Counter()
    def copyTokens(type, token, (srow, scol), (erow, ecol), line, indents=None):
        #print tok_name[type], repr(token)
        if type in [IGNORE, PI]:
            tokens.append(line)
        elif type in [STRING, FREESTR]:                        
            if type == STRING and srow == erow:
                tokens.append(token)
            else:
                lines = counter.getLines( (srow-1, scol), (erow-1, ecol) )                
                if upgrade and type == FREESTR:
                    if lines[0][0]=='#':
                        line = lines[0]
                        count = len(line)
                        line = line.lstrip('#')
                        count = count - len(line)
                        lines[0] = '1'*count + '.' + line
                    elif lines[0][0]==';':
                        lines[0] = '#' + lines[0][1:]
                #print 'ln', lines                
                tokens.extend(lines )
        elif type == NL:
            if not line[:scol] or line[:scol].strip('<'): #todo: stop sending this extra NL if the whitespace is all <<<
                #print tok_name[type], repr(token)
                if line.replace('<', ' ').strip():
                    #contains non-whitespace must be inside a multiline parentheses
                    #todo don't send NL in that case unless it really is a NL
                    tokens.append(token)
                else:
                    tokens.append(line)                    
            else:
                pass#print 'skipped NL', repr(token), line[:scol]
        elif upgrade and type == COMMENT:
            tokens.append('#' + token[1:])
        elif type not in [INDENT, DEDENT]:
            #print tok_name[type], repr(token)
            tokens.append(token)
    if markupOnly:
        tokens.append('#?zml0.9 markup\n')
    tokenize(stream.readline, tokeneater = copyTokens, useFreestr=not markupOnly, counter = counter)
    return ''.join(tokens)

def upgrade(path, markupOnly = False):
    import glob, os.path
    for f in glob.glob(path):
        resultpath = os.path.splitext(f)[0]+'.new.zml'
        results = copyZML(open(f,'rb'), markupOnly, upgrade = True)
        print 'upgrading to ', resultpath
        open(resultpath, 'wb').write(results)        

if __name__ == '__main__':
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
        ''' % sys.argv[0]
        print cmd_usage
        sys.exit(0)
        
    def opt(opt, default):
        value = False
        try:
            i = sys.argv.index(opt)
            value = default
            if i+1 < len(sys.argv)-2 and sys.argv[i+1][0] != '-':
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
    try:            
        klass = opt('-mm', '')
        index = klass.rfind('.')
        if index > -1:
           module = klass[:index]
           __import__(module)
        if klass.find('(') == -1:
            klass += '()'
        mmf= eval(klass) 
    except:
        mmf = None
    
    if switch('-u', '--upgrade'):
        upgrade(sys.argv[-1], markupOnly)
    else:
        if sys.argv[-1] == '-':
            file = sys.stdin
        else:
            file = open(sys.argv[-1])
        
        print zml2xml(file, mmf, debug, prettyprint=prettyprint,
                rootElement = rootElement, mixed=not markupOnly)    

