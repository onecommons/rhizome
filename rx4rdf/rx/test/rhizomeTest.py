"""
    Rx4RDF unit tests

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

from rx import raccoon, utils, logging, rhizome
import unittest, os, os.path, shutil, glob

RHIZOMEDIR = '../../rhizome'

class RhizomeTestCase(unittest.TestCase):
    '''
    Run test "scripts".
    
    Our pathetic little scripting environment works like this:
    
    The Raccoon's -r option records requests sent to it and then pickles
    the list when you use Ctrl-C to shutdown.
    
    The -d [picklefile] option plays back those requests.
    
    Our test-config.py adds a page named "assert" that lets us write Python assertions
    that will get executed when played back.
    '''
    
    def setUp(self):
        logging.BASIC_FORMAT = "%(asctime)s %(levelname)s %(name)s:%(message)s"        
        logLevel = DEBUG and logging.DEBUG or logging.INFO
        logging.root.setLevel(logLevel)
        logging.basicConfig()
        raccoon.DEFAULT_LOGLEVEL = logLevel

    def testNoSpamFixer(self):
        contents='''<?xml version=1.0 standalone=true ?>
        <!doctype asdf>
        <test link='foo' t='1'>
        <a href='http://viagra.com'>spam</a>
        <!-- comment -->
        <![CDATA[some < & > unescaped! ]]>
        some content&#233;more content&amp;dsf<a href='http://viagra.com/next' rel='next' />
        </test>'''
        result = '''<?xml version=1.0 standalone=true ?>
        <!doctype asdf>
        <test link='foo' t='1'>
        <a href='http://viagra.com' rel="nofollow" >spam</a>
        <!-- comment -->
        <![CDATA[some < & > unescaped! ]]>
        some content&#233;more content&amp;dsf<a href='http://viagra.com/next' rel="nofollow" />
        </test>'''
        import utilsTest
        runLinkFixer = utilsTest.utilsTestCase.runLinkFixer.im_func        
        runLinkFixer(self, rhizome.SanitizeHTML, contents, result)

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
        The script:
        1. logs in as admin
        1. add a page called testminoredit,
        1. modifies it several times with and without the minor edit
        1. then asserts that the correct number revisions and checks the expected first
        character of the final revision
        '''
        for configpath in glob.glob('test-config*.py'):
            print 'testing ', configpath
            self.executeScript(configpath, glob.glob('minoredit.*.pkl'))

    def testSmokeTest(self):
        '''
        So far this script only does this:
        1. edit the zmlsandbox
        1. view it
        1. create new html page called "sanitize" using illegal html (e.g. javascript)
        1. view it
        1. create a new user account
        1. view it
        '''
        for configpath in glob.glob('test-config*.py'):
            print 'testing ', configpath
            self.executeScript(configpath, glob.glob('smoketest.*.pkl'))

    def testNonAscii(self):
        '''
        This script:
        1. Creates a text page with non-ascii name, title and contents
        1. Previews it
        1. Views it
        1. Re-edits it
        1. Creates a page with binary content (via file upload)
        1. Views it
        '''
        for configpath in glob.glob('test-config*.py'):
            print 'testing ', configpath
            self.executeScript(configpath, glob.glob('nonascii.*.pkl'))


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
    except (IndexError, ValueError):
        unittest.main()
    else:
        tc = RhizomeTestCase(test)
        tc.setUp()
        getattr(tc, test)() #run test
