"""
    General purpose utilities

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from __future__ import generators
import os.path
import os, sys, sha, types, re
from stat import *
from time import *
from types import *
from binascii import unhexlify, b2a_base64

from rx.htmlfilter import * #for backwards compatiblity

from Ft.Rdf import Util, Model, Statement, OBJECT_TYPE_RESOURCE, OBJECT_TYPE_LITERAL, OBJECT_TYPE_UNKNOWN
from Ft.Rdf.Drivers import Memory

from Ft.Lib import Uuid, Uri
import Ft.Rdf
#note: because we change these values here other modules need to import utils
#before importing any Ft.Rdf modules
Ft.Rdf.BNODE_BASE = 'bnode:'
Ft.Rdf.BNODE_BASE_LEN = len('bnode:')
from Ft.Rdf import BNODE_BASE, BNODE_BASE_LEN

_bNodeCounter  = 0
#like this so this will be a valid bNode token (NTriples only allows alphanumeric, no _ or - etc.
_sessionBNodeUUID = "x%032xx" % Uuid.GenerateUuid()

def generateBnode(name=None):
    """
    Generates blank nodes (bnodes), AKA anonymous resources
    """
    global _bNodeCounter, _sessionBNodeUUID
    _bNodeCounter += 1
    name = name or `_bNodeCounter`    
    return BNODE_BASE + _sessionBNodeUUID +  name

class NotSetType(object):
    '''use when None is a valid value'''
    
NotSet = NotSetType()

def kw2dict(**kw):
    #not needed in python 2.3, dict ctor does the same thing
    return kw

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

def createThreadLocalProperty(name, fget=True, fset=True, fdel=True, doc=None, **kw):
    '''
    usage:
      class foo(object):
         aThreadLocalAttribute = utils.createThreadLocalProperty('__aThreadLocalAttribute')

    A KeyError will be thrown when attempting to get an attribute that has not been set in the current thread.
    For example, if an attribute is set in __init__() and then retrieved in another thread.
    To avoid this, pass an initValue argument, whose value will be used to initialize the attribute.
        
    Deleting an attribute will delete it for all threads.
    '''
    import thread
    if kw.has_key('initValue'):
        initAttr = True
        initValue =  kw['initValue']
        assert len(kw) == 1
    else:
        initAttr = False
        assert len(kw) == 0
        
    def getThreadLocalAttr(self):    
        attr = getattr(self, name, None)
        if attr is None:
            attr = {}
            setattr(self, name, attr)
        if initAttr:            
            return attr.setdefault(thread.get_ident(), initValue)
        else:
            return attr[thread.get_ident()]
    
    def setThreadLocalAttr(self, value):        
        attr = getattr(self, name, None)
        if attr is None:
            attr = {}
            setattr(self, name, attr)            
        attr[thread.get_ident()] = value

    if fget:
        fget = getThreadLocalAttr
    else:
        fget = None

    if fset:
        fset = setThreadLocalAttr
    else:
        fset = None

    if fdel:
        fdel = lambda self: delattr(self, name)
    else:
        fdel = None
        
    return property(fget, fset, fdel, doc)

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

#see w3.org/TR/rdf-testcases/#ntriples 
#todo: assumes utf8 encoding and not string escapes for unicode 
Removed = object()
Comment = object()
def parseTriples(lines, bNodeToURI = lambda x: x, charencoding='utf8'):
    remove = False
    for line in lines:
        line = line.strip()
        if not line: #trailing whitespace
            break;
        if not isinstance(line, unicode):
           line = line.decode(charencoding)            
        if line.startswith('#!remove'): #this extension to NTriples allows us to incrementally update a model using NTriples
            remove = True
            continue
        elif line[0] == '#': #comment
            remove = False
            continue        
        subject, predicate, object = line.split(None,2)
        if subject.startswith('_:'):
            subject = subject[2:] #bNode
            subject = bNodeToURI(subject)
        else:
            subject = subject[1:-1] #uri
            
        if predicate.startswith('_:'):
            predicate = predicate[2:] #bNode
            predicate = bNodeToURI(predicate)
        else:
            assert predicate[0] == '<' and predicate[-1] == '>', 'malformed predicate: %s' % predicate
            predicate = predicate[1:-1] #uri
            
        object = object.strip()        
        if object[0] == '<': #if uri
            object = object[1:object.find('>')]
            objectType = OBJECT_TYPE_RESOURCE
        elif object.startswith('_:'):
            object = object[2:object.rfind('.')].strip()
            object = bNodeToURI(object)
            objectType = OBJECT_TYPE_RESOURCE
        else:                        
            quote = object[0] #add support for using either ' or " (spec says just ")
            endquote = object.rfind(quote)
            literal = object[1:endquote]
            if literal.find('\\') != -1:
                #use split and join to replace even pairs of // with /
                #without have the resulting single / accidently escape the next character
                unescaped = literal.split(r'\\') 
                escaped = [x.replace('\\' + quote, quote).replace(r'\n', '\n').
                             replace(r'\r', '\r').replace(r'\t', '\t') for x in unescaped]
                literal = '\\'.join(escaped) 
            if object[endquote+1]=='@':
                lang = object[endquote+2:object.rfind('.')].strip()
                objectType = lang
            elif object[endquote+1]=='^':                
                objectType = object[endquote+3:object.rfind('.')].strip()
            else:    
                objectType = OBJECT_TYPE_LITERAL
            object = literal
        #print "parsed: ", subject, predicate, object
        if remove:
            remove = False
            yield (Removed, (subject, predicate, object, objectType))
        else:
            if objectType != OBJECT_TYPE_RESOURCE or object:
                #hack to handle malformed NTriples doc -- skip statements that have <> as the object
                yield (subject, predicate, object, objectType)

def DeserializeFromN3File(n3filepath, driver=Memory, dbName='', create=0, scope='',
                        modelName='default', model=None):
    #todo: rename this function to ...NTFile
    if not model:
        if create:
            db = driver.CreateDb(dbName, modelName)
        else:
            db = driver.GetDb(dbName, modelName)
        db.begin()
        model = Model.Model(db)
    else:
        db = model._driver
        
    if isinstance(n3filepath, ( type(''), type(u'') )):
        stream = file(n3filepath, 'r+')
    else:
        stream = n3filepath
        
    #bNodeMap = {}
    #makebNode = lambda bNode: bNodeMap.setdefault(bNode, generateBnode(bNode))
    makebNode = lambda bNode: BNODE_BASE + bNode
    for stmt in parseTriples(stream,  makebNode):
        if stmt[0] is Removed:            
            stmt = stmt[1]
            model.remove( Statement.Statement(stmt[0], stmt[1], stmt[2], '', scope, stmt[3]) )
        else:
            model.add( Statement.Statement(stmt[0], stmt[1], stmt[2], '', scope, stmt[3]) )                
    #db.commit()
    return model, db

def deserializeRDF(modelPath, driver=Memory, dbName='', scope='', modelName='default', fileType=None):
    if not fileType:
        if modelPath[-3:] == '.mk':
            fileType = 'mk'
        elif modelPath[-3:] == '.nt':
            fileType = 'nt'
        elif modelPath[-4:] == '.rdf':
            fileType = 'xml'
            
    if fileType == 'mk':
        from rx import metakitdriver
        db =  metakitdriver.GetDb(modelPath, modelName)
        model = Model.Model(db)            
    elif fileType == 'nt':
        model, db = DeserializeFromN3File(modelPath,driver, dbName, False, scope, modelName)
    elif fileType == 'xml':
        try:
            #if rdflib is installed, use its RDF/XML parser because it doesn't suck            
            import rdflib.TripleStore
            ts = rdflib.TripleStore.TripleStore()
            ts.parse(Uri.OsPathToUri(modelPath))
            from Ft.Rdf.Drivers import Memory    
            db = Memory.CreateDb('', 'default')
            import Ft.Rdf.Model
            model = Ft.Rdf.Model.Model(db)
            import RxPath
            if not RxPath.useRDFLibParser:
                raise ImportError()

            #print 'parsing', modelPath, 'with rdflib'
            model.add( list(RxPath.rdflib2Statements(ts.triples( (None, None, None)))) )
        except ImportError:
            model, db = Util.DeserializeFromUri(Uri.OsPathToUri(modelPath),
                                               driver, dbName, False, scope) 
    else: #todo: add support for rxml
        raise 'unknown file type reading RDF: %s, only .rdf, .nt and .mk supported' % os.path.splitext(modelPath)[1]
    return model, db

def convertToNTriples(path, fileType=None):
    import StringIO
    model, db = deserializeRDF(path,fileType=fileType)
    moreTriples = StringIO.StringIO()                  
    stmts = model.statements()
    writeTriples(stmts, moreTriples)
    return moreTriples.getvalue() 
                   
def writeTriples(stmts, stream):
    subject = 0
    predicate = 1
    object = 2
    objectType = 5
    if stmts and isinstance(stmts, (type([]), type(()) )) and isinstance(
                    stmts[0], Statement.Statement):
        stmts = Model.Model(None)._unmapStatements(stmts)
    for stmt in stmts:       
       if stmt[0] is Comment:
           stream.write("#" + stmt[1].encode('utf8') + "\n")
           continue

       if stmt[0] is Removed:
           stream.write("#!remove\n")
           stmt = stmt[1]
       if stmt[subject].startswith(BNODE_BASE):
            stream.write('_:' + stmt[subject][BNODE_BASE_LEN:].encode('utf8') ) 
       else:
            stream.write("<" + stmt[subject].encode('utf8') + ">")
       if stmt[predicate].startswith(BNODE_BASE):
            stream.write( '_:' + stmt[predicate][BNODE_BASE_LEN:].encode('utf8') ) 
       else:            
           stream.write(" <" + stmt[predicate].encode('utf8') + ">")
       if stmt[objectType] == OBJECT_TYPE_RESOURCE:
            if stmt[object].startswith(BNODE_BASE):
                stream.write(' _:' + stmt[object][BNODE_BASE_LEN:].encode('utf8')  + ".\n") 
            else:
                stream.write(" <" + stmt[object].encode('utf8')  + "> .\n")
       else:           
           #escaped = repr(stmt[object])
           #if escaped[0] = 'u': 
           #    escaped = escaped[2:-1] #repr uses ' instead of " for string (and so doesn't escape ")
           #else:
           #    escaped = escaped[1:-1]
           escaped = stmt[object].replace('\\', r'\\').replace('\"', r'\"').replace('\n', r'\n').replace('\r', r'\r').replace('\t', r'\t').encode('utf8')
           if stmt[objectType] in [OBJECT_TYPE_LITERAL, OBJECT_TYPE_UNKNOWN]:
               stream.write(' "' + escaped + '" .\n')
           elif stmt[objectType].find(':') == -1: #must be a lang code
               stream.write(' "' + escaped + '"@' + stmt[objectType].encode('utf8'))
               stream.write(" .\n")
           else: #objectType must be a URI
               stream.write(' "' + escaped + '"^^' + stmt[objectType].encode('utf8'))
               stream.write(" .\n")

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

class Res(dict):
    '''simplify building RDF statements. dict-like object representing a resource with a dict of property/values
       usage:
       Res.nsMap = { ... } #global namespace map
       
       res = Res(resourceName, nsMap) #2nd param is optional instance override of global nsMap
       
       res['q:name'] = 'foo' #add a statement with property 'q:name' and object literal 'foo'
       
       res['q:name'] = Res('q:name2') #add a statement with property 'q:name' and object resource 'q:name2'
       
       #if prefix not found in nsMap it is treated as an URI
       res['http://foo'] = Res('http://bar') #add a statement with property http://foo and object resource 'http://bar'

       #if resourceName starts with '_:' it is treated as a bNode
       res['_:bNode1']
       
       #if you want multiple statements with the same property, use a list as the value, e.g.:
       res.setdefault('q:name', []).append(child)
       
       #retrieve the properties in the resource's dictionary as a NTriples string
       res.toTriples()

       #return a NTriples string by recursively looking at each resource that is the object of a statement
       res.toTriplesDeep()
    '''
    
    nsMap =  { 'owl': 'http://www.w3.org/2002/07/owl#',
           'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs' : 'http://www.w3.org/2000/01/rdf-schema#' }

    def __init__(self, uri=None, nsMap = None):
        if nsMap is not None:
            self.nsMap = nsMap
        if uri is None:
            uri = '_:'+ generateBnode()[BNODE_BASE_LEN:]
        self.uri = self.getURI(uri)

    def __eq__(self, other):
        return self.uri == other.uri

    def __ne__(self, other):
        return self.uri != other.uri
    
    def __cmp__(self, other):
        return cmp(self.uri, other.uri)

    def __hash__(self):
        return hash(self.uri)        

    def __getitem__(self, key):
        return super(Res, self).__getitem__(self.getURI(key))
    
    def __setitem__(self, key, item):    
        return super(Res, self).__setitem__(self.getURI(key), item)

    def __delitem__(self, key):
        return super(Res, self).__delitem__(self.getURI(key))

    def __contains__(self, key):
        return super(Res, self).__contains__(self.getURI(key))

    def getURI(self, key):
        if key.startswith('_:'):
            return key #its a bNode
        index = key.find(':')
        if index == -1: #default ns
            prefix = ''
            local = key
        else:
            prefix = key[:index]
            local = key[index+1:]
        if self.nsMap.get(prefix) is not None:
            return self.nsMap[prefix] + local 
        else:#otherwise assume its a uri
            return key
    
    def toStatementsDeep(self):
        stmts = []
        curlist = [ self ]
        done = [ self ]
        while curlist:
            #print [x.uri for x in reslist], [x.uri for x in done]
            res = curlist.pop()
            stmts2, reslist = res.toStatements(done)
            done.extend(reslist)
            curlist.extend(reslist)
            stmts.extend(stmts2) 
        return stmts
        
    def toStatements(self, doneList = None):
        stmts = []
        reslist = []
        if self.uri.startswith('_:'):
            s = BNODE_BASE+self.uri[2:]
        else:
            s = self.uri
        for p, v in self.items():
            if p.startswith('_:'):
                p = BNODE_BASE + p[2:] #but note that in RDF, its technically illegal for the predicate to be a bnode 
            if not isinstance(v, (type(()), type([])) ):
                v = (v,)
            for o in v:                                    
                if isinstance(o, Res):                    
                    if o.uri.startswith('_:'):
                        oUri = BNODE_BASE+o.uri[2:]
                    else:
                        oUri = o.uri
                    stmts.append(Statement.Statement(s, p, oUri, objectType=OBJECT_TYPE_RESOURCE))
                    if doneList is not None and o not in doneList:
                        reslist.append(o)
                else: #todo: datatype, lang                    
                    stmts.append(Statement.Statement(s, p, o, objectType=OBJECT_TYPE_LITERAL))
        if doneList is None:
            return stmts
        else:
            return stmts, reslist

    def toTriplesDeep(self):
        t = ''
        curlist = [ self ]
        done = [ self ]
        while curlist:
            #print [x.uri for x in reslist], [x.uri for x in done]
            res = curlist.pop()
            t2, reslist = res.toTriples(done)
            done.extend(reslist)
            curlist.extend(reslist)
            t += t2
        return t

    def toTriples(self, doneList = None):
        triples = ''
        reslist = []
        if not self.uri.startswith('_:'):
            s = '<' + self.uri + '>'
        else:
            s = self.uri
        for p, v in self.items():
            if not p.startswith('_:'):
                p = '<' + p + '>'
            if not isinstance(v, (type(()), type([])) ):
                v = (v,)
            for o in v:                                    
                triples += s + ' ' + p
                if isinstance(o, Res):
                    if o.uri.startswith('_:'):
                        triples += ' '+ o.uri + '. \n'
                    else:
                        triples += ' <'+ o.uri + '>. \n'                        
                    if doneList is not None and o not in doneList:
                        reslist.append(o)
                else: #todo: datatype, lang
                    escaped = o.replace('\\', r'\\').replace('\"', r'\"').replace('\n', r'\n').replace('\r', r'\r').replace('\t', r'\t')
                    triples += ' "' + escaped.encode('utf8') + '" .\n'
        if doneList is None:
            return triples
        else:
            return triples, reslist
    
class InterfaceDelegator:
    '''assumes only methods will be called on this object and the methods always return None'''
    def __init__(self, handlers):
        self.handlers = handlers
    
    def call(self, name, args, kw):
        for h in self.handlers:
            getattr(h, name)(*args, **kw)
        
    def __getattr__(self, name):
        return lambda *args, **kw: self.call(name, args, kw)

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
        if useNested:
            if self.nested_exc_info[1]:
                args = self.nested_exc_info[1].args
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
        if pre:
            pre(self)
        for field in fields:
            if field is not None:
                field.visit(pre=pre, post=post)
        if post:
            post(self)            
            
    def _visit0(self, pre=None, post=None):        
        if pre:
            pre(self)
        if post:
            post(self)            
        
    def _visitlr(self, pre=None, post=None):
        _visit(self, [self._left, self._right], pre=pre, post=post)

    def _additiveVisit(self, pre=None, post=None):
        if pre:
            pre(self)
        if not self._leftLit:            
            self._left.visit(pre=pre, post=post)
        if not self._rightLit:
            self._right.visit(pre=pre, post=post)
        if post:
            post(self)            
                            
    XPath.ParsedExpr.FunctionCall.visit = lambda self, pre=None, post=None: _visit(self, self._args, pre, post)
    XPath.ParsedExpr.ParsedNLiteralExpr.visit = _visit0
    XPath.ParsedExpr.ParsedLiteralExpr.visit = _visit0    
    XPath.ParsedExpr.ParsedVariableReferenceExpr.visit = _visit0
    XPath.ParsedExpr.ParsedUnionExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedPathExpr.visit = _visitlr #may have implicit decendent-or-self step too
    XPath.ParsedExpr.ParsedFilterExpr.visit = \
            lambda self, pre=None, post=None: _visit(self, [self._filter, self._predicates], pre, post)
    XPath.ParsedExpr.ParsedOrExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedAndExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedEqualityExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedRelationalExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedMultiplicativeExpr.visit = _visitlr
    XPath.ParsedExpr.ParsedAdditiveExpr.visit = _additiveVisit
    XPath.ParsedExpr.ParsedUnaryExpr.visit = lambda self, visitor: _visit(self, [self._exp], pre, post)
    XPath.ParsedAbbreviatedAbsoluteLocationPath.ParsedAbbreviatedAbsoluteLocationPath.visit = \
                    lambda self, pre=None, post=None: _visit(self, [self._rel], pre, post)
    XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath.visit = \
                    lambda self, pre=None, post=None: _visit(self, [self._left, self._right], order='pre')
    XPath.ParsedAbsoluteLocationPath.ParsedAbsoluteLocationPath.visit = \
                    lambda self, pre=None, post=None: _visit(self, [self._child], pre, post)
    XPath.ParsedAxisSpecifier.AxisSpecifier.visit = _visit0
    XPath.ParsedNodeTest.NodeTestBase.visit = _visit0
    XPath.ParsedPredicateList.ParsedPredicateList.visit = \
                    lambda self, pre=None, post=None: _visit(self, self._predicates, pre, post)
    XPath.ParsedRelativeLocationPath.ParsedRelativeLocationPath.visit = _visitlr
    XPath.ParsedStep.ParsedStep.visit = \
            lambda self, pre=None, post=None: _visit(self, [self._axis, self._nodeTest, self._predicates], pre, post)
    XPath.ParsedStep.ParsedAbbreviatedStep.visit = _visit0
    XPath.ParsedStep.ParsedNodeSetFunction.visit = \
            lambda self, pre=None, post=None: _visit(self, [self._function, _self._predicates], pre, post)
    Xslt.XPathExtensions.SortedExpression.visit = \
            lambda self, pre=None, post=None: _visit(self, [self.expression], pre, post)
    Xslt.XPathExtensions.RtfExpr.visit = _visit0

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
    XPath.ParsedAbbreviatedRelativeLocationPath.ParsedAbbreviatedRelativeLocationPath.__iter__ = \
                    lambda self: _iter(self, [self._left, self._right])
    XPath.ParsedAbsoluteLocationPath.ParsedAbsoluteLocationPath.__iter__ = \
                    lambda self: _iter(self, [self._child])
    XPath.ParsedAxisSpecifier.AxisSpecifier.__iter__ = _iter0
    XPath.ParsedNodeTest.NodeTestBase.__iter__ = _iter0
    XPath.ParsedPredicateList.ParsedPredicateList.__iter__ = lambda self: _iter(self, self._predicates)
    XPath.ParsedRelativeLocationPath.ParsedRelativeLocationPath.__iter__ = _iterlr
    XPath.ParsedStep.ParsedStep.__iter__ = \
            lambda self: _iter(self, [self._axis, self._nodeTest, self._predicates])
    XPath.ParsedStep.ParsedAbbreviatedStep.__iter__ = _iter0
    XPath.ParsedStep.ParsedNodeSetFunction.__iter__ = lambda self: _iter(self, [self._function, _self._predicates])
    Xslt.XPathExtensions.SortedExpression.__iter__ = lambda self: _iter(self, [self.expression])
    Xslt.XPathExtensions.RtfExpr.__iter__ = _iter0

except ImportError: #don't create a dependency on Ft.Xml.XPath
    pass

