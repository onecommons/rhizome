"""
    Rhizml to XML
    
    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx.rhizmltokenize import *
from rx import rhizmltokenize, utils
import re
try:
    import cStringIO
    StringIO = cStringIO
except ImportError:
    import StringIO

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
        self.output.write( u'<!--' + string + '-->')
        
    def text(self, string):
        self.__finishElement()
        self.output.write( string ) #no escaping -- allow inline xml markup
        
    def whitespace(self, string):
        pass#self.output.write( string ) #this put whitespace in places you wouldn't expect

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
    def getDefault(self):        
        return LowerCaseMarkupMap() 

class MarkupMapFactoryHandler(Handler):
    '''    
    Calls MarkupMapFactory.startElement for the first element encountered
    and MarkupMapFactory.attrib and MarkupMapFactory.comment until the second element is encountered

    If the MarkupMapFactory returns a MarkupMap, use that one
    '''
    def __init__(self, st, markupfactory=DefaultMarkupMapFactory()):
        self.markupfactory = markupfactory
        self.elementCount = 0
        self.st = st

    def startElement(self, element):
        if self.elementCount < 1: #examine first element encountered
            mm = self.markupfactory.startElement(element)
            if mm:
                self.st.mm = mm
        else:
            self.elementCount += 1
            
    def attrib(self, name, value):
        if self.elementCount < 2:
            mm = self.markupfactory.attrib(name, value)
            if mm:
                self.st.mm = mm            
                            
    def comment(self, string): 
         if self.elementCount < 2:
            mm = self.markupfactory.comment(string)
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
    escapeXML = checkEscapeXML and not (strQuoted[0] in 'rR' or (strQuoted[0] in 'pP' and strQuoted[1] in 'rR'))#we xml escape strings unless raw quote type is specifed        
    #python 2.2 and below won't eval unicode strings while in unicode, so temporarily encode as UTF-8
    #NOTE: may cause some problems, but good enough for now
    strUTF8 = strQuoted.encode("utf-8")
    #remove p prefix from string
    if strUTF8[0] in 'pP':
        strUTF8 = 'u' + strUTF8[1:]
    elif strUTF8[0] in 'rR' and strUTF8[1] in 'pP':
        strUTF8 = 'ur' + strUTF8[2:]
    strUnquoted = eval(strUTF8)
    if escapeXML:
        #escape and then remove the \ for any \< or \&
        #todo: handle odd number of \ > 1, like \\\< (broken now)
        strUnquoted = re.sub(r'(?<!\\)\\(\&(?!amp;)|\<)', r'\1', xmlescape(strUnquoted)) 
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

ampSearchProg = re.compile(r'(((?<!\\)(\\\\)+)|[^\\]|^)&')
ltSearchProg = re.compile(r'(((?<!\\)(\\\\)+)|[^\\]|^)<')
def xmlescape(s):    
    r'''xml escape & and < unless proceeded by an odd number of \ '''
    return re.sub(ltSearchProg, r'\1&lt;', re.sub(ampSearchProg, r'\1&amp;', s)) #&amp sub must go first
        
def rhizmlString2xml(strText, markupMapFactory=None, handler=None):
    if type(strText) == type(u''):
        strText = strText.encode("utf8")
    fd = StringIO.StringIO(strText)
    contents = rhizml2xml(fd, mmf=markupMapFactory, handler=handler)   
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
            parseLinkType(string, self.annotationList)
        
    if annotationList is None:
        annotationList = []
    handler = TypeParseHandler(annotationList)    
    rhizmlString2xml(' '+string, handler=handler) #add some indention
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
                    if string[start+1] == '|': #|| = header                    
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
            
def rhizml2xml(fd, mmf=None, debug = 0, handler=None, prettyprint=False, rootElement = None, getMM=False):
    """
    given a string of rhizml, return a str of xml
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
            if not untilElem or utilElem == wikiElem:
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
    handler = utils.InterfaceDelegator( [ outputHandler, MarkupMapFactoryHandler(st, mmf) ] )

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
        '''          
          \ to continue line
          linking:
            [name] internal link (site:name)
            [url] external link #http:, ftp:, mailto:, https:, or news:
            [name | link]
            [type: link] typed link 
            [name | type: link] 
            [[ to escape [
            images: *.png *.jpg *.gif unless type == 'wiki:xlink-replace'
            
        escaping:
           line starts with "`"  raw contents (as markup)
           line starts with \'\'\' or """ or r\'\'\' or r""" raw (as markup) multilines      
        '''
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
            print "STATE: A %d, Ch %d nI %d Fr %d NL %d" % (st.in_attribs, st.in_elemchild, st.wantIndent, st.in_freeform, st.nlcount)
            print "TOKEN: %d,%d-%d,%d:\t%s\t%s" % (srow, scol, erow, ecol, tok_name[type], repr(token))
        if type == WHITESPACE:
            if not st.in_attribs and not st.in_elemchild:
                handler.whitespace(token)
            return 
        if type == FREESTR:            
            st.in_freeform = 1
            #each extra blank line __between__ wiki paragraphs closes one markup element
            while st.nlcount:                
                if  st.nlcount > 1 and elementStack:
                    handler.endElement( elementStack.pop() )
                    indents.pop()
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
                st.nlcount += 1
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
            return
        
        if st.wantIndent and type != ENDMARKER: #newline, check for indention
            if type == INDENT:
                pass#handler.whitespace('\n' + token)
            else:
                while st.lineElems: #for future if we want to support multiple elements per line e.g. elem1: elem2: 'OK!'
                    handler.endElement( elementStack.pop() )
                    st.lineElems -= 1
            st.wantIndent = 0
            st.lineElems = 0
        
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
            handler.comment( token[1:] )
        elif type ==  ENDMARKER:
            while st.wikiStack: popWikiStack()
            while elementStack:
                handler.endElement( elementStack.pop() )
        elif type == ERRORTOKEN and not token.isspace(): #not sure why this happens
            raise "parse error %d,%d-%d,%d:\t%s\t%s" % (srow, scol, erow, ecol, tok_name[type], repr(token))
                    
    rhizmltokenize.tokenize(fd.readline, tokeneater=tokenHandler)
    handler.endDocument()

    if getMM:
        return st.mm
    
    if rootElement: 
      xml = "<%s>%s</%s>" % (rootElement, output.getvalue(), rootElement)
    else:
      xml = output.getvalue()

    if prettyprint:
        import Ft.Xml
        xmlInputSrc = Ft.Xml.InputSource.DefaultFactory.fromString(xml)
        prettyOutput = StringIO.StringIO()
        reader = Ft.Xml.Domlette.NonvalidatingReader
        xmlDom = reader.parse(xmlInputSrc)        
        Ft.Xml.Lib.Print.PrettyPrint(xmlDom, stream=prettyOutput)
        return prettyOutput.getvalue()
    else:
        return xml
    
if __name__ == '__main__':             
    def opt(opt, default):
        value = False
        try:
            i = sys.argv.index(opt)
            value = default
            if sys.argv[i+1][0] != '-':
                value = sys.argv[i+1]
        except:
            pass
        return value
    
    def switch(opt):
        switch = opt in sys.argv
        return switch
        
    import sys
    debug = switch('-d')
    prettyprint = switch('-p')
    rootElement = opt('-r', 'rhizml')
    try:            
        klass = opt('-m', '')
        index = klass.rfind('.')
        if index > -1:
           module = klass[:index]
           __import__(module)        
        mmf= eval(klass) 
    except:
        mmf = None
    
    if len(sys.argv) > 1 and sys.argv[-1][0] != '-':
        print rhizml2xml(open(sys.argv[-1]), mmf, debug, prettyprint=prettyprint, rootElement = rootElement)
    else:
        #print rhizml2xml(sys.stdin, mmf, debug, prettyprint=prettyprint, rootElement = rootElement)
        print "usage: -d(ebug) -r [rootelement] -m markupmapclass -p(rettyprint) file"
