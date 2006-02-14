'''
 RxPath query engine, including an implementation of RDF Schema.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    

RxPath query engine

Given an XPath expression and a context, execute the following steps:

1. Analyze the expression to see what parts, if any, will be applied 
to a RxPath DOM. Each of those parts of the expression will be replaced
with a XPath function call that will perform the following steps:

2. Substitute any XPath variable references with the appropriate value. 

3.  translates the XPath expression into a much simpler abstract
syntax tree (AST) that represents the query in terms of a minimal set
of relational algebra operations. All RxPath expressions can be
represented by minimal set of relational algebra operations applied to
a set of triples that represent the statements in the model.

Select: XPath predicates and node tests correspond to the select
operation. This operation needs to support sub-queries in the select
predicate; if the corresponding XPath sub-expression is a relative
path, the query will be correlated with the outer query, otherwise
(i.e. an absolute XPath path), it will not be correlated.

Join: The only join needed is a reflexive equijoin between the object
and subject of a statement. The descendent axis corresponds to a
recursive (transitive closure) version of this join.

Project - XPath's parent and ancestor axes correspond to a project
operation on the joined result set, as does the position of the final
step of an XPath path.

Union - for the XPath union operator.

4.  Next, the AST may be transformed. Transformations may happen for a
few reasons: One, to provide schema support if the underlying query
engine doesn't support that, for example, by updating a property match
by also matching of its sub-properties. Two, to optimize the query,
for example reversing join operands. Three, to support the underlying
query engine; for example, SPARQL doesn't support a recursive join, so
it is replaced with the union of some configurable number of optional
joins.

5.  Process the query.  SPARQL doesn't directly support nested queries
as filter conditions, using optional graph patterns for correlated
(relative) sub-expressions and the union operator for non-correlated
(absolute) sub-expressions.

6.  Filter rows in the result set by evaluating any select predicates
that could not be handled by the underlying query processor. For XPath
functions that are not translatable to query primitives (this includes
numeric predicates, which are just shorthand for the position()
function), the filter condition will be dynamically applied to the
result set, with the XPath function called with a simulated XPath
context. This allows the implementation to be compatible with standard
XPath functions. The XPath context is recreated as follows:

We can obtain RxPath's notion of document order by lexicographically
sorting the result set.

We determine the position and size attributes of the XPath context by
performing the equivalent of a "group by" operation on all the rows to
the left of the current evaluation point.

The context's current node can be synthesized by building DOM node
based on values in the current row of the result set. Attributes such
as siblings and children that can not be determined from the result
set are lazily computed on request by executing additional queries.

If the XPath function takes additional parameters that correspond to
nested queries, we can create a node set from the appropriate column
of the result set, one for each row.

7. Convert the result set to a node set as described in the previous
step.
'''
from __future__ import generators
from rx import utils, RxPath
from rx.RxPath import Tupleset
from utils import XPath, flattenSeq, GeneratorType
from Ft.Lib import boolean
from Ft.Xml import EMPTY_NAMESPACE
from Ft.Xml.XPath import ParsedExpr
try:
    from Ft.Xml.XPath import _comparisons
    eq = _comparisons.eq
    ne = _comparisons.eq
except ImportError:
    #must be an older version of 4Suite
    eq = lambda a, b: a == b
    ne = lambda a, b: a != b
    
from xml.dom import Node
import operator, copy, sys

class QueryException(Exception): pass

class PositionDependentException(QueryException): pass

class ReplaceRxPathSubExpr(utils.XPathExprVisitor):
    '''
    Visits an XPath expression and, whenever it encounters a AbsoluteLocationPath
    and the context node is a RxPath node, replaces that path with a FunctionCall
    that evaluates the corresponding RxPath query.
    '''
    #todo move modifications in _ParsedAbbreviatedRelativeLocationPath_evaluate to here

    def __init__(self, context, expr, checkPos = False, explain=False):
        super(ReplaceRxPathSubExpr,self).__init__()
        self.context = context
        self.abortIfPositionDependent = checkPos
        
        #when the beginRxPath is set we replace with the first encountered
        #path expression with of FunctionCall
        self.beginRxPath = context.node and context.node.__module__.lower().startswith('rx')
        self.explain= explain
        self.changed = False
        self.resultExpr = expr
        expr.visit(self.visit)
        
    def absPath(self, node):
        if self.beginRxPath:
            #replace this with a RxPathQueryFunc and stop
            self.createRxPathQueryClosure()             
            self.beginRxPath = False
            return self.NEXT
        else:
            return self.DESCEND
            
    ParsedAbsoluteLocationPath = absPath

    def createRxPathQueryClosure(self):
        #for now we can assume the exp is an absolute path or exp is a relative path
        #and the context node is an RxPath document 
        ast = Path2AST(self.context, self.currentNode,explain=self.explain)
        #todo if parent is a PathExp than the left side is a $var or a func()
        #we'll need to replace it with the closure func and pass the left side to it
        #this can't happen now as we don't support relPaths yet
        astRoot = ast.currentOpStack[0]

        name = 'evalRxPathQuery'
        dummyArg = XPath.ParsedExpr.ParsedLiteralExpr( repr(astRoot) )
        
        funcCall = XPath.ParsedExpr.FunctionCall1(name, (None,name), (dummyArg,) )

        def evaluateQuery(context, dummy):
            #we just want a representation of the AST stored in the XPath expression
            #so we pass it in as a argument that is ignored 
            doc = context.node.rootNode
            
            queryContext = QueryContext(context, doc.model, explain=self.explain) 
            result = astRoot.evaluate(SimpleQueryEngine(),queryContext)

            if self.explain:
                return result
            
            if isinstance(result, NodesetTupleset):
                return result.nodeset
            else:
                assert isinstance(result, Tupleset)                
                if isinstance(result, Projection):
                    finalpos = result.position
                else:
                    finalpos = -1
                #return list(result ) 
                return filter(None, [row2Node(doc, row, finalpos) for row in result])
        
        evaluateQuery.xpathExprs = ast.xpathExprs
        funcCall._func = evaluateQuery

        self.changed = True
        if self.ancestors:
            #the current field of the parent node to the new function
            self.ancestors[-1] = funcCall
            return self.ancestors[-1][0] #return the parent node
        else:
            #its the topmost node
            self.resultExpr = funcCall
            return funcCall

    def FunctionCall(self, node):
        #todo: if leftside of PathExpr: if node.name in rxpathfuncs: self.beginRxPath = True
        if self.abortIfPositionDependent:
            (prefix, local) = node._key
            if prefix:
                try:
                    expanded = (self.context.processorNss[prefix], local)
                except:
                    raise XPath.RuntimeException(RuntimeException.UNDEFINED_PREFIX, prefix)
            else:
                expanded = node._key

            if expanded in PosDependentFuncs:
                raise PositionDependentException()
            
        return -1

    def relPath(self, node):
        if self.abortIfPositionDependent:
            #now that we're entering a new path we don't need to check for this anymore
            self.abortIfPositionDependent = False
        return -1

        #todo:
        if self.beginRxPath and self.contextIsRoot:
            #replace this with a RxPathQueryFunc and stop
            self.createRxPathQueryClosure(node)
            #self.parent
            self.beginRxPath = False        
        return -1
    
    ParsedStep = ParsedAbbreviatedStep = ParsedRelativeLocationPath\
    = ParsedAbbreviatedRelativeLocationPath = relPath

    ####################todo:###################################
    #right now we just look for absolute location paths
    #def ParsedAbbreviatedAbsoluteLocationPath #//foo #todo 

    def ParsedVariableReferenceExpr(self, node):
        return 1
        #todo: if leftside of PathExpr:
        if isinstance(node.value, list): #nodeset
            for domNode  in node.value:
                isRxPathNode = domNode.__module__.lower().startswith('rx')
                if not isRxPathNode:
                    #can't do RxPath query here, so stop
                    self.beginRxPath = False                    
                    break
                self.beginRxPath = True
        return 1 
                
def row2Node(doc, row, finalPos = -1):
    '''
    statements is a list of joined statements, corresponding
    to all the columns in a row
    '''
