# mrucache.py -- defines class MRUCache
# Takes capacity, a valueCalc function, and an optional hashCalc function
# to make an MRU/LRU cache instance with a getValue method that either retrieves
# cached value or calculates a new one. Either way, makes the value MRU.
# Alpha version. NO WARRANTY. Use at your own risk
# Copyright (c) 2002 Bengt Richter 2001-10-05. All rights reserved.
# Use per Python Software Foundation (PSF) license.
# 

from rx import utils
_defexception = utils.DynaExceptionFactory(__name__)
_defexception('not cacheable')

class UseNode(object):
    """For linked list kept in most-recent .. least-recent *use* order"""
    __slots__ = ['value','hkey','older','newer', 'sideEffects']
    def __init__(self, value, hkey, older=None, newer=None):
        self.value = value  # as returned by user valueCalc function
        self.hkey = hkey    # defaults to arg tuple for valueCalc, or else
                            # result of user hashCalc function called with those args
        self.older = older  # link to node not as recently used as current
        self.newer = newer  # Note that list is circular: mru.newer is lru
                            # and lru.older is mru, which is the reference point.
                            
class MRUCache:
    """
    Produces cache object with given capacity for MRU/LRU list.
    Uses user-supplied valueCalc function when it can't find value in cache.
    Uses optional user-supplied hashCalc function to make key for finding
    cached values or uses valueCalc arg tuple as key.
    MRU/LRU list is initialized with a dummy node to a circular list of length one.
    This node becomes LRU and gets overwritten when the list fills to capacity.
    """
    debug = False
    
    def __init__(self,
        capacity,       # max number of simultaneous cache MRU values kept
        valueCalc=None,      # user function to calculate actual value from args
        hashCalc=None,  # normally takes same args as valueCalc if present
        #valueCalc might have some sideEffects that we need to reproduce when we retrieve the cache value:
        sideEffectsFunc=None, #execute the sideEffectsFunc when we return retrieve the value from the cache
        sideEffectsCalc=None, #calculate the sideEffects when we calculate the value
        isValueCacheableCalc=None, #calculate if the value should be cached
        capacityCalc = lambda k, v: 1 #calculate the capacity of the value
    ):
        """ """
        self.capacity = capacity
        self.hashCalc = hashCalc
        self.valueCalc = valueCalc
        self.sideEffectsCalc = sideEffectsCalc
        self.sideEffectsFunc = sideEffectsFunc
        self.isValueCacheableCalc = isValueCacheableCalc
        self.capacityCalc = capacityCalc
        self.__init()
        
    def __init(self):
        self.mru = UseNode(`'<unused value>'`, '<*initially unused node*>') # ``for test
        self.mru.older = self.mru.newer = self.mru  # init circular list
        self.nodeSize = 1
        self.nodeDict = dict([(self.mru.hkey, self.mru)])

    def getValue(self, *args, **kw):  # magically hidden whether lookup or calc
        """
        Get value from cache or calcuate a new value using user function.
        Either way, make the new value the most recently used, replacing
        the least recently used if cache is full.
        """    
        return self.getOrCalcValue(self.valueCalc, hashCalc=self.hashCalc,
                sideEffectsFunc=self.sideEffectsFunc, sideEffectsCalc=self.sideEffectsCalc,
                                isValueCacheableCalc=self.isValueCacheableCalc,*args, **kw)
    
    def getOrCalcValue(self, valueCalc, *args, **kw):
        '''
        Like getValue() except you must specify the valueCalc function and (optionally)
        hashCalc, sideEffectCalc, sideEffectsFunc and isValueCacheableCalc as keyword arguments.
        Use this when valueCalc may vary or when valueCalc shouldn't be part of the cache or the owner of the cache.

        self.valueCalc, self.hashCalc, self.sideEffectsCalc, etc. are all ignored by this function.
        '''
        if kw.has_key('hashCalc'):
            hashCalc = kw['hashCalc']
            del kw['hashCalc']
        else:
            hashCalc = None

        if kw.has_key('sideEffectsCalc'):
            sideEffectsCalc = kw['sideEffectsCalc']
            del kw['sideEffectsCalc']
        else:
            sideEffectsCalc = None
            
        if kw.has_key('sideEffectsFunc'):
            sideEffectsFunc = kw['sideEffectsFunc']
            del kw['sideEffectsFunc']
        else:
            sideEffectsFunc = None

        if kw.has_key('isValueCacheableCalc'):
            isValueCacheableCalc = kw['isValueCacheableCalc']
            del kw['isValueCacheableCalc']
        else:
            isValueCacheableCalc = None

        if self.capacity == 0: #no cache, so just execute valueCalc
            return valueCalc(*args, **kw)
            
        if hashCalc:
            try: 
                hkey = hashCalc(*args, **kw)
            except NotCacheable: #can't calculate a key
                return valueCalc(*args, **kw)
        else:
            hkey = args # use tuple of args as default key for first stage LU
            #warning: kw args will not be part of key
        try:
            node = self.nodeDict[hkey]
            if self.debug: print 'found key', hkey, 'value', node.value
            assert node.hkey == hkey
            #if node.invalidate and node.invalidate(node.value, *args, **kw):
            #    self.removeNode(node)
            #    raise KeyError 
            if sideEffectsFunc:
                #print 'found key:\n', hkey, '\n value:\n', node.value
                sideEffectsFunc(node.value, node.sideEffects, *args, **kw)            
            value = node.value
        except KeyError:
            # here we know we can't get to value
            # calculate new value
            value = valueCalc(*args, **kw)

            if self.capacityCalc(hkey, value) > self.capacity:
                return value #too big to be cached
            #note this check doesn't take into account the current
            #nodeSize so the cache can grow to just less than double the capacity
            
            if isValueCacheableCalc and not isValueCacheableCalc(hkey, value, *args, **kw):
                return value #value isn't cacheable
            
            if sideEffectsCalc:
                sideEffects = sideEffectsCalc(value, *args, **kw)
            else:
                sideEffects = None

            # get mru use node if cache is full, else make new node
            lru = self.mru.newer    # newer than mru circularly goes to lru node
            if self.nodeSize<self.capacity:
                # put new node between existing lru and mru
                node = UseNode(value, hkey, self.mru, lru)
                node.sideEffects = sideEffects
                self.nodeSize +=self.capacityCalc(hkey, value)
                # update links on both sides
                self.mru.newer = node     # newer from old mru is new mru
                lru.older = node    # older than lru poits circularly to mru
                # make new node the mru
                self.mru = node
            else:
                # position of lru node is correct for becoming mru so
                # jusr replace value and hkey #
                self.nodeSize -= self.capacityCalc(lru.hkey, lru.value)
                lru.value = value
                lru.sideEffects = sideEffects
                # delete invalidated key->node mapping
                del self.nodeDict[lru.hkey]
                lru.hkey = hkey
                self.nodeSize += self.capacityCalc(lru.hkey, lru.value)
                self.mru = lru # new lru is next newer from before
            self.nodeDict[hkey] = self.mru      # add new key->node mapping
            return value
            
        # Here we have a valid node. Just update its position in linked lru list
        # we want take node from older <=> node <=> newer
        # and put it in lru <=> node <=> mru and then make new node the mru
        # first cut it out unless it's first or last
        if node is self.mru:            # nothing to do
            return value
        lru = self.mru.newer            # circles from newest to oldest
        if node is lru:
            self.mru = lru              # just backs up the circle one notch
            return value
        # must be between somewhere, so cut it out first
        node.older.newer = node.newer   # older neighbor points to newer neighbor
        node.newer.older = node.older   # newer neighbor points to older neighbor
        # then put it between current lru and mru
        node.older = self.mru           # current mru is now older
        self.mru.newer = node
        node.newer = lru                # newer than new mru circles to lru
        lru.older = node
        self.mru = node                 # new node is new mru
        return value

    def removeNode(self, node):
        assert node.older is not None #can't remove the first node
        node.older.newer = node.newer
        self.nodeSize -= self.capacityCalc(node.hkey, node.value)
        del self.nodeDict[node.hkey]                

    def clear(self):
        """
        Clear out circular list and dictionary of cached nodes.
        Re-init empty with same capacity and user functions
        for posssible continued use.
        """
        this = self.mru
        lru = this.newer
        while 1:
            next = this.older
            this.older = this.newer = None
            del this
            this = next
            if this is lru: break
        this.older = this.newer = None
        del this
        self.nodeDict.clear()
        # re-init with previous parameters
        self.__init()

