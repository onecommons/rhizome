"""
    Tokenizer for RhizML

    This is a modification of Python 2.2's tokenize module and behaves
    exactly the same except for:

    * NAME tokens also can include '.', ':' and '-' (aligning them with XML's NMTOKEN production)
      (but the trailing ':', if present, is treated as a OP)
    * The COMMENT deliminator is changed from '#' to ';'
    * Three new string tokens are introduced:
      1. STRLINE, which behaves similar to a comment: any characters following a '`'
         to the end of the line are part of the token
      2. the optional FREESTR token, which if true (the default),
    causes any non-indented, non-continued line to be returned whole as a FREESTR token
        Its presence is controlled by the 'useFreestr' keyword parameter added to tokenize() (default: True)
      3. WHITESPACE so the tokeneater function gets notified of all the whitespace
    
    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

import string, re
from token import *

import token
__all__ = [x for x in dir(token) if x[0] != '_'] + ["COMMENT", "tokenize", "NL", 'STRLINE', 'FREESTR','WHITESPACE']
del token

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
Triple = group("[uU]?[rR]?'''", '[uU]?[rR]?"""')
# Single-line ' or " string.
String = group(r"[uU]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*'",
               r'[uU]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*"')

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
ContStr = group(r"[uU]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*" +
                group("'", r'\\\r?\n'),
                r'[uU]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*' +
                group('"', r'\\\r?\n'))
PseudoExtras = group(r'\\\r?\n', Comment, Triple, StrLine)
PseudoToken = Whitespace + group(PseudoExtras, Funny, ContStr, Name, Number) 

tokenprog, pseudoprog, single3prog, double3prog = map(
    re.compile, (Token, PseudoToken, Single3, Double3))
endprogs = {"'": re.compile(Single), '"': re.compile(Double),
            "'''": single3prog, '"""': double3prog,
            "r'''": single3prog, 'r"""': double3prog,
            "u'''": single3prog, 'u"""': double3prog,
            "ur'''": single3prog, 'ur"""': double3prog,
            "R'''": single3prog, 'R"""': double3prog,
            "U'''": single3prog, 'U"""': double3prog,
            "uR'''": single3prog, 'uR"""': double3prog,
            "Ur'''": single3prog, 'Ur"""': double3prog,
            "UR'''": single3prog, 'UR"""': double3prog,
            'r': None, 'R': None, 'u': None, 'U': None}

tabsize = 8

class TokenError(Exception): pass

class StopTokenizing(Exception): pass

def printtoken(type, token, (srow, scol), (erow, ecol), line, *args): # for testing
    print "%d,%d-%d,%d:\t%s\t%s" % \
        (srow, scol, erow, ecol, tok_name[type], repr(token))

def tokenize(readline, tokeneater=printtoken, useFreestr = True):
    try:
        tokenize_loop(readline, tokeneater)
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
        #print 'LN:', pos, line
        
        if literalstr: #continued FREESTR
            literalstr = literalstr + line
            if line.rstrip()[-1] ==  '\\':
                literalstr = literalstr.rstrip()[:-1]                
            else: #end of FREESTR
                tokeneater(FREESTR, literalstr, literalstrstart, (lnum, max), line, indents)
                literalstr = ''
            continue

        doIndent = True
        if useFreestr and line and not continued and not contstr and not line[0].isspace():# and line[0] not in '\'"': #free-form text
            if line[0] in ("'", '"') or \
               line[:2] in ("r'", 'r"', "R'", 'R"',"u'", 'u"', "U'", 'U"') or \
               line[:3] in ("ur'", 'ur"', "Ur'", 'Ur"', "uR'", 'uR"', "UR'", 'UR"' ):
              doIndent = False #this is a quoted string but treat like wiki markup (don't dedent)
            else:
              if line.rstrip()[-1] !=  '\\':
                  tokeneater(FREESTR, line, (lnum, 0), (lnum, max), line,indents)
              else:  #start literal
                  literalstrstart = (lnum, 0)          
                  literalstr = line.rstrip()[:-1]
              continue

        if contstr:                            # continued string
            if not line:
                #raise TokenError, ("EOF in multi-line string", strstart)
                if contstr[0] in 'uUrR':
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
                if line[pos] == ' ': column = column + 1
                elif line[pos] == '\t': column = (column/tabsize + 1)*tabsize
                elif line[pos] == '\f': column = 0
                else: break
                pos = pos + 1
            if pos == max: break            

        if pos >= len(line): #seems to happens when the last line == "'''" and there's no NL
            continue

        if line[pos] in '\r\n':           # skip blank lines            
            tokeneater(NL, line[pos:],(lnum, pos), (lnum, len(line)), line)
            continue
          
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
                               "u'''", 'u"""', "U'''", 'U"""',
                               "ur'''", 'ur"""', "Ur'''", 'Ur"""',
                               "uR'''", 'uR"""', "UR'''", 'UR"""'):
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
                                  "u'", 'u"', "U'", 'U"') or \
                    token[:3] in ("ur'", 'ur"', "Ur'", 'Ur"',
                                  "uR'", 'uR"', "UR'", 'UR"' ):
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

if __name__ == '__main__':                     # testing
    import sys
    if len(sys.argv) > 1: tokenize(open(sys.argv[1]).readline)
    else: tokenize(sys.stdin.readline)
