'''
 jql query engine, including an implementation of RDF Schema.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    

jql query engine

Given an jql expression and a context, execute the following steps:

3.  translates the jql object into a simple abstract
syntax tree (AST) that represents the query in terms of a minimal set
of relational algebra operations that are applied to
a set of triples that represent the statements in the model.

The following operations are defined:
predicate operations that operate on values and return boolean

* and, or, not, eq, in, compare

tupleset operations that take a tupleset and return a tupleset

Filter

resource set operations that take a tupleset and return a resource set:

* Join 
* Union
* Intersect

operations that take a resource set and return a tupleset:

Project 

other:

Construct: 

Join(on,  #only support equijoin on one "column", e.g. subject or predicate
  args) #args -- input tables: ops that evaluate to tuplesets (or resourcesets)
  #evaluates to resource set
Union(args) #args return resource set #
Filter(sp=None, pp=None, op=None) #takes predicate ops that take a value return a bool, evaluates to a tupleset
Construct(pattern, where=None) pattern is a list or dict whose values are either construct, dependent variable reference, or project; 'where' is an op that returns a tupletset
DependentVariable References: tupleset variables are resolved by looking for cells labeled on the current tupleset

Project takes resource set and finds matching properties. This input tupleset
usually specified by 'id'.
To support query engines that can do more efficient we also annotate
the corresponding resource set op with the requested projections.

Example:
{*}
=>
construct({
 * : project('*') //find all props
},

Example: 
{ * where(type=bar, foo=*) }
=>
construct({
 * : project('*') //find all props
},
join(SUBJECT as subject, 
    filter(?subject, 'type', 'bar'), 
        filter(?subject, 'foo')),
)

Example: 
{ * where(type=bar or foo=*) }
=>
construct({
 * : filter(?subject) //find all props
},
union(filter(?subject, 'type', 'bar'), 
       filter(?subject, 'foo')),
    )
)

Example:
{
id : ?parent,
derivedprop : prop(a)/prop(b), 
children : {                
    id : ?child,
    *
    where({ 
       child = ?child,
       parent= ?parent
    })
  }
  
where (cost > 3) 
}

=>


construct({
id : var('parent'), 
derivedprop : NumberFunOp('/', project('a')/project('b')),
children : construct({
        id : var('child'),
        * : project(*) //find all props
    }, //using:
    join(      
      filter(None, eq('child'), None, objlabel='child'),
      filter(None, eq('parent'), objlabel='parent')
    )
  )
}, filter(None, eq('cost'), gt(3))

cost-base query rewriter could rewrite this to the equivalent query:

{
id : ?parent,
derivedprop : prop(a)/prop(b), 
children : {                
    id : ?child,
    *
    where({ //joinop instead of constructop when inside a where
       child = ?child,
       parent= { id : ?parent
            where (cost>3) 
         }
    })
  }
}

construct({
id : Label('parent'),
derivedprop : NumberFunOp('/', project('a')/project('b')),
children : construct({
        id : LabelOp('child'),
        * : project(*) //find all props
    }, join(SUBJECT,
          filter(None, eq('child'), None, objlabel='child'),
          filter(None, eq('parent'), //see below
               join(SUBJECT,
                    filter(None, eq('cost'), gt(3)),
                    subjectlabel='parent')
          )
   )
});

where the "see below" filter is rewritten:
join( (OBJECT, SUBJECT),
    filter(None, eq('parent'), None, objectlabel='parent'),
    filter(None, eq('cost'), gt(3))
)


execution order:

build op tree and context
  var list built by asociating with parent join
execute tree:
 root op: construct
   resolves id for start model
     looks up var ref
        execute child join return resourceset
   execute where op with start model
   for each row build result list
      for each key in construct
         derivedprop : execute op with current row
         children : execute construct with current row
            child var should be in resourceset row
              project

what about:
{
id : ?parent,
children : {
    id : ?child,
    where({
      foo = 'bar'
      where({
       child = ?child,
       parent= ?parent
      })
    )
  }
}
what does ?parent resolve to? just the inner join but filter 'children' list
or the more restrictive outer join. The latter is more intuitive but the former
interpretation is more expressive. for now, whichever is easiest to implement.

what about distributive construction? -- e.g. copy all the properties of a subquery
into the parent. Could do this by allowing variables in property positions?

project(parent.a)
project(parent.b)
 project(child.*)
  join  => resource : { child : [], parent : [] } 
    filter(child)
    filter(parent)
filter(cost)

assuming simple mapping to tables, sql would look like:

select t1.id, t2.a/t2.b as derivedprop, t2.* from t1, t2, rel 
where (rel.child = t2.id and rel.parent = t1.id) and cost > 3

direct ops translation:

select parent as id, t2.* from t2 join (select child, parent from rel) r on t2.id = r.child

if t1 properties were requested:

select t1.*, t2.* from t2 join (select child, parent from rel) r on (t2.id = r.child) join t1 on (t1.id = r.parent) where t1.cost > 3

Example: 
{child : *} //implies { child : * where(child=*) }
//semantically same as above since there's no need for relationship table
construct({ child : ?obj }, filter(?subject, 'child', ?obj))

'''

