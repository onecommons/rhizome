'''
basic structure of a jql query:

construct = {
columnname | string : expression | [expression?] | construct
*
where(
    (expression,) |
    (columname = expression,)+
)

querypartfunc(expression) # groupby | orderby | limit | offset
}

expression = join | expr
join = { expr }
expr =

where(dfad=adfff, adfad=adfa or and or not
{
foo : bar #where foo = bar
"foo" : "bar" #construct: foo : bar
"foo" : bar  #construct foo, where foo = bar
foo : "bar" #where foo = "bar"
foo : ?child.baz
where ({ id=?child, foo="dd"})
'''

from jqlAST import *
import logging
logging.basicConfig() #XXX only if logging hasn't already been set
errorlog = logging.getLogger('parser')

class JQLParseException(Exception):
    pass

class Tag(tuple):
    __slots__ = ()

    def __new__(cls, *seq):
        return tuple.__new__(cls, seq)

    def __repr__(self):
        return self.__class__.__name__+tuple.__repr__(self)

    #for compatibility with QueryOp iterators:
    args = property(lambda self: self)

class _Env (object):
    _tagobjs = {}

    def __getattr__(self, attr):
        tagclass = self._tagobjs.get(attr)
        if not tagclass:
            #create a new subclass of Tag with attr as its name
            tagclass = type(Tag)(attr, (Tag,), {})
            self._tagobjs[attr] = tagclass
        return tagclass

T = _Env()

class QName(Tag):
    __slots__ = ()

    def __new__(cls, prefix, name):
        return tuple.__new__(cls, (prefix, name) )

    prefix = property(lambda self: self[0])
    name = property(lambda self: self[1])

#####PLY ####

import ply.lex
import ply.yacc

###########
#### TOKENS
###########

reserved = ('TRUE', 'FALSE', 'NULL', 'NOT', 'AND', 'OR', 'IN', 'IS', 'NS',
            'OPTIONAL', 'WHERE', 'LIMIT', 'OFFSET', 'GROUPBY', 'ORDERBY')

tokens = reserved + (
    # Literals (identifier, integer constant, float constant, string constant, char const)
    'NAME', 'INT', 'FLOAT', 'STRING',

    # Operators (+,-,*,/,%,  |,&,~,^,<<,>>, ||, &&, !, <, <=, >, >=, ==, !=)
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MOD',
    #'OR', 'AND', 'NOT', 'XOR', 'LSHIFT', 'RSHIFT',
    #'LOR', 'LAND', 'LNOT',
    'LT', 'LE', 'GT', 'GE', 'EQ', 'NE',

    # Delimeters ( ) [ ] { } , . 
    'LPAREN', 'RPAREN',
    'LBRACKET', 'RBRACKET',
    'LBRACE', 'RBRACE',
    'COMMA', 'PERIOD', 'COLON',

    'URI', 'VAR', 'QNAME', 'QSTAR', 'ID',
)

# Operators
t_PLUS             = r'\+'
t_MINUS            = r'-'
t_TIMES            = r'\*'
t_DIVIDE           = r'/'
t_MOD           = r'%'
t_LT               = r'<'
t_GT               = r'>'
t_LE               = r'<='
t_GE               = r'>='
t_EQ               = r'==?'
t_NE               = r'!='

# Delimeters
t_LPAREN           = r'\('
t_RPAREN           = r'\)'
t_LBRACKET         = r'\['
t_RBRACKET         = r'\]'
t_LBRACE           = r'\{'
t_RBRACE           = r'\}'
t_COMMA            = r','
t_PERIOD           = r'\.'
t_COLON            = r':'

reserved_map = { }
for r in reserved:
    reserved_map[r.lower()] = r

reserved_constants = {
 'true' : True,
 'false' : False,
 'null' : None
}

_namere = r'[A-Za-z_\$][\w_\$]*'

