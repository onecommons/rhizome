"""
    General purpose utilities

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from __future__ import generators
import os.path
import os, sys, sha
from stat import *
from time import *
from types import *
from binascii import unhexlify, b2a_base64

from Ft.Rdf import Util, Model, Statement, OBJECT_TYPE_RESOURCE, OBJECT_TYPE_LITERAL, OBJECT_TYPE_UNKNOWN
from Ft.Rdf.Drivers import Memory

from Ft.Rdf import BNODE_BASE, BNODE_BASE_LEN
from Ft.Lib import Uuid
_bNodeCounter  = 0
_sessionBNodeUUID = "x" + Uuid.UuidAsString(Uuid.GenerateUuid()) + "_"  #like this so this will be a valid xml nmtoken

def generateBnode(name=None):
    """
    Generates blank nodes (bnodes), AKA anonymous resources
    """
    global _bNodeCounter, _sessionBNodeUUID
    _bNodeCounter += 1
    name = name or `_bNodeCounter`    
    return BNODE_BASE + _sessionBNodeUUID +  name

def cond(ifexp, thenexp, elseexp = lambda: None):
    '''to enable short circuit evaluation the thenexp and elseexp parmeters are functions that are lazily evaluated'''
    if ifexp:
        return thenexp()
    else:
        return elseexp()

def createThreadLocalProperty(name, fget=True, fset=True, fdel=True, doc=None, initAttr=False, initValue=None):
    '''
    usage:
      class foo(object):
         aThreadLocalAttribute = utils.createThreadLocalProperty('__aThreadLocalAttribute')

    A KeyError will be thrown when attempting to get an attribute that has not been set in the current thread.
    For example, if an attribute is set in __init__() and then retrieved in another thread.
    To avoid this, set initAttr to True, which will set the attribute value to initValue by default.
    
    Deleting an attribute will delete it for all threads.
    '''
    import thread
    
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
    return data.replace('&','&amp').replace('<','&lt;').replace('>','&gt;')

def diff(new, old, cutoffOffset = -100):
    '''
    returns a list of changes needed to transform new to old unless the length
    of the list of changes is greater the length of the old content itself plus 
    the cutoffOffset, in which case None is returned.
    '''
    maxlen = len(old) + cutoffOffset
    old = old.splitlines()
    new = new.splitlines()
    changes = []
    import difflib
    cruncher = difflib.SequenceMatcher(None, new, old)
    patchlen = 0
    for tag, alo, ahi, blo, bhi in cruncher.get_opcodes():#to turn a into b
        if tag == 'replace':        
            #g = self._fancy_replace(a, alo, ahi, b, blo, bhi)
            changes.append( ( 'r', alo, ahi, old[blo:bhi] ) )
            patchlen = reduce(lambda x, y: x + len(y), old[blo:bhi], patchlen)
        elif tag == 'delete':
            changes.append( ( 'd', alo, ahi) )
        elif tag == 'insert':
            changes.append( ( 'i', alo, old[blo:bhi]) )
            patchlen = reduce(lambda x, y: x + len(y), old[blo:bhi], patchlen)
        if patchlen > maxlen:
            return None #don't bother
    return changes

def patch(base, patch, sep = '\n'):
    base = base.splitlines()
    for op in patch:
        if op[0] == 'r':
            base[op[1]:op[2]] = op[3]
        elif op[0] == 'd':
            del base[ op[1]:op[2]]
        elif op[0] == 'i':
            base.insert(op[1], op[2])
    return sep.join(base)

def walkDir(path, fileFunc, *funcArgs, **kw):
##        if filefuncArgs is not None:
##            if not isinstance(filefuncArgs, TupleType):
##                filefuncArgs = (filefuncArgs, )
##        else
##            filefuncArgs = () #to pass None as arguement pass in (None, )            
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

class SLListIter(object):
    def __init__(self, sllist):
        self._iter = iter(sllist.data)
        self._next = sllist.next
        
    def __iter__(self):
        return self

    def next(self):
        try: 
            return self._iter.next()
        except StopIteration:
            if self._next is None:                        
                raise
            else:
                self._iter = iter(self._next.data)
                self._next = self._next.next
            return self.next()

class SLList(object):
    def __init__(self, init = []):
        self.data = init
        self.next = None

    def __iter__(self):
        return SLListIter(self)

    def extend(self, sllist):
        if isinstance(sllist, SLList):
            if self.next is None:
                self.next = sllist
            else:
                self.data.extend(sllist)
        else:
            self.data.extend(sllist)
            
    def __getitem__(self, index):
        l = len(self.data)
        if index < l:
            return self.data[index]
        elif not self.next is None:
            return self.next[index - l]
        else:
            raise IndexError()
            
    def __len__(self):    
        if self.next is None:
            return len(self.data)
        else:
            return len(self.data) + self.next.__len__() 

#see w3.org/TR/rdf-testcases/#ntriples 
#todo: assumes utf8 encoding and not string escapes for unicode
def parseTriples(lines, bNodeToURI = None):        
    for line in lines:
        line = line.strip().decode('utf8')
        if not line: #trailing whitespace
            break;
        if line[0] == '#': #comment
            continue
        subject, predicate, object = line.split(None,2)
        if subject.startswith('_:'):
            subject = subject[2:] #bNode
            subject = bNodeToURI(subject)
        else:
            subject = subject[1:-1] #uri
        predicate = predicate[1:-1] #uri
        object = object.strip()        
        if object[0] == '<': #if uri
            object = object[1:object.find('>')]
            objectType = OBJECT_TYPE_RESOURCE
        elif object.startswith('_:'):
            object = object[2:object.find('.')].strip()
            object = bNodeToURI(object)
            objectType = OBJECT_TYPE_RESOURCE
        else:                        
            quote = object[0] #add support for using either ' or " (spec says just ")
            object = object[1:object.rfind(quote)] #todo: also handle the optional ^^datatype or @lang after the "
            if object.find('\\') != -1:
                object = object.replace(r'\\', '\\').replace('\\' + quote, quote).replace(r'\n', '\n').replace(r'\r', '\r').replace(r'\t', '\t')
            objectType = OBJECT_TYPE_LITERAL
        #print "parsed: ", subject, predicate, object
        yield (subject, predicate, object, objectType)

def DeserializeFromN3File(n3filepath, driver=Memory, dbName='', create=0, scope='',
                        modelName='default', model=None):
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
        
    bNodeMap = {}
    for stmt in parseTriples(stream, lambda bNode: bNodeMap.setdefault(bNode, generateBnode(bNode)) ):
        model.add( Statement.Statement(stmt[0], stmt[1], stmt[2], '', scope, stmt[3]) )                
    #db.commit()
    return model, db

def deserializeRDF(modelPath, driver=Memory, dbName='', scope='', modelName='default'):
    if modelPath[-3:] == '.mk':
        import metakitdriver
        db =  metakitdriver.GetDb(modelPath, modelName)
        model = Model.Model(db)            
    elif modelPath[-3:] == '.nt':
        model, db = DeserializeFromN3File(modelPath,driver, dbName, False, scope, modelName)
    elif modelPath[-4:] == '.rdf':
        model, db = Util.DeserializeFromUri(modelPath, driver, dbName, False, scope) 
    else: #todo: add support for rxml
        raise 'unknown file type reading RDF: %s, only .rdf, .nt and .mk supported' % os.path.splitext(modelPath)[1]
    return model, db

def writeTriples(stmts, stream):
    subject = 0
    predicate = 1
    object = 2
    objectType = 5
    for stmt in stmts:            
       stream.write("<" + stmt[subject] + "> ")
       stream.write("<" + stmt[predicate] + "> ")
       if stmt[objectType] == OBJECT_TYPE_RESOURCE:
            stream.write("<" + stmt[object] + "> .\n")
       else:           
           #escaped = repr(stmt[object])
           #if escaped[0] = 'u': 
           #    escaped = escaped[2:-1] #repr uses ' instead of " for string (and so doesn't escape ")
           #else:
           #    escaped = escaped[1:-1]
           escaped = stmt[object].replace('\\', r'\\').replace('\"', r'\"').replace('\n', r'\n').replace('\r', r'\r').replace('\t', r'\t')

           if stmt[objectType] in [OBJECT_TYPE_LITERAL, OBJECT_TYPE_UNKNOWN]:
               stream.write('"' + escaped.encode('utf8') + '" .\n')
	       #else:
           #    stream.write('"' + escaped.encode('utf8') + '"^^' + stmt[objectType])
	       #    stream.write(" .\n")

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
            #    stdout = os.popen('\\cygwin\\usr\\local\\bin\\nilsimsa ' + filepath) 
            #    val = stdout.read(64) #just read the first 64 bytes of first line     #re.match('[\dA-Fa-f]{64}', input)
            #    err = stdout.close()
            #    assert err is None, "nilsimsa returned an error: " + str(err) #todo error handling
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
       
       res = Res(uri, nsMap) #2nd param is optional instance override of global nsMap
       
       res['q:name'] = 'adfasdfdf' #assign property with literal
       
       #if prefix not found in nsMap treat as an URL
       res['http://foo'] = Res('http://') #assign a resource
       
       #if you want multiple statements with the same property, use a list as the value, e.g.:
       res.setdefault('q:name', []).append(child)
       
       #retrieve the statements as NTriples:
       res.toTriples()
    '''
    
    nsMap =  { 'owl': 'http://www.w3.org/2002/07/owl#',
           'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs' : 'http://www.w3.org/2000/01/rdf-schema#' }

    def __init__(self, uri, nsMap = None):
        if nsMap is not None:
            self.nsMap = nsMap
        self.uri = self.getURI(uri)

    def __eq__(self, other):
        return self.uri == other.uri

    def __ne__(self, other):
        return self.uri != other.uri
    
    def __cmp__(self, other):
        return cmp(self.uri, other.uri)

    def __hash__(self):
        return hash(self.uri, other.uri)        

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
    '''assumes only methods will be called on this object'''
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

