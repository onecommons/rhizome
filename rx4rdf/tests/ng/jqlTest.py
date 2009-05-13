from ng import jql, sjson
from ng.jqlAST import *
from rx import RxPath
import sys, pprint

#aliases for convenience
jc = JoinConditionOp
cs = ConstructSubject
def cp(*args, **kw):
    if len(args) == 1:
        return ConstructProp(None, args[0], **kw)
    return ConstructProp(*args, **kw)



'''
todo: query tests:

*joins:
outer joins (maybe())
semi-join (in)
anti-join (not in)
* unions (or)
* intersect (not)

* construction:
id keys only (not objects)
'''

class Test(object):
    def __init__(self, attrs):
        self.__dict__.update(attrs)

def t(query=None, results=None, **kw):
    '''
    optional arguments:
    rows: test the tupleset result matches this
    results : test the result of query execution matches this
    name: name the test
    '''
    defaults = dict(ast=None, rows=None, result=None, skip=False,
                skipParse=False, model=None, name=None)
    defaults.update(query=query, results=results)
    defaults.update(kw)
    return Test(defaults)

class Tests:

###################################
########### basic tests ###########
###################################
    simpleModel = [
        { "parent":"1", "child":"2"},
        { "parent":"1", "child":"3"},
        { "id" : "1"},
        { "id" : "2", "foo" : "bar"},
        { "id" : "3", "foo" : "bar"}
    ]

    firstTests = (simpleModel, [t(
''' { id : ?parent,
      derivedprop : a + b,
      children : { id : ?child,
                   *
                   where( {child = ?child,
                        parent = ?parent
                       })
                 }
    }
''',skipParse=1,
ast=Root(
 Join(
  jc(Join( #row : subject, "child", "parent"
    Filter(None, Eq('child'), None, objectlabel='child'),
    Filter(None, Eq('parent'), None, objectlabel='parent'),
    ), 'parent'),  #this can end up with child cell as a list
),
 Construct([
    cs('id'),
    #XXX outerjoin broken:
    #cp('derivedprop',  qF.getOp('add', Project('a'), Project('b'))),
    cp('children', Construct([
            cs('id', 'child'),
            cp(Project('*')) #find all props
        ]))
    ])
),
#expected rows: id, (child, parent)
rows=[['1',
    [
      ['2', '1'], ['3', '1']
    ]
]]
),
t(
''' { id : ?parent,
      derivedprop : a + b,
      children : { id : ?child,
                   foo : 'bar',                   
                   where( {child = ?child,
                        parent = ?parent
                       })
                 }
    }
''',skipParse=1,
ast=Root(
 Join( #row  : (subject, (subject, foo, ("child", ("child", "parent"))))
  jc(
    Join( #row : subject, foo, ("child", ("child", "parent"))
     jc(Join( #row : subject, ("child", "parent")
       Filter(None, Eq('child'), None, objectlabel='child'),
       Filter(None, Eq('parent'), None, objectlabel='parent'),
       ),'child'),
     Filter(None, Eq('foo'), Eq('bar'), objectlabel='foo')
    ),
    'parent'),  #this can end up with child cell as a list
),
 Construct([
    cs('id'),
    #cp('derivedprop',  qF.getOp('add', Project('a'), Project('b'))),
    cp('children', Construct([
            cs('id', 'child'),
            cp(Project('foo')) #find all props
        ]))
    ])
),
#expected results (id, (child, foo), parent)
rows=[['1',
    [
       ['bar', '3', '1'], ['bar', '2', '1']
    ]
]]
)
])

    basicModel = [{}, {}]
    basicTests = (basicModel, [
#join on prop
('''
{
foo : { * } #find objects whose id equals prop's value
where (bar = 'match')
}
''',
'''ConstructOp({
    'foo': ConstructOp({'id': Label('_construct1'), 
                        '*': ProjectOp('*')})
    }, JoinOp(FilterOp(None, 'bar', 'match'),
        FilterOp(None, 'foo', None, objectlabel='_construct1')
        )
    )''',
['result']
),
#correlated variable reference
('''
{ id : ?parent,
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
''',
'''ConstructOp({
    id : Label('parent'),
    derivedprop : NumberFunOp('/', project('a')/project('b')),
    children : construct({
            id : Label('child'),
            '*' : project('*') #find all props
        },
      )
    },
     join(
         join(
          filter(None, eq('child'), None, objlabel='child'),
          filter(None, eq('parent'), None, objlabel='parent')
         ),
         filter(None, eq('cost'), gt(3)),
         joinon=(SUBJECT,'parent') #group child vars together per join row
       )
    )''',
['result']
),
t(name="implicit join via attribute reference",
query='''
{
id : ?parent,
foo : ?f,
where( foo = {
    id : ?parent.foo
  })
}
'''),
t(name="implicit join via attribute reference",
query='''
{
buzz : ?child.blah
# above is equivalent to the following (but displays only ids, not objects)
"buzz" : { id : ?child, *}
where (buzz = ?child.blah)
}
''', 
ast=Join(
Filter(None, 'buzz', Join(Filter(None, 'blah', None)) )
),
astrewrite= Join(
    jc(Join(
        jc(Filter(None, Eq('buzz'), None, subjectlabel='_1'), OBJECT),
        jc(Filter(None, Eq('blah'), None, subjectlabel='blah'), SUBJECT)
      ),
    '_1')
)
###
#=>  {
#  id : _1
#  where(
#   baz = {
#
#      where(id = _1)
#   }
#   )
#  }
###
)
 ])


   #### BerlinSPARQLBenchmark tests
  ## see http://www4.wiwiss.fu-berlin.de/bizer/BerlinSPARQLBenchmark/spec/index.html#queriesTriple
  #######
    benchmarkModel = [{
    }]

    benchmarkTests = (benchmarkModel, [
  #1
  '''
  { 
   rdfs:label : *
   where (
   type = ?type,
   bsbm:productFeature = ?f1,
   bsbm:productFeature = ?f2,
   bsbm:numericProp > ?x
   )
  }
  ''',
  #2
  '''
  {
  rdfs:label : *,
  rdfs:comment : *, 
   producer : { id : ?producer, rdfs:label : * },
   dc:publisher :  ?producer,
   feature : { rdfs:label : * },
   optional( prop4 : *, prop5: *)
    where (id = ?product)
  }
  ''',
  #3 some specific features but not one feature
  '''
  where (bsbm:productFeature = ?productfeature1 and
  bsbm:productFeature != ?productfeature2) 
  ''',
  #4 union of two feature sets:
''' 
where (feature1 or feature2)
''',
#5 Find products that are similar to a given product.
'''
'''
])

