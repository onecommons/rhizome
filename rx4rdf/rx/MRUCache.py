# mrucache.py -- defines class MRUCache
# Takes capacity, a valueCalc function, and an optional hashCalc function
# to make an MRU/LRU cache instance with a getValue method that either retrieves
# cached value or calculates a new one. Either way, makes the value MRU.
# Alpha version. NO WARRANTY. Use at your own risk
# Copyright (c) 2002 Bengt Richter 2001-10-05. All rights reserved.
# Use per Python Software Foundation (PSF) license.
# 

class UseNode:
    """For linked list kept in most-recent .. least-recent *use* order"""
    __slots__ = ['value','hkey','older','newer']
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
    def __init__(self,
        capacity,       # max number of simultaneous cache MRU values kept
        valueCalc,      # user function to calculate actual value from args
        hashCalc=None,  # normally takes same args as valueCalc if present
    ):
        """ """
        self.capacity = capacity
        self.hashCalc = hashCalc
        self.valueCalc = valueCalc
        
        self.mru = UseNode(`'<unused value>'`, '<*initially unused node*>') # ``for test
        self.mru.older = self.mru.newer = self.mru  # init circular list
        self.nodeCount = 1
        self.nodeDict = dict([(self.mru.hkey, self.mru)])

    def getValue(self, *args):  # magically hidden whether lookup or calc
        """
        Get value from cache or calcuate a new value using user function.
        Either way, make the new value the most recently used, replacing
        the least recently used if cache is full.
        """
        if self.hashCalc:
            hkey = self.hashCalc(*args)
        else:
            hkey = args         # use tuple of args as default key for first stage LU
        try:
            node = self.nodeDict[hkey]
            assert node.hkey == hkey
        except KeyError:
            # here we know we can't get to value
            # calculate new value
    	    value = self.valueCalc(*args)

            # get mru use node if cache is full, else make new node
            lru = self.mru.newer    # newer than mru circularly goes to lru node
            if self.nodeCount<self.capacity:
                # put new node between existing lru and mru
                node = UseNode(value, hkey, self.mru, lru)
                self.nodeCount += 1
                # update links on both sides
                self.mru.newer = node     # newer from old mru is new mru
                lru.older = node    # older than lru poits circularly to mru
                # make new node the mru
                self.mru = node
            else:
                # position of lru node is correct for becoming mru so
                # jusr replace value and hkey #
                lru.value = value
                # delete invalidated key->node mapping
                del self.nodeDict[lru.hkey]
                lru.hkey = hkey
                self.mru = lru # new lru is next newer from before
            self.nodeDict[hkey] = self.mru      # add new key->node mapping
            return value
            
        # Here we have a valid node. Just update its position in linked lru list
        # we want take node from older <=> node <=> newer
        # and put it in lru <=> node <=> mru and then make new node the mru
        # first cut it out unless it's first or last
        if node is self.mru:            # nothing to do
            return node.value
        lru = self.mru.newer            # circles from newest to oldest
        if node is lru:
            self.mru = lru              # just backs up the circle one notch
            return lru.value
        # must be between somewhere, so cut it out first
        node.older.newer = node.newer   # older neighbor points to newer neighbor
        node.newer.older = node.older   # newer neighbor points to older neighbor
        # then put it between current lru and mru
        node.older = self.mru           # current mru is now older
        self.mru.newer = node
        node.newer = lru                # newer than new mru circles to lru
        lru.older = node
        self.mru = node                 # new node is new mru
        return node.value

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
        self.__init__(self.capacity, self.valueCalc, self.hashCalc)

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