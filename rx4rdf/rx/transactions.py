'''
Most of the code here is based on PEAK's transactions.py, specifically:
http://cvs.eby-sarna.com/PEAK/src/peak/storage/transactions.py?rev=1.33
(also available at http://svn.eby-sarna.com/*checkout*/PEAK/src/peak/storage/transactions.py?rev=1573 )
'''

import time
import os, os.path
from rx import utils
from rx import logging #for python 2.2 compatibility

class TransactionError(Exception):
    '''Base transaction error'''

class NotReadyError(TransactionError):
    """One or more transaction participants were unready too many times"""

class TransactionInProgress(TransactionError):
    """Action not permitted while transaction is in progress"""

class OutsideTransaction(TransactionError):
    """Action not permitted while transaction is not in progress"""

class BrokenTransaction(TransactionError):
    """Transaction can't commit, due to participants breaking contracts
       (E.g. by throwing an exception during the commit phase)"""

class BasicTxnErrorHandler(object):
    """Simple error handling policy, w/simple logging, no retries"""

    def voteFailed(self, txnService, participant):
        txnService.log.warning(
            "%s: error during participant vote", txnService, exc_info=True
        )

        # Force txn to abort
        txnService.fail()
        raise

    def commitFailed(self, txnService, participant):
        txnService.log.critical(
            "%s: unrecoverable transaction failure", txnService,
            exc_info=True
        )
        txnService.fail()
        raise

    def abortFailed(self, txnService, participant):
        txnService.log.warning(
            "%s: error during participant abort", txnService,
            exc_info=True
        )
        # ignore the error

    def finishFailed(self, txnService, participant, committed):
        txnService.log.warning(
            "%s: error during participant finishTransaction", txnService,
            exc_info=True
        )
        # ignore the error

class TransactionState(object):
    """Helper object representing a single transaction's state"""

    #participants = binding.Make(list)
    #info         = binding.Make(dict)    
    timestamp    = None
    safeToJoin   = True
    cantCommit   = False
    inCommit     = False
    inAbort      = False
    
    def __init__(self):
       self.participants = []
       self.info = {}

class TransactionService(object):
    """Basic transaction service component"""

    #state          = binding.Make(TransactionState)
    errorHandler   = BasicTxnErrorHandler() #binding.Make(BasicTxnErrorHandler)
    stateFactory = TransactionState
        
    def __init__(self, loggerName='transactions'):         
        self.state = self.stateFactory()
        self.log = logging.getLogger(loggerName)

    def join(self, participant):
        if not self.isActive():
            raise OutsideTransaction
        elif self.state.cantCommit:
            raise BrokenTransaction
        elif self.state.safeToJoin:
            if participant not in self.state.participants:
                self.state.participants.append(participant)
                participant.inTransaction = True
        else:
            raise TransactionInProgress

    def isDirty(self):
        '''return True if any of the transaction participants were modified'''    
        if not self.isActive():
            raise OutsideTransaction

        for p in self.state.participants:
            if p.isDirty(self):
                return True
        return False

    def _prepareToVote(self):

        """Get votes from all participants

        Ask all participants if they're ready to vote, up to N+1 times (where
        N is the number of participants), until all agree they are ready, or
        an exception occurs.  N+1 iterations is sufficient for any acyclic
        structure of cascading data managers.  Any more than that, and either
        there's a cascade cycle or a broken participant is always returning a
        false value from its readyToVote() method.

        Once all participants are ready, ask them all to vote."""

        tries = 0
        unready = True
        state = self.state

        while unready and tries <= len(state.participants):
            unready = [p for p in state.participants if not p.readyToVote(self)]
            tries += 1

        if unready:
            raise NotReadyError(unready)

        self.state.safeToJoin = False

    def _vote(self):
        for p in self.state.participants:
            try:
                p.voteForCommit(self)
            except:
                self.errorHandler.voteFailed(self,p)

    def begin(self, **info):
        if self.isActive():
            raise TransactionInProgress

        self.state = self.stateFactory()
        self.state.timestamp = time.time()
        self.addInfo(**info)

    def commit(self):
        if not self.isActive():
            raise OutsideTransaction

        if self.state.cantCommit:
            raise BrokenTransaction

        self._prepareToVote()
        self._vote()
        #bug? vote failed will raise the participant's error and _cleanup will never get called
        
        try:
            self.state.inCommit = True 
            for p in self.state.participants:
                try:
                    p.commitTransaction(self)
                except:
                    self.errorHandler.commitFailed(self,p)
        finally:
            self.state.inCommit = False 
            
        self._cleanup(True)

    def fail(self):
        if not self.isActive():
            raise OutsideTransaction
        self.state.cantCommit = True
        self.state.safeToJoin = False

    def removeParticipant(self,participant):
        self.state.participants.remove(participant)
        participant.inTransaction = False

    def abort(self):
        if not self.isActive():
            raise OutsideTransaction

        self.fail()

        try:
            self.state.inAbort = True 
            for p in self.state.participants[:]:
                try:
                    p.abortTransaction(self)
                except:
                    self.errorHandler.abortFailed(self,p)
        finally:
            self.state.inAbort = False 

        self._cleanup(False)

    def getTimestamp(self):
        """Return the time that the transaction began, in time.time()
        format, or None if no transaction in progress."""

        return self.state.timestamp

    def addInfo(self, **info):
        if self.state.cantCommit:
            raise BrokenTransaction
        elif self.state.safeToJoin:
            self.state.info.update(info)
        else:
            raise TransactionInProgress

    def getInfo(self):
        return self.state.info

    def _cleanup(self, committed):
        for p in self.state.participants[:]:
            try:
                p.finishTransaction(self,committed)
            except:
                self.errorHandler.finishFailed(self,p,committed)

        self.state = self.stateFactory()
        
    def isActive(self):
        return self.state.timestamp is not None

    def __contains__(self,ob):
        return ob in self.state.participants