from optparse import OptionParser

if __name__ == "__main__":
    usage = "usage: %prog [options]"
    parser = OptionParser(usage)
    for name, default in [('printmodel', 0), ('printast', 1), ('explain', 1)]:
        parser.add_option('--'+name, dest=name, default=default, 
                                                action="store_true")
    (options, args) = parser.parse_args()

    model, tests = Tests.firstTests
    model = sjson.sjson().to_rdf( { 'results' : model } )
    model = RxPath.MemModel(model)
    if options.printmodel:
        print 'model', list(model)

    count = 0
    for (i, test) in enumerate(tests):
        if test.skip:
            continue
        count += 1

        if test.name:
            name = test.name
        else:
            name = "%d" % i
        print '*** running test:', name

        if test.ast:
            if not test.skipParse:
                testast = jql.buildAST(test.query)
                assert testast == test.ast, ('unexpected ast for test %d' % i)
            else:
                ast = test.ast
        else:
            ast = jql.buildAST(test.query)

        jql.rewriteAST(ast)
        if options.printast:
            print "ast:"
            pprint.pprint(ast)

        if test.rows is not None:
            if options.explain:
                print "explain plan:"
                explain = sys.stdout
            else:
                explain = None
            evalAst = ast.evalOp
            testrows = list(jql.evalAST(evalAst, model, explain=explain))
            print 'rows:'
            print 'labels', evalAst.labels
            pprint.pprint(testrows)
            assert test.rows== test.rows,  ('unexpected rows for test %d' % i)
        elif options.explain:
            print "explain plan:"
            evalAst = ast.evalOp
            testrows = list(jql.evalAST(evalAst, model, explain=sys.stdout))

        print "execute and construct (with debug):"
        testresults = list(jql.evalAST(ast, model, debug=True))
        print "Construct Results:"
        pprint.pprint(testresults)
        if test.results is not None:
            assert test.results == testresults,  ('unexpected results for test %d' % i)

    print '***** %d tests passed, %d skipped' % (count, len(tests) - count)