from __future__ import generators
from rx import utils, RxPath
from rx.RxPath import Tupleset, EMPTY_NAMESPACE
from utils import flattenSeq, GeneratorType

import operator, copy, sys

SUBJECT = 0
OBJECT = 3

def runQuery(query):
    ast = BuildAST(query)
    astRoot = ast.currentOpStack[0]
    #see evaluateQuery():
    queryContext = QueryContext(context, doc.model) 
    result = astRoot.evaluate(SimpleQueryEngine(),queryContext)
    for row in result:
        yield row #row is list of joined statements

def buildAst(query, context=None):
    if not context:
        context = ConstructOp()
    if isinstance(query, dict):
        for key, value in query.items():
            if isinstance(key, where):
                pass
            elif key == '*':
                pass
            elif key == 'id':
                pass
            else:
                pass #prop
    return context

def evalAst(op, model, bindvars=()):
    pass

class QueryException(Exception): pass

class QueryContext(object):
 
    def __init__(self, initModel, ast, explain=False, vars=None):
        self.initialModel = initModel
        self.currentTupleset = initModel        
        self.explain=explain
        self.ast = ast
        if ast is None:
            self.vars = self._findVars(ast)
        else:
            self.vars = vars

    def __copy__(self):
        copy = QueryContext(self.initialModel, self.ast, self.explain, self.vars)
        copy.currentTupleset = self.currentTupleset
        return copy

    def _findVars(self, ast):
        #nope!!!
        for op in ast:
            if isinstance(op, FilterOp):
                for position, name in op.labels.items():
                    assert op.getType() == ResourceSet
                    self.vars[name] = VarOp(op.parent, position)


#############################################################
########################   AST   ############################
#############################################################

#define the AST syntax using Zephyr Abstract Syntax Definition Language.
#(see http://www.cs.princeton.edu/~danwang/Papers/dsl97/dsl97-abstract.html)
#If the AST gets more complicated we could write a code generator using
#http://svn.python.org/view/python/trunk/Parser/asdl.py

syntax = '''
-- Zephyr ASDL's five builtin types are identifier, int, string, object, bool

module RxPathQuery
{
    exp =  boolexp | AnyFunc(exp*) | Query(subquery)
            
    subquery = Filter(subquery input?, boolexp* subject,
                    boolexp* predicate, boolexp* object) |
               Join(subquery left, subquery right) | 
               Project(subquery input, column id)  |
               Union(subquery left, subquery right)

    boolexp = BoolFunc(exp*) 
    -- nodesetfunc, eqfunc, orfunc, andfunc
}
'''

BooleanType = bool
ObjectType = object
NumberType = float
StringType = unicode

class ResourceSet(Tupleset):
    '''
    (resource uri, {varname : [values+]}),*
    or maybe: tuples, collabels = []
    '''

QueryOpTypes = ( Tupleset, ResourceSet, ObjectType, StringType, NumberType, BooleanType )
NullType = None

