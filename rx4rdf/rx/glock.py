#!/usr/bin/env python
#----------------------------------------------------------------------------
# glock.py:                 Global mutex
#
# See __doc__ string below.
#
# Requires:
#    - Python 1.5.2 or newer (www.python.org)
#    - On windows: win32 extensions installed
#           (http://www.python.org/windows/win32all/win32all.exe)
#    - OS: Unix, Windows.
#
# $Id$
#----------------------------------------------------------------------------
'''
This module defines the class GlobalLock that implements a global
(inter-process) mutex that works on Windows and Unix, using file-locking on
Unix (I also tried this approach on Windows but got some tricky problems so I
ended using a Win32 Mutex).

@see: class L{GlobalLock} for more details.
'''
__version__ = '0.2.' + '$Revision$'[12:-2]
__author__ = 'Richard Gruet', 'rjgruet@yahoo.com'
__date__    = '$Date$'[7:-2], '$Author$'[9:-2]
__since__ = '2000-01-22'
__doc__ += '\n@author: %s (U{%s})\n@version: %s' % (__author__[0],
                                            __author__[1], __version__)
__all__ = ['GlobalLock', 'GlobalLockError', 'NotOwner']

# Imports:
import sys, string, os

lockingDisabled=0
# System-dependent imports for locking implementation:
_windows = (sys.platform == 'win32')

if _windows:
    try:
        import win32event, win32api, pywintypes
    except ImportError:
        lockingDisabled=1
        sys.stderr.write('Warning! The win32 extensions not installed -- locking disabled.\n')
elif sys.platform == 'cygwin':
    lockingDisabled=1
    sys.stderr.write('Warning! locking does not seem to work on cygwin -- locking disabled.\n')
else:   # assume Unix
    try:
        import fcntl
    except ImportError:
        sys.stderr.write("On what kind of OS am I ? (Mac?) I should be on "
                         "Unix but can't import fcntl.\n")
        raise
    import threading

# Exceptions :
# ----------
class GlobalLockError(Exception):
    ''' Error raised by the glock module.
    '''
    pass

class NotOwner(GlobalLockError):
    ''' Attempt to release somebody else's lock.
    '''
    pass


# Constants
# ---------:
if sys.version[:3] < '2.2':
    True, False = 1, 0  # built-in in Python 2.2