class TransactionParticipant(object):
    inTransaction = False

    def isDirty(self,txnService):
        '''return True if this transaction participant was modified'''    
        return True #default to True if we don't know one way or the other
    
    def readyToVote(self, txnService):
        return True

    def voteForCommit(self, txnService):
        pass

    def commitTransaction(self, txnService):
        pass

    def abortTransaction(self, txnService):
        pass

    def finishTransaction(self, txnService, committed):
        self.inTransaction = False

class RaccoonTransactionState(TransactionState):
    def __init__(self):
        super(RaccoonTransactionState, self).__init__()        
        self.additions = []
        self.removals = []
        self.newResources = []
        self.result = []
        self.kw = {}
        self.contextNode = None
        self.retVal = None

class RaccoonTransactionService(TransactionService,utils.object_with_threadlocals):
    lock = None
    stateFactory = RaccoonTransactionState

    def __init__(self, server):        
        self.server = server
        #Raccoon associates each request with one transaction context
        #and one thread; therefore we need one transaction context per thread
        self.initThreadLocals(state=RaccoonTransactionState())
        super(RaccoonTransactionService, self).__init__(server.log.name)

    def newResourceHook(self, node):
        '''
        This is intended to be set as the DOMStore's newResourceTrigger
        '''
        if self.isActive() and self.state.safeToJoin:
            self.state.newResources.append(node)
            self._runActions('before-new', {'_newResources' : [node]})

    def addHook(self, node):
        '''
        This is intended to be set as the DOMStore's addTrigger
        '''
        if self.isActive() and self.state.safeToJoin:            
            self.state.additions.append(node)
            isnew = node.parentNode in self.state.newResources
            kw = {'_added' : [node], '_isnew' : isnew,
                  '_newResources': self.state.newResources}
            self._runActions('before-add', kw)

    def removeHook(self, node):
        '''
        This is intended to be set as the DOMStore's removeTrigger
        '''
        from rx import RxPathDom
        if self.isActive() and self.state.safeToJoin:
            state = self.state
            if isinstance(node, RxPathDom.Resource):
                state.removals.extend(node.childNodes)
                isnew = node in state.newResources                
            else:
                state.removals.append(node)
                isnew = node.parentNode in state.newResources
            kw = {'_removed' : [node], '_isnew' : isnew,
                  '_newResources': state.newResources}
            self._runActions('before-remove', kw)
                
    def _runActions(self, trigger, morekw=None):      
       actions = self.server.actions.get(trigger)       
       if actions:
            state = self.state
            kw = state.kw.copy()
            if morekw is None: 
                morekw = { '_added' : state.additions,
                           '_removed' : state.removals,
                           '_newResources': state.newResources}
            kw.update(morekw)
            errorSequence= self.server.actions.get(trigger+'-error')
            self.server.callActions(actions,state.result, kw,
                    state.contextNode,  state.retVal,
                    globalVars= self.server.globalRequestVars + morekw.keys(),
                    errorSequence=errorSequence)

    def join(self, participant):
        super(RaccoonTransactionService, self).join(participant)
        if not self.lock: #lock on first join
            self.lock = self.server.getLock()
   
    def _cleanup(self, committed):
        success = not self.state.cantCommit

        #if transaction completed successfully
        if success:
            self._runActions('after-commit')

        try:
            super(RaccoonTransactionService, self)._cleanup(committed)
        finally:
            if self.lock:  #hmm, can we release the lock earlier?
                self.lock.release()
                self.lock = None
        
    def _prepareToVote(self):
        #todo: treating these two actions as transaction participants either end of the list
        #with the action running in voteForCommit() would be more elegant
        #but right now the txn doesn't clean up if a vote fails
        
        #we're about to complete the transaction,
        #here's the last chance to modify it
        try:
            self._runActions('before-prepare')
        except:
            self.abort()
            raise

        super(RaccoonTransactionService, self)._prepareToVote()

        #the transaction is about to be comitted
        #this trigger let's you look at the completed state
        #and gives you a chance to abort the transaction        
        assert not self.state.safeToJoin 
        try:
            #print self.state.additions
            self._runActions('before-commit')
        except:
            self.abort()
            raise
            
        return True

