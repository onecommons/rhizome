#!/usr/bin/env python

import sys, glob, os, os.path, tempfile
from distutils.core import setup
#import py2exe

version_string = "0.4.1"

PACKAGE_NAME = 'rx4rdf'

if sys.version_info[:2] < (2,2):
	print "Sorry, %s requires version 2.2 or later of Python" % PACKAGE_NAME
	sys.exit(1)

classifiers = """\
Development Status :: 3 - Alpha
Intended Audience :: Developers
Intended Audience :: Other Audience
License :: OSI Approved :: GNU General Public License (GPL)
Programming Language :: Python
Topic :: Internet :: WWW/HTTP
Topic :: Internet :: WWW/HTTP :: Dynamic Content
Topic :: Text Processing :: Markup :: XML
Topic :: Software Development :: Libraries :: Python Modules
Operating System :: Microsoft :: Windows
Operating System :: Unix
"""

if sys.version_info < (2, 3):
    _setup = setup
    def setup(**kwargs):
        if kwargs.has_key("classifiers"):
            del kwargs["classifiers"]
            del kwargs["download_url"]
        _setup(**kwargs)	

def createScript(scriptFile, sourceFile):
    from distutils import sysconfig
    install_dir = sysconfig.get_python_lib() + os.sep + 'rx'
    source_py = install_dir + os.sep + sourceFile
    
    script_suffix = ''
    script_str = '#! /bin/sh\n\n%s %s "$@"\n' % (sys.executable, source_py)
    if sys.platform == 'win32' :
        arg_str = '%1 %2 %3 %4 %5 %6 %7 %8 %9'
        script_str = '%s %s %s\n' % (sys.executable, source_py, arg_str)
        script_suffix = '.bat'

    LOCAL_SCRIPT = scriptFile + script_suffix
    LOCAL_SCRIPT = os.path.join(tempfile.gettempdir(), LOCAL_SCRIPT)
    try :
        os.unlink(LOCAL_SCRIPT)
    except :
        pass
    
    try :
        fp = open(LOCAL_SCRIPT, "w")
        fp.write(script_str)
        fp.close()
        if sys.platform != 'mac' :
            os.chmod(LOCAL_SCRIPT, 0755)
    except :
        print "Unable to create utility script."
        raise
    return LOCAL_SCRIPT

data_files = [
		   ('share/rx4rdf',[ 'changelog.txt', 'COPYING', 'README.txt'] ),
		   ('share/rx4rdf/rdfscribbler',glob.glob('rdfscribbler/*') ),
		   ('share/rx4rdf/docs',glob.glob('docs/*') ),
        ]

#setup doesn't handle directory trees well, e.g. just using glob on each subtree doesn't work
def _addFiles(data_files, dirname, names):     
    data_files.append( ( os.path.join('share/rx4rdf', dirname), 
       [os.path.join(dirname, name) for name in names if os.path.isfile(os.path.join(dirname, name))]) 
       )

os.path.walk('site', _addFiles, data_files)
os.path.walk('rhizome', _addFiles, data_files)

setup(name=PACKAGE_NAME,
#metadata:
	  version=version_string,
	  description="An application stack for building RDF-based applications and web sites",
	  author="Adam Souzis",
	  author_email="asouzis@users.sf.net",      
	  url="http://rx4rdf.sf.net",
	  download_url="http://sourceforge.net/project/showfiles.php?group_id=85676",
	  license = "GNU GPL",
	  platforms = ["any"],	  
	  classifiers = filter(None, classifiers.split("\n")),
          long_description= """Rx4RDF shields developers from the complexity of RDF by enabling you to
use familar XML technologies like XPath, XSLT and XUpdate to query, transform 
and manipulate RDF. Also included are two applications that utilize Rx4RDF:
Rhizome, a wiki-like content management and delivery system with wiki-like
markup languages for authoring XML and RDF, and RDFScribbler, for viewing and editing RDF models.""",	  
#packaging info:	  	  
      packages = ['rx', 'rx/logging22', 'rx/test'],
	  data_files = data_files,
	  scripts = [ createScript('run-raccoon', 'raccoon.py'),
	              createScript('zml', 'zml.py'),
	          ]
	  )
