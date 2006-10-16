"""
    General purpose utilities

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from __future__ import generators
import os.path
import os, sys, sha, types, re, copy
from stat import *
from time import *
from types import *
from binascii import unhexlify, b2a_base64

from rx.htmlfilter import * #for backwards compatiblity

if sys.version_info < (2, 3):
    def enumerate(collection):
        'Generates an indexed series:  (0,coll[0]), (1,coll[1]) ...'     
        i = 0
        it = iter(collection)
        while 1:
            yield (i, it.next())
            i += 1
    __builtins__.enumerate = enumerate
    
class NotSetType(object):
    '''use when None is a valid value'''
    
NotSet = NotSetType()

def kw2dict(**kw):
    #not needed in python 2.3, dict ctor does the same thing
    return kw

_flattenTypes = (list,tuple, GeneratorType, type({}.iteritems()) )
def flattenSeq(seq, depth=0xFFFF, flattenTypes=None):
    '''
    >>> list(flattenSeq([ [1,2], 3, [4,5]]))
    [1, 2, 3, 4, 5]
    >>> list(flattenSeq([ [1,2], 3, [4,5]], 0 ))
    [[1, 2], 3, [4, 5]]
    >>>
    >>> list(flattenSeq([ [1,2], 3, [4,5]], 1 ))
    [1, 2, 3, 4, 5]
    >>>
    >>> list(flattenSeq([ [1,2], 3, [4,[5] ]], 1 ))
    [1, 2, 3, 4, [5]]
'''
    if flattenTypes is None:
        flattenTypes = _flattenTypes
    for a in seq:
        if depth > 0 and isinstance(a, flattenTypes):
            for i in flattenSeq(a, depth-1):
                yield i
        else:
            yield a

def bisect_left(a, x, cmp=cmp, lo=0, hi=None):
    """
    Like bisect.bisect_left except it takes a comparision function.
    
    Return the index where to insert item x in list a, assuming a is sorted.

    The return value i is such that all e in a[:i] have e < x, and all e in
    a[i:] have e >= x.  So if x already appears in the list, i points just
    before the leftmost x already there.

    Optional args lo (default 0) and hi (default len(a)) bound the
    slice of a to be searched.
    """

    if hi is None:
        hi = len(a)
    while lo < hi:
        mid = (lo+hi)//2        
        if cmp(a[mid],x) < 0: lo = mid+1
        else: hi = mid
    return lo

import threading
try:
    threading.local
except AttributeError:
    #for versions < Python 2.4
    #copied from 2.4's _threading_local.py
    class _localbase(object):
        __slots__ = '_local__key', '_local__args', '_local__lock'

        def __new__(cls, *args, **kw):
            self = object.__new__(cls)
            key = '_local__key', 'thread.local.' + str(id(self))
            object.__setattr__(self, '_local__key', key)
            object.__setattr__(self, '_local__args', (args, kw))
            object.__setattr__(self, '_local__lock', RLock())

            if args or kw and (cls.__init__ is object.__init__):
                raise TypeError("Initialization arguments are not supported")

            # We need to create the thread dict in anticipation of
            # __init__ being called, to make sire we don't cal it
            # again ourselves.
            dict = object.__getattribute__(self, '__dict__')
            currentThread().__dict__[key] = dict

            return self

    def _patch(self):
        key = object.__getattribute__(self, '_local__key')
        d = currentThread().__dict__.get(key)
        if d is None:
            d = {}
            currentThread().__dict__[key] = d
            object.__setattr__(self, '__dict__', d)

            # we have a new instance dict, so call out __init__ if we have
            # one
            cls = type(self)
            if cls.__init__ is not object.__init__:
                args, kw = object.__getattribute__(self, '_local__args')
                cls.__init__(self, *args, **kw)
        else:
            object.__setattr__(self, '__dict__', d)

    class local(_localbase):

        def __getattribute__(self, name):
            lock = object.__getattribute__(self, '_local__lock')
            lock.acquire()
            try:
                _patch(self)
                return object.__getattribute__(self, name)
            finally:
                lock.release()

        def __setattr__(self, name, value):
            lock = object.__getattribute__(self, '_local__lock')
            lock.acquire()
            try:
                _patch(self)
                return object.__setattr__(self, name, value)
            finally:
                lock.release()

        def __delattr__(self, name):
            lock = object.__getattribute__(self, '_local__lock')
            lock.acquire()
            try:
                _patch(self)
                return object.__delattr__(self, name)
            finally:
                lock.release()


        def __del__():
            threading_enumerate = enumerate
            __getattribute__ = object.__getattribute__

            def __del__(self):
                key = __getattribute__(self, '_local__key')

                try:
                    threads = list(threading_enumerate())
                except:
                    # if enumerate fails, as it seems to do during
                    # shutdown, we'll skip cleanup under the assumption
                    # that there is nothing to clean up
                    return

                for thread in threads:
                    try:
                        __dict__ = thread.__dict__
                    except AttributeError:
                        # Thread is dying, rest in peace
                        continue

                    if key in __dict__:
                        try:
                            del __dict__[key]
                        except KeyError:
                            pass # didn't have anything in this thread

            return __del__
        __del__ = __del__()
        
    from threading import currentThread, enumerate, RLock
        
    threading.local = local 

class object_with_threadlocals(object):    
    '''
    Creates an attribute whose value will be local to the current
    thread.
    Deleting an attribute will delete it for all threads.

    usage:
        class HasThreadLocals(object_with_threadlocals):
            def __init__(self, bar):
                #set values that will initialize across every thread
                self.initThreadLocals(tl1 = 1, tl2 = bar)
    '''

    def __init__(self, **kw):
        return self.initThreadLocals(**kw)
        
    def initThreadLocals(self, **kw):    
        self._locals = threading.local()
        for propname, initValue in kw.items():
            defaultValueAttrName = '__' + propname + '_initValue'
            setattr(self, defaultValueAttrName, initValue)
            prop = getattr(self, propname, None)
            if not isinstance(prop, object_with_threadlocals._threadlocalattribute):
                self._createThreadLocalProp(propname, defaultValueAttrName)

    def _createThreadLocalProp(self, propname, defaultValueAttrName):
        def get(self):
            try:
                return getattr(self._locals, propname)
            except AttributeError:
                value = getattr(self, defaultValueAttrName)
                setattr(self._locals, propname, value)
                return value

        def set(self, value):
            setattr(self._locals, propname, value)
            
        prop = self._threadlocalattribute(propname, get, set, doc='thread local property for ' + propname)
        setattr(self.__class__, propname, prop)                 

    class _threadlocalattribute(property):
        def __init__(self, propname, *args, **kw):
            self.name = propname
            return property.__init__(self, *args, **kw)
    

def htmlQuote(data):
    return data.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def diff(new, old, cutoffOffset = -100, sep = '\n'):
    '''
    returns a list of changes needed to transform the first string to the second unless the length
    of the list of changes is greater the length of the old content itself plus 
    the cutoffOffset, in which case None is returned.
    '''
    maxlen = len(old) + cutoffOffset
    old = old.split(sep) 
    new = new.split(sep)     
    import difflib
    cruncher = difflib.SequenceMatcher(None, new, old)
    return opcodes2Patch(new, old, cruncher.get_opcodes(), maxlen)

##def merge3(base, first, second):
##    #compare first set changes with second set of changes
##    #if any of the ranges overlap its a conflict
##    #for each change

##    
##    old = old.split(sep) 
##    new = new.split(sep)     
##    import difflib
##    cruncher = difflib.SequenceMatcher(None, new, old)
##    changeset1 = cruncher1.get_opcodes()
##    ranges1 = [(alo, ahi) for tag, alo, ahi, blo, bhi in changeset1
##       if tag != 'equals']
##    ranges1.sort()
##
##    changeset2 = cruncher2.get_opcodes()
##    ranges2 = [(alo, ahi) for tag, alo, ahi, blo, bhi in changeset2
##       if tag != 'equals']
##    ranges2.sort()
##    range2 = iter(range2)
##    for lo, hi in range1: pass
##
##def merge3ToPatch(new1, old, opcodes1, new2, opcodes2):
##    '''
##    Converts a list of opcodes as returned by difflib.SequenceMatcher.get_opcodes()
##    into a list that can be applied to the first sequence using patchList() or patch(),
##    allowing the second list to be discarded.
##    '''
##    changes = []
##    patchlen = 0
##    offset = 0    
##    for tag, alo, ahi, blo, bhi in opcodes1:#to turn a into b
##        clo, chi = opcodes2.next()
##        if clo < alo:
##            if chi < ahi: #overlapping change: conflict
##                #for each new version, find the content that covers the overlapping ranges
##                lo = min(alo1, alo2)
##                hi = max(ahi1, ahi2)
##                #...keep looking left and right make the sure the outer overlap doesn't overlap with another change
##                changes.append( ( 'c', alo1+offset, ahi2+offset, old1[blo:bhi] ))
##            else:
##                updatePatch(changes, old, offset, patchlen, tag2, alo2, ahi2, blo2, bhi2)
##        else:
##            if clo < ahi: #overlapping change: conflict
##                'c'
##            else:
##                updatePatch(changes, old, offset, patchlen, tag1, alo1, ahi1, blo1, bhi1)
##    return changes
                
def updatePatch(changes, old, offset, patchlen, tag, alo, ahi, blo, bhi, maxlen=0):
    if tag == 'replace':        
        #g = self._fancy_replace(a, alo, ahi, b, blo, bhi)            
        changes.append( ( 'r', alo+offset, ahi+offset, old[blo:bhi] ))
        offset += (bhi - blo) - (ahi - alo)
        if maxlen:
            patchlen = reduce(lambda x, y: x + len(y), old[blo:bhi], patchlen)
    elif tag == 'delete':            
        changes.append( ( 'd', alo+offset, ahi+offset) )
        offset -= ahi - alo
    elif tag == 'insert':            
        changes.append( ( 'i', alo+offset, old[blo:bhi] ))
        offset += bhi - blo
        if maxlen:
            patchlen = reduce(lambda x, y: x + len(y), old[blo:bhi], patchlen)
    if patchlen > maxlen:
        return None #don't bother
    return offset, patchlen
            
def opcodes2Patch(new, old, opcodes, maxlen = 0):
    '''
    Converts a list of opcodes as returned by difflib.SequenceMatcher.get_opcodes()
    into a list that can be applied to the first sequence using patchList() or patch(),
    allowing the second list to be discarded.
    '''
    changes = []
    patchlen = 0
    offset = 0    
    for tag, alo, ahi, blo, bhi in opcodes:#to turn a into bn
        retVal = updatePatch(changes, old, offset, patchlen, tag, alo, ahi, blo, bhi, maxlen)
        if retVal is None:
            return None #don't bother
        else:
            offset, patchlen = retVal
    return changes

def patch(base, patch, sep = '\n'):
    base = base.split(sep)
    for op in patch:
        if op[0] == 'r':
            base[op[1]:op[2]] = op[3]
        elif op[0] == 'd':
            del base[ op[1]:op[2]]
        elif op[0] == 'i':
            base.insert(op[1], sep.join(op[2]) )
        elif op[0] == 'c':
            #todo: 'c' not yet implemented
            base.insert(op[1], '<<<<<')
            base.insert(op[1], sep.join(op[2]) )
            base.insert(op[1], '=====')
            base.insert(op[1], sep.join(op[2]) )
            base.insert(op[1], '>>>>>')            
    return sep.join(base)

def patchList(base, patch):
    for op in patch:
        if op[0] == 'r':
            base[op[1]:op[2]] = op[3]
        elif op[0] == 'd':
            del base[ op[1]:op[2]]
        elif op[0] == 'i':
            base[op[1]:op[1]] = op[2]    

def removeDupsFromSortedList(aList):       
    def removeDups(x, y):
        if not x or x[-1] != y:
            x.append(y)
        return x
    return reduce(removeDups, aList, [])

def diffSortedList(oldList, newList, cmp=cmp):
    '''
    Returns a list of instructions for turning the first list 
    into the second assuming they both sorted lists of comparable objects
    
    The instructions will be equivalent to the list returned by
    difflib.SequenceMatcher.get_opcodes()

    An optional comparision function can be specified.    
    '''
    opcodes = []
    nstart = nstop = ostart = ostop = 0

    try:
        last = 'i'            
        old = oldList[ostop]            
        
        last = 'd'
        new = newList[nstop]     
        while 1:
            while cmp(old,new) < 0:
                last = 'i'
                ostop += 1                            
                old = oldList[ostop]                
            if ostop > ostart:
                #delete the items less than new
                op = [ 'delete', ostart, ostop, None, None]
                opcodes.append( op )
                ostart = ostop

            assert cmp(old, new) >= 0
            if cmp(old, new) == 0:                
                last = 'i='
                ostart = ostop = ostop+1            
                old = oldList[ostop]
                
                last = 'd'
                nstart = nstop = nstop+1
                new = newList[nstop]     
      
            while cmp(old, new) > 0:
                last = 'd'
                nstop += 1 
                new = newList[nstop]                                
            if nstop > nstart:
                #add
                op = [ 'insert', ostart, ostop, nstart, nstop]
                opcodes.append( op )
                nstart = nstop

            assert cmp(old, new) <= 0
            
            if cmp(old, new) == 0:
                last = 'i='
                ostart = ostop = ostop+1            
                old = oldList[ostop]                
                
                last = 'd'
                nstart = nstop = nstop+1
                new = newList[nstop]                     
    except IndexError:
        #we're done
        if last[0] == 'i':
            if last[-1] == '=':
                try:
                    nstart = nstop = nstop+1
                    new = newList[nstop]
                except IndexError:
                    return opcodes #at end of both lists so we're done
            
            if ostop > ostart:
                #delete the items less than new
                op = [ 'delete', ostart, ostop, None, None]
                opcodes.append( op )
            if len(newList) > nstop:
                op = [ 'insert', ostop, ostop, nstop, len(newList)]
                opcodes.append( op )                
        else:
            if nstop > nstart:
                #add
                op = [ 'insert', ostart, ostop, nstart, nstop]
                opcodes.append( op )                            
            op = [ 'delete', ostop, len(oldList), None, None]
            opcodes.append( op )

    return opcodes

def walkDir(path, fileFunc, *funcArgs, **kw):
    path = os.path.normpath(path).replace(os.sep, '/')
    assert S_ISDIR( os.stat(path)[ST_MODE] )

    def _walkDir(path, recurse, funcArgs, kw):
        '''recursively descend the directory rooted at dir
        '''
        for f in os.listdir(path):
            pathname = '%s/%s' % (path, f) #note: as of 2.2 listdir() doesn't return unicode                        
            mode = os.stat(pathname)[ST_MODE]
            if S_ISDIR(mode):
                # It's a directory, recurse into it
                if recurse:
                    recurse -= 1
                    if not dirFunc:
                        _walkDir(pathname, recurse, funcArgs, kw)
                    else:
                        dirFunc(pathname, lambda *args, **kw:
                                _walkDir(pathname, recurse, args, kw), *funcArgs, **kw)   
            elif S_ISREG(mode):
                if fileFunc:
                    fileFunc(pathname, f, *funcArgs, **kw)
            else:
                # Unknown file type, raise an exception
                raise 'unexpected file type: %s' % pathname #todo?

    if kw.has_key('recurse'):
        recurse = kw['recurse']
        assert recurse >= 0
        del kw['recurse']
    else:
        recurse = 0xFFFFFF
    dirFunc = kw.get('dirFunc')
    if not dirFunc:
        _walkDir(path, recurse, funcArgs, kw)
    else:
        del kw['dirFunc']
        return dirFunc(path, lambda *args, **kw: _walkDir(path, recurse, args, kw), *funcArgs, **kw)

def sanitizeFilePath(filepath): #as in "sanity"
    if sys.platform != 'win32':
        return filepath    
    import win32api
    try:
        return win32api.GetShortPathName(filepath.replace('/','\\') ).replace('%','%%')
    except:        
        return filepath

def nilsimsa(filepath):
    filepath = sanitizeFilePath(filepath) #todo nilsisma doesn't like ` in filesnames -- but are ' ok
    tries=0
    while 1:
        try:
            val = execcmd('\\cygwin\\usr\\local\\bin\\nilsimsa "' + filepath + '"')[:64]#just read the first 64 bytes of first line
            #todo: don't hard code path
            assert long(val, 16) #this will throw an exception if input isn't valid
            return val #e.g. 'e932f4a082fb0aa8b6926cb190145188d583e9520f9e87ab8070cec1c304648f' 
        except:
            tries += 1
            if tries > 3:
                raise
            sleep(1)

def execcmd(cmdline, successVal = None):
    stdout = os.popen(cmdline)
    val = stdout.read()
    err = stdout.close()        
    assert err == successVal, cmdline + " returned an error: " + str(err) + val#todo error handling
    return val

def fillpopcount():
 from array import array
 popcount = array('B') #unsigned char mapped to python int 
 for i in range(256):
     popcount.append(0)
     for j in range(8):
         popcount[i]+= 1&(i>>j)
 return popcount

popcount = fillpopcount()
def compareNilsimsa(n1, n2, nilsimsaThreshold):    
    v1 = unhexlify(n1)
    v2 = unhexlify(n2)
    bits = 0
    for i in range(32):
        bits+=popcount[255&( ord(v1[i])^ord(v2[i]) )];
    bits = 128 - bits    
    if bits >= nilsimsaThreshold:
        return bits 
    else:
        return 0

class Hasher:
    def __init__(self):                         
        self.sha = sha.new()
    def write(self, line):
        #print line
        self.sha.update(line.strip().encode('utf8'))

def shaDigest(filepath):
    BUF = 8192
    sha1 = sha.new()
    shaFile = file(filepath, 'rb', BUF)
    for line in iter(lambda: shaFile.read(BUF), ""):
        sha1.update(line)
    shaFile.close()
    return b2a_base64(sha1.digest())[:-1]
    
def shaDigestString(line):
    sha1 = sha.new()
    sha1.update(line)
    return b2a_base64(sha1.digest())[:-1]
            
def getVolumeInfo(path):
    if sys.platform == 'win32':  #or sys.platform == 'cygwin':
        from win32api import GetVolumeInformation
        path = os.path.abspath(path)
        assert path[1]==':', 'unc not supported yet' #todo
        drive = path[:3]
        #todo: If you are attempting to obtain information about a floppy drive that does not have a floppy disk or a CD-ROM drive that does not have a compact disc, the system displays a message box asking the user to insert a floppy disk or a compact disc, respectively. To prevent the system from displaying this message box, call the SetErrorMode function with SEM_FAILCRITICALERRORS.
        volumeName, volSerialNumber, maxFileLength, flags, fs = GetVolumeInformation(drive)
        import win32file
        driveType = win32file.GetDriveType(drive)            
        driveTypemap = { win32file.DRIVE_UNKNOWN :	'unknown',
                         win32file.DRIVE_NO_ROOT_DIR :	'unknown',
                         win32file.DRIVE_REMOVABLE : 'removable',
                         win32file.DRIVE_FIXED : 'local',
                         win32file.DRIVE_REMOTE : 'remote',
                         win32file.DRIVE_CDROM : 'removable',
                         win32file.DRIVE_RAMDISK : 'local' }
        volumeType = driveTypemap[driveType]
        return volumeName, volumeType, volSerialNumber
    else:
        assert 0, 'NYI!' #todo
    
class InterfaceDelegator:
    '''assumes only methods will be called on this object and the methods always return None'''
    def __init__(self, handlers):
        self.handlers = handlers
    
    def call(self, name, args, kw):
        for h in self.handlers:
            getattr(h, name)(*args, **kw)
        
    def __getattr__(self, name):
        return lambda *args, **kw: self.call(name, args, kw)

class Bitset(object):
    '''
>>> bs = Bitset()
>>> bs[3] = 1
>>> [i for i in bs]
[False, False, False, True]
    '''
    
    def __init__(self):
        self.bits = 0
        self._size = 0
                
    def __setitem__(self, i, v):
        if v:
            self.bits |= (1<<i)
        else:
            self.bits &= ~(1<<i)

        if i+1 > self._size:
            self._size = i+1
            
    def __getitem__(self, i):
        return bool(self.bits & (1<<i))

    def __nonzero__(self):
        return bool(self.bits)
        
    def __len__(self):
        return self._size

    def __iter__(self):
        for i in xrange(self._size):
            yield self[i]

    def append(self, on):
         self.bits <<= 1
         if on:
             self.bits |= 1

class Singleton(type):
    '''from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/102187
    usage:
    class C: __metaclass__=Singleton
    '''
    def __init__(cls,name,bases,dic):
        super(Singleton,cls).__init__(name,bases,dic)
        cls.instance=None
    def __call__(cls,*args,**kw):
        if cls.instance is None:
            cls.instance=super(Singleton,cls).__call__(*args,**kw)
        return cls.instance

class MonkeyPatcher(type):
    '''    
    This metaclass provides a convenient way to patch an existing class instead of defining a subclass.
    This is useful when you need to fix bugs or add critical functionality to a library without
    modifying its source code. It also can be use to write aspect-oriented programming style code where
    methods for a class are defined in separate modules.
    
    usage:
    given a class named NeedsPatching that needs the method 'buggy' patched.
    'unused' never needs to be instantiated, the patching occurs as soon as the class statement is executed.
    
    class unused(NeedsPatching):
        __metaclass__ = MonkeyPatcher

        def buggy(self):           
           self.buggy_old_() 
           self.newFunc()
           
        def newFunc(self):
            pass    
    '''
    
    def __init__(self,name,bases,dic):
        assert len(bases) == 1
        self.base = bases[0]
        for name, value in dic.items():
            if name in ['__metaclass__', '__module__']:
                continue
            try:
                oldValue = getattr(self.base,name)
                hasOldValue = True
            except:
                hasOldValue = False
            setattr(self.base, name, value)
            if hasOldValue:                
                setattr(self.base, name+'_old_', oldValue)

    def __call__(self,*args,**kw):
        '''instantiate the base object'''        
        return self.base.__metaclass__.__call__(*args,**kw)

class NestedException(Exception):
    def __init__(self, msg = None,useNested = False):
        if not msg is None:
            self.msg = msg
        self.nested_exc_info = sys.exc_info()
        self.useNested = useNested
        if useNested and self.nested_exc_info[0]:
            if self.nested_exc_info[1]:
                args = getattr(self.nested_exc_info[1], 'args', ())
            else: #nested_exc_info[1] is None, a string must have been raised
                args = self.nested_exc_info[0]
        else:
            args = msg
        Exception.__init__(self, args)
            
class DynaException(Exception):
    def __init__(self, msg = None):
        if not msg is None:
            self.msg = msg        
        Exception.__init__(self, msg)
    
class DynaExceptionFactory(object):
    '''
    Defines an Exception class
    usage:
    _defexception = DynaExceptionFactory(__name__)
    _defexception('not found error') #defines exception NotFoundError
    ...
    raise NotFoundError()
    '''    
    def __init__(self, module, base = DynaException):
        self.module = sys.modules[module] #we assume the module has already been loaded
        #self.module = __import__(module) #doesn't work for package -- see the docs for __import__ 
        self.base = base
                        
    def __call__(self, name, msg = None):
        classname = ''.join([word[0].upper()+word[1:] for word in name.split()]) #can't use title(), it makes other characters lower
        dynaexception = getattr(self.module, classname, None)
        if dynaexception is None:
            #create a new class derived from the base Exception type
            msg = msg or name            
            dynaexception = type(self.base)(classname, (self.base,), { 'msg': msg })
            #print 'setting', classname, 'on', self.module, 'with', dynaexception
            #import traceback; print traceback.print_stack(file=sys.stderr)
            setattr(self.module, classname, dynaexception)
        return dynaexception

try:
    from Ft.Xml import XPath, Xslt, Lib, EMPTY_NAMESPACE
    import Ft.Xml.Xslt.XPathExtensions

    def _visit(self, fields, pre=None, post=None):        
        return pre(self, fields, *(post or ()))
        
        if pre:
            if not pre(self):
                return False
        for field in fields:
            if field is not None:
                if not field.visit(pre=pre, post=post):
                    return False
        if post:
            if not post(self):
                return False
        return True
            
    def _visit0(self, pre=None, post=None):
        return pre(self, (), *(post or ()))    
    
        if pre:
            if not pre(self):
                return False
        if post:
            if not post(self):
                return False
        return True
    
    def _visitlr(self, pre=None, post=None):
        return _visit(self, ['_left', '_right'], pre=pre, post=post)

    def _additiveVisit(self, pre=None, post=None):
        fields = []
        if not self._leftLit:            
            fields.append('_left')
        if not self._rightLit:
            fields.append('_right')

        return pre(self, fields, *(post or ()))

        if pre:
            if not pre(self):
                return False
        if not self._leftLit:            
            if not self._left.visit(pre=pre, post=post):
                return False
        if not self._rightLit:
            if not self._right.visit(pre=pre, post=post):
                return False
        if post:
            if not post(self):
                return False
        return True
                            
    XPath.ParsedExpr.FunctionCall.visit = lambda self, pre=None, post=None: _visit(self, range(len(self._args)), pre, post)
    XPath.ParsedExpr.ParsedNLiteralExpr.visit = _visit0
    XPath.ParsedExpr.ParsedLiteralExpr.visit = _visit0    
    XPath.ParsedExpr.ParsedVariableReferenceExpr.visit = _visit0
    XPath.ParsedExpr.ParsedUnionExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedPathExpr.visit = _visitlr #may have implicit decendent-or-self step too
    XPath.ParsedExpr.ParsedFilterExpr.visit = \
            lambda self, pre=None, post=None: _visit(self, ['_filter', '_predicates'], pre, post)
    XPath.ParsedExpr.ParsedOrExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedAndExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedEqualityExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedRelationalExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedMultiplicativeExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedAdditiveExpr.visit = _additiveVisit
    XPath.ParsedExpr.ParsedUnaryExpr.visit = lambda self, visitor: _visit(self, ['_exp'], pre, post)
    XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath.visit = \
                    lambda self, pre=None, post=None: _visit(self, ['_rel'], pre, post)
    #has implicit decendent-or-self step too:
    XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath.visit = _visitlr
    XPath.ParsedAbsoluteLocationPath.ParsedAbsoluteLocationPath.visit = \
                    lambda self, pre=None, post=None: _visit(self, ['_child'], pre, post)
    XPath.ParsedAxisSpecifier.AxisSpecifier.visit = _visit0
    XPath.ParsedNodeTest.NodeTestBase.visit = _visit0
    XPath.ParsedPredicateList.ParsedPredicateList.visit = \
                    lambda self, pre=None, post=None: _visit(self, range(len(self._predicates)), pre, post)
    XPath.ParsedRelativeLocationPath.ParsedRelativeLocationPath.visit = _visitlr
    XPath.ParsedStep.ParsedStep.visit = \
            lambda self, pre=None, post=None: _visit(self, ['_axis', '_nodeTest', '_predicates'], pre, post)
    XPath.ParsedStep.ParsedAbbreviatedStep.visit = _visit0
    XPath.ParsedStep.ParsedNodeSetFunction.visit = \
            lambda self, pre=None, post=None: _visit(self, ['_function', '_predicates'], pre, post)
    Xslt.XPathExtensions.SortedExpression.visit = \
            lambda self, pre=None, post=None: _visit(self, ['expression'], pre, post)
    Xslt.XPathExtensions.RtfExpr.visit = _visit0

    class _Ancestors(list):
        
        def __setitem__(self, i, value):
            node, field = self[i]
            if isinstance(node, XPath.ParsedExpr.FunctionCall):            
                node._args[field] = value
                if field < 3:
                    fieldName = '_arg' + str(field)
                    if hasattr(node, fieldName):
                        setattr(node, fieldName, value)
            elif isinstance(node, XPath.ParsedPredicateList.ParsedPredicateList):
                node._predicates[field] = value
            else:
                setattr(node, field, value)

    class XPathExprVisitor(object):
        DESCEND = -1
        STOP = 0
        NEXT = 1
            
        def __init__(self):
            self.ancestors = _Ancestors()
            self.currentNode = None
            self.currentFields = None

        def _dispatch(self, node, fields, *args):
            nodeName = node.__class__.__name__
            if nodeName.startswith('FunctionCall'):
                nodeName = 'FunctionCall'
            func = getattr(self, nodeName, None)
            if not func:
                #flatten class hierarchy:
                if isinstance(node, XPath.ParsedAxisSpecifier.AxisSpecifier):
                    nodeName = 'AxisSpecifier'
                elif isinstance(node, XPath.ParsedNodeTest.NodeTestBase):
                    nodeName = 'NodeTestBase'
                func = getattr(self, nodeName, None)
            if func:            
                ret = func(node,*args)
            else:
                ret = self.DESCEND
            if ret == self.DESCEND:
                return self.descend(node, fields, *args)
            else:
                return ret

        def getAncestors(self, reversed=False):
            if reversed:
                rev = copy.copy(self.ancestors)
                rev.reverse()
                return rev
            else:
                return self.ancestors
                        
        def descend(self, node=None, fields=None, *args):
            '''
            Visit methods may call this with a modified list of fields.
            '''
            if node is None:
                node = self.currentNode
            if fields is None:
                fields = self.currentFields

            if isinstance(node, XPath.ParsedExpr.FunctionCall):            
                attr = '_args'
            elif isinstance(node, XPath.ParsedPredicateList.ParsedPredicateList):
                attr = '_predicates'
            else:
                attr = None
                
            stopped = False
            remainingFields = []
            for field in fields:
                if stopped:
                    remainingFields.append(fields)
                else:
                    if attr:
                        fieldValue = getattr(node, attr)[field]
                    else:
                        fieldValue = getattr(node, field)
                    if fieldValue:
                        self.ancestors.append( (node, field) )
                        try:
                            res = fieldValue.visit(self.visit, args)
                        finally:
                            self.ancestors.pop()
                        if res == self.STOP:
                            stopped = True
                            
            self.currentFields = remainingFields
            if stopped:
                return self.STOP
            else:
                return self.NEXT

        def visit(self, node, fields, *args):
            oldNode = self.currentNode
            oldFields = self.currentFields            
            self.currentNode = node
            self.currentFields = fields
            try:
                return self._dispatch(node, fields, *args)
            finally:
                self.currentNode = oldNode
                self.currentFields = oldFields

    def _iter(self, fields):
        yield self
        for field in fields:
            if field is not None:
                for node in field:
                    yield node

    def _iter0(self):
        yield self
        
    def _iterlr(self):    
        return _iter(self, [self._left, self._right])

    def _additiveIter(self):
        yield self
        if not self._leftLit:
            for node in self._left:
                yield node
        if not self._rightLit:
            for node in self._right:
                yield node

    XPath.ParsedExpr.FunctionCall.__iter__ = lambda self: _iter(self, self._args)
    XPath.ParsedExpr.ParsedNLiteralExpr.__iter__ = _iter0
    XPath.ParsedExpr.ParsedLiteralExpr.__iter__ = _iter0    
    XPath.ParsedExpr.ParsedVariableReferenceExpr.__iter__ = _iter0
    XPath.ParsedExpr.ParsedUnionExpr.__iter__ = _iterlr
    XPath.ParsedExpr.ParsedPathExpr.__iter__ = _iterlr #may have implicit decendent-or-self step too
    XPath.ParsedExpr.ParsedFilterExpr.__iter__ = lambda self: _iter(self, [self._filter, self._predicates])
    XPath.ParsedExpr.ParsedOrExpr.__iter__ = _iterlr
    XPath.ParsedExpr.ParsedAndExpr.__iter__ = _iterlr
    XPath.ParsedExpr.ParsedEqualityExpr.__iter__ = _iterlr
    XPath.ParsedExpr.ParsedRelationalExpr.__iter__ = _iterlr
    XPath.ParsedExpr.ParsedMultiplicativeExpr.__iter__ = _iterlr
    XPath.ParsedExpr.ParsedAdditiveExpr.__iter__ = _additiveIter
    XPath.ParsedExpr.ParsedUnaryExpr.__iter__ = lambda self: _iter(self, [self._exp])
    XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath.__iter__ = \
                    lambda self: _iter(self, [self._rel])
    #has implicit decendent-or-self step too:
    XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath.__iter__ = _iterlr
    XPath.ParsedAbsoluteLocationPath.ParsedAbsoluteLocationPath.__iter__ = \
                    lambda self: _iter(self, [self._child])
    XPath.ParsedAxisSpecifier.AxisSpecifier.__iter__ = _iter0
    XPath.ParsedNodeTest.NodeTestBase.__iter__ = _iter0
    XPath.ParsedPredicateList.ParsedPredicateList.__iter__ = lambda self: _iter(self, self._predicates)
    XPath.ParsedRelativeLocationPath.ParsedRelativeLocationPath.__iter__ = _iterlr
    XPath.ParsedStep.ParsedStep.__iter__ = \
            lambda self: _iter(self, [self._axis, self._nodeTest, self._predicates])
    XPath.ParsedStep.ParsedAbbreviatedStep.__iter__ = _iter0
    XPath.ParsedStep.ParsedNodeSetFunction.__iter__ = lambda self: _iter(self, [self._function, self._predicates])
    Xslt.XPathExtensions.SortedExpression.__iter__ = lambda self: _iter(self, [self.expression])
    Xslt.XPathExtensions.RtfExpr.__iter__ = _iter0

except ImportError: #don't create a dependency on Ft.Xml.XPath
    pass