class QueryOp(object):
    '''
    Base class for the AST.
    '''        
    #maybe this should derive from rx.DomTree to enable
    #XPath expressions to be used for query rewriting 

    parent = None
    args = ()
    labels = ()

    @classmethod
    def _costMethodName(cls):
        return 'cost'+ cls.__name__

    @classmethod
    def _evalMethodName(cls):
        return 'eval'+ cls.__name__

    def getType(self):
        return ObjectType

    def isIndependent(self):
        for a in self.args:
            if not a.isIndependent():
                return False
        return True

    def cost(self, engine, context):
        return getattr(engine, self._costMethodName())(self, context)

    def evaluate(self, engine, context):
        '''
        Given a context with a sourceModel, evaluate either modified
        the context's resultModel or returns a value to be used by a
        parent QueryOp's evaluate()
        '''
        return getattr(engine, self._evalMethodName())(self, context)

    def __repr__(self):
        return self.__class__.__name__
    
    def _bydepth(self,level=0):
        for a in self.args:
            for descend, lvl in a.depth(level+1):
                yield descend, lvl
        yield self, level

    def _deepest(self, deepest):
        return [i[0] for i in
                    sorted(self._bydepth(), key=lambda k:k[1], reverse=deepest)]

    def deepestfirst(self):
        '''
        return descendants by ordered by rank, deepest-first
        '''
        return self._deepest(True)

    def deepestlast(self):
        '''
        return descendants by ordered by rank, deepest-last
        '''
        return self._deepest(False)

    def appendArg(self, arg):
        self.args.append(arg)
        arg.parent = self

class ResourceSetOp(QueryOp):
    '''
    These operations take one or more tuplesets and return a resource set.
    '''
    
    def __init__(self, *args, **kw):
        '''

        keywords:
        join: tuple
        
        '''
        self.args = []
        self.positions = []
        for a in args:
            self.appendArg(a)

    def appendArg(self, op, pos=SUBJECT):
        if isinstance(filter, FilterOp):
            assert pos in (SUBJECT,OBJECT)
            self.positions.append(pos)
        elif isinstance(rsOp, ResourceSetOp):
            self.positions.append(None)
        else:
            raise QueryException('bad ast')        
        QueryOp.appendArg(self, filter)

    def getType(self):
        return Resourceset

class JoinOp(ResourceSetOp):
    '''
    handles "and"
    '''

class UnionOp(ResourceSetOp):
    '''
    handles "or"
    '''

class IntersectOp(ResourceSetOp):
    '''
    handles 'not'
    '''

class ConstructOp(QueryOp):
    '''
    '''
    def __init__(self, pattern, where):
        self.pattern = pattern
        self.where = where

    args = property(lambda self: self.pattern.values()+self.where)


class FilterOp(QueryOp):
    '''
    Filters rows out of a tupleset based on predicate
    '''    
    
    def __init__(self, sub=None, pred=None, obj=None,
                 subjectlabel=None, propertylabel=None,objectlabel=None):
        
        self.predicates = [sub, pred, obj]
        self.labels = list(QueryOp.labels)
        for k in kw:
            if k == 'subjectlabel':
                self.labels[SUBJECT] = kw[k]
            if k == 'objectlabel':
                self.labels[OBJECT] = kw[k]

    def getType(self):
        return Tupleset

    def __repr__(self):
         args = ', '.join([repr(a) for a in flattenSeq(self.predicates)])
         pos = 'select ' + str(self.finalPosition) + ' from ' + str(self.joinPosition)
         return pos + ' where(' + args + ')'
         
    args = property(lambda self: flattenSeq(self.predicates))
        
    def appendArg(self, arg, pos):
        self.predicates[pos] = arg

class LabelOp(QueryOp):

    def __init__(self, name):
        self.name = name

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
                value = bool(value)
        self.value = value

    def getType(self):
        if isinstance(self.value, QueryOpTypes):
            return type(self.value)
        else:
            return ObjectType

    def __repr__(self):
        return repr(self.value)

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

    def __repr__(self):
        if self.name:
            name = self.name[1]
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
    
    def __init__(self, left=None, right=None):
        self.args = []
        if left:
            assert right
            self.appendArgs(left)
            self.appendArgs(right)

    def getType(self):
        return BooleanType

class AndOp(BooleanOp):

    def __repr__(self):
        if not self.args:
            return ''
        elif len(self.args) > 1:
            return ' and '.join( [repr(a) for a in self.args] )
        else:
            return repr(self.args[0])

class OrOp(BooleanOp):
    def __repr__(self):
        return 'or:' + self.args and ' or '.join( [repr(a) for a in self.args] )

class InOp(BooleanOp):
    '''Like OrOp + EqOp but the first argument is only evaluated once'''
    
    def __repr__(self):
        rep = repr(self.args[0]) + ' in (' 
        return rep + ','.join([repr(a) for a in self.args[1:] ]) + ')'

class EqOp(BooleanOp):

    def __init__(self, op='eq'):
        self.args = []
        self.op = op
        
    def __repr__(self):
        op = self.op == 'eq' and ' = ' or ' != '
        return '(' + op.join( [repr(a) for a in self.args] ) + ')'

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

