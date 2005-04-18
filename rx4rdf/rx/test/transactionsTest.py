"""
Transaction and Persistence tests
"""

from rx.transactions import *
import unittest, glob, os, os.path

class TxnStateTest(unittest.TestCase):

    def setUp(self):
        self.ts = TransactionService()
        self.p  = LogParticipant()
        self.log = self.p.log = []

    def testOutside(self):
        ts = self.ts

        for op in ts.commit, ts.abort, ts.fail:
            self.assertRaises(OutsideTransaction, op)

        self.assertRaises(OutsideTransaction, ts.join, self.p)
        assert self.log == []

    def testFail(self):
        ts = self.ts

        ts.begin()
        ts.fail()

        self.assertRaises(BrokenTransaction, ts.join, self.p)
        self.assertRaises(BrokenTransaction, ts.commit)

        ts.abort()
        assert self.log == []

    def testStampAndActive(self):
        ts = self.ts

        assert not ts.isActive()
        assert ts.getTimestamp() is None

        for fini in ts.commit, ts.abort:
            ts.begin()
            assert ts.isActive()

            from time import time
            assert abs(time() - ts.getTimestamp()) < 5

            fini()

            assert not ts.isActive()
            assert ts.getTimestamp() is None

        assert self.log ==[]

    def testSimpleUse(self):
        ts = self.ts
        ts.begin()
        ts.join(self.p)
        ts.commit()

        ts.begin()
        ts.join(self.p)
        ts.abort()

        assert self.log == [
            ('readyToVote',ts), ('voteForCommit',ts), ('commit',ts),
            ('finish',ts,True), ('abort',ts), ('finish',ts,False),
        ]


class LogParticipant(TransactionParticipant):

    def readyToVote(self, txnService):
        self.log.append(("readyToVote", txnService))
        return True

    def voteForCommit(self, txnService):
        self.log.append(("voteForCommit", txnService))


    def commitTransaction(self, txnService):
        self.log.append(("commit", txnService))

    def abortTransaction(self, txnService):
        self.log.append(("abort", txnService))

    def finishTransaction(self, txnService, committed):
        self.log.append(("finish", txnService, committed))

class UnreadyParticipant(LogParticipant):

    def readyToVote(self, txnService):
        self.log.append(("readyToVote", txnService))
        return False

class ProcrastinatingParticipant(LogParticipant):

    status = 0

    def readyToVote(self, txnService):
        self.log.append(("readyToVote", txnService))
        old = self.status
        self.status += 1
        return old

class VotingTest(unittest.TestCase):

    def setUp(self):
        self.ts = TransactionService()
        self.p_u  = UnreadyParticipant()
        self.p_p  = ProcrastinatingParticipant()
        self.p_n  = LogParticipant()
        self.log = self.p_u.log = self.p_p.log = self.p_n.log = []

    def testUnready(self):
        ts = self.ts

        ts.begin()
        ts.join(self.p_u)
        ts.join(self.p_p)
        ts.join(self.p_n)

        self.assertRaises(NotReadyError, ts.commit)

        # just a lot of ready-to-vote attempts
        assert self.log == [('readyToVote',ts)]*len(self.log)


    def testMixed(self):
        ts = self.ts

        ts.begin()
        ts.join(self.p_p)
        ts.join(self.p_n)

        ts.commit()


        # 2 participants * 1 retry for first, rest are all * 2 participants

        assert self.log == \
            [('readyToVote',ts)]   * 4 + \
            [('voteForCommit',ts)] * 2 + \
            [('commit',ts)]        * 2 + \
            [('finish',ts,True)]   * 2


    def testNormal(self):
        ts = self.ts

        ts.begin()
        ts.join(self.p_n)
        ts.commit()

        assert self.log == [
            ('readyToVote',ts),
            ('voteForCommit',ts),
            ('commit',ts),
            ('finish',ts,True),
        ]

if __name__ == '__main__':
    import sys    
    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = TxnStateTest(test)
        tc.setUp()
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()