####################
# test stuff follows 

def testcalc(*args):    # plays role of user valueCalc
    return '<V:%s>' % `args`
    
def testhash(*args):    # plays role of user hashCalc
    return '<H:%s>' % `args`
    
def test():
    cache = MRUCache(5, testcalc, testhash)

    def mrustr(mru):
        node = mru; s=[]
        while 1:
            s.append(node.value.split("'")[1])
            node = node.older
            if node is mru: break
        return ''.join(s)
            
    def dosome(s):
        sbef = mrustr(cache.mru)
        for calcArg in s:
            v = cache.getValue(calcArg)
            print '\n--- getValue(%s) ---\n' % calcArg
            mru = node = cache.mru
            while 1:
                print node.hkey, node.value, '(older:%s, newer:%s)'%(
                    node.older.hkey, node.newer.hkey)
                node = node.older
                if node is mru: break
        saft = mrustr(cache.mru)
        print 'MRU %s +refs %s => %s' %(sbef,s,saft)
    dosome('aabcdef')   # leaves mru..lru = fedcb
    dosome('fb')        # bfedc
    dosome('f')         # fbedc
    dosome('d')         # dfbec
    cache.clear()
    for k,v in vars(cache).items():
        print '%12s = %s' % (`k`,`v`)
    dosome(')-;? ')
    cache.clear()
    for k,v in vars(cache).items():
        print '%12s = %s' % (`k`,`v`)

if __name__ == '__main__':
    test()