#for associative ops: (a op b) op c := a op b op c 
def flattenOp(args, opType):        
    for a in args:        
        if isinstance(a, opType):
            for i in flattenOp(a.args, opType):
                yield i
        else:
            yield a

#############################################################
#################### QueryPlan ##############################
#############################################################

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
            assert len(result) == self.groupby_offset, '%s should be %s in %s' %(
                                len(result),self.groupby_offset, self.tupleset)
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

#############################################################
################ Evaluation Engine ##########################
#############################################################

class PropShape(object):
    omit = 'omit' #when MAYBE()
    usenull= 'usenull'
    uselist = 'uselist' #when [] specified
    nolist = 'nolist'

class ConstructProp(object):

   def __init__(self, name, ifEmpty=PropShape.usenull, ifSingle=PropShape.nolist):
       self.name = name,
       self.shape = shape
       assert ifEmpty in (PropShape.omit, PropShape.usenull, PropShape.uselist)
       self.ifEmpty = ifEmpty
       assert ifSingle in (PropShape.nolist, PropShape.uselist)
       self.ifSingle = ifSingle

class SimpleQueryEngine(object):

    def evalConstructOp(self, op, context):
        '''
        Evaluate operation and then return a generator that yields
        '''
        #top-level construct has a resourceset op and a pattern that contains
        #projectops (or derived expressions)...
        #eval the op and then walk thru each row
        #output a result object by applying the expressions

        idpattern = op.pattern.get('id')
        if idpattern:
            varref = idpattern.findRef()
            if varref:
                context.currentTupleset = varref.execute(self, context)

        resourceset = op.where.evaluate(self, context)
        pattern = {}
        assert isinstance(op.pattern, dict) #XXX support list pattherns
        for k, v in op.pattern.items():
            if k.name == 'id':
                continue
            pattern[k] = v.evaluate(self, context)

        def resultFunc(offset=-1, limit=-1):
            for r in resourceset:
                res['id'] = r[0]                
                for k, v in pattern.items():
                    res[k.name] = v #v is a generator, needs resource context
                yield res
        
        return resultFunc(op.offset, op.limit) #XXX
            
    def evalJoinOp(self, op, context):
        def getArgs():
            for i, preds in enumerate(op.predicates):
                for arg in flattenOp(preds, AndOp):
                     yield (arg.cost(self, context), i, arg)

        args = [x for x in getArgs()]        
        if not args:
            return context.currentTupleset
        
        args.sort() #sort by cost

        #either an empty tupleset or it set and returns currentTupleset
        #if the args is dependent, e.g. a filter 
        right = self._evalAnd(args, context)
            
        if _findModel(right):
            #'everything matches'
            return context.currentTupleset
        elif _findModel(context.currentTupleset) or _findModel(context.joinTupleset): 
            #current model is all the statements, so no need to join
            return Projection(right, 0,op='Subject SelectOp')
        else:
            #XXX assume Tuplse set is ordered correctly
             #todo: order issue if joinPos == object 
            lslice = slice( op.joinPosition, op.joinPosition+1)
            rslice = slice( 0, 1) #subject
            return MergeJoin(context.joinTupleset, right, lslice,rslice)
                    
    def costJointOp(self, op, context):
        args = list(flattenSeq(op.predicates))
        #like costAndOp:
        if args:                    
            total = reduce(operator.add, [a.cost(self, context) for a in args], 0.0)
            cost = total / len(args)
        else:
            cost = 1.0
        if op.finalPosition == 1: #assume matching predicates are more expensive
            cost += 5
        if op.finalPosition == OBJTYPE_POS:
            cost += 10
        #if op.joinPosition < 0: #its absolute:
        #    cost /= 10          #independent thus cheaper?
        return cost 

    def _evalFuncOp(self, op, args, context):
        return op.metadata.func(context, *args)
        
    def evalAnyFuncOp(self, op, context):
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
                result = self._evalFuncOp(op, values, jcontext) #XXX
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

                result = xpathEquality(jleftValue, jrightValue, op) #XXX
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
            return xpathEquality(leftValue, rightValue, op) #XXX
                                    
    def costEqOp(self, op, context):
        assert len(op.args) == 2        
        return op.args[0].cost(self, context) + op.args[1].cost(self, context)
    
    def evalConstantOp(self, op, context):
        assert not op.xpathExp
        return op.value

    def costConstantOp(self, op, context):
        return 0.0
        