##    last = len(row)-1
##    for i, column in enumerate(row):        
##        if i == 0:
##            node = doc.findSubject(column)
##            assert node, 'subject ' + column + 'not found!'
##        if i < last or finalPos != SUB_POS:
##            #we're
##            currentStatement = row[max(i-1,0):i+4]
##            node = node.findPredicate(currentStatement)
##            assert node, 'statement ' + str(row) + str(i) + 'not found!'
##            if i < last or finalPos != PRED_POS:
##                node = node.firstChild

    start = 0; stop =  5
    while 1:
        stmt = row[start:stop]
        node = doc.findSubject(stmt[0])
        if not node: #inner list resources might not show up
            return None        
        if finalPos != SUB_POS:
            assert len(stmt) >= 5, `stmt` + `finalPos` + `node` + `row`
            node = node.findPredicate(stmt )
            if not node:
                return None #some stmts like rdf:type rdfs:Resource don't show up
            if finalPos != PRED_POS:
                assert finalPos != SCOPE_POS
                assert finalPos != OBJTYPE_POS, 'not yet implemented'
                node = node.firstChild
        break
        start+=5; stop+=5
    return node

#define the AST syntax using Zephyr Abstract Syntax Definition Language.
#(see http://www.cs.princeton.edu/~danwang/Papers/dsl97/dsl97-abstract.html)
#If the AST gets more complicated we could write a code generator using
#http://svn.python.org/view/python/trunk/Parser/asdl.py

syntax = '''
-- Zephyr ASDL's five builtin types are identifier, int, string, object, bool

module RxPathQuery
{
    exp =  boolexp | AnyFunc(exp*) | Query(subquery)
            
    subquery = Select(subquery input?, boolexp* subject,
                    boolexp* predicate, boolexp* object) |
               Join(subquery left, subquery right) | 
               Project(subquery input, column id)  |
               Union(subquery left, subquery right)

    boolexp = BoolFunc(exp*) 
    -- nodesetfunc, eqfunc, orfunc, andfunc
}
'''

#for now the query AST type system mirrors XPath. Object is the base for the other types
#todo: should the type system reflect resource vs. Literal vs. data type literal?
try:
    from Ft.Xml.XPath.XPathTypes import *
except ImportError:    
    from Ft.Xml.XPath.Types import *#old 4Suite
ObjectType = object #4suite bug: missing from XPathTypes.__all__

XPathTypes = ( NodesetType,StringType,NumberType,BooleanType)

QueryOpTypes = ( Tupleset, StringType, NumberType, BooleanType )
NullType = None

class QueryOp(object):
    '''
    Base class for RxPath's AST. 
    '''        
    #maybe this should derive from rx.DomTree to enable
    #XPath expressions to be used for query rewriting 

    xpathExp = None
    
    def getType(self):
        return ObjectType

    def getArgs(self):
        return ()

    def isIndependent(self):
        if not self.xpathExp:
            for a in self.getArgs():
                if not a.isIndependent():
                    return False
            return True
        else:
            #todo: abspath and funcs that don't depend on context node are independent
            return False

    def getPosition(self):
        return -1

    def evaluate(self, engine, context):
        '''
        Given a context with a sourceModel, evaluate either modified
        the context's resultModel or returns a value to be used by a
        parent QueryOp's evaluate()
        '''
    
    def __repr__(self):
        return self.__class__.__name__
    
    #def __iter__(self):
    #    yield self

SUB_POS = 0
PRED_POS = 1
OBJ_POS = 2
OBJTYPE_POS = 3 #used when stepping to predicate attributes
SCOPE_POS = 4

def _getPosition(node):
    from rx import RxPathDom    
    if isinstance(node, RxPathDom.Subject):
        return 0
    elif isinstance(node, RxPathDom.BasePredicate):
        return 1
    elif isinstance(node, RxPathDom.Object):
        return 2
    return -1
        
class SelectOp(QueryOp):
    '''
    An optional input rowset,
    and list of predicates,
    each predicate has a FilterOp and an optional exp

    if object or predicate filters are defined and the subquery
    is relative (i.e. the SelectOp as an input rowset)
    accessing size or position subject or predicate expression
    raises an exception that will cause the filter to be recalculated
    without object or predicate filters
    this let's us properly handle expressions like /foo/bar[2]/*[blah(.)]
    -- even for subject, consider: /foo[2][.='uri']

    /foo[blah/bar]/buz
    ==
    /foo[buz][blah/bar]/*
    
    '''    
    
    def __init__(self, position = -1):
        self.finalPosition = self.joinPosition = position
        self.predicates = ( [], [], [], [] )

    def getType(self):
        return Tupleset

    def isIndependent(self):
        return self.joinPosition < 0

    def __repr__(self):
         args = ', '.join([repr(a) for a in flattenSeq(self.predicates)])
         if self.xpathExp:
             with = ' with ' + repr(self.xpathExp)
         else:
             with = ''
         pos = 'select ' + str(self.finalPosition) + ' from ' + str(self.joinPosition)
         return pos + ' where(' + args + ')' + with

    #def __iter__(self):
    #    yield self        
    #    for arg in flattenSeq(self.predicates):
    #        yield arg
         
    def getPosition(self):
        '''
        Return the position if it is known.
        (if xpathExp is set, we can't know this)
        '''
        if not self.xpathExp:
            return self.finalPosition
        else:
            return -1

    def getArgs(self):
        return flattenSeq(self.predicates)
        
    def appendArg(self, arg):        
        assert self.finalPosition > -1
        self.predicates[self.finalPosition].append(arg)

    def cost(self, engine, context):
        return engine.costSelectOp(self, context)

    def evaluate(self, engine, context):
        return engine.evalSelectOp(self, context)
                
class AnyFuncOp(QueryOp):
    
    def __init__(self, key=(), metadata=None):
        self.name = key
        self.args = []
        self.metadata = metadata or self.defaultMetadata
        
    def getType(self):
        return self.metadata.type

    def isIndependent(self):
        independent = super(AnyFuncOp, self).isIndependent()
        if independent: #the args are independent
            return self.metadata.isIndependent
        else:
            return False

    def getArgs(self):
        return self.args

    def appendArg(self, arg):
        self.args.append(arg)

    def __repr__(self):
        if self.name:
            name = self.name[1]
        elif self.xpathExp:
            name = 'func[' +repr(self.xpathExp) +']'
        else:
            raise TypeError('malformed FuncOp, no name or xpath expr')
        return name + '(' + ','.join( [repr(a) for a in self.args] ) + ')'

    def cost(self, engine, context):
        return engine.costAnyFuncOp(self, context)

    def evaluate(self, engine, context):
        return engine.evalAnyFuncOp(self, context)

class NumberFuncOp(AnyFuncOp):
    def getType(self):
        return NumberType

class StringFuncOp(AnyFuncOp):
    def getType(self):
        return StringType

class BooleanFuncOp(AnyFuncOp):
    def getType(self):
        return BooleanType
    
class BooleanOp(QueryOp):
    '''
    BooleanOps filter the sourceModel, setting the resultModel to
    all the statements that evaluate to true given the BooleanOp.
    '''
    
    def __init__(self):
        self.args = []
        
    def getType(self):
        return BooleanType

    def getArgs(self):
        return self.args

    def appendArg(self, arg):
        self.args.append(arg)

    #def __iter__(self):
    #    yield self
    #    for arg in self.args:
    #        yield arg

class AndOp(BooleanOp):
    def __repr__(self):
        if not self.args:
            return ''
        elif len(self.args) > 1:
            return ' and '.join( [repr(a) for a in self.args] )
        else:
            return repr(self.args[0])
    

    def evaluate(self, engine, context):
        return engine.evalAndOp(self, context)

    def cost(self, engine, context):
        return engine.costAndOp(self, context)

class OrOp(BooleanOp):
    def __repr__(self):
        return 'or:' + self.args and ' or '.join( [repr(a) for a in self.args] )

    def evaluate(self, engine, context):
        return engine.evalOrOp(self, context)

    def cost(self, engine, context):
        return engine.costOrOp(self, context)

class InOp(BooleanOp):
    '''Like OrOp + EqOp but the first argument is only evaluated once'''
    
    def __repr__(self):
        rep = repr(self.args[0]) + ' in (' 
        return rep + ','.join([repr(a) for a in self.args[1:] ]) + ')'

    def evaluate(self, engine, context):
        return engine.evalInOp(self, context)

    def cost(self, engine, context):
        return engine.costInOp(self, context)

