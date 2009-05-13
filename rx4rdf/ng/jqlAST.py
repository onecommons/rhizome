from ng import *
from rx.utils import flattenSeq, flatten

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

def depthfirstsearch(root, descendPredicate = None, visited = None):
    """
    Given a starting vertex, root, do a depth-first search.
    """
    import collections
    to_visit = collections.deque()
    if visited is None:
        visited = set()

    to_visit.append(root) # Start with root
    while len(to_visit) != 0:
        v = to_visit.pop()
        if id(v) not in visited:
            visited.add( id(v) )
            yield v
            if not descendPredicate or descendPredicate(v):
                to_visit.extend(v.args)

class QueryOp(object):
    '''
    Base class for the AST.
    '''

    parent = None
    args = ()
    labels = ()
    name = None
    value = None #evaluation results maybe cached here

    @classmethod
    def _costMethodName(cls):
        return 'cost'+ cls.__name__

    @classmethod
    def _evalMethodName(cls):
        return 'eval'+ cls.__name__

    def getType(self):
        return ObjectType

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self.args == other.args

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
        indent = self.parent and '\n' or ''
        parent = self.parent
        while parent:
            indent += '  '
            parent = parent.parent
        if self.name is not None:
            name = self.name
            if isinstance(name, tuple): #if qname pair
                name = self.name[1]
            namerepr = ':'+ repr(name)
        else:
            namerepr = ''
        if self.args:
            argsrepr = '(' + ','.join([repr(a) for a in self.args]) + ')'
        else:
            argsrepr = ''
        return (indent + self.__class__.__name__ + namerepr
                + (self.labels and repr(self.labels) or '')
                + argsrepr)

    def _siblings(self):
        if not self.parent:
            return []
        return [a for a in self.parent.args if a is not self]
    siblings = property(_siblings)

    def depthfirst(self, descendPredicate=None):
        '''
        yield descendants depth-first (pre-order traversal)
        '''
        for n in depthfirstsearch(self, descendPredicate):
            yield n

    def _bydepth(self,level=0):
        for a in self.args:
            for descend, lvl in a._bydepth(level+1):
                yield descend, lvl
        yield self, level

    def breadthfirst(self, deepestFirst=False, includeLevel=False):
        '''
        yield descendants (and self) by ordered by level
        if deepestFirst = True, yield deepest level first
        if includeLevel = True, yield (node, level) pairs 
        '''
        return [includeLevel and i or i[0] for i in
            sorted(self._bydepth(), key=lambda k:k[1], reverse=deepestFirst)]

    def appendArg(self, arg):
        self.args.append(arg)
        arg.parent = self

class ErrorOp(QueryOp):
    def __init__(self, args, name=''):
        if not isinstance(args, (list, tuple)):
            args = (args,)
        self.args = args
        self.name = "Error " + name

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
        self.labels = []
        for a in args:
            self.appendArg(a)
        self.construct = kw.get('construct', {})
        self.ref = kw.get('ref')

    def appendArg(self, op):
        if isinstance(op, (Filter,ResourceSetOp)):
            op = JoinConditionOp(op)
        elif not isinstance(op, JoinConditionOp):
            raise QueryException('bad ast')
        QueryOp.appendArg(self, op)

    def getType(self):
        return Resourceset

class Join(ResourceSetOp):
    '''
    handles "and"
    '''

class Union(ResourceSetOp):
    '''
    handles "or"
    '''

class Except(ResourceSetOp):
    '''
    handles 'not'
    '''