def t_INT(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_FLOAT(t):
    r'(\d+)(\.\d+)?((e|E)(\+|-)?(\d+))'
    t.value = float(t.value)
    return t

# String literal
t_STRING = r'''(?:"(?:[^"\n\r\\]|(?:"")|(?:\\x[0-9a-fA-F]+)|(?:\\.))*")|(?:'(?:[^'\n\r\\]|(?:'')|(?:\\x[0-9a-fA-F]+)|(?:\\.))*')'''

t_URI = r'''<(([a-zA-Z][0-9a-zA-Z+\\-\\.]*:)/{0,2}[0-9a-zA-Z;/?:@&=+$\\.\\-_!~*'()%]+)?("\#[0-9a-zA-Z;/?:@&=+$\\.\\-_!~*'()%]+)?>'''

def t_VAR(t):
    v = t.value[1:]
    if v.lower() == 'id': #reserved var
        t.type = 'ID'
        t.value = 'ID'
    else:
        t.value = T.var(v)
    return t
t_VAR.__doc__ = r'\?'+ _namere +''

def t_QNAME(t):
    prefix, name = t.lexer.lexmatch.group('prefix','name')
    if prefix:
        t.value = QName(prefix[:-1], name)
    else:
        key = t.value.lower() #make keywords case-insensitive (like SQL)
        t.type = reserved_map.get(key,"NAME")
        t.value = reserved_constants.get(key, t.value)
    return t

t_QNAME.__doc__ = '(?P<prefix>'+_namere+':)?(?P<name>' + _namere + ')'

def t_QSTAR(t):    
    t.value = QName(t.value[:-2], '*')
    return t
t_QSTAR.__doc__ = _namere + r':\*'

# SQL/C-style comments
def t_comment(t):
    r'/\*(.|\n)*?\*/'
    t.lexer.lineno += t.value.count('\n')

# Comment (both Python and C++-Style)
def t_linecomment(t):
    r'(//|\#).*\n'
    t.lexer.lineno += 1

def t_error(t):
    errorlog.error("Illegal character %s" % repr(t.value[0]))
    t.lexer.skip(1)

# Newlines
def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += t.value.count("\n")

# Completely ignored characters
t_ignore = ' \t\x0c'

lexer = ply.lex.lex(errorlog=errorlog) #optimize=1)

# Parsing rules
def p_construct(p):
    '''
    construct : dictconstruct
                | listconstruct
    '''
    p[0] = Root(Join(), p[1])

precedence = (
    ('left', 'ASSIGN'),
    ('left', 'OR'),
    ('left', 'AND'),
    ('right','NOT'),
    ("left", "IN"), 
    ("nonassoc", 'LT', 'LE', 'GT', 'GE', 'EQ', 'NE'),
    ('left','PLUS','MINUS'),
    ('left','TIMES','DIVIDE', 'MOD'),
    ('right','UMINUS', 'UPLUS'),
)

def p_expression_notin(p):
    """
    expression : expression NOT IN expression
    """    
    p[0] = Not(In(p[1], p[4]))

def p_expression_binop(p):
    """
    expression : expression PLUS expression
              | expression MINUS expression
              | expression TIMES expression
              | expression DIVIDE expression
              | expression MOD expression
              | expression LT expression
              | expression LE expression
              | expression GT expression
              | expression GE expression
              | expression EQ expression
              | expression NE expression
              | expression IN expression              
              | expression AND expression
              | expression OR expression
    """
    #print [repr(p[i]) for i in range(0,4)]
    p[0] = _opmap[p[2].upper()](p[1], p[3])

def p_expression_uminus(p):
    '''expression : MINUS expression %prec UMINUS
                  | PLUS expression %prec UPLUS'''
    if p[1] == '-':
        p[0] = qF.getOp('negate',p[2])
    else:
        p[0] = p[2]

def p_expression_notop(p):
    'expression : NOT expression'
    p[0] = Not(p[2])

def p_expression_isop(p):
    '''
    expression : expression IS NULL
               | expression IS NOT NULL
    '''
    if len(p) == 4:
        p[0] = IsNull(p[1])
    else:
        p[0] = Not(IsNull(p[1]))

def p_expression_group(p):
    'expression : LPAREN expression RPAREN'
    p[0] = p[2]

def p_expression_atom(p):
    'expression : atom'
    p[0] = p[1]

def p_atom_constant(p):
    '''constant : INT
            | FLOAT
            | STRING
            | NULL
            | TRUE
            | FALSE
    '''
    p[0] = p[1]

def p_atom(p):
    """atom : columnref
            | VAR
            | ID
            | funccall
            | constant
            | join
    """
    p[0] = p[1]

def p_barecolumnref(p):
    '''barecolumnref : NAME
                    | QNAME
                    | TIMES
                    | URI
                    | QSTAR
    '''
    p[0] = p[1]

def p_columnref_trailer(p):
    '''
    columnreftrailer : barecolumnref
                    | columnreftrailer PERIOD barecolumnref
    '''
    if len(p) == 2:
        p[0] = [ p[1] ]
    else:
        p[0] = p[1]
        p[1].append(p[3])

def p_columnref(p):
    '''
    columnref : VAR PERIOD columnreftrailer
              | columnreftrailer
    '''
    if len(p) == 2:
        p[0] = Project(p[1])
    else:
        p[0] = Project(p[3], p[1])

def p_funcname(p):
    '''funcname : NAME
                | QNAME
    '''
    p[0] = p[1]

def p_funccall(p):
    "funccall : funcname LPAREN arglist RPAREN"
    try:
        p[0] = qF.getOp(p[1], *p[3])
    except KeyError:
        msg = "unknown function " + p[1]
        p[0] = ErrorOp(p[3], msg)
        errorlog.error(msg)

def p_arglist(p):
    """
    arglist : arglist COMMA argument
            | arglist COMMA keywordarg
            | keywordarg
            | argument
    constructitemlist : constructitemlist COMMA constructitem
                      | constructitem
    constructoplist : constructoplist COMMA constructop
                      | constructop
    listconstructitemlist : listconstructitemlist COMMA listconstructitem
                          | listconstructitem
    """
    if len(p) == 4:
        p[0] = p[1] + [p[3]]
    else:
        p[0] = [p[1]]

def p_constructoplist(p):
    """
    constructoplist : constructoplist constructop
    """    
    p[0] = p[1].append(p[2])

def p_arglist_empty(p):
    """
    arglist : empty
    constructitemlist : constructempty
    constructoplist : empty
    listconstructitemlist : empty
    """
    p[0] = []

def p_argument(p):
    '''
    argument : expression
    '''
    p[0] = p[1]

def p_keyword_argument(p):
    '''
    keywordarg : NAME EQ expression  %prec ASSIGN
    '''
    p[0] = T.keywordarg(p[1], p[3])

def p_join(p):
    "join : LBRACE expression RBRACE"
    try:
        p[0] = makeJoinExpr(p[2])
    except QueryException:
        p[0] = ErrorOp(p[2], "Invalid Join")
        errorlog.error("invalid join: " + repr(p[2]))

def p_constructitem(p):
    '''
    constructitem : dictkey COLON dictvalue
                    | optional
                    | TIMES
    '''
    if len(p) == 2:
        if p[1] == '*':
            p[0] = '*' #ConstructProp(None, '*')
        else:
            p[0] = p[1]
    else:
        p[0] = ConstructProp(p[1], p[3])

def p_dictkey(p): 
    '''
    dictkey : STRING
            | columnname
    '''
    p[0] = p[1]

def p_columnname(p): 
    '''
    columnname : NAME
               | QNAME
               | URI
    '''
    p[0] = p[1]

def p_dictvalue(p): 
    '''
    dictvalue : LBRACKET expression RBRACKET 
              | construct
              | expression
    '''
    if len(p) == 4:
        p[0] = T.forcelist(p[2])
    else:
        p[0] = p[1]

def p_optional(p):
    '''
    optional : OPTIONAL LPAREN constructitemlist RPAREN
             | OPTIONAL LPAREN constructitemlist COMMA RPAREN
    '''
    for i, prop in enumerate(p[3]):
        if isinstance(prop, ConstructSubject):
            p[3][i] = ErrorOp(prop, "Subject in Optional")
            errorlog.error('subject spec not allowed in Optional')
        else:
            prop.ifEmpty = PropShape.omit
            #XXX jc.join = 'outer'
    p[0] = p[3]

def p_constructop(p):
    '''
    constructop : constructopname LPAREN expression RPAREN
    '''
    p[0] = T.constructop(p[1], p[3])


XXX = '''
constructop : WHERE LPAREN expression RPAREN
            | GROUPBY LPAREN columnamelist RPAREN
            | ORDERBY LPAREN columnamelist RPAREN
            | NS LPAREN keywordarglist RPAREN
            | LIMIT NUMBER
            | OFFSET NUMBER
'''

def p_constructopname(p):
    '''
    constructopname : WHERE
                    | LIMIT
                    | OFFSET
                    | GROUPBY
                    | ORDERBY
                    | NS
    '''
    p[0] = p[1]

def p_dictconstruct(p):
    '''
    dictconstruct : LBRACE constructitemlist RBRACE
                  | LBRACE constructitemlist constructoplist RBRACE
                  | LBRACE constructitemlist COMMA constructoplist RBRACE                  
                  | LBRACE constructitemlist COMMA constructoplist COMMA RBRACE
    '''
    if len(p) == 4:
        p[0] = T.dictconstruct( p[2], None)
    elif len(p) == 5:
        p[0] = T.dictconstruct( p[2], p[3])
    else:
        p[0] = T.dictconstruct( p[2], p[4])

def p_listconstruct(p):
    '''
    listconstruct : LBRACKET listconstructitemlist RBRACKET
        | LBRACKET listconstructitemlist constructoplist RBRACKET
        | LBRACKET listconstructitemlist COMMA constructoplist RBRACKET
        | LBRACKET listconstructitemlist COMMA constructoplist COMMA RBRACKET
    '''
    if len(p) == 4:
        p[0] = T.listconstruct( p[2], None)
    elif len(p) == 5:
        p[0] = T.listconstruct( p[2], p[3])
    else:
        p[0] = T.listconstruct( p[2], p[4])

def p_listconstructitem(p):
    '''
    listconstructitem : expression
                      | optional
    '''
    p[0] = p[1]

def p_error(p):
    if p:
        errorlog.error("Syntax error at '%s'" % p.value)
    else:
        errorlog.error("Syntax error at EOF")

def p_empty(p):
    'empty :'
    pass

def p_constructempty(p):
    'constructempty :'
    #redundant rule just to make it obvious that the related reduce/reduce
    #conflict is harmless
    pass

parser = ply.yacc.yacc(start="construct", errorlog=errorlog ) #, debug=True)

####parse-tree-to-ast mapping ####

_opmap = {
"AND" : And,
"OR" : Or,
"NOT" : Not,
"IN" : In,
"=" : Eq,
"==" : Eq,
'!=' : lambda *args: Not(Eq(*args)),
'<' : lambda *args: Cmp('<',*args),
'>' : lambda *args: Cmp('>',*args),
'<=' : lambda *args: Cmp('<=',*args),
'>=' : lambda *args: Cmp('>=',*args),
'+' : lambda *args: qF.getOp('add',*args),
'-' : lambda *args: qF.getOp('sub',*args),
'*' : lambda *args: qF.getOp('mul',*args),
'/' : lambda *args: qF.getOp('div',*args),
'%' : lambda *args: qF.getOp('mod',*args),
}

logicalops = {
 And : Join,
 Or : Union,
}

def columnRefToAST(project):
    '''
    Return a (pred, obj) pair

    bar return Eq('bar'), Project(OBJECT)

    bar.baz return

    JoinCondition(
    Join(
        jc(Filter(None, Eq('bar'), None, subjectlabel='_1'), OBJECT),
        jc(Filter(None, Eq('baz'), None, objectlabel='baz'), OBJECT)
      )
    '_1')

    In other words, join the object value of the "bar" filter with object value
    of "baz" filter.
    We add the label'baz' so that the project op can retrieve that value.
    The join condition join this join back into the enclosing join
    using the subject of the "bar" filter.

    If the filter was where(bar.baz = 'val') then add

    eq(project('baz'), 'val')

    foo = bar.baz

    Having(None, Eq('foo'), Project('baz'))

    to the enclosing join


    bar == { ?id where }

    Filter(Eq('bar'), Join(jc(
        Filter(None, Eq('foo'), None, propertyname='foo'), 'foo'))

    ?foo.bar is shorthand for
    { id : ?foo where(bar) }


    '''
    #XXX we need to disabiguate labels with the same name
    Join(
    jc(Join(
        jc(Filter(None, Eq('buzz'), None, subjectlabel='_1'), OBJECT),
        jc(Filter(None, Eq('blah'), None, subjectlabel='blah'), SUBJECT)
      ),
    '_1')
    )

    return (pred, object)

def makeJoinExpr(expr):
    '''
    Rewrite expression into Filters, operations that filter rows
    and ResourceSetOps (join, union, except), which group together the Filter 
    results by id (primary key).
    
    We also need to make sure that filter which apply individual statements
    (id, property, value) triples appear before filters that apply to more than
    one statement and so operate on the simple filter results.
    '''
    return expr

    cmproots = []
    to_visit = []
    visited = set()
    to_visit.append( (None, expr) )

    newexpr = None
    while to_visit:
        parent, v = to_visit.pop()
        if id(v) not in visited:
            visited.add( id(v) )

            notcount = 0
            while isinstance(v, Not):
                notcount += 1
                assert len(v.args) == 1
                v = v.args[0]
            
            optype = logicalops.get(type(v))
            if optype:
                if notcount % 2: #odd # of nots
                #if the child of the Not is a logical op, we need to treat this
                #as a Except op otherwise just include it in the compare operation
                    notOp = Except()
                    if not parent:
                        parent = newexpr = notOp
                    else:
                        parent.appendArg(notOp)
                        parent = notOp

                if not parent:
                    parent = newexpr = optype()
                elif type(parent) != optype:
                    #skip and(and()) or(or())
                    parent.appendArg(optype())
                
                to_visit.extend([(v, a) for a in v.args]) #descend
            else:
                if not parent: #default to Join
                    parent = newexpr = Join()
                if notcount % 2:
                    v = Not(v)
                cmproots.append( (parent, v) )

    #for each top-level comparison in the expression
    for parent, root in cmproots:
        #first add filter or join conditions that correspond to the columnrefs
        #(projections) that appear in the expression
        #then try to consolidate the expression into those. If it doesn't "fit"
        #in any of those append a new Filter with the expression.

        columns = []
        subject = None
        #look for Project ops but don't descend into ResourceSetOp (Join) ops
        for child in root.depthfirst(
                descendPredicate=lambda op: not isinstance(op, ResourceSetOp)):

            if isinstance(child, Project):
                columns.append( child )
            #else isinstance(child, ID): #XXX subject
        #foo = 'bar': Not(Eq('foo') and Eq('bar'))

        if len(columns) > 1: #XXX
            #handle wildcard objects, *, qstart
            raise QueryException('HAVING not yet implementing')
        elif columns:
            column[0].parent.replace(column[0], ObjectPlaceHolder)
            obj = root
            pred = Eq(column[0]) #XXX handle wildcard
        else: #no column refs
            pred = None
            obj = None
            if subject:
                subject = root

        parent.appendArg( Filter(subject, pred, obj) )

    return newexpr

tests = [
"{*,}",
"{*/1}", #bad
'''{ 'ok': */1 }''',
'''{ *, 
    where(type=bar OR foo=*)
    }''',
"{ * where(type=bar or foo=*) }",
'''
{
id : ?artist,
foo : { id : ?join },
"blah" : [ {*} ]
where( {
    ?id == 'http://foaf/friend' and
    topic_interest = ?ss and
    foaf:topic_interest = ?artist.foo.bar #Join(
  })
GROUPBY(foo)
}
'''
]

for test in tests:
    print "Test:", test.strip()
    try:
        result = parser.parse(test)#,tracking=True)

    except JQLParseException, e:
        print "error:", e

    print "Result:", result
    continue
    try:
        for dd in result[0]:
            if isinstance(dd,dict):
                print dd.items()
    except TypeError,te:
        pass
    print
