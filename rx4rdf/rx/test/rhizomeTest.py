"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

from rx import raccoon, utils, logging
import unittest, os, os.path, shutil, glob

RHIZOMEDIR = '../../rhizome'

class RhizomeTestCase(unittest.TestCase):
    '''
    Run test "scripts".
    Our pathetic little scripting environment works like this:
    The -r option records requests sent Raccoon and then pickles the list
    The -d plays back those requests
    Our test-config.py adds a page named "assert" that lets us write Python assertions
    that will get executed when played back.
    '''
    
    def setUp(self):
        logging.BASIC_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"        
        logLevel = DEBUG and logging.DEBUG or logging.INFO
        logging.root.setLevel(logLevel)
        logging.basicConfig()
        raccoon.DEFAULT_LOGLEVEL = logLevel

    def executeScript(self, config, histories):
        histories = [os.path.abspath(x) for x in histories]
        config, rhizomedir = [os.path.abspath(x) for x in (config, RHIZOMEDIR)]        
        currpath = os.path.abspath( os.getcwd() )
        tempdir = os.tempnam(None,'rhizometest')
        os.mkdir(tempdir)
        os.chdir(tempdir)
        try:
            for playback in histories:
                print 'playing back', playback
                raccoon.main(['-x','-d', playback, '-a', config,
                #these args are used in the test-configs:
                '--testplayback', '--rhizomedir', rhizomedir,'--includedir', currpath])
        finally:
            os.chdir(currpath)
            if SAVE_WORK:
                print 'work saved at', tempdir
            else:
                shutil.rmtree(tempdir)
    
    def testMinorEdit(self):
        '''
        This script, logs in as admin, add a page called testminoredit,
        modifies it several times with and without the minor edit
        then asserts that the correct number revisions and checks the expected first
        character of the final revision
        '''
        for configpath in glob.glob('test-config*.py'):
            print 'testing ', configpath
            self.executeScript(configpath, glob.glob('testminoredit.*.pkl'))

SAVE_WORK=False
DEBUG = False

if __name__ == '__main__':
    import sys    
    #import os, os.path
    #os.chdir(os.path.basename(sys.modules[__name__ ].__file__))
    if sys.argv.count("--save"):
        SAVE_WORK=True
        del sys.argv[sys.argv.index('--save')]
    DEBUG = sys.argv.count('--debug')
    if DEBUG:
        del sys.argv[sys.argv.index('--debug')]
    try:
        test=sys.argv[sys.argv.index("-r")+1]
        tc = RaccoonTestCase(test)
        tc.setUp()
        getattr(tc, test)() #run test
    except (IndexError, ValueError):
        unittest.main()
