from rx.RxPath import Tupleset, ColumnInfo, EMPTY_NAMESPACE

SUBJECT = 0
PROPERTY = 1
OBJECT = 2

def getitemdeep(l, pos):
    '''
    retrieves an item from nested lists where index is a sequence like (1, 2, ...)
    '''
    if isinstance(pos, int):
        return l[pos]
    for i in pos:
        l = l[i]
    return l

class ResourceSet(Tupleset):
    '''
    (resource uri, {varname : [values+]}),*
    or maybe: tuples, collabels = []
    '''

BooleanType = bool
ObjectType = object
NumberType = float
StringType = unicode

QueryOpTypes = ( Tupleset, ResourceSet, ObjectType, StringType, NumberType,
    BooleanType )
NullType = type(None)

class QueryException(Exception): pass

try:
    from functools import partial
except ImportError:
    def partial(func, *args, **keywords):
            def newfunc(*fargs, **fkeywords):
                newkeywords = keywords.copy()
                newkeywords.update(fkeywords)
                return func(*(args + fargs), **newkeywords)
            newfunc.func = func
            newfunc.args = args
            newfunc.keywords = keywords
            return newfunc