#----------------------------------------------------------------------------
class GlobalLock:
#----------------------------------------------------------------------------
    ''' A global mutex.

        B{Specification}
        
         - The lock must act as a global mutex, ie block between different
           candidate processus, but ALSO between different candidate
           threads of the same process.
         
         - It must NOT block in case of reentrant lock request issued by
           the SAME thread.
         - Extraneous unlocks should be ideally harmless.

        B{Implementation}

        In Python there is no portable global lock AFAIK. There is only a
        LOCAL/ in-process Lock mechanism (threading.RLock), so we have to
        implement our own solution:

         - Unix: use fcntl.flock(). Recursive calls OK. Different process OK.
           But <> threads, same process don't block so we have to use an extra
           threading.RLock to fix that point.
         - Windows: We use WIN32 mutex from Python Win32 extensions. Can't use
           std module msvcrt.locking(), because global lock is OK, but
           blocks also for 2 calls from the same thread!
    '''
    def __init__(self, fpath, lockInitially=False):
        ''' Creates (or opens) a global lock.

            @param fpath: Path of the file used as lock target. This is also
                         the global id of the lock. The file will be created
                         if non existent.
            @param lockInitially: if True locks initially.
        '''
        if _windows:
            self.name = string.replace(fpath, '\\', '_')
            self.mutex = win32event.CreateMutex(None, lockInitially, self.name)
        else: # Unix
            self.name = fpath
            self.flock = open(fpath, 'w')
            self.fdlock = self.flock.fileno()
            self.threadLock = threading.RLock()
        if lockInitially:
            self.acquire()

    def __del__(self):
        #print '__del__ called' ##
        try: self.release()
        except: pass
        if _windows:
            win32api.CloseHandle(self.mutex)
        else:
            try: self.flock.close()
            except: pass

    def __repr__(self):
        return '<Global lock @ %s>' % self.name

    def acquire(self):
        ''' Locks. Suspends caller until done.

            On windows an IOError is raised after ~10 sec if the lock
            can't be acquired.
            @exception GlobalLockError: if lock can't be acquired (timeout)
        '''
        if _windows:
            r = win32event.WaitForSingleObject(self.mutex, win32event.INFINITE)
            if r == win32event.WAIT_FAILED:
                raise GlobalLockError("Can't acquire mutex.")
        else:
            # Acquire 1st the global (inter-process) lock:
            try:
                fcntl.flock(self.fdlock, fcntl.LOCK_EX) # blocking
            except IOError: #(errno 13: perm. denied,
                            #       36: Resource deadlock avoided)
                raise GlobalLockError('Cannot acquire lock on "file" %s\n' %
                                        self.name)
            #print 'got file lock.' ##
            # Then acquire the local (inter-thread) lock:
            self.threadLock.acquire()
            #print 'got thread lock.' ##

    def release(self):
        ''' Unlocks. (caller must own the lock!)

            @return: The lock count.
            @exception IOError: if file lock can't be released
            @exception NotOwner: Attempt to release somebody else's lock.
        '''
        if _windows:
            try:
                win32event.ReleaseMutex(self.mutex)
            except pywintypes.error, e:
                errCode, fctName, errMsg =  e.args
                if errCode == 288:
                    raise NotOwner("Attempt to release somebody else's lock")
                else:
                    raise GlobalLockError('%s: err#%d: %s' % (fctName, errCode,
                                                              errMsg))
        else:
            # Acquire 1st the local (inter-thread) lock:
            try:
                self.threadLock.release()
            except AssertionError:
                raise NotOwner("Attempt to release somebody else's lock")

            # Then release the global (inter-process) lock:
            try:
                fcntl.flock(self.fdlock, fcntl.LOCK_UN)
            except IOError: # (errno 13: permission denied)
                raise GlobalLockError('Unlock of file "%s" failed\n' %
                                                            self.name)

class LockGetter:
    '''
    Helper class enabling the "resource acquisition is initialization" pattern.
    The constructor acquires the resource (the lock) and the destructor releases it
    (e.g. when garage collected).
    Because of the subtlies of the behavior of destructors it is recommended to call
    release() instead of using the del statement to explictly release the lock.
    '''
    def __init__(self, globalLock):
        self.globalLock = globalLock
        self.globalLock.acquire()
        
    def __del__(self):
        #print '__del__ called' ##
        if self.globalLock:
            self.globalLock.release()
        
    def release(self):
        self.globalLock.release()
        self.globalLock = None

if lockingDisabled:
    class DummyLock:
        def __init__(self, fpath, lockInitially=False): pass
        def acquire(self): pass
        def release(self): pass
    GlobalLock = DummyLock

#----------------------------------------------------------------------------
def test():
#----------------------------------------------------------------------------
    print 'Testing glock.py...' 
    
    # unfortunately can't test inter-process lock here!
    lockName = 'myFirstLock'
    l = GlobalLock(lockName)
    if not _windows:
        assert os.path.exists(lockName)
    l.acquire()
    l.acquire() # reentrant lock, must not block
    l.release()
    l.release()
    if _windows:
        try: l.release()
        except NotOwner: pass
        else: raise Exception('should have raised a NotOwner exception')

    # Check that <> threads of same process do block:
    import threading, time
    thread = threading.Thread(target=threadMain, args=(l,))
    print 'main: locking...',
    l.acquire()
    print ' done.'
    thread.start()
    time.sleep(3)
    print '\nmain: unlocking...',
    l.release()
    print ' done.'
    time.sleep(0.1)
    
    print '=> Test of glock.py passed.'
    return l

def threadMain(lock):
    print 'thread started(%s).' % lock
    print 'thread: locking (should stay blocked for ~ 3 sec)...',
    lock.acquire()
    print 'thread: locking done.'
    print 'thread: unlocking...',
    lock.release()
    print ' done.'
    print 'thread ended.'

#----------------------------------------------------------------------------
#       M A I N
#----------------------------------------------------------------------------
if __name__ == "__main__":
    l = test()
