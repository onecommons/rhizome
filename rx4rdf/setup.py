#!/usr/bin/env python

import sys, glob, os.path
from distutils.core import setup
#import py2exe

version_string = "0.2.0"

PACKAGE_NAME = 'rx4rdf'

if sys.version_info[:2] < (2,2):
	print "Sorry, %s requires version 2.2 or later of python" % PACKAGE_NAME
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


data_files = [
		    ('share/rx4rdf',[ 'changelog.txt', 'COPYING', 'README.txt'] ),
		   ('share/rx4rdf/rhizome',glob.glob('rhizome/*') ),
		   ('share/rx4rdf/rdfscribbler',glob.glob('rdfscribbler/*') ),
		   ('share/rx4rdf/docs',glob.glob('docs/*') ),
        ]

def _addFiles(data_files, dirname, names):     
    data_files.append( ( os.path.join('share/rx4rdf', dirname), 
       [os.path.join(dirname, name) for name in names if os.path.isfile(os.path.join(dirname, name))]) 
       )
os.path.walk('site', _addFiles, data_files)

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
	  data_files = data_files
	  )