class EqOp(BooleanOp):

    def __init__(self, op='eq'):
        self.args = []
        self.op = op
        
    def __repr__(self):
        op = self.op == 'eq' and ' = ' or ' != '
        return '(' + op.join( [repr(a) for a in self.args] ) + ')'

    def evaluate(self, engine, context):
        return engine.evalEqOp(self, context)

    def cost(self, engine, context):
        return engine.costEqOp(self, context)

class ConstantOp(QueryOp):
    '''
    '''
    def __init__(self, value):
        if not isinstance( value, QueryOpTypes):            
            #coerce
            if isinstance(value, str):
                value = unicode(value, 'utf8')
            elif isinstance(value, (int, long)):
                value = float(value)
            elif isinstance(value, type(True)):
                value = boolean.bool(value)
            elif isinstance(value, NodesetType):
                value = NodesetTupleset(value)
        self.value = value
        
    def getType(self):
        if isinstance(self.value, QueryOpTypes):
            return type(self.value)
        else:
            return ObjectType

    def isIndependent(self):
        return True

    def getPosition(self):
        value = self.value        
        if value and isinstance(value, Tupleset):
            #we can assume all nodes in the same position
            return _getPosition(value[0]) #todo
        return -1
    
    def __repr__(self):
        if isinstance(self.value, Tupleset):
            return 'Nodeset' #we don't want to muddy up are nice determistic string
        return repr(self.value)

    def evaluate(self, engine, context):
        return engine.evalConstantOp(self, context)

    def cost(self, engine, context):
        return engine.costConstantOp(self, context)

PosDependentFuncs = [   (EMPTY_NAMESPACE, 'last'),
    (EMPTY_NAMESPACE, 'position'),
    (EMPTY_NAMESPACE, 'count'), ]

NumberFuncs = PosDependentFuncs + [(EMPTY_NAMESPACE, 'sum'),
    (EMPTY_NAMESPACE, 'ceiling'),(EMPTY_NAMESPACE, 'floor'),
    (EMPTY_NAMESPACE, 'round'), ]

from Ft.Xml.XPath import MathFunctions
NumberFuncs += MathFunctions.ExtFunctions.keys()

class QueryFuncMetadata:
    factoryMap = { StringType: StringFuncOp, NumberType : NumberFuncOp,
      BooleanType : BooleanFuncOp
      }
    
    def __init__(self, func, type=None, opFactory=None, isIndependent=True,
                                                             costFunc=None):
        self.func = func        
        self.type = type or ObjectType
        self.isIndependent = isIndependent
        self.opFactory  = opFactory or self.factoryMap.get(self.type, AnyFuncOp)
        self.costFunc = costFunc

AnyFuncOp.defaultMetadata = QueryFuncMetadata(None)
            
#todo: SupportedFuncs should be per query engine and schema handler
SupportedFuncs = {
    (EMPTY_NAMESPACE, 'true') :
      QueryFuncMetadata(lambda *args: True, BooleanType, None, True,
                        lambda *args: 0),
    (EMPTY_NAMESPACE, 'false') :
      QueryFuncMetadata(lambda *args: False, BooleanType, None, True,
                        lambda *args: 0),
}


def getFuncOp(name):
    if isinstance(name, (unicode, str)):
        name = (EMPTY_NAMESPACE, name)
    funcMetadata = SupportedFuncs[name]
    return funcMetadata.opFactory(name,funcMetadata)

class QueryContext(object):
    
    def __init__(self, xpathContext, initModel, pos=-1, modelContext = '', explain=False):
        self.xpathContext = xpathContext
        self.initialModel = initModel        
        self.currentTupleset = initModel
        self.currentPosition = pos
        self.modelContext = modelContext
        self.explain=explain
        self.joinTupleset = initModel

    def __copy__(self):
        copy = QueryContext(self.xpathContext, self.initialModel,
                        self.currentPosition,self.modelContext,self.explain)
        copy.currentTupleset = self.currentTupleset
        copy.joinTupleset= self.currentTupleset
        return copy
        
        
        
