#! /usr/bin/env python
"""
    ZML to XML/XML to ZML
    
    Copyright (c) 2003-4 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, released under GPL v2, see COPYING for details.
    
    See http://rx4rdf.liminalzone.org/ZML for more info on ZML.    
"""

######################################################
###begin tokenizer
######################################################
"""
    Tokenizer for ZML

    This is a modification of Python 2.2's tokenize module and behaves
    the same except for:

    * NAME tokens also can include '.', ':' and '-' (aligning them with XML's NMTOKEN production)
      (but the trailing ':', if present, is treated as a OP)
    * The COMMENT deliminator is changed from '#' to ';'
    * New string tokens are introduced:
      1. STRLINE, which behaves similar to a comment: any characters following a '`'
         to the end of the line are part of the token
      2. the optional FREESTR token, which if true (the default),
    causes any non-indented, non-continued line to be returned whole as a FREESTR token
        Its presence is controlled by the 'useFreestr' keyword parameter added to tokenize() (default: True)
      3. WHITESPACE so the tokeneater function gets notified of all the whitespace
      4. IGNORE for lines that begin with '#!'
      5. PI for lines that begin with '#?'
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

def group(*choices): return '(' + '|'.join(choices) + ')'
def any(*choices): return apply(group, choices) + '*'
def maybe(*choices): return apply(group, choices) + '?'

COMMENTCHAR = ';' # instead of #
Whitespace = r'[ \f\t]*'
Comment = r';[^\r\n]*' #replace # with ;
StrLine = r'`[^\r\n]*'
Ignore = Whitespace + any(r'\\\r?\n' + Whitespace) + maybe(Comment) + maybe(StrLine)
Name = r'[a-zA-Z_][\w:.-]*' #added _:.-

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

Bracket = '[][(){}]'
Special = group(r'\r?\n', r'[:#,]') #removed `. replace ; with #
Funny = group(Operator, Bracket, Special)

PlainToken = group(Funny, String, Name, Number) 
Token = Ignore + PlainToken

# First (or only) line of ' or " string.
ContStr = group(r"[pP]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*" +
                group("'", r'\\\r?\n'),
                r'[pP]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*' +
                group('"', r'\\\r?\n'))
PseudoExtras = group(r'\\\r?\n', Comment, Triple, StrLine)
PseudoToken = Whitespace + group(PseudoExtras, Funny, ContStr, Name, Number) 

tokenprog, pseudoprog, single3prog, double3prog = map(
    re.compile, (Token, PseudoToken, Single3, Double3))
endprogs = {"'": re.compile(Single), '"': re.compile(Double),
            "'''": single3prog, '"""': double3prog,
            "r'''": single3prog, 'r"""': double3prog,
            "p'''": single3prog, 'p"""': double3prog,
            "pr'''": single3prog, 'pr"""': double3prog,
            "P'''": single3prog, 'R"""': double3prog,
            "U'''": single3prog, 'U"""': double3prog,
            "pR'''": single3prog, 'pR"""': double3prog,
            "Pr'''": single3prog, 'Pr"""': double3prog,
            "PR'''": single3prog, 'PR"""': double3prog,
            'r': None, 'R': None, 'p': None, 'p': None}

tabsize = 8

class TokenError(Exception): pass

class StopTokenizing(Exception): pass

def printtoken(type, token, (srow, scol), (erow, ecol), line, *args): # for testing
    print "%d,%d-%d,%d:\t%s\t%s" % \
        (srow, scol, erow, ecol, tok_name[type], repr(token))

def tokenize(readline, tokeneater=printtoken, useFreestr = True):
    try:
        tokenize_loop(readline, tokeneater, useFreestr)
    except StopTokenizing:
        pass

