                            README

                         Rx4RDF and Rhizome
                         Version 0.2.0
                         Feb 29, 2004
 
  Introduction
  ------------
  This is the third release of Rx4RDF and Rhizome.  It is 
  alpha quality: not many known bugs, but many missing features and not 
  extensively tested. Please send feedback to rx4rdf-discuss@lists.sf.net

  What is it?
  -----------
  Rx4RDF is a specification and reference implementation for           
  querying, transforming and updating RDF.
  
  Rhizome is a Wiki-like content management and delivery system built on 
  Rx4RDF that generalizes the wiki concept in several ways.
  
  What's new in this release?
  ---------------------------  
  RxPath has been completely reimplemented. The first implementation was a 
  proof-of-concept, this one is intended for production use. 
  Enhancements include: signficant performance boost, retrieves statements 
  from the underlying model on demand, incrementally updates the underlying model, 
  support transactions and rollback, and provides RDF model independence through 
  a simple API (includes adapters for 4Suite and Redland).
  
  Racoon is several times faster as result of adding various caches throughout 
  the request pipeline (taking advantage of the (nearly) side-effect free nature
  of XPath and XSLT).

  In addition there have several other enhancements, see changelog.txt for more
  details.

  Known (major) bugs
  ----------
  (Also see http://rx4rdf.liminalzone.org/Status for more general information.)
  
  Rx4RDF
  * See comment at top of RxPathDom.py for discrepancies with the RxPath
  specification. In particular, the descendant axis is too greedy -- it 
  doesn't only follow transitive relations.
  * RxSLT doesn't handle xsl:copy-of as specified in the RxPath spec.
  
  Racoon
  * The stand-alone http server often throws socket exceptions with the message 
  "(10053, 'Software caused connection abort')", but this appears to be harmless.
  * The global write lock doesn't seem to work correctly on CygWin and is disabled 
  on that platform.
  
  Rhizome
  * Rhizome stores previous revisions as a diff against the next version
  so if you directly change the content file on disk, the Rhizome will not 
  be able reconstruct the diff.
  * Unrelated to this, you can only view the current and previous revisions, 
  trying to view older ones result in an error (but they are there -- the  
  query fails because of the above mentioned greedy descendant axis bug).
    
  Requirements
  ------------
    
  Rx4RDF requires Python 2.2 or later and 4Suite 1.0a1 (4Suite.org).
   
  Rx4RDF and Rhizome are known to run on Linux, Windows 2000 and Cygwin 
  and should work on any platform that supports Python and 4Suite.
  
  On Windows, the Python Win32 Extensions (python.org/windows/win32all) 
  must be installed or locking will be disabled.
  
  Installation
  ------------

  This is a standard Python source distribution. To install:

  1. Unzip
  2. Run python <unzip dir>/setup.py install     
  
  docs/Download contains a quick start guide.

  Documentation
  -------------
  
  The /docs directory is contains a static export of the Rx4RDF site.
  Alternatively, you can visit http://rx4rdf.sf.net for the latest content 
  or run the local copy of the site found in the /site directory:
  
  cd <unzip dir>/site
  python ../rx/racoon.py -a site-config.py
  browse to http://localhost:8000 (edit server.cfg to change the port).
   
  Licensing
  ---------

  This software is licensed under GPL. It can be found in the file
  named "COPYING" in this directory.
 
  Feedback
  --------
  
  Questions? Comments? Bug reports? Any feedback is greatly appreciated --
  send them to rx4rdf-discuss@lists.sf.net