class Path2AST(utils.XPathExprVisitor):
    '''
    parse and add filter conditions until done or we encounter something we can't handle

    outline:
     start:
      -> absolute path or (rel path or step) when called recursively
        -> Step with unsupported axis -> make step unsupported
        -> AbbreviatedRelativeLocationPath -> make step unsupported
        -> NodeTest/NameTest -> add eq bool func
        -> predicate list
            -> supported op (and = or): boolfunc            
            -> union, path, filterexpre, abbreviateabsolutepath -> new Subquery, unsupported
            -> relative or abs path => new Subquery, new AstVisitor()

            -> number or pos func or numfunc and parent predicatelist -> make step unsupported

            -> unsupported func or op (> != +) -> make func or op unsupported
            -> supported funcs (uri, iscompatibleproperty, etc.) -> add op, descend

            -> var ref -> resolve, to string if necessary?
            -> literal 
    '''                  
            
    def __init__(self, context, expr,position=-1, explain=False):
        super(Path2AST,self).__init__() 
        self.context = context
        self.currentOpStack = []
        self.initialPosition = position
        self.inPredicate = False
        self.explain = explain
        self.xpathExprs = []
        expr.visit(self.visit)

    def _pathInPredicate(self):
        if self.inPredicate:
            astVisitor = Path2AST(self.context, self.currentNode,
                                  self.currentOpStack[0].finalPosition,explain=self.explain)
            self.currentOpStack[-1].appendArg(astVisitor.currentOpStack[0])
            return 1 #next
        else:
            return False
        
    def _startStep(self):
        if self._pathInPredicate():
            return 1
        elif not self.currentOpStack:
            self.currentOpStack.append( SelectOp(self.initialPosition) )
        else:
            assert isinstance(self.currentOpStack[-1], SelectOp)
        return False

    def ParsedAbsoluteLocationPath(self, exp):
        if self._pathInPredicate():
            return 1
        else:
            assert not self.currentOpStack
            self.currentOpStack.append( SelectOp() )
            return -1 #descend

    def ParsedAbbreviatedRelativeLocationPath(self, exp): #"//"
        #self.addJoin(exp, recursive=True) #XXX
        if self._startStep(): 
            return 1 #handled, move on

        #handle the left side
        self.descend(exp, ['_left'])
        
        #we don't handle this now so treat the right side as unhandled
        newExpVisitor = ReplaceRxPathSubExpr(self.context, exp._right,explain=self.explain)
        exp._right = newExpVisitor.resultExpr
        exp._left = XPath.ParsedStep.ParsedAbbreviatedStep(False)
        self.currentOpStack[-1].xpathExp = exp
        self.xpathExprs.append( exp )
        self.currentOpStack[-1].finalPosition -= 1
        
        return 1 #next
        
    def ParsedRelativeLocationPath(self, exp):
        if self._startStep(): 
            return 1 #handled, move on
        else:
            return -1 
    
    def ParsedStep(self, exp):
        if self._startStep(): 
            return 1 #we're in a predicate so this is handled, move on
        else:
            stop = self._step(exp._axis._axis)
            if not stop:
                if self._handleNodeTest(self.currentOpStack[-1], exp._nodeTest):
                    try:
                        retVal = self.descend(exp,['_predicates'])
                    except PositionDependentException:
                        retVal = self.STOP
                else:
                    retVal = self.STOP
                
                if retVal == self.STOP:
                    #encountered a position dependent predicate
                    selectOp = self.currentOpStack[-1]
                    selectOp.xpathExp = self._extractPathRemainder()
                    self.xpathExprs.append( selectOp.xpathExp )
                    assert selectOp.finalPosition > -1
                    if selectOp.finalPosition == OBJTYPE_POS:
                        selectOp.finalPosition = PRED_POS
                    else:
                        selectOp.finalPosition -= 1
                    return 0
                return 1 #next
            else:
                return 0 #stop

    def ParsedAbbreviatedStep(self, exp):        
        if self._startStep(): 
            return 1 #handled, move on
        else:
            if exp.parent: # ".."
                stop = self._step('parent')
                return not stop 
            else:
                return 1

    def _handleNodeTest(self, selectOp, nodeTest):
        nodeType, key = nodeTest.getQuickKey(self.context.processorNss)

        if selectOp.finalPosition == OBJTYPE_POS:
            #set by predicate attribute step:
            #selectOp.finalPosition = PRED_POS
            #handle xml:lang, rdf:datatype, listid, uri
            return False
        elif not nodeType:
            assert repr(nodeTest) == 'node()'
            return True#no-op: matches everything
        if selectOp.finalPosition == OBJ_POS:
            if isinstance(nodeTest, XPath.ParsedNodeTest.PrincipalTypeTest
                                            ) or nodeType == Node.TEXT_NODE:
                literalMatch = nodeType == Node.TEXT_NODE
                if not literalMatch:
                    assert repr(nodeTest) == '*'
                eq = EqOp(literalMatch and 'ne' or 'eq')                
                eq.appendArg(SelectOp(OBJTYPE_POS))
                eq.appendArg(ConstantOp(RxPath.OBJECT_TYPE_RESOURCE))
                selectOp.finalPosition = OBJTYPE_POS
                selectOp.appendArg(eq)
                selectOp.finalPosition = OBJ_POS
                return True
        elif nodeType != Node.ELEMENT_NODE:
            #anything else will never match
            selectOp.appendArg(ConstantOp(False))
            return True
        elif isinstance(nodeTest, XPath.ParsedNodeTest.PrincipalTypeTest):
            assert repr(nodeTest) == '*'
            return True #no-op: matches everything

        #at this point nodeTest will be either a local name,
        #qualfied name or namespace test
        if key is None: #namespace test
            nameUri = self.context.processorNss[nodeTest._prefix] + '*'
            return False #todo
        else:
            namespaceURI = key[0] or '' #this will be None if LocalName 
            nameUri = namespaceURI + RxPath.getURIFragmentFromLocal(key[1])
        
        if selectOp.finalPosition == OBJ_POS:
            return False #todo
        if selectOp.finalPosition == SUB_POS:#or selectOp.finalPosition == OBJ_POS:
            #type match: /foo is equivalent to /*[is-subclass-of(rdf:type,uri('foo'))]
            #:= subquery that with 2 predicates: predicate = rdf:type and object in subclass list
            op = SelectOp(selectOp.finalPosition)
            
            eq1 = EqOp()                
            eq1.appendArg(SelectOp(PRED_POS))
            eq1.appendArg(ConstantOp('http://www.w3.org/1999/02/22-rdf-syntax-ns#type'))
            op.finalPosition = PRED_POS
            op.appendArg(eq1)
            
            eq2 = InOp()
            eq2.appendArg(SelectOp(OBJ_POS))            
            #for RDFSSchema only
            subMap = getattr(self.context.node.rootNode.schema,
                                            'currentSubTypes',{})
            for sub in subMap.get(nameUri,[nameUri]):
                eq2.appendArg(ConstantOp(sub))

            op.finalPosition = OBJ_POS
            op.appendArg(eq2)            
        elif selectOp.finalPosition == PRED_POS:
            #add condition where predicate in subproperty list
            op = InOp()
            op.appendArg(SelectOp(PRED_POS))
            #for RDFSSchema only
            subMap = getattr(self.context.node.rootNode.schema,
                                        'currentSubProperties',{})
            for sub in subMap.get(nameUri,[nameUri]):
                op.appendArg(ConstantOp(sub))

        selectOp.appendArg(op)
        return True

    def ParsedPredicateList(self, exp):
        #create a AndOp with each predicate
        #then add the AndOp to the parent SelectOp
        #if a predicate returns stop (because it encountered a position dependent predicate)
        #each subsequent predicate is a unsupportedBoolFunc        
        #and then we call _extractPathRemainder to stop processing this path after this step

        assert not self.inPredicate        
        self.inPredicate = True

        selectOp = self.currentOpStack[-1]
        assert isinstance(selectOp,SelectOp)
        currentOp = AndOp()
        self.currentOpStack.append( currentOp )
        try:
            retVal = self.descend()
            if currentOp.args:
                selectOp.appendArg(currentOp)
        finally:
            self.currentOpStack.pop()
            assert isinstance(self.currentOpStack[-1],SelectOp), repr(self.currentOpStack[-1])
            self.inPredicate = False
        
        return retVal #stop or next 

    #####the following will only be called inside the PredicateList#####    

    def visitUnsupportedExpr(self, exp, funcFactory = AnyFuncOp):
        assert self.inPredicate
        #we need to still look for function calls that depend on the context position
        visitor = ReplaceRxPathSubExpr(self.context, exp,checkPos = True,explain=self.explain)
        subexpr = visitor.resultExpr
        funcOp = funcFactory()
        funcOp.xpathExp = subexpr
        self.xpathExprs.append( exp )
        self.currentOpStack[-1].appendArg( funcOp )
        return 1

    def visitBooleanUnsupportedExpr(self, exp):
        return self.visitUnsupportedExpr(exp,BooleanFuncOp)

    def visitNumberUnsupportedExpr(self, exp):
        return self.visitUnsupportedExpr(exp,NumberFuncOp)
                                         
    ParsedAbbreviatedAbsoluteLocationPath = ParsedPathExpr = \
        ParsedFilterExpr = ParsedUnionExpr = visitUnsupportedExpr

    ParsedRelationalExpr = visitBooleanUnsupportedExpr

    ParsedMultiplicativeExpr = ParsedAdditiveExpr = ParsedUnaryExpr = \
        visitNumberUnsupportedExpr

    def _visitWithOp(self, op):
        self.currentOpStack.append(op)
        try:
            self.descend()
        finally:
            self.currentOpStack.pop()
        return 1
            
    def ParsedOrExpr(self, exp):
        assert self.inPredicate
        return self._visitWithOp( OrOp() )
    
    def ParsedAndExpr(self, exp):
        assert self.inPredicate
        return self._visitWithOp( AndOp() )
    
    #def coerceToBoolean():
        #for and/or and any expression whose immediate parent is a predicateList
        #we need to coerce the type to boolean
        #if the type is a nodeset we are testing whether it is empty or not
        #ignore: OK to let query engine deal with this

    def coerceToString(self, lexpr, rexpr):
        '''
        Check if the comparing the 2 expression requires lexpr to be coerced
        to a string and adjust lexpr if necessary.
        Return false if we can't figure out whether we need to adjust lexpr
        '''
        ltype = lexpr.getType()
        rtype = rexpr.getType()

        if ltype == ObjectType or rtype == ObjectType:
            return False

        if ltype == Tupleset:
            lpos = lexpr.getPosition()
            if lpos < 0:
                return False
            elif lpos == PRED_POS:
                if rtype is not BooleanType:                    
                    #number or string coercion implies selecting the object's value
                    if isinstance(lexpr, SelectOp):
                        lexpr.finalPosition = OBJ_POS
                    else:
                        #todo: support Nodeset ConstantOps containing predicates
                        return False

        #optimization: if an expression is a Constant with a nodeset containing a single node
        #we can always convert it to a string for the comparison
        if (rtype == NodesetTupleset and isinstance(rexpr, ConstantOp)
            and len(rexpr.value.nodeset) == 1):
            #optimization
            rexpr.value = RxPath.StringValue(rexpr.value.nodeset)
        return True
        
    def ParsedEqualityExpr(self, exp):
        #to be able to add use AST nodes we need to know the types of
        #the arguments, and if an argument is a nodeset and the other
        #is not a boolean we need to know the position of the nodeset
        #because we need to map the implicit string conversion to a
        #adjust the predicate if it is a predicate
        assert self.inPredicate
        eqOp = EqOp(exp._op == '=' and 'eq' or 'ne')
        oldOp = self.currentOpStack[-1]
        self.currentOpStack.append(eqOp)
        try:                
            currentExprs = self.xpathExprs[:]
             
            self.descend()
                        
            lexpr, rexpr = eqOp.getArgs() #must have 2 args

            for expr in (lexpr, rexpr):
                if (expr.getType() == NodesetTupleset and isinstance(expr, ConstantOp)
                    and len(expr.value.nodeset) == 0):
                    #optimization
                    #nodeset equality means this expression will never be true
                    oldOp.appendArg( getFuncOp('false') )
                    self.xpathExprs = currentExprs #revert 
                    return 1
                
            if (self.coerceToString(lexpr, rexpr) and 
                self.coerceToString(rexpr, lexpr)):
                #the query engine can handle the operands
                oldOp.appendArg( eqOp)
                return 1
        finally:
            self.currentOpStack.pop()
            assert oldOp is self.currentOpStack[-1], (oldOp,self.currentOpStack[-1])            

        return self.visitBooleanUnsupportedExpr(exp)
    
    def FunctionCall(self, exp):
        assert self.inPredicate

        (prefix, local) = exp._key
        if prefix:
            try:
                expanded = (self.context.processorNss[prefix], local)
            except:
                raise XPath.RuntimeException(RuntimeException.UNDEFINED_PREFIX, prefix)
        else:
            expanded = exp._key

        if expanded in PosDependentFuncs:
            raise PositionDependentException()
        
        #if the immediate parent is a predicate list
        #and this function returns a number
        #then this is selecting a node based on position and so we can't 
        #handle this path after this predicate
        
        if isinstance(self.ancestors[-1][0],XPath.ParsedPredicateList.ParsedPredicateList):
            if expanded in NumberFuncs: 
                return self.STOP #== 0
            elif expanded not in SupportedFuncs:
                #todo: get func and check for result attribute, 
                #unknown type, there's a chance it's a Number
                return self.STOP #== 0
        
        if expanded in SupportedFuncs: #todo: various func list and dicts
            funcMetadata = SupportedFuncs[expanded]
            op = funcMetadata.opFactory(expanded,funcMetadata)
            return self._visitWithOp(op)
        else:
            #unsupported func
            #todo: get func and check for result attribute, use as type arg
            return self.visitUnsupportedExpr(exp)
        
    def ParsedNLiteralExpr(self, exp):
        assert self.inPredicate
        #if the immediate parent is a predicate list
        #then this is selecting a node based on position and so we can't 
        #handle this path after this predicate
        if isinstance(self.ancestors[-1][0],XPath.ParsedPredicateList.ParsedPredicateList):
            #we must stop converting this path to the AST because the data engine doesn't guarantee
            #the order in which the query is processed
            return self.STOP #== 0
        else:
            self.currentOpStack[-1].appendArg(ConstantOp(exp._literal))
            return 1
    
    def ParsedLiteralExpr(self, exp):
        assert self.inPredicate
        self.currentOpStack[-1].appendArg(ConstantOp(exp._literal))
        return 1
        
    def ParsedVariableReferenceExpr(self, exp):
        assert self.inPredicate
        #todo: we need to add a VarRef op to enable this to be used inside XSLT? 
        value = exp.evaluate(self.context)
        if (isinstance(value, (int, long, float)) and
            isinstance(self.ancestors[-1][0],XPath.ParsedPredicateList.ParsedPredicateList)):
            return self.STOP #== 0            
        elif isinstance(value, NodesetType):
            #todo handle nodeset, make sure not RxPath elements or all in the same position
            #otherwise can handle the parent node
            self.xpathExprs.append(exp) #we need to extract a key
            self.currentOpStack[-1].appendArg(ConstantOp(value)) 
            return 1
        else:
            self.currentOpStack[-1].appendArg(ConstantOp(value))
            return 1
    
    def _extractPathRemainder(self):
        #assuming the current node is a Step
        #extract an expression that starts with this step
        
        #unless this step is the first one it will always be the
        #_right field of a ParsedRelativeLocationPath
        
        exp = self.currentNode
        assert isinstance(exp, (XPath.ParsedStep.ParsedStep,
                               XPath.ParsedStep.ParsedAbbreviatedStep)), exp

        topMost = None
        for ancestor, field in self.getAncestors(reversed=1):
            if isinstance(ancestor, XPath.ParsedRelativeLocationPath.
                                         ParsedRelativeLocationPath):
                topMost = ancestor
            else:
                break

        if topMost:            
            #change exp to the ParsedRelativeLocationPath
            parent, field = self.ancestors[-1]
            if field == '_right':
                #todo: wrong? what if are steps has predicates that can't be handled?
                #construct a new ParsedRelativeLocationPath?

                #already handled by the SelectOp, so do nothing
                parent._left = XPath.ParsedStep.ParsedAbbreviatedStep(False)
            else:
                assert field == '_left'
            exp = topMost                        

        #analyze the rest of the expression for nested absolute paths
        subexpr = ReplaceRxPathSubExpr(self.context, exp,checkPos = False,explain=self.explain)        
        return subexpr.resultExpr
        
    def _step(self, axis):
        stop = False #whether or not to stop processing the expr

        selectOp = self.currentOpStack[-1]
        assert isinstance(selectOp, SelectOp)        
        pos = selectOp.finalPosition
        
        if axis == 'child':
            if pos < OBJ_POS:
                selectOp.finalPosition += 1
            else:
                #subQuery.op.xpathExp = exp #self.addJoin(exp)
                #self.currentPosition = 'subject'
                stop = True
        elif axis == 'parent':
            if pos > SUB_POS:
                if pos == OBJTYPE_POS:
                    selectOp.finalPosition = PRED_POS
                else:
                    selectOp.finalPosition -= 1
            else:                
                stop = True
        elif axis == 'attribute': 
            if pos == PRED_POS:
                selectOp.finalPosition = OBJTYPE_POS
            else:
                stop = True                
            #the only valid attribute for the other elements is "about",
            #which is the same as the string-value and so this is a no-op                
        elif axis != 'self':        
            stop = True

        if stop:
            exp = self._extractPathRemainder()
            self.currentOpStack[-1].xpathExp = exp
            self.xpathExprs.append( exp )
        return stop