def tokenize_loop(readline, tokeneater, useFreestr = True):
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
            else:
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
                #raise TokenError, ("EOF in multi-line string", strstart)
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
          
        if doIndent:
          if column > indents[-1]:           # count indents or dedents
              indents.append(column)
              tokeneater(INDENT, line[:pos], (lnum, 0), (lnum, pos), line)
          while column < indents[-1]:
              indents = indents[:-1]
              tokeneater(DEDENT, '', (lnum, pos), (lnum, pos), line)
        tokeneater(WHITESPACE, line[:pos], (lnum, 0), (lnum, pos), line)

        if line[pos] in COMMENTCHAR:           # skip comments 
                tokeneater(COMMENT, line[pos:],
                           (lnum, pos), (lnum, len(line)), line)
                continue

        if line[pos] in '`':           # our new type of string
                tokeneater(STRLINE, line[pos:],
                           (lnum, pos), (lnum, len(line)), line)
                continue

        else:                                  # continued statement
            if not line:
                raise TokenError, ("EOF in multi-line statement", (lnum, 0))
            continued = 0

        while pos < max:
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
                    
                elif initial == '\\':                      # continued stmt
                    continued = 1
                else:
                    if initial in '([{': parenlev = parenlev + 1
                    elif initial in ')]}': parenlev = parenlev - 1
                    tokeneater(OP, token, spos, epos, line)
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

