from zml import *

def makeReallyOldParser():
    '''
    Globally sets the ZML parser compatible with the ZML syntax prior to Rhizome 0.3.1    
    '''
    global OLCHAR, COMMENTCHAR, NEWSTMTCHAR, pseudoprog, endprogs
    OLCHAR = '#'
    COMMENTCHAR = ';'
    NEWSTMTCHAR = ''
    pseudoprog, endprogs = makeTokenizer()

def copyZML(stream, markupOnly = False, upgrade = False):
    if upgrade:
        makeReallyOldParser()
    tokens = []
    
    class CopyParseState:
        in_xml = None
        MARKUPSTARTCHAR = '<'
        
        def __init__(self, useFreestr=True):
            self.lines = []
            self.useFreestr = useFreestr
            self.want_freestr = 0

        def setMarkupMode(self, mode):
            self.useFreestr = not mode

        def handlesVersion(self, version):
            return True
            
        def __setattr__(self, name, value):
            if name == 'currentLine':
                #print 'c',value, self
                self.lines.append(value)
            else:
                self.__dict__[name] = value

        def getLines(self, (srow, scol), (erow, ecol) ):
            lines = self.lines[srow:erow+1]
            #print (srow, scol), (erow, ecol), lines
            lines[0] = lines[0][scol:]
            lines[-1] = lines[-1][:ecol]
            return lines

        def tokenHandler(self, type, token, (srow, scol), (erow, ecol), line):
            #print srow, erow, tok_name[type], repr(token)
            #if type == PI and token[:3] == 'zml':
            #    todo
            #elif...
            if type in [IGNORE, PI]:            
                tokens.append(line)
            elif type in [STRING, FREESTR]:                        
                if type == STRING and srow == erow:
                    tokens.append(token)
                else:
                    lines = self.getLines( (srow-1, scol), (erow-1, ecol) )
                    if upgrade and type == FREESTR:
                        if lines[0][0]=='#':
                            line = lines[0]
                            count = len(line)
                            line = line.lstrip('#')
                            count = count - len(line)
                            lines[0] = '1'*count + '.' + line
                        elif lines[0][0]==';':
                            lines[0] = '#' + lines[0][1:]
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
        tokens.append('#?zml0.7 markup\n')

    counter = Parser(not markupOnly, parseStateFactory=CopyParseState)
    tokenize(stream.readline, counter)
    return ''.join(tokens)

def upgrade(path, markupOnly = False):
    import glob, os.path
    for f in glob.glob(path):
        resultpath = os.path.splitext(f)[0]+'.new.zml'
        results = copyZML(open(f,'rb'), markupOnly, upgrade = True)
        print 'upgrading to ', resultpath
        open(resultpath, 'wb').write(results)        

class OldParseState(ParseState):
    forVersion = [0.7, 0.9]
    
    def __init__(self, mixedMode=True, mmf=None):
        ParseState.__init__(self, mixedMode, mmf)
        self.useFreestr = mixedMode
        #the stack of elements created by wiki markup that has yet to be closed
        #should maintain this order:
        #  nestable block elements (e.g. section, blockquote)*,
        #  block elements (e.g. p, ol/li, table/tr)+,
        #  inline elements*
        self.wikiStack = []    
        self.wikiStructureStack = {}
        self.toClose = 0 #how many inline elements need to be closed at the end of the wikimarkup line

        self.MARKUPSTARTCHAR = '<'
        


    #this is always 0
    want_freestr = property(lambda self: 0, lambda self, v: None)
    
    def setMarkupMode(self, mode):
        self.useFreestr = not mode

    def processInlineToken(st, elem, inlineTokens):
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
        #close the current parent elements until we encounter nestable
        #block element or P (latter only in the case going from inline to inline)
        if st.wikiStack and st.wikiStack[-1] != newStructureElem: 
            while st.wikiStack and st.mm.canonizeElem(st.wikiStack[-1]) not in \
                  [st.mm.SECTION, st.mm.BLOCKQUOTE, st.mm.P, newStructureElem]:
               st.popWikiStack()

        if newStructureElem == st.mm.BLOCKQUOTE: #note: too difficult to allow blockquotes to nest
            inBlockQuote = wikiStructureStack.get(st.mm.BLOCKQUOTE, 0)
            if inBlockQuote: #close block quote
                while wikiStructureStack.get(st.mm.BLOCKQUOTE, 0):
                    st.popWikiStack() #will decrement wikiStructureStack
            #else: #open block quote #todo HACK!
            st.pushWikiStack(st.mm.BLOCKQUOTE)
            wikiStructureStack[st.mm.BLOCKQUOTE] = 1
            return
            
        if string.startswith('----'):
            st.pushWikiStack(st.mm.HR)
            st.popWikiStack() #empty element pop the HR
            return

        pos = 0                                
        if lead in '*:!+|'+OLCHAR:
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
                    #use helem instead of parent, lineElem
                    if lineElem:                        
                        structureElem = helem[0]
                        lineElem = helem[1]
                    else:
                        structureElem = helem
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
        while st.toClose: #close the line elements: e.g. LI, H1, DD, TR
            st.popWikiStack()
            st.toClose -= 1