#for associative ops: (a op b) op c := a op b op c 
def flattenOp(args, opType):        
    for a in args:        
        if isinstance(a, opType):
            for i in flattenOp(a.args, opType):
                yield i
        else:
            yield a

class SimpleTupleset(Tupleset):
    '''
    Interface for representing a set of tuples
    '''
    
    def __init__(self, generatorFuncOrSeq=(), hint=None,op=''):
        if not callable(generatorFuncOrSeq):
            #assume its a sequence
            self.generator = lambda: iter(generatorFuncOrSeq)
            self.seqSize = len(generatorFuncOrSeq)
            self.hint = hint or generatorFuncOrSeq
        else:
            self.generator = generatorFuncOrSeq
            self.seqSize = sys.maxint
            self.hint = hint #for debugging purposes
        self.op=op #for debugging
        self.cache = None

    def size(self):    
        return self.seqSize
        
    def filter(self, conditions=None):        
        '''Returns a iterator of the tuples in the set
           where conditions is a position:value mapping
        '''    
        #if self.cache is None:
        #    self.cache = list(self.generator())
        #for row in self.cache:
        for row in self.generator():
            if conditions:
                for pos, test in conditions.iteritems():
                    if row[pos] != test:
                        break #no match
                else:
                    yield row
            else:
                yield row

    def explain(self, out, indent=''):        
        print >>out, indent,'SimpleTupleset',hex(id(self)), 'for', self.op, 'with:'
        indent += ' '*4
        if isinstance(self.hint, Tupleset):            
            self.hint.explain(out,indent)
        else:
            print >>out, self.hint


class MutableTupleset(Tupleset):
    '''
    Interface for representing a set of tuples
    '''
    def __init__(self, seq=()):
        self._rows = [row for row in seq]
    
    def filter(self, conditions=None):        
        '''Returns a iterator of the tuples in the set
           where conditions is a position:value mapping
        '''                
        for row in self._rows:
            if conditions:
                for pos, test in conditions.iteritems():
                    if row[pos] != test:
                        break #no match
                else:
                    yield row
            else:
                yield row
    
    def size(self):
        return len(self._rows)

    def __contains__(self, row):
        return row in self._rows

    def update(self, rows):
        for row in rows:
#            if row not in self._rows: #todo!
                self._rows.append(row)        

    def append(self, row, *moreRows):
        assert not moreRows
        self._rows.append(row)
                 
def joinTuples(tableA, tableB, joinFunc):
    '''
    given two tuple sets and join function
    yield an iterator of the resulting rows
    '''
    lastRowA = None
    for rowA in tableA:
        for resultRow in joinFunc(rowA, tableB, lastRowA):            
            yield rowA, resultRow
        lastRowA = rowA, resultRow