class UnknownMarkupMap(Exception): pass

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
            assert element == self.element
            self.output.write(u' />') #empty element
            self.element = None            
        else:
            self.output.write( u'</' + element + '>')        
        
    def comment(self, string):
        self.__finishElement()
        assert string.find('--') == -1, ' -- not allowed in comments'
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
    child is None, a (unicode) string, or an annotation

    Note: if the annotation is just text, self.child will be set but self.name will be None
    '''
    def __init__(self, name=None):
        self.name = name
        self.attribs = []
        self.child = None

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
        self.wikiStructure = { '*' : [self.UL, self.LI ], '#' : [self.OL, self.LI],
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
                
    def mapAnnotationsToMarkup(self, annotations, name):
        type = annotations[0].name or annotations[0].child
        return self.SPAN, [('class',xmlquote(type) )], name

    def mapLinkToMarkup( self, link, name, annotations, isImage, isAnchorName):
        '''
        return (element, attrib list, text)
        '''
        if name is None:
            if link.startswith('site:///'):
                name = link[len('site:///'):]
            else:
                name = link
        #print link, not annotations or [a.name for a in annotations]
        if isImage and (annotations is None or \
                   not [annotation for annotation in annotations if annotation.name == 'wiki:xlink-replace']):
            attribs = [ ('src', xmlquote(link)), ('alt', xmlquote(name)) ]
            return self.IMG, attribs, ''
        else:
            if isAnchorName:
                attribs = [('name', xmlquote(link)) ]
            else:
                attribs = [ ('href', xmlquote(link)) ]
            if annotations:
                attribs += [ ('rel', xmlquote(annotations[0].name)) ]
            return self.A, attribs, name

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
    def __init__(self, st, markupfactory=DefaultMarkupMapFactory()):
        self.markupfactory = markupfactory
        self.elementCount = 0
        self.st = st

    def startElement(self, element):
        #examine first element encountered
        if not self.markupfactory.done and self.elementCount < 1: 
            mm = self.markupfactory.startElement(element)
            if mm:
                self.st.mm = mm
        self.elementCount += 1
            
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

def normalizeAttribs(attribs, handler=None):
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
    if handler is not None:
        for name, value in cleanAttribs:
            handler.attrib(name, value)
    return cleanAttribs

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
        quote.replace('&', '&amp;')
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

def _group(*choices): return '(' + '|'.join(choices) + ')'
defexp =  r'\='
tableexp= r'\|' 
bold= r'__'
italics= r'(?<!:)//' #ignore cases like http://
monospace= r'\^\^'
brexp= r'\~\~' 
linkexp = r'\[.*?\]'#any [.*] except when a [ is behind the leading
#todo linkexp doesn't handle ] in annotation strings or IP6 hostnames in URIs
#match any of the above unless proceeded by an odd number of \
inlineprog = re.compile(r'(((?<!\\)(\\\\)+)|[^\\]|^)'+_group(defexp,tableexp,bold,monospace,italics,linkexp,brexp))

def inlineTokenMap(st):
    return { '/' : st.mm.I, '_' : st.mm.B, '^' : st.mm.TT}

def parseLinkType(string, annotationList = None):
    '''
    parse the annotation string e.g.:
    foo:bar attribute='value': foo:child 'sometext'; foo:annotation2; 'plain text annotation';
    returns a list of Annotations
    '''
    class TypeParseHandler(Handler):
        def __init__(self, annotationList):            
            self.annotation = Annotation()
            self.annotationList = annotationList
            self.annotationList.append( self.annotation )
            
        def startElement(self, element):
            if self.annotation.name == None:
                self.annotation.name = element
            else:
                assert self.annotation.child == None
                self.annotation.child = Annotation(element)
                self.annotation = self.annotation.child
                
        def attrib(self, name, value):            
            self.annotation.attribs.append( (name, value) )
            
        def text(self, string):
            self.annotation.child = string
            
        def comment(self, string):
            #anything after the ; is another annotation, if anything
            if string:
                parseLinkType(string, self.annotationList)
        
    if annotationList is None:
        annotationList = []
    handler = TypeParseHandler(annotationList)
    zmlString2xml(string, handler=handler, mixed=False)
    return annotationList
 
def _handleInlineWiki(st, handler, string, wantTokenMap=None, userTextHandler=None):
    inlineTokens = inlineTokenMap(st)
    if wantTokenMap is None:
        wantTokenMap = inlineTokens
    if userTextHandler is None:
        userTextHandler = lambda s: handler.text(s)
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
                if string[start+1] == ']':  #handle special case of [] -- just print it 
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
                    namechunks = [] #parse any wiki markup in the name
                    _handleInlineWiki(st, handler, name, None, lambda s: namechunks.append(s))
                    name = ''.join(namechunks)                    
                linkinfo = nameAndLink[-1].strip()
                
                words = linkinfo.split()
                if len(words) > 1:
                    #print 'word ', words
                    if words[-1][-1] == ';': #last character is the annotation delineator, so there's no link
                        #todo: actually, a valid URL could end in a ';' but that is an extremely rare case we don't support
                        link = None
                        type = ' '.join(words)
                    elif words[-2][-1] == ';':
                        link = words[-1]
                        type = ' '.join(words[:-1])
                    else: #must be a link like [this is also a link] handled below
                        assert name is None, 'link names or URLs can not have spaces'
                        type = None
                    if type:
                        type = parseLinkType(type) #type is a list of Annotations
                else:
                    type = None
                                                        
                #support: [this is also a link] creates a hyperlink to an internal WikiPage called 'ThisIsAlsoALink'.
                if name is None and len(words) > 1 and [word for word in words if word.isalnum()]: #if no punctuation etc.
                    link = ''
                    for word in words:
                        link += word.capitalize()
                    name = ' '.join(words)
                else:
                    if type is None: #if the type has already been set, so has the link (which might be None)
                        link = words[0]

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
                
                handler.startElement(element)
                for name, value in attribs:
                    handler.attrib(name, value)
                if text:
                    handler.text( text )
                handler.endElement(element)
            else:
                textHandler( string[pos:start+1] )                
                pos = start+1 #skip one of the brackets                
                continue
        else:
            break            
    textHandler( string[pos:] )    
    
def handleInlineWiki(st, handler, string, wantTokenMap ):
    #if markup appears on the line following a wiki line (that ends in ::) this markup will be a child of the wiki element
    #nope too complicated!!!
    if 0:#string[-2:] == '::': 
        return _handleInlineWiki(st, handler, string[:-2], wantTokenMap)
        st.in_wikicont = 1
    else:
        return _handleInlineWiki(st, handler, string, wantTokenMap)
        st.in_wikicont = 0
            
def zml2xml(fd, mmf=None, debug = 0, handler=None, prettyprint=False,
               rootElement = None, getMM=False, mixed=True):
    """
    given a string of zml, return a string of xml
    """
    #debug = 1
    if mmf is None:
        mmf=DefaultMarkupMapFactory()
        
    def addWikiElem(wikiElem):
        if isinstance(wikiElem, type( () )):
            attribs = wikiElem[1]
            elem = wikiElem[0]
        else:
            attribs = []
            elem = wikiElem
        handler.startElement(elem)
        for name, value in attribs:
            handler.attrib(name, value)
            
    def pushWikiStack(wikiElem):
        addWikiElem(wikiElem)
        st.wikiStack.append(wikiElem)
        
    def popWikiStack(untilElem = None):        
        while st.wikiStack:
            wikiElem = st.wikiStack.pop()
            if isinstance(wikiElem, type( () )):
                handler.endElement(wikiElem[0])
            else:
                handler.endElement(wikiElem)
            if wikiStructureStack.get(st.mm.canonizeElem(wikiElem)):
                wikiStructureStack[st.mm.canonizeElem(wikiElem)]-= 1
            if not untilElem or untilElem == wikiElem:
                return wikiElem
        raise IndexError('pop from empty list')

    class state: pass  
    st = state()    
    st.in_attribs = 0
    st.in_wikicont = 0 #not implemented
    st.in_elemchild = 0
    st.wantIndent = 0
    st.lineElems = 0 #just 0 or 1 right now
    st.in_freeform = 0 #are we in wikimarkup?
    st.nlcount = 0 #how many blank lines following wikimarkup
    st.toClose = 0 #how many inline elements need to be closed at the end of the wikimarkup line
    st.attribs = []
    st.pushWikiStack = pushWikiStack
    st.popWikiStack = popWikiStack
    #the stack of elements created by wiki markup that has yet to be closed
    #should maintain this order: nestable block elements (e.g. section, blockquote)*, block elements (e.g. p, ol/li, table/tr)+, inline elements*
    st.wikiStack = []
    st.mm = mmf.getDefault()
    elementStack = []
    wikiStructureStack = {}
    output = StringIO.StringIO()
    outputHandler = handler or OutputHandler(output)
    handler = InterfaceDelegator( [ outputHandler, MarkupMapFactoryHandler(st, mmf) ] )

    def stringToText(token):
        preformatted = token[0] in 'Pp' or (token[0] in 'rR' and token[1] in 'pP')
        string = stripQuotes(token)
        if preformatted:
            addWikiElem(st.mm.PRE)            
        handler.text(string)
        if preformatted:
            if isinstance(st.mm.PRE, type( () )):
                handler.endElement(st.mm.PRE[0])
            else:
                handler.endElement(st.mm.PRE)
             
    def handleWikiML(string):
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
               popWikiStack()

        if newStructureElem == st.mm.BLOCKQUOTE: #note: too difficult to allow blockquotes to nest
            inBlockQuote = wikiStructureStack.get(st.mm.BLOCKQUOTE, 0)
            if inBlockQuote: #close block quote
                while wikiStructureStack.get(st.mm.BLOCKQUOTE, 0):
                    popWikiStack() #will decrement wikiStructureStack
            else: #open block quote
                pushWikiStack(st.mm.BLOCKQUOTE)
                wikiStructureStack[st.mm.BLOCKQUOTE] = 1
            return
            
        if string.startswith('----'):
            pushWikiStack(st.mm.HR)
            popWikiStack() #empty element pop the HR
            return

        pos = 0                                
        if lead in '*#:-!+|':
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
                    pushWikiStack(helem)
                    st.toClose += 1
                    done = True
                else:
                    structureElem = helem #use helem instead of parent
            if not done:
                if lead == '|': #tables don't nest
                    level = 1
                else:
                    level = pos                
                #print 'pos wss ', pos, wikiStructureStack
                #close or deepen the outline structure till it matches the level
                closeSameLevel = parent in [st.mm.SECTION] #when we encounter a nestable element close and restart the same level
                while level-closeSameLevel < wikiStructureStack.get(parent, 0):
                    popWikiStack() #will decrement wikiStructureStack                
                currlevel = wikiStructureStack.get(parent, 0)
                while level > currlevel:
                    pushWikiStack(structureElem)
                    currlevel += 1
                wikiStructureStack[parent] = level
                if lineElem:
                    pushWikiStack(lineElem)
                    st.toClose += 1
        else:
            #if no structural element is specfied and the wikistack is empty (eg. we're starting out)
            #or only contains elements that require block elem children, start a P
            if not st.wikiStack or st.mm.canonizeElem(st.wikiStack[-1]) in [st.mm.SECTION, st.mm.BLOCKQUOTE]:
               pushWikiStack(st.mm.P) 
            if lead == '\\' and string[1] in '*#:-!+| ': #handle escape 
                pos += 1

        wantTokenMap = inlineTokenMap(st)
        if lead == '+':
            wantTokenMap['='] = st.mm.DD
        elif lead == '|':
            if pos == 2: #||
                cell = st.mm.TH
            else:
                cell = st.mm.TD
            wantTokenMap['|'] = cell
            pushWikiStack(cell)
            st.toClose += 1
        handleInlineWiki( st, handler, string[pos:], wantTokenMap) 
        if st.in_wikicont:
            return
        while st.toClose: #close the line elements: e.g. LI, H1, DD, TR
            popWikiStack()
            st.toClose -= 1
        
    def tokenHandler(type, token, (srow, scol), (erow, ecol), line, indents=None):
        if debug:                
            print >>sys.stderr, "STATE: A %d, Ch %d nI %d Fr %d NL %d" % (st.in_attribs, st.in_elemchild, st.wantIndent, st.in_freeform, st.nlcount)
            print >>sys.stderr, "TOKEN: %d,%d-%d,%d:\t%s\t%s" % (srow, scol, erow, ecol, tok_name[type], repr(token))
        if type == WHITESPACE:
            if not st.in_attribs and not st.in_elemchild:
                handler.whitespace(token.replace('<', ' '))
            return 
        if type == FREESTR:            
            st.in_freeform = 1
            
            while st.nlcount:
                #this can never happen now:
                #if  st.nlcount > 1 and elementStack:
                #    #each extra blank line __between__ wiki paragraphs closes one markup element
                #    handler.endElement( elementStack.pop() )
                #    indents.pop()
                st.nlcount -= 1            
            handleWikiML(token) #handle wikiml 
            return
        elif st.in_freeform:
            if type == NL:
                if st.in_wikicont: 
                    return #skip blank lines after a wiki line ending in \
                #NL == a blank line - close the P:
                while st.wikiStack:
                    popWikiStack()                
                handler.whitespace(token)
                st.nlcount = 1 #used to be += 1 but we disabled this "feature"
                if not line[:scol] or line[:scol].strip('<'):#if the 'whitespace' is all '<'s continue
                    return
            elif type in [STRLINE, STRING]:
                #encounting a string with no indention immediately after a FREESTR:
                #just write out the string at the same markup level
                stringToText(token)
                st.nlcount = 0
                return
            elif type == NEWLINE:
                handler.whitespace(token)
                return 
            else:
                st.in_freeform = 0
                st.nlcount = 0

        if not st.in_wikicont: 
            while st.wikiStack: popWikiStack()
            assert st.toClose == 0

        if type == NL: #skip blank lines
            if not line[:scol] or line[:scol].strip('<'):#if the 'whitespace' is all '<'s continue
                return
        
        if st.wantIndent and type != ENDMARKER: #newline, check for indention
            if type == INDENT or type == INDENT:
                #handler.whitespace('\n' + token)
                st.lineElems -= 1
            else:
                #if we don't see an indent and we just encountered an element
                #(e.g. elem:) then pop that elem from the stack
                while st.lineElems: #support multiple elements per line e.g. elem1: elem2: 'OK!'
                    handler.endElement( elementStack.pop() )
                    st.lineElems -= 1
            st.wantIndent = 0
        
        if type == NAME:
            if st.in_attribs:
                st.attribs.append(token)
            #elif st.in_elemchild:
            #    handler.text(token)              
            else:
                elementStack.append(token)
                st.in_attribs = 1
                st.lineElems += 1                
        elif type == STRLINE: #`a string
            if st.in_attribs:
                #in attribs but never encountered the :
                st.in_attribs = 0
                handler.startElement( elementStack[-1])
                normalizeAttribs(st.attribs,handler)
                st.attribs = []
            stringToText(token)
        elif type == STRING:            
            if not st.in_attribs:
                stringToText(token)                
            else:        
                string = stripQuotes(token)
                st.attribs.append(xmlquote(string))
        elif type == OP:
            if token == ':':
                st.in_attribs = 0
                st.in_elemchild = 1
                #assert len(st.attribs) % 2 == 0 #is even
                #attribDict = dict([ ( attribs[i], attribs[i+1]) for i in range( 0, len(attribs), 2)]) #no dict, we want to preserve order
                handler.startElement( elementStack[-1])
                normalizeAttribs(st.attribs, handler)
                st.attribs = []
            else:
                assert token in '=(),', 'invalid token: ' + token + ' on line #' + `srow` + ' col ' + `scol` + ' line: ' + line
                assert st.in_attribs, ' on line #' + `srow` + ' col ' + `scol` + ' line: ' + line
                if token == '=':
                    st.attribs.append(token)
        elif type == NUMBER:
            if st.in_attribs:
                st.attribs.append(token)
            elif st.in_elemchild:
                handler.text(token)
            else:
                raise 'error: a number shouldnt be here: ' + token
        elif type == DEDENT:
            if st.in_attribs: #never encountered the :
                st.in_attribs = 0
                handler.startElement( elementStack[-1])
                normalizeAttribs(st.attribs, handler)
                st.attribs = []            
            if elementStack: #this will be empty when the top level elements are indented and then we dedent
                handler.endElement( elementStack.pop() )
            #handler.whitespace('\t')
        elif type == NEWLINE:
            if st.in_attribs: #never encountered the :
                st.in_attribs = 0
                handler.startElement( elementStack[-1])
                normalizeAttribs(st.attribs,handler)
                st.attribs = []
            
            st.in_elemchild = 0
            if st.lineElems: #don't set wantIndent if the line just had a string or comment 
                st.wantIndent = 1
                
            handler.whitespace(token)
        elif type == COMMENT:
            if st.in_attribs:
                #in attribs but never encountered the :
                st.in_attribs = 0
                handler.startElement( elementStack[-1])
                normalizeAttribs(st.attribs,handler)
                st.attribs = []
            handler.comment( token[1:] )
        elif type == PI:
            split = token.split(None, 1)
            name = split[0]
            if name.lower().startswith('zml'):
                if len(split) > 1:
                    #look at each word in the PI for a URI
                    uris = [x for x in split[1].split() if x.find(':') > -1]
                    if uris:
                        assert len(uris) == 1, 'malformed zml prologue'
                        st.mm = mmf.getMarkupMap(uris[0])
                        mmf.done = True
            else:
                if len(split) > 1:
                    value = split[1]
                else:
                    value = ''
                handler.pi(name, value)                
        elif type == ENDMARKER:
            while st.wikiStack: popWikiStack()
            while elementStack:
                handler.endElement( elementStack.pop() )
        elif type == ERRORTOKEN and not token.isspace(): #not sure why this happens
            raise "parse error %d,%d-%d,%d:\t%s\t%s" % (srow, scol, erow, ecol, tok_name[type], repr(token))
                    
    tokenize(fd.readline, tokeneater=tokenHandler, useFreestr=mixed)
    handler.endDocument()

    if getMM:
        return st.mm
    
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
            self.out.write(self.indent + ';' +data+self.nl)  

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

def xml2zml(input, out, NL = os.linesep):
    zml = XML2ZML(out, nl=NL)
    out.write('#?zml0.9 markup'+ NL)
    zml.feed( input )
    zml.close()
    
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
    
    def switch(opt):
        switch = opt in sys.argv
        return switch

    toZml = switch('-z')
    if toZml:
        if sys.argv[-1] == '-':
            text = sys.stdin.read()
        else:
            text = open(sys.argv[-1]).read()
        xml2zml(text, sys.stdout)
        sys.exit(0)
        
    debug = switch('-d')
    prettyprint = switch('-p')
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
    
    if sys.argv[-1] == '-':
        file = sys.stdin
    else:
        file = open(sys.argv[-1])
    print zml2xml(file, mmf, debug, prettyprint=prettyprint,
                rootElement = rootElement, mixed=not markupOnly)    