class JoinConditionOp(QueryOp):
    '''
    helper op
    '''
    INNER = 'inner'
    RIGHTOUTER = 'right outer'

    def __init__(self, op, position=SUBJECT, join=INNER):
        self.op = op
        self.args = (op,)
        op.parent = self
        self.position = position #index or label
        self.join = join

    name = property(lambda self: '%s:%s' % (str(self.position),self.join) )

    def getPositionLabel(self):
        if isinstance(self.position, int):
            return ''
        else:
            return self.position

    def resolvePosition(self, throw=True):
        '''
        Return the column index for the join
        To handle joins on labels, this needs to be called after the underlying
        op is evaluated.
        '''
        if not isinstance(self.position, int):
            #print 'resolve', str(self.op), repr(self.op.labels)
            for name, pos in self.op.labels:
                if self.position == name:
                    #print 'found', name, pos
                    return pos

            if throw:                
                raise QueryException('unknown label ' + self.position)
            else:
                return None
        else:
            return self.position

    def _xxxresolvePosition(self, columns, throw=True):
        '''
        Return the column index for the join
        To handle joins on labels, this needs to be called after the underlying
        op is evaluated.
        '''
        if not isinstance(self.position, int):
            #print 'resolve', str(self.op), repr(self.op.labels)
            for col in columns:                
                if self.position == col.label:
                    #print 'found', name, pos
                    return col.pos
                elif isinstance(col.type, NestedColumn) and col.type.columns:
                    nestedpos = self.resolvePosition(col.type.columns, False)
                    if nestedpos is not None:
                        return flatten( (col.pos, nestedpos) )

            if throw:
                print tupleset, tupleset.columns
                raise QueryException('unknown label ' + self.position)
            else:
                return None
        else:
            return self.position


class Filter(QueryOp):
    '''
    Filters rows out of a tupleset based on predicate
    '''

    def __init__(self, sub=None, pred=None, obj=None,
                 subjectlabel=None, propertylabel=None, objectlabel=None):

        self.predicates = [sub, pred, obj]        
        self.labels = []
        if subjectlabel:
            self.labels.append( (subjectlabel, SUBJECT) )
        if propertylabel:
            self.labels.append( (propertylabel, PROPERTY) )
        if objectlabel:            
            self.labels.append( (objectlabel, OBJECT) )
 
    def getType(self):
        return Tupleset

    args = property(lambda self: [a for a in self.predicates if a])

    def appendArg(self, arg, pos):
        self.predicates[pos] = arg
        arg.parent = self

    def addLabel(self, label, pos):
        for (name, p) in self.labels:
            if name == label:
                if p == pos:
                    return
                else:
                    raise QueryException("label already used " + label)
        self.labels.append( (label, pos) )

class Label(QueryOp):

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return super(Label, self).__eq__(other) and self.name == self.name

class Constant(QueryOp):
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

    def __eq__(self, other):
        return super(Constant,self).__eq__(other) and self.value == other.value

    def __repr__(self):
        return repr(self.value)

class AnyFuncOp(QueryOp):

    def __init__(self, key=(), metadata=None, *args):
        self.name = key
        self.args = args or []
        self.metadata = metadata or self.defaultMetadata

    def getType(self):
        return self.metadata.type

    def isIndependent(self):
        independent = super(AnyFuncOp, self).isIndependent()
        if independent: #the args are independent
            return self.metadata.isIndependent
        else:
            return False
    
    def __eq__(self, other):
        return super(AnyFuncOp,self).__eq__(other) and self.name == other.name

    #def __repr__(self):
    #    if self.name:
    #        name = self.name[1]
    #    else:
    #        raise TypeError('malformed FuncOp, no name')
    #    return name + '(' + ','.join( [repr(a) for a in self.args] ) + ')'

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

    left = None
    right = None
    
    def __init__(self, left=None, right=None):
        self.args = []
        if left is not None:
            if not isinstance(left, QueryOp):
                left = Constant(left)
            self.left = left
            self.appendArg(left)
            if right is not None:
                if not isinstance(right, QueryOp):
                    right = Constant(right)
                self.right = right
                self.appendArg(right)

    def __repr__(self):
        if not self.args:
            return self.name + '()'
        elif len(self.args) > 1:
            return '(' + self.name.join( [repr(a) for a in self.args] ) + ')'
        else:
            return self.name + '(' +  repr(self.args[0]) + ')'

    def getType(self):
        return BooleanType

class And(BooleanOp):
    name = ' and '

class Or(BooleanOp):
    name = ' or '

class In(BooleanOp):
    '''Like OrOp + EqOp but the first argument is only evaluated once'''
    def __repr__(self):
        rep = repr(self.args[0]) + ' in ('
        return rep + ','.join([repr(a) for a in self.args[1:] ]) + ')'

class Eq(BooleanOp):
    def __repr__(self):
        return '(' + ' = '.join( [repr(a) for a in self.args] ) + ')'

class IsNull(BooleanOp):
    def __repr__(self):
        return repr(self.args[0]) + ' is null '