def crossJoin(rowA,tableB,lastRowA):
    '''cross join'''
    for row in tableB:
        yield row
    
class Join(RxPath.Tupleset):
    '''
    Corresponds to an join of two tuplesets
    Can be a inner join or right outer join, depending on joinFunc
    '''
    def __init__(self, left, right, joinFunc=crossJoin, op=''):
        self.left = left
        self.right = right
        self.joinFunc = joinFunc

    def getJoinType(self):
        return self.joinFunc.__doc__

    def explain(self, out, indent=''):        
        print >>out, indent, 'Join',hex(id(self)),'with:',self.getJoinType()
        indent += ' '*4
        self.left.explain(out,indent)
        self.right.explain(out,indent)        
            
class IterationJoin(Join):
    '''
    Corresponds to an join of two tuplesets
    Can be a inner join or right outer join, depending on joinFunc
    '''
    def __init__(self, left, right, joinFunc=crossJoin, op=''):
        self.left = left
        self.right = right
        self.joinFunc = joinFunc
        
    def filter(self, conditions=None):
        for left, right in joinTuples(self.left, self.right, self.joinFunc):
            row = left + right
            if conditions:
                for key, value in conditions.iteritems():
                    if row[key] != value:
                        break
                else:
                    yield row
            else:
                yield row

    def left_inner(self):
        '''
        Returns iterator of the left inner rows
        '''
        def getInner():
            lastRowA = None
            for rowA in self.left:                
                for right in self.joinFunc(rowA,self.right,lastRowA):
                    #todo: if joinFunc is a right outer join,
                    #test that right isn't null                    
                    yield rowA
                    lastRowA = rowA, right
                    break;
                
        return SimpleTupleset(getInner, self, op='left_inner')

class MergeJoin(Join):
    '''
    Assuming the left and right tables are ordered by the columns 
    used by the join condition, do synchronized walk through of each table.
    '''
        
    def __init__(self, left, right, lpos, rpos, op=''):
        self.left = left
        self.right = right
        self.leftJoinSlice = lpos
        self.rightJoinSlice = rpos
        
    def _filter(self, conditions=None):
        li = iter(self.left)
        ri = iter(self.right)
        lpos = self.leftJoinSlice 
        rpos=self.rightJoinSlice
        
        l = li.next(); r = ri.next()
        while 1:        
            while l[lpos] < r[rpos]:
                l = li.next() 
            while r[rpos] < l[lpos]:
                r = ri.next()        
            if l[lpos] == r[rpos]:
                #inner join 
                if conditions:
                    row = l + r
                    for key, value in conditions.iteritems():
                        if row[key] != value:
                            break
                    else:
                        yield l, r
                else:
                    yield l, r
                l = li.next();
    
    def filter(self, conditions=None):
        for left, right in self._filter(conditions):
            yield left+right
            
    def left_inner(self):
        '''
        Returns iterator of the left inner rows
        '''
        def getInner():
            for left, right in self._filter():
                yield left

        return SimpleTupleset(getInner, self, op='MergeJoin.left_inner')

    def getJoinType(self):
        return 'ordered merge'

class ObsoleteJoin(Join):
    #todo remove
    '''
    Corresponds to an join of two tuplesets
    Can be a inner join or right outer join, depending on joinFunc
    '''
        
    def filter(self, conditions=None):
        keys = dict([(k[0],1) for k in self.right])
        
        if conditions and 0 in conditions:
            if conditions[0] not in keys:
                return
                
        for row in self.left.filter(conditions):
            joinkey = row[0]
            if joinkey in keys:
                yield row
    
        #if self.left.filter > len(keys)
        conditions = dict(conditions or {})
        
        for key in self.right:
            conditions[0]=key
            for row in self.left.filter(conditions):
                yield row
            
    def left_inner(self):
        '''
        Returns iterator of the left inner rows
        '''
        return self
        
    def getJoinType(self):
        return 'merge'
        
class Projection(RxPath.Tupleset):
    '''
    Corresponds to a nodeset with all nodes of the same type (position)
    '''
    #todo: not really a projection any more rename to GroupBy
    #todo?: need to adjust position for joins?    

    def __init__(self, tupleset, position, distinct=True,op=''):
        #todo: to support joins needs to be a more generalized tuple set
        self.tupleset = tupleset
        #todo: for more general query languages like XQuery or SPARQL,
        #needs to be a tuple of positions
        self.position = position
        if position == 0: #subject
            self.groupby_offset = 1
        else:
            self.groupby_offset = 5 #the whole statement        
        self.distinct=distinct
        self.op=op #for debugging

    def toStatements(self, context):
        if self.position == 0: 
            model = _findModel(self.tupleset)
            if model:
                return model
            
            def getRowsForSubjects():
                lastSubject = None
                for row in self:
                    #print 'subject', row
                    subject = row[0]
                    if subject != lastSubject:
                        lastSubject = subject
                        for stmt in context.initialModel.filter(
                            {0 : subject}):
                            yield stmt
                            
            return SimpleTupleset(getRowsForSubjects,self,op='PROJECT toStatements')
        else:
            return self.tupleset
        
    def filter(self, conditions=None):
        #if conditions:
        #    assert (len(conditions) <= self.position+1), conditions

        distinct = self.distinct
        last = None
        
        for row in self.tupleset:
            result = row[:self.groupby_offset]
            if distinct:                
                if result == last:
                    continue
                else:
                    last = result
                    
            if conditions:
                for key, value in conditions.iteritems():
                    if result[key] != value:
                        break
                else:
                    yield result
            else:
                yield result

    def size(self):
        return self.tupleset.size()

    def left_inner(self):
        return Projection(self.tupleset.left_inner(), self.position, op='left_inner of ' + self.op)

    def explain(self, out, indent=''):        
        print >>out, indent,'Projection', hex(id(self)), self.position, \
              self.distinct and 'DISTINCT' or '','for', self.op,'using:'
        indent += ' '*4
        self.tupleset.explain(out,indent)
    
class Union(RxPath.Tupleset):
    '''
    Corresponds to a nodeset containing nodes of different node types
    '''
    def __init__(self, projections=None,op=''):
        projections = projections or []
        self.tuplesets = projections #set of tuplesets
        self.op=op #for debugging
        #self.correlated = {} #correlated positions (columns) between projections
    
    def filter(self, conditions=None):
        for tupleset in self.tuplesets:
            for row in tupleset.filter(conditions):
                 yield row

    def toStatements(self, context):
        return Union([t.toStatements(context) for t in self.tuplesets],op='UNION toStatements')
        
    def explain(self, out, indent=''):        
        print >>out, indent, 'Union', hex(id(self)),'for', self.op, 'with:'
        indent += ' '*4
        for t in self.tuplesets:
            t.explain(out,indent)


class NodesetTupleset(RxPath.Tupleset):
    '''
    Presents a XPath nodeset as a tupleset
    Note: This is class is incomplete and pretty must only good
    for passing a nodeset through the query evaluation process
    and for testing whether it is empty or not.
    '''

    def __init__(self, nodeset, hintXPath=None, hintResultSet=None):
        self.nodeset = nodeset
        #for debugging purposes
        self.hintXPath =hintXPath
        self.hintResultSet = hintResultSet

    def filter(self, conditions=None):
        assert not conditions, 'filtering NodesetTupleset not yet supported'
        for node in self.nodeset:
            yield [node] 

    def toStatements(self, context):
        from rx import RxPathDom
        
        def getStatements():
            for node in self.nodeset:
                if isinstance(node, RxPathDom.Object):
                    node = node.parentNode #get predicate
                for stmt in node.getModelStatements():
                    yield stmt        
                                
        return SimpleTupleset(getStatements,self,op='NODESET toStatements')

    def explain(self, out, indent=''):
        print >>out, indent, 'NodesetTuple',repr(self.hintXPath),'using:'
        indent += ' '*4
        if self.hintResultSet:
            self.hintResultSet.explain(out,indent)
        else:
            print >>out, indent, 'None'
        
    def __contains__(self, row):
        if not self.nodeset or not row:
            return False
        
        if len(row) > 1:
            #convert row to a nodeset
            row = row2Node(self.nodeset[0].rootNode, row)
            if not row:
                return False        
            value =  [ row ]
        else:
            #row is just a single value
            value = row[0]
        return ParsedExpr._nodeset_compare(eq, value, self.nodeset)
    
    def __repr__(self):
        return repr(self.nodeset)

