#!/usr/bin/env python

import sys, glob
from distutils.core import setup
#import py2exe

version_string = "0.1.1"

PACKAGE_NAME = 'rx4rdf'

if sys.version_info[:2] < (2,2):
	print "Sorry, %s requires version 2.2 or later of python" % PACKAGE_NAME
	sys.exit(1)

setup(name=PACKAGE_NAME,
	  version=version_string,
	  description="reference implementations of RxPath, RxSLT, RxUpdate, RxML, and RhizML along with the Rhizome and RDFScribbler web applications",
	  author="Adam Souzis",
	  author_email="asouzis@users.sf.net",      
	  url="http://rx4rdf.sf.net",
	  license = "GNU GPL",
      packages = ['rx'],
#	  scripts = ['archiver.py' ],
	  data_files = [
		    ('rx',[  'COPYING', 'README.txt'] ),
		   ('rx/rhizome',glob.glob('rx/rhizome/*.*') ),
		   ('rx/rdfscribbler',glob.glob('rx/rdfscribbler/*.*') ),
		   ('rx/test',glob.glob('rx/test/*.*') ),
        ],
      long_description= """Rx4RDF shields developers from the complexity of RDF by enabling you to
use familar XML technologies like XPath, XSLT and XUpdate to query, transform 
and manipulate RDF. Also included are two applications that utilize Rx4RDF:
Rhizome, a wiki-like content management and delivery system, and RDFScribbler,
for viewing and editing RDF models."""
	  )
