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
       parent = { id = ?parent,
             cost>3
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
import jqlAST

from rx import utils, RxPath
from rx.utils import flattenSeq, flatten
import operator, copy, sys, pprint, itertools
from ng import jqlAST, jqlparse
from ng import *

def runQuery(query, model):
    ast = buildAST(query)
    return evalAST(ast, model)

def buildAST(query):
    return jqlparse.parse(query)

def rewriteAST(ast):
    if not isinstance(ast, jqlAST.Select):
        return
    op = ast
    #create a mapping of join conditions' join "column" to the join op
    #use this to add labels if the projections are being selected
    joins = {}
    where = op.where
    if not where:
        where = Join()
    for child in where.breadthfirst():
        if isinstance(child, jqlAST.JoinConditionOp) and not isinstance(
                                                    child.position, int):
            assert isinstance(child.parent, jqlAST.Join)
            joins[child.position] = child.parent

    currentConstruct = op.construct
    #look through each Project op referenced by the construct
    #and see if there's a corresponding filter for the Project op
    #if there is add a label so that the column is preserved
    #if there isn't, add an outer join so the column is retrieved if present

    #print 'children', len(list(op.construct.depthfirst() ))
    for child in op.construct.depthfirst():
        if isinstance(child, jqlAST.Construct):
            currentConstruct = child
        elif isinstance(child, jqlAST.Project) and not child.join:
            #find the join the Project will be associated with
            #(skip if join already set by parser)
            if currentConstruct.id.getLabel():
                join = joins.get(currentConstruct.id.getLabel())
            else:                
                join = where
            if join:
                child.join = join
                if child.name != '*':
                    #check for matching filter already be defined
                    test = jqlAST.Eq(child.name, jqlAST.Project(PROPERTY))
                    found = False
                    for arg in join.args:
                        assert(isinstance(arg, jqlAST.JoinConditionOp))
                        if not isinstance(arg.op, jqlAST.Filter):
                            continue
                        #XXX predicates
                        if test in arg.op.args:
                            arg.op.addLabel(child.name, OBJECT)
                            found = True
                    if found:
                        continue
                    filter = jqlAST.Filter(test,objectlabel=child.name)
                    #set as outer join #XXX outer join seems broken
                    join.appendArg(
                        jqlAST.JoinConditionOp(filter, SUBJECT,
                                    jqlAST.JoinConditionOp.RIGHTOUTER) )
                else:
                    pass #XXX if '*' preserve object column on all filters
            else:
                pass #XXX need to construct a join

def evalAST(ast, model, bindvars=(), explain=None, debug=False):
    #rewriteAST(ast)
    queryContext = QueryContext(model, ast, explain, debug)
    result = ast.evaluate(SimpleQueryEngine(),queryContext)
    if explain:
        result.explain(explain)
    for row in result:
        yield row #row is list of joined statements

class QueryContext(object):
    currentRow = None
    currentValue = None
    
    def __init__(self, initModel, ast, explain=False, debug=False, vars=None):
        self.initialModel = initModel
        self.currentTupleset = initModel        
        self.explain=explain
        self.ast = ast
        self.vars = vars
        self.debug=debug

    def __copy__(self):
        copy = QueryContext(self.initialModel, self.ast, self.explain, 
                                                        self.debug, self.vars)
        copy.currentTupleset = self.currentTupleset
        copy.currentValue = self.currentValue
        copy.currentRow = self.currentRow
        return copy

    def __repr__(self):
        return 'QueryContext' + repr([repr(r) for r in ['model',
            self.initialModel,'tupleset', self.currentTupleset, 'row',
                self.currentRow, 'value', self.currentValue]])


#############################################################
#################### QueryPlan ##############################
#############################################################
def _colrepr(self):
    colstr =''
    if self.columns:
        def x(c):
            s = c.label
            if isinstance(c.type, Tupleset):
                s += '('+','.join( map(x,c.type.columns) ) +')'
            return s
        colstr = ','.join( map(x,self.columns) )
    return '('+colstr+')'

def _reordercols(cols):
    for i, c in enumerate(cols):
        c.pos = i
    return cols

def validateRowShape(columns, row):
    if columns is None:
        return
    assert isinstance(row, (tuple,list)), row
    assert len(columns) == len(row), '(c %d:%s, r %d:%s)'%(len(columns), columns,  len(row), row)
    for (ci, ri) in itertools.izip(columns, row):
        if isinstance(ci.type, Tupleset):
            assert isinstance(ri, Tupleset), '%s %s' % (ri, ci.type)
            if ri:
                #validate the first row of the tupleset
                return validateRowShape(ci.type.columns, ri[0])
        else:
            assert not isinstance(ri, Tupleset), ri

class SimpleTupleset(Tupleset):
    '''
    Interface for representing a set of tuples
    '''
    
    def __init__(self, generatorFuncOrSeq=(),hint=None, op='',
                                columns=None, debug=False, colmap=None):
        if not callable(generatorFuncOrSeq):
            #assume its a sequence
            self.generator = lambda: iter(generatorFuncOrSeq)
            self.seqSize = len(generatorFuncOrSeq)
            self.hint = hint or generatorFuncOrSeq
        else:
            self.generator = generatorFuncOrSeq
            self.seqSize = sys.maxint
            self.hint = hint #for debugging purposes
        self.op=op #msg for debugging
        self.debug = debug #for even more debugging
        self.cache = None
        self.columns = columns
        self.colmap = colmap
        if debug:
            self._filter = self.filter
            self.filter = self._debugFilter

    def _debugFilter(self, conditions=None, hints=None):
        results = tuple(self._filter(conditions, hints))        
        print self.__class__.__name__,hex(id(self)), '('+self.op+')', \
          'on', self.hint, 'cols', _colrepr(self), 'filter:', repr(conditions),\
          'results:'
        pprint.pprint(results)
        [validateRowShape(self.columns, r) for r in results]
        for row in results:
            yield row

    def size(self):    
        return self.seqSize
        
    def filter(self, conditions=None, hints=None):
        '''Returns a iterator of the tuples in the set
           where conditions is a position:value mapping
        '''
        if hints and 'makeindex' in hints:
            makecache = hints['makeindex']
        else:
            makecache = None

        if self.cache is not None and makecache == self.cachekey:
            for row in self.cache.get(conditions[makecache], ()):
                yield row
            return
        elif makecache is not None:
            cache = {}           

        if 0:#self.debug:
            rows = list(self.generator())
            print 'SimpleTupleset',hex(id(self)), '('+self.op+')', \
                            '(before filter) on', self.hint, 'results', rows
        else:
            rows = self.generator()

        colmap = self.colmap
        for row in rows:
            if makecache is not None:
                key =row[makecache]
                cache.setdefault(key,[]).append(row)

            match = row
            if conditions:
                for pos, test in conditions.iteritems():
                    if row[pos] != test:
                        match = None
                        break #no match

            if match is not None:
                if colmap:
                    row = tuple(colmap(row))
                yield row

        #only set the cache for future use until after we've iterated through
        #all the rows
        if makecache is not None:
            self.cache = cache
            self.cachekey = makecache

    def __repr__(self):
        return 'SimpleTupleset ' + hex(id(self)) + ' for ' + self.op

    def explain(self, out, indent=''):
        print >>out, indent, repr(self), _colrepr(self),'with:'
        indent += ' '*4
        if isinstance(self.hint, Tupleset):            
            self.hint.explain(out,indent)
        else:
            print >>out, self.hint


class MutableTupleset(list, Tupleset):
    '''
    Interface for representing a set of tuples
    '''
    columns = None

    def __init__(self, columns=None, seq=(), reorder=True):
        if columns is not None:
            if reorder :
                self.columns = [ColumnInfo(i, c.label, c.type)
                                    for (i, c) in enumerate(columns)]
            else:
                self.columns = columns
        return list.__init__(self, [row for row in seq])
    
    def filter(self, conditions=None, hints=None):
        '''Returns a iterator of the tuples in the set
           where conditions is a position:value mapping
        '''                
        for row in self:
            if conditions:
                for pos, test in conditions.iteritems():
                    if row[pos] != test:
                        break #no match
                else:
                    yield row
            else:
                yield row
    
    def size(self):
        return len(self)
    
    def __repr__(self):
        if self.columns:
            return 'MutableTupleset'+repr(self.columns)
        else:
            return 'MutableTupleset'+ list.__repr__(self)
                 
def joinTuples(tableA, tableB, joinFunc):
    '''
    given two tuple sets and join function
    yield an iterator of the resulting rows
    '''
    lastRowA = None
    for rowA in tableA:
        for resultRow in joinFunc(rowA, tableB, lastRowA):
            if resultRow is not None:
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
    def __init__(self, left, right, joinFunc=crossJoin, columns=None,
                                                    msg='', debug=False):
        self.left = left
        self.right = right
        self.joinFunc = joinFunc
        self.columns = columns
        self.msg = msg
        self.debug = debug
        if debug:
            self._filter = self.filter
            self.filter = self._debugFilter

    def _debugFilter(self, conditions=None, hints=None):
        results = tuple(self._filter(conditions, hints))        
        print self.__class__.__name__,hex(id(self)), '('+self.msg+')', 'on', \
            (self.left, self.right), 'cols', _colrepr(self), 'filter:', repr(conditions), 'results:'
        pprint.pprint(results)
        [validateRowShape(self.columns, r) for r in results]
        for row in results:
            yield row

    def getJoinType(self):
        return self.joinFunc.__doc__

    def __repr__(self):
        return self.__class__.__name__+' '+ hex(id(self))+' with: '+(self.msg
            or self.getJoinType())

    def explain(self, out, indent=''): 
        print >>out, indent, repr(self), _colrepr(self)
        indent += ' '*4
        self.left.explain(out,indent)
        self.right.explain(out,indent)        
            
class IterationJoin(Join):
    '''
    Corresponds to an join of two tuplesets
    Can be a inner join or right outer join, depending on joinFunc
    '''
        
    def filter(self, conditions=None, hints=None):
        for left, right in joinTuples(self.left, self.right, self.joinFunc):
            row = left + right
            flatrow = row #flatten(row, flattenTypes=ColGroup)
            #print 'Imatch', hex(id(self)), flatrow, 'filter', conditions
            if conditions:
                for key, value in conditions.iteritems():
                    if flatten(flatrow[key]) != value: #XXX
                        #print '@@@@skipped@@@', row[key], '!=', repr(value), flatten(row[key])
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
        
    def __init__(self, left, right, lpos, rpos, msg=''):
        self.left = left
        self.right = right
        self.leftJoinSlice = lpos
        self.rightJoinSlice = rpos
        self.msg = msg
        
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
    
    def filter(self, conditions=None, hints=None):
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

def getcolumn(pos, row):
    '''
    yield a sequence of values for the nested column
    '''
    pos = list(pos)
    #print 'gc', pos, row
    p = pos.pop(0)    
    cell = row[p]
    if pos:
        assert isinstance(cell, Tupleset), "cell %s p %s restp %s" % (cell, p, pos)
        for nestedrow in cell:
            assert isinstance(nestedrow, (list, tuple)
                ) and not isinstance(nestedrow, Tupleset), "%s" % (type(nestedrow))
            for (c, row) in getcolumn(pos, nestedrow):
                #print 'ct', c
                yield (c, row)
    else:
        yield (cell, row)

def choosecolumns(groupby, columns, pos=None):
    '''
    "above" columns go first, omit groupby column
    '''
    pos = pos or []
    level = len(pos)
    for i, c in enumerate(columns):
        if groupby[level-1] == i:
            if level == len(groupby):
                continue #groupby column, skip this column
            for nc in choosecolumns(groupby, c, pos):
                yield pos+[nc]
        else:
            yield c

def groupbyUnordered(tupleset, groupby, columns, debug=False):
    '''
    Group the given tupleset by the column specified by groupby
    yields a row the groupby key and a nested tupleset containing the non-key columns
    of the tupleset. The nested tupleset
    will have one row for each occurence of the key. If the groupby key
    is nested, the columns of ancestor tuplesets will be duplicated for each key
    and cell coalesced into lists if necessary XXX

    (a1, (b1, (c1,c2)), (a2, (b2, (c1,c2)) => groupby(c)
    => (c1, ( (a1, (b1)), (a2, (b2)) ) ), (c2, ( (a1, (b1)), (a2, (b2)) ) )

    (a1, b1), (a1, b2) => groupby(a) => (a1, (b1,b2))
                       => groupby(b) => (b1, (a1)), (b2, (a1))

    [a, b] => [a, Tupleset[b]] => [b, Tupleset[a]]

    (a1, b1, c1), (a1, b2, c1) => groupby(a) => (a1, ( (b1, c1), (b2, c2) ) )
                               => groupby(b) => (b1, (a1, (c1))), (b2, (a1,(c2)) )
                               => groupby(c) => (c1, (b1, (a1))), (c2, (b2, (a1)))

    [a, b, c] => [a, NestedRows[b,c]] => [b, [a, NestedRows[c]] ]

    (a1, b1, c1), (a1, b1, c1) => groupby(a) => (a1, ( (b1, c1), (b1, c1) ) )
                               => groupby(b) => (b1, (a1, (c1, c1)) )
                               => groupby(c) => (c1, (b1, (a1)))

    columns is a list of indexes into the rows
    (all of the source columns except for the group by)
    '''
    resources = {}
    for row in tupleset:
        outputrow = []
        for colpos in columns:
            if len(colpos) < len(groupby):
                outputcell = []
                for v, ignore in getcolumn(colpos, row):
                    #print 'above', row, colpos, v
                    outputcell.append(v)
                assert len(outputcell)==1, 'above coalesce %s' % outputcell
                outputrow.append( outputcell[0] )

        for (key, row) in getcolumn(groupby, row):
            #print 'gb', key, row
            outputrow = outputrow[:]
            vals = resources.get(key)
            if vals is None:
                vals = MutableTupleset()
                resources[key] = vals
            for col in columns:
                colpos = col[len(groupby)-1:] #adjust position
                if not colpos:
                    #handled by 'above' logic above
                    continue
                assert len(colpos)==1, 'unexpected multi-level position %s' % colpos
                #print 'below1', row, key, colpos, row[colpos[0]]
                outputrow.append( row[colpos[0]] )
            vals.append(outputrow)
    for key, values in resources.iteritems():
        #print 'gb out', [key, values]
        yield [key, values]

def groupbyOrdered(tupleset, pos, labels=None, debug=False):
    '''
    More efficient version of groupbyUnordered -- use if the tupleset is
    ordered by column in the given pos
    '''
    for row in tupleset:
        raise Exception('nyi') #XXX

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
        
    def filter(self, conditions=None, hints=None):
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
    
    def filter(self, conditions=None, hints=None):
        for tupleset in self.tuplesets:
            for row in tupleset.filter(conditions, hints):
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
        #XXX:
        while isinstance(tupleset, Projection):
            tupleset = tupleset.tupleset
        
        if isinstance(tupleset, RxPath.Model):
            return tupleset
                
    return None

#############################################################
################ Evaluation Engine ##########################
#############################################################
#for associative ops: (a op b) op c := a op b op c
def flattenOp(args, opType):
    if isinstance(args, jqlAST.QueryOp):
        args = (args,)
    for a in args:
        if isinstance(a, opType):
            for i in flattenOp(a.args, opType):
                yield i
        else:
            yield a

def _setConstructProp(op, pattern, prop, v, name):
    if not v:
        if prop.ifEmpty == jqlAST.PropShape.omit:
            return
        elif prop.ifEmpty == jqlAST.PropShape.uselist:
            val = v
        elif prop.ifEmpty == jqlAST.PropShape.usenull:
            val = None #null
    elif (prop.ifSingle == jqlAST.PropShape.nolist
            and len(v) == 1):
        val = v[0]
    else: #uselist
        val = v

    if op.shape is op.dictShape:
        pattern[name] = val
    else:
        pattern.append(val)

def _labelsToColumns(labels, tupleset, start=0):
    return [ColumnInfo(start+i, name,
          (tupleset and tupleset.columns and len(tupleset.columns)>pos
          and tupleset.columns[pos].type) or object)
                      for i,(name, pos) in enumerate(labels)]

#def _findFlatPos(columns, label, start=0):
#    for i,c in enumerate(columns):
#        if c.label == label:
#            return start + i
#        if isinstance(c.type, NestedRows):
#            pos = _findFlatPos(c.type.columns, start+i)
#            if pos > -1:
#                return pos
#    return -1

class SimpleQueryEngine(object):
    
    def evalSelect(self, op, context):
        if op.where:
            context.currentTupleset = op.where.evaluate(self, context)
        #print 'where ct', context.currentTupleset
        return op.construct.evaluate(self, context)

    def evalConstruct(self, op, context):
        '''
        Construct ops operate on currentValue (a cell -- that maybe multivalued)
        '''
        tupleset = context.currentTupleset
        assert isinstance(tupleset, Tupleset), type(tupleset)

        def construct():
            count = 0

            assert context.currentTupleset is tupleset
            for i, row in enumerate(tupleset.filter()):
                if op.parent.offset is not None and op.parent.offset < i:
                    continue
                context.currentRow = row
                pattern = op.shape()

                if not op.id.getLabel(): 
                    subjectcol = (0,) 
                else:
                    subjectlabel = op.id.getLabel()
                    subjectcol = tupleset.findColumnPos(subjectlabel)
                    if not subjectcol:
                        raise QueryException(
                            'construct: could not find subject label %s in %s'
                            % (subjectlabel, tupleset.columns))
                idcells = list(getcolumn(subjectcol, row))
                assert len(idcells) == 1, '%s %s %s' % (subjectcol, subjectlabel, idcells)
                #get the first item in the nested sequence
                idvalue = iter(flattenSeq( idcells[0][1] )).next()

                #ccontext.currentTupleset = SimpleTupleset((row,),
                #            hint=(row,), op='construct',debug=context.debug)
                for prop in op.args:
                    if isinstance(prop, jqlAST.Join): #XXX
                        continue
                    if isinstance(prop, jqlAST.ConstructSubject):
                        #print 'cs', prop.name, idvalue
                        if not prop.name: #omit 'id' if prop if name is empty
                            continue
                        if op.shape is op.dictShape:
                            pattern[prop.name] = idvalue
                        elif op.shape is op.listShape:
                            pattern.append(idvalue)
                    elif prop.value.name == '*':
                        for name, value in prop.value.evaluate(self, context):                            
                            _setConstructProp(op, pattern, prop, value, name)
                    else:
                        ccontext = context
                        if isinstance(prop.value, jqlAST.Select):
                            ccontext = copy.copy( ccontext )
                            #if id label is set use that, or use the property name
                            label = prop.value.construct.id.getLabel() or prop.name                            
                            col = tupleset.findColumnPos(label, True)
                            #print row
                            if not col:
                                raise QueryException(
                                    'construct: could not find label %s in %s'
                                    % (label, tupleset.columns))
                            else:
                                pos, rowInfoTupleset = col

                            v = list([row for cell,row in getcolumn(pos, row)])
                            #print '!!!v', col, label, v, 'row', row
                            assert isinstance(v, (list, tuple, Tupleset))
                            #assert isinstance(col.type, Tupleset)
                            ccontext.currentTupleset = SimpleTupleset(v,
                              columns=rowInfoTupleset.columns,
                              hint=v,
                              op='nested construct value', debug=context.debug)

                        #print '!!v eval', prop, '\n', prop.value
                        v = list(prop.value.evaluate(self, ccontext))
                        #print '####PROP', prop.name or prop.value.name, 'v', v
                        _setConstructProp(op, pattern, prop, v,
                                                prop.name or prop.value.name)

                yield pattern
                count+=1
                if op.parent.limit is not None and op.parent.limit < count:
                    break

        return SimpleTupleset(construct, hint=tupleset, op='construct',
                                                            debug=context.debug)

    def _groupby(self, tupleset, joincond, msg='group by ',debug=False):
        #XXX use groupbyOrdered if we know tupleset is ordered by subject
        position = tupleset.findColumnPos(joincond.position)
        assert position is not None, '%s %s' % (tupleset, tupleset.columns)
        #print '_groupby', joincond.position, position, tupleset.columns
        coltype = object
        #XXX use choosecolumns
        columns = [
            ColumnInfo(0, joincond.parent.name or '', coltype),
            ColumnInfo(1, joincond.getPositionLabel(),
                                            MutableTupleset(tupleset.columns) )
        ]
        colpositions = [(c.pos,) for c in tupleset.columns]
        return SimpleTupleset(
            lambda: groupbyUnordered(tupleset, position,
                colpositions, debug=debug),
            columns=columns, 
            hint=tupleset, op=msg + repr(joincond.position),  debug=debug)

    def evalJoin(self, op, context):
        #XXX context.currentTupleset isn't set when returned
        args = sorted(op.args, key=lambda arg: arg.op.cost(self, context))
        if not args:
            tmpop = jqlAST.JoinConditionOp(jqlAST.Filter())
            tmpop.parent = op
            args = [tmpop]

        #evaluate each op, then join on results
        #XXX optimizations:
        # 1. if the result of a projection can used for a filter, apply it and
        # use that as source of the filter
        # 2. estimate and compare cost of projecting the prior result so next filter
        # can use that as source (compare with cost of filtering with current source)
        # 3.if we know results are ordered properly we can do a MergeJoin
        #   (more efficient than IterationJoin):
        #lslice = slice( joincond.position, joincond.position+1)
        #rslice = slice( 0, 1) #curent tupleset is a
        #current = MergeJoin(result, current, lslice,rslice)

        previous = None
        while args:
            joincond = args.pop(0)

            assert isinstance(joincond, jqlAST.JoinConditionOp)
            result = joincond.op.evaluate(self, context)
            assert isinstance(result, Tupleset)

            current = self._groupby(result, joincond,debug=context.debug)
            #print 'groupby col', current.columns
            if previous:
                def joinFunc(leftRow, rightTable, lastRow):
                    for row in rightTable.filter({0 : leftRow[0]},
                        hints={ 'makeindex' : 0 }):                            
                            yield row
                    #XXX handle outer join

                coltype = object #XXX
                assert current.columns and len(current.columns) >= 1
                assert previous.columns is not None
                #columns: (left + right)
                columns = _reordercols(previous.columns + current.columns) 
                previous = IterationJoin(previous, current, joinFunc,
                                columns,joincond.name,debug=context.debug)
            else:
                previous = current
        #print 'join col', previous.columns
        return previous

    def _findSimplePredicates(self, op, context):
        simpleops = (jqlAST.Eq,) #only Eq supported for now
        #XXX support isref() by mapping to objecttype
        complexargs = []
        simplefilter = {}
        for pred in op.args:
            complexargs.append(pred)
            if not isinstance(pred, simpleops):
                continue
            if isinstance(pred.left, jqlAST.Project) and pred.right.isIndependent():
                proj = pred.left
                other = pred.right
            elif isinstance(pred.right, jqlAST.Project) and pred.left.isIndependent():
                proj = pred.right
                other = pred.left
            else:
                continue
            if not proj.isPosition():
                continue
            if proj.name in simplefilter:
                #position already taken, treat as complex
                continue
            value = other.evaluate(self, context)
            simplefilter[proj.name] = value
            complexargs.pop()

        return simplefilter, complexargs

    def evalFilter(self, op, context):
        '''
        Find slots
        '''
        simplefilter, complexargs = self._findSimplePredicates(op, context)

        columns = []
        for label, pos in op.labels:
            columns.append( ColumnInfo(len(columns), label, object) )

        def colmap(row):
            for label, pos in op.labels:
                yield row[pos]

        tupleset = context.currentTupleset
        #first apply all the simple predicates that we assume are efficient       
        if simplefilter or not complexargs:
            #XXX: optimization: if cost is better filter on initialmodel
            #and then find intersection of result and currentTupleset
            tupleset = SimpleTupleset(
                lambda tupleset=tupleset: tupleset.filter(simplefilter),
                columns = complexargs and tupleset.columns or columns,
                colmap = not complexargs and colmap or None,
                hint=tupleset, op='selectWithValue1', debug=context.debug)

        if not complexargs:
            return tupleset

        #now create a tupleset that applies the complex predicates to each row
        def getArgs():
            for i, pred in enumerate(complexargs):
                for arg in flattenOp(pred, jqlAST.And):
                     yield (arg.cost(self, context), i, arg)

        fcontext = copy.copy( context )
        def filterRows():
            args = [x for x in getArgs()]
            args.sort() #sort by cost
            #for cost, i, arg in args:
            #    if arg.left.isIndependent():
                    #XXX evalFunc, etc. to use value
                    #XXX memoize results lazily
            #        arg.left.value = arg.left.evaluate(self, fcontext)
                
            for row in tupleset:
                for cost, i, arg in args:                    
                    fcontext.currentRow = row
                    #fcontext.currentValue = row[i]
                    value = arg.evaluate(self, fcontext)
                    if not value:
                        break
                if not value:
                    continue
                yield row

        return SimpleTupleset(filterRows, hint=tupleset,columns=columns,
                colmap=colmap, op='complexfilter', debug=context.debug)

    def evalProject(self, op, context):
        '''
        Operates on current row and returns a value

        Project only applies to * -- other Projections get turned into Filters
        (possible as outer joins) and so have already been processed
        '''
        # projection can be IterationJoin or a MergeJoin, the latter will walk
        # thru all resources in the db unless filter constraints can be used to deduce
        # a view or data engine join that can be used, e.g. an index on type
        # In fact as an optimization since most query results will have a limited
        # range of types we could first project on type and use that result to
        # choose the type index. On the other hand, if that projection uses an
        # iteration join it might be nearly expensive as doing the iteration join
        # on the subject only.
        if op.name != '*':
            col = context.currentTupleset.findColumn(op.name, True)
            if not col:
                raise QueryException(op.name + " projection not found")
            return [context.currentRow[col.pos]]
            #context.currentRow[pos]
            #for (name, pos) in op.join.labels:
            #    if name == op.field:
            #        return context.currentRow[pos]            
        else:
            tupleset = context.initialModel
            subject = context.currentRow[SUBJECT]
            def getprops():
                rows = tupleset.filter({
                    SUBJECT:subject
                })
                for row in rows:
                    v = row[OBJECT]
                    if not isinstance(v, (list,tuple)):
                        v = [v]
                    yield row[PROPERTY], v

            return SimpleTupleset(getprops,
                    hint=tupleset, op='project *',debug=context.debug)

    def costProject(self, op, context):
        #if op.name == "*": 
        return 1.0 #XXX

#XXXX
    def costFilter(self, op, context):
        return 1.0 #XXX

        #simple cheaper than complex
        #dependent cheaper then
        #subject cheaper object cheaper than predicate
        SIMPLECOST = [1, 4, 2]
        #we have to evaluate each row
        COMPLEXCOST = []
        #we have to evaluate each row
        DEPENDANTCOST = []

        cost = 0 #no-op
        for i, pred in enumerate(op.args):
            if not pred:
                continue
            assert pred.getType() == BooleanType
            assert pred.left
            #XXX dont yet support something like: where customcompare(prop1, prop2)
            assert pred.right is None, 'multi-prop compares not yet implemented'

            if pred.left.isIndependent():
                if isinstance(pred, jqlAST.Eq): #simple
                    positioncost = SIMPLECOST
                else:
                    positioncost = COMPLEXCOST
            else:
                positioncost = DEPENDANTCOST

            cost += (pred.left.cost(self, context) * positioncost[i])

        return cost

    def costJoin(self, op, context):
        return 2.0 #XXX

        args = list(flattenSeq(op.args))
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

    def evalConstant(self, op, context):
        return op.value

    def costConstant(self, op, context):
        return 0.0

    def evalEq(self, op, context):
        lvalue = op.left.evaluate(self, context)
        if op.right:
            rvalue = op.left.evaluate(self, context)
        else:
            rvalue = context.currentValue
        return lvalue == rvalue

    def costEq(self, op, context):
        return 0
        
    def evalAnyFuncOp(self, op, context):
        values = [arg.evaluate(self, context) for arg in op.args]
        return op.metadata.func(*values)

    def costAnyFuncOp(self, op, context):
        if op.metadata.costFunc:
            cost = op.metadata.costFunc(self, context)        
            if not op.isIndependent():
                return cost * 50 #dependent is much more expensive
            else:
                return cost
        else:
            return 1 #XXX

    #XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX###############

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
                    
    def evalAnd(self, op, context):
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

    def costAnd(self, op, context):
        #minCost = min([a.cost(self, context) for a in op.args])
        #figure out the average cost
        if not op.args:
            return 0.0
        total = reduce(operator.add, [a.cost(self, context) for a in op.args], 0.0)
        return total / len(op.args)

    def evalOr(self, op, context):
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
    
    def costOr(self, op, context):
        return reduce(operator.add, [a.cost(self, context) for a in op.args], 0.0)

    def evalIn(self, op, context):        
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

    def costIn(self, op, context):
        return reduce(operator.add, [a.cost(self, context) for a in op.args], 0.0)

    def evalEq(self, op, context):        
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
                    op='selectWithValue2 '+ value)
            
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
                                    
    def costEq(self, op, context):
        assert len(op.args) == 2        
        return op.args[0].cost(self, context) + op.args[1].cost(self, context)
    
        