def _findModel(tupleset):
    if isinstance(tupleset, Union):
        tuplesets = tupleset.tuplesets
    else:
        tuplesets = (tupleset,)
    for tupleset in tuplesets:
        if isinstance(tupleset, Union):
            model = _findModel(tupleset)
            if model:
                return model
            continue
        
        while isinstance(tupleset, Projection):
            tupleset = tupleset.tupleset
        
        if isinstance(tupleset, RxPath.Model):
            return tupleset
                
    return None
    
def xpathEquality(left, right, op='eq'):
    '''equivalent to XPath equality semantics'''
    if (isinstance(left, NodesetTupleset) and 
       isinstance(right, NodesetTupleset)):
        #hacky optimiziation
        if op == 'eq':
            cmpfunc = eq
        else:
            cmpfunc = ne        
        return ParsedExpr._nodeset_compare(cmpfunc,left.nodeset,right.nodeset)
    elif isinstance(left,Tupleset) and isinstance(right,Tupleset):
        #if an item appears in both sets return True
        #(note: we've already took care of string value conversion)
        if left.size() > right.size():
            #swap
            tmp = left
            left = right
            right = tmp
        if op == 'eq':
            for row in left:
                if row in right:
                    return True
        else:
            for lrow in left:
                for rrow in right:
                    if lrow != rrow:
                        return True
        return False            
    elif isinstance(right,Tupleset):
        #swap
        tmp = left
        left = right
        right = tmp
    elif not isinstance(left,Tupleset):
        #neither is a Tupleset
        if op == 'eq':
            return right == left
        else:
            return right != left

    #now left is tupleset, right is a simple type
    if isinstance(right,(bool,BooleanType)):
        if right:
            return left.asBool()
        else:
            return not left.asBool()
    else:
        if op == 'eq':
            return [right] in left
        else: 
            assert op=='ne'
            for row in left:
                if [right] != row:
                    return True
            return False
                
