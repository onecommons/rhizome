"""
    glock unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
import unittest
from rx import glock

class glockTestCase(unittest.TestCase):
    def setUp(self):
        self.lockName = 'test.lock'
       
    def tearDown(self):
        pass

    def test1(self):
        #like rx.racoon.getLock()
        lock = glock.GlobalLock(self.lockName, True)
        lock.release()

    def test2(self):
        #like rx.racoon.getLock()
        globalLock = glock.GlobalLock(self.lockName)
        lock = glock.LockGetter(globalLock)
        lock2 = glock.LockGetter(globalLock)
        lock2.release()
        lock.release()

if __name__ == '__main__':
    import sys
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = glockTestCase(test)
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()
 