class FileFactory(object):
    """Stream factory for a local file object"""

    def __init__(self, filename):    
        self.filename = filename

    def open(self,mode,seek=False,writable=False,autocommit=False):
        return self._open(mode, 'r'+(writable and '+' or ''), autocommit)

    def create(self,mode,seek=False,readable=False,autocommit=False):
        return self._open(mode, 'w'+(readable and '+' or ''), autocommit)

    def update(self,mode,seek=False,readable=False,append=False,autocommit=False):
        return self._open(mode, 'a'+(readable and '+' or ''), autocommit)

    def exists(self):
        return os.path.exists(self.filename)

    def _acRequired(self):
        raise NotImplementedError(
            "Files require autocommit for write operations"
        )

    def _open(self, mode, flags, ac):
        if mode not in ('t','b','U'):
            raise TypeError("Invalid open mode:", mode)

        if not ac and flags<>'r':
            self._acRequired()
        return open(self.filename, flags+mode)

    def delete(self,autocommit=False):
        if not autocommit:
            self._acRequired()
        os.unlink(self.filename)
        
    # XXX def move(self, other, overwrite=True, mkdirs=False, autocommit=False):

class TxnFileFactory(TransactionParticipant, FileFactory):
    """Transacted file (stream factory)"""
    isDeleted = False
    _isDirty = False

    def __init__(self, filename):
        super(TxnFileFactory, self).__init__(filename)  
        self.tmpName = self.filename+'.$$$'

    def _txnInProgress(self):
        raise TransactionInProgress(
            "Can't use autocommit with transaction in progress"
        )

    def isDirty(self,txnService):
        return self._isDirty or self.isDeleted
    
    def delete(self, autocommit=False):
        if self.inTransaction:
            if autocommit:
                self._txnInProgress()   # can't use ac in txn

            if not self.isDeleted:
                os.unlink(self.tmpName)
                self.isDeleted = True
        elif autocommit:
            os.unlink(self.filename)
        else:
            # Neither autocommit nor txn, join txn and set deletion flag
            self.isDeleted = True

    def _open(self, mode, flags, ac):
        if mode not in ('t','b','U'):
            raise TypeError("Invalid open mode:", mode)
        elif self.inTransaction:
            if ac:
                self._txnInProgress()
            if flags!='r':
                self._isDirty = True
            return open(self.tmpName, flags+mode)
        # From here down, we're not currently in a transaction...
        elif ac or flags=='r':
            # If we're reading, just read the original file
            # Or if autocommit, then also okay to use original file
            return open(self.filename, flags+mode)
        elif '+' in flags and 'w' not in flags:
            # Ugh, punt for now
            raise NotImplementedError(
                "Mixed-mode (read/write) access not supported w/out autocommit"
            )
        else:

            # Since we're always creating the file here, we don't use 'a'
            # mode.  We want to be sure to erase any stray contents left over
            # from another transaction.  XXX Note that this isn't safe for
            # a multiprocess environment!  We should use a lockfile.
            stream = open(self.tmpName, flags.replace('a','w')+mode)
            self.isDeleted = False
            return stream

    def exists(self):
        if self.inTransaction:
            return not self.isDeleted
        return os.path.exists(self.filename)

    def commitTransaction(self, txnService):
        if self.isDeleted:
            os.unlink(self.filename)
            return

        try:
            os.rename(self.tmpName, self.filename)
        except OSError:
            # Windows can't do this atomically.  :(  Better hope we don't
            # crash between these two operations, or somebody'll have to clean
            # up the mess.
            os.unlink(self.filename)
            os.rename(self.tmpName, self.filename)

    def abortTransaction(self, txnService):
        #todo: what if the file is open? (esp. on windows)
        if not self.isDeleted and os.path.exists(self.tmpName):
            os.unlink(self.tmpName)

    def finishTransaction(self, txnService, committed):
        super(TxnFileFactory, self).finishTransaction(txnService, committed)
        self.isDeleted = False

#class EditableFile(TxnFile): #todo?