class SimpleQueryEngine(object):

    def xpathExpCost(self, xpathExp, context):
        if not xpathExp:
            return 0
        else:
            return 1000 #todo: better analysis ;)

    def xpathEvaluate(self, exp, context, rows, pos):
        if pos > -1:            
            nodeset = filter(None, [row2Node(context.node.rootNode, row, pos)
                                                            for row in rows])
        else:
            nodeset = [context.node.rootNode]
        
        state = context.copy()
        size = len(nodeset)
        res = []        
        for pos in range(size):
            context.position, context.size = pos + 1, size                          
            context.node = nodeset[pos] 
            subRt = exp.evaluate(context)
            if res:
                assert isinstance(res, NodesetType)
                assert isinstance(subRt, NodesetType)
                res = res+subRt #RxPath.Set.Union(res,subRt) #todo: is Union necessary?  
            else:
                res = subRt#can be anytype
        context.set(state)
        return res

    def _matchesPredicates(self, op, args, context):
        '''
        evaluate the selectOp's predicates on the given row
        '''
        result = self._evalAnd(args, context)
        if op.finalPosition > -1:# and op.joinPosition < 0:
            result = Projection(result, op.finalPosition,op='Indep SelectOp')
            
        if not op.xpathExp:
            return result
        else:            
            assert isinstance(result, Tupleset)
            
            if context.explain:
                return NodesetTupleset([], op.xpathExp, result) 
            nodeset = self.xpathEvaluate(op.xpathExp, context.xpathContext,
                                                    result, op.finalPosition)
            assert isinstance(nodeset, NodesetType)
            return NodesetTupleset(nodeset,op.xpathExp) 
        
    def evalSelectOp(self, op, context):
        def getArgs():
            for i, preds in enumerate(op.predicates):
                for arg in flattenOp(preds, AndOp):
                     yield (arg.cost(self, context), i, arg)

        args = [x for x in getArgs()]

        if not args and not op.xpathExp:
            if op.finalPosition > -1:
                if op.joinPosition == 0: 
                    tupleset = context.currentTupleset
                else:
                    tupleset = context.currentTupleset
                return Projection(tupleset, op.finalPosition,op='NoOpSelectOp')
            else:
                return context.currentTupleset
        
        args.sort() #sort by cost
        #args.reverse()
        
        right = self._matchesPredicates(op, args, context)
 
        if op.joinPosition == 0:                          
            if _findModel(right):
                #everything matches
                return context.currentTupleset
            elif _findModel(context.currentTupleset) or _findModel(context.joinTupleset): 
                #current model is all the statements, so no need to join
                return Projection(right, 0,op='Subject SelectOp')
            else:
                 #todo: order issue if joinPos == object 
                lslice = slice( op.joinPosition, op.joinPosition+1)
                rslice = slice( 0, 1) #subject               
                return MergeJoin(context.joinTupleset, right, lslice,rslice)
        else:
            #either absolute or relative to the initial model, so join isn't necessary
            return right
                    
    def costSelectOp(self, op, context):
        args = list(flattenSeq(op.predicates))
        #like costAndOp:
        if args:                    
            total = reduce(operator.add, [a.cost(self, context) for a in args], 0.0)
            cost = total / len(args)
        else:
            cost = 1.0
        cost += self.xpathExpCost(op.xpathExp, context)
        if op.finalPosition == 1: #assume matching predicates are more expensive
            cost += 5
        if op.finalPosition == OBJTYPE_POS:
            cost += 10
        #if op.joinPosition < 0: #its absolute:
        #    cost /= 10          #independent thus cheaper?
        return cost 

    def _evalFuncOp(self, op, args, context):
        if op.xpathExp:
            if context.explain:
                if op.isIndependent():
                    return NodesetTupleset([], op.xpathExp)
                else:
                    return NodesetTupleset([], op.xpathExp, context.currentTupleset) 
            
            if op.isIndependent():
                #this isn't supported right now, but could be for absolute paths
                #and XPath functions that don't depend on the context node                
                result = op.xpathExp.evaluate(context.xpathContext)
            else:
                result = self.xpathEvaluate(op.xpathExp, context.xpathContext,
                                context.currentTupleset, context.currentPosition)
            if isinstance(result, NodesetType):
                return NodesetTupleset(result)
            else:
                return result
        else:
            return op.metadata.func(context, *args)
        
    def evalAnyFuncOp(self, op, context):
        if op.xpathExp:
            #if a xpathExp is set there will be no func or args, they are
            #contained in the XPath expression
            assert not op.metadata.func and not op.args

        def indepMap(arg):
            if arg.isIndependent():
                return arg.evaluate(self, context)
            else:
                return arg
        #evaluate and replace any independent args
        args = map(indepMap, op.args)
        
        if op.isIndependent():            
            #all args will be independent too
            return self._evalFuncOp(op, args, context)
        else:
            #evaluate for each row
            joinPos = context.currentPosition            
            def joinFunc(leftRow, rightTable, lastRow):
                '''Dependent evaluation of func'''
                if lastRow and leftRow[:joinPos+1] == lastRow[0][:joinPos+1]:
                    #optimization, assumes left rows are ordered
                    #if the dependent columns are the same don't bother re-calculating the value
                    #print 'anyfunc groupby', leftRow[:joinPos+1]
                    yield lastRow[1]

                jcontext = copy.copy( context )
                jcontext.currentTupleset = SimpleTupleset((leftRow,))
                jcontext.currentPosition = joinPos

                def depMap(arg):
                    if isinstance(arg, QueryOp): #dependent arg
                        return arg.evaluate(self, jcontext)
                    else:
                        return arg #independent, already calculated

                values = map(depMap, args)
                result = self._evalFuncOp(op, values, jcontext)
                if isinstance(result,Tupleset):
                    for resultRow in result:
                        yield resultRow
                else:
                    if result: #todo: hack: we can do this optimization
                        #because currently this will always be evaluated as bool
                        yield [result]
            
 #           if context.currentPosition == 0:
 #               current = Projection(context.currentTupleset, 0,op='AnyFunc')
 #           else:
 #               current = context.currentTupleset 
 #           return IterationJoin(current, SimpleTupleset(op="AnyFunc: "+ repr(op)), joinFunc)
            return IterationJoin(context.currentTupleset.toStatements(context), SimpleTupleset(op="AnyFunc: "+ repr(op)), joinFunc)
         
    def costAnyFuncOp(self, op, context):        
        if op.metadata.costFunc:
            cost = op.metadata.costFunc(self, context)        
            if not op.isIndependent():
                return cost * 50 #dependent is much more expensive
            else:
                return cost
        else:
            return self.xpathExpCost(op.xpathExp, context)

    def evaluateToBoolean(self, op, context):        
        result = op.evaluate(self, context)
        if isinstance(result, Tupleset):            
            if op.isIndependent():
                return result.asBool()
            else:
                #we assume dependent ops return a join,
                #and that the left side will be original tupleset
                #left_inner will return the rows that match
                return result.left_inner() #todo
        else:
            return result
                    
    def evalAndOp(self, op, context):
        assert not op.xpathExp
        #first flatten nested ands
        #then sort by cost and evaluate in that order        
        args = [(a.cost(self, context), -1, a) for x in flattenOp(op.args, AndOp)]
        args.sort()
        return self._evalAnd(args, context)
    
    def _evalAnd(self, args, context):
        context = copy.copy(context)        
        for cost, pos, arg in args:
            if pos > -1:
                context.currentPosition = pos

            result = self.evaluateToBoolean(arg, context)
            
            if isinstance(result, Tupleset):
                context.currentTupleset = result
            else:
                if not result:
                    return SimpleTupleset(op='evalAndEmpty') #nothing matches 

        return context.currentTupleset           

    def costAndOp(self, op, context):
        #minCost = min([a.cost(self, context) for a in op.args])
        #figure out the average cost
        if not op.args:
            return 0.0
        total = reduce(operator.add, [a.cost(self, context) for a in op.args], 0.0)
        return total / len(op.args)

    def evalOrOp(self, op, context):
        assert not op.xpathExp

        args = [(a.cost(self, context), a) for x in flattenOp(op.args, OrOp)]
        args.sort()
        
        resultSoFar = Union(op='OrOp') #MutableTupleset()
        startTupleset = context.currentTupleset
        context = copy.copy( context )

        for cost, arg in args:            
            result = self.evaluateToBoolean(arg, context)
            if isinstance(result, Tupleset):
                if result is startTupleset:                    
                    return startTupleset #all rows matched
                #we only want to examine rows that haven't already been marked as true
                #is this worth it? big win when all match but probably not most of the time
                #context.currentTupleset = context.currentTupleset.difference(result)
                #if not context.currentTupleset.size(): 
                #    return startTupleset #nothing left so every row matched
                resultSoFar.tuplesets.append(result)
                #resultSoFar.update( result )
            else:
                if result:
                    return startTupleset #everything matches
        return resultSoFar
    
    def costOrOp(self, op, context):
        return reduce(operator.add, [a.cost(self, context) for a in op.args], 0.0)

    def evalInOp(self, op, context):        
        assert not op.xpathExp

        left = op.args[0]
        args = op.args[1:]

        if left.isIndependent():
            leftValue = left.evaluate(self, context)
        else:
            leftValue = None

        resultSoFar = Union(op='InOp') #MutableTupleset()
        startTupleset = context.currentTupleset
        #print 'inop source', list(context.currentTupleset)
        context = copy.copy( context )

        for arg in args:
            if arg.isIndependent():
                rightValue = arg.evaluate(self, context)
            else:
                rightValue = None
            result = self._evalEq(left, arg, context, leftValue, rightValue)
            if isinstance(result, Tupleset):
                if result is startTupleset:                    
                    return startTupleset #all rows matched
                #we only want to examine rows that haven't already been marked as true
                #todo: is this worth it? yes when all match
                #is this worth it? big win when all match but probably not most of the time
                #context.currentTupleset = context.currentTupleset.difference(result)
                #if not len(context.currentTupleset): #todo
                #    return startTupleset #nothing left so every row matched
                resultSoFar.tuplesets.append(result)
                #resultSoFar.update( result )
            else:
                if result:
                    return startTupleset #everything matches
        #print 'resultSoFar', list(resultSoFar)
        return resultSoFar

    def costInOp(self, op, context):
        return reduce(operator.add, [a.cost(self, context) for a in op.args], 0.0)

    def evalEqOp(self, op, context):        
        assert not op.xpathExp
        assert len(op.args) == 2
        left, right = op.args
        leftValue = rightValue = None
        if left.isIndependent():
            leftValue = left.evaluate(self, context)                    
        if right.isIndependent():
            rightValue = right.evaluate(self, context)        
        return self._evalEq(left, right, context, leftValue, rightValue, op.op)

    def _selectWithValue(self, context, selectop, value):
        #optimization:
        #if we know the selectop's final position and
        #the other side is a simple value we can filter by that value
        #before evaluating the selectop
        assert selectop.joinPosition > -1
        
        context = copy.copy( context )
        if selectop.joinPosition < 1: #for 0 (join on subject) or -1 (absolute, no join)
            context.joinTupleset =  context.currentTupleset
            tupleset = context.initialModel.toStatements(context) 
        else: #no join -1 (absolute) or pred or obj
            tupleset = context.currentTupleset.toStatements(context)
        
        context.currentTupleset = SimpleTupleset(
                    lambda: tupleset.filter(
                    #todo: modelContext?
                    {selectop.finalPosition : value}), tupleset,
                    op='selectWithValue '+ value)
            
        return selectop.evaluate(self, context)

        #if the current tupleset isn't the model, do a mergejoin to avoid 
        #filtering linearly 
        #this is only a win if the current tupleset is large and most rows don't match
        #compareSlice = slice(selectop.finalPosition, selectop.finalPosition+1)
        #context.joinTupleset = MergeJoin(tupleset, 
        #        SimpleTupleset(lambda: context.initialModel.filter(
        #            #todo: modelContext?
        #            {selectop.finalPosition : value}), context.initialModel,
        #            op='selectWithValue '+ value),
        #        compareSlice, compareSlice)
        #return selectop.evaluate(self, context) #will return a Projection of a Join
    
    def _evalEq(self, left, right, context, leftValue, rightValue, op='eq'):
        if leftValue is None or rightValue is None:
            #one or both are dependent: return a Tupleset
            
            #first, try to optimize:
            if op == 'eq':
                if isinstance(left, SelectOp):
                    if left.getPosition() > -1 and (rightValue is not None
                                        and not isinstance(rightValue, Tupleset)):
                        return self._selectWithValue(context, left, rightValue)
                elif isinstance(right, SelectOp):                
                    if right.getPosition() > -1 and (leftValue is not None
                                        and not isinstance(leftValue, Tupleset)):
                        return self._selectWithValue(context, right, leftValue)
            
            context = copy.copy( context )        
            def joinFunc(leftRow, rightTable,lastLeftRow):
                '''Dependent EqOp join'''
                
                jcontext = copy.copy( context )
                jcontext.currentTupleset = SimpleTupleset((leftRow,),op='eqJoinFunc')

            #def compareFunc():
            #    '''Dependent EqOp'''
                
                if leftValue is None:
                    jleftValue = left.evaluate(self, jcontext)
                else:
                    jleftValue = leftValue
                
                if rightValue is None:
                    jrightValue = right.evaluate(self, jcontext)
                else:
                    jrightValue = rightValue

                result = xpathEquality(jleftValue, jrightValue, op)
                if result:
                    yield [result]
            
            #return SimpleTupleset(compareFunc, op='EqOp')
            
            #if not isinstance(leftValue, Tupleset):
            #    leftValue = SimpleTupleset((leftValue,) )
            
            #joinFunc(): leftRow, rightTable
                
            #    result = xpathEquality(jleftValue, jrightValue, op)
            #    if result:
            #        yield [result]
                        
            return IterationJoin(context.currentTupleset, 
                    SimpleTupleset(hint=right, op='EqOp'+repr(left)), joinFunc)
        else: #both are independent
            return xpathEquality(leftValue, rightValue, op)
                                    
    def costEqOp(self, op, context):
        assert len(op.args) == 2        
        return op.args[0].cost(self, context) + op.args[1].cost(self, context)
    
    def evalConstantOp(self, op, context):
        assert not op.xpathExp
        return op.value

    def costConstantOp(self, op, context):
        return 0.0
        