class Cmp(BooleanOp):

    def __init__(self, op, *args):
        self.op = op
        return super(Cmp, self).__init__(*args)

    def __repr__(self):
        op = self.op
        return '(' + op.join( [repr(a) for a in self.args] ) + ')'

class Not(BooleanOp):
    def __repr__(self):
        return 'not(' + ','.join( [repr(a) for a in self.args] ) + ')'

class QueryFuncMetadata(object):
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

class QueryFuncs(object):

    SupportedFuncs = {
        (EMPTY_NAMESPACE, 'true') :
          QueryFuncMetadata(lambda *args: True, BooleanType, None, True,
                            lambda *args: 0),
        (EMPTY_NAMESPACE, 'false') :
          QueryFuncMetadata(lambda *args: False, BooleanType, None, True,
                            lambda *args: 0),
    }

    def addFunc(self, name, func, type=None, cost=None):
        if isinstance(name, (unicode, str)):
            name = (EMPTY_NAMESPACE, name)
        if cost is None or callable(cost):
            costfunc = cost
        else:
            costfunc = lambda *args: cost
        self.SupportedFuncs[name] = QueryFuncMetadata(func, type, costFunc=costfunc)

    def getOp(self, name, *args):
        if isinstance(name, (unicode, str)):
            name = (EMPTY_NAMESPACE, name)
        funcMetadata = self.SupportedFuncs[name]
        return funcMetadata.opFactory(name,funcMetadata,*args)

qF = QueryFuncs() #todo: SupportedFuncs should be per query engine and schema handler
qF.addFunc('add', lambda a, b: a+b, NumberType)
qF.addFunc('sub', lambda a, b: a-b, NumberType)
qF.addFunc('mul', lambda a, b: a*b, NumberType)
qF.addFunc('div', lambda a, b: a/b, NumberType)
qF.addFunc('mod', lambda a, b: a%b, NumberType)
qF.addFunc('negate', lambda a: -a, NumberType)

class Project(QueryOp):    
    join = None
    
    def __init__(self, field, var=None):
        self.varref = var #XXX
        if isinstance(file, (list,tuple)):
            field = field[0] #XXX
        self.name = field #name or '*'

class PropShape(object):
    omit = 'omit' #when MAYBE()
    usenull= 'usenull'
    uselist = 'uselist' #when [] specified
    nolist = 'nolist'

class ConstructProp(QueryOp):
    def __init__(self, name, value, ifEmpty=PropShape.usenull,
                ifSingle=PropShape.nolist):
       self.name = name #if name is None (and needed) derive from value (i.e. Project)
       self.value = value
       value.parent = self
       assert ifEmpty in (PropShape.omit, PropShape.usenull, PropShape.uselist)
       self.ifEmpty = ifEmpty
       assert ifSingle in (PropShape.nolist, PropShape.uselist)
       self.ifSingle = ifSingle

    args = property(lambda self: (self.value,))

    def __eq__(self, other):
        return super(ConstructProp,self).__eq__(other) and self.name == other.name

class ConstructSubject(QueryOp):
    def __init__(self, name='id', value=None):
        self.name = name        
        if value: #could be a string
            if not isinstance(value, QueryOp):
                value = Label(value)
            value.parent = self
        self.value = value

    def getLabel(self):
        if self.value:
            return self.value.name
        else:
            return ''

    args = property(lambda self: self.value and (self.value,) or ())

    def __eq__(self, other):
        return super(ConstructSubject,self).__eq__(other) and self.name == other.name

class Construct(QueryOp):
    '''
    '''
    dictShape= dict
    listShape= list
    offset = None
    limit = None

    def __init__(self, props, shape=dictShape):
        self.args = []
        for p in props:
            self.appendArg(p)
            if isinstance(p, ConstructSubject):
                self.id = p
        if not self.id:
            self.id = ConstructSubject()
            self.id.parent = self
        self.shape = shape

    def __eq__(self, other):
        return (super(Construct,self).__eq__(other)
            and self.shape == other.shape and self.id == self.id)

class Root(QueryOp):
    def __init__(self, evalOp, construct):
        self.evalOp = evalOp
        evalOp.parent = self
        self.construct = construct
        construct.parent = self

    args = property(lambda self:  (self.evalOp, self.construct))

