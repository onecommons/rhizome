                            README

                         Rx4RDF and Rhizome
                         Version 0.1.3
                         Dec 15, 2003
 
  Introduction
  ------------
  This is the second release of Rx4RDF and Rhizome.  It is 
  alpha quality: not many known bugs, but many missing features and not 
  extensively tested. Please send feedback to rx4rdf-discuss@lists.sf.net

  What is it?
  -----------
  Rx4RDF is a specification and reference implementation for           
  querying, transforming and updating RDF.
  Rhizome is a Wiki-like content management and delivery system        
  built on Rx4RDF.

  What's new in this release?
  ---------------------------
  * Major changes to Rhizome (and Racoon): it now supports users, sessions, 
  authentication, and authorization (via access tokens, permissions, roles, 
  and authorization groups). To modify structural pages you must now login 
  in as the default administrator: login "admin", default password "admin".
       
  * Logging is now used throughout Rx4RDF and Rhizome (including with Python 2.2). 
  The command line option -l [log.config] will load the specified log config file. 
  
  * Many minor bug fixes and a few critical ones, including support for Python 2.3.
  
  * Other changes include search (output as RSS or HTML), improved RhizML and more.
  See changelog.txt for more details.

  Known bugs
  ----------
  (Also see http://rx4rdf.liminalzone.org/Status for more general infomation.)
  
  Rx4RDF
  * See comment at top of RDFDom.py for discrepancies with the RxPath
  specification. In particular, the descendant axis is too greedy -- it 
  doesn't only follow transitive relations.
  * RxSLT doesn't handle xsl:copy as specified in the RxPath spec.
  
  Racoon
  * The stand-alone http server often throws socket exceptions, but this appears
  to be harmless.
  * when saving a page or metadata the whole RDF model is reloaded but 
  the Action still has a reference to the old model which might lead 
  to unexpected behavior when developing custom applications.

  Rhizome
  * Rhizome stores previous revisions as a diff against the next version
  so if you change the content file on disk or use the "minor edit" checkbox, 
  the Rhizome will not be able reconstruct the diff.
  * Unrelated to this, you can only view the current and previous revisions, 
  trying to view older ones result in an error (but they are there).
    
  Documentation
  -------------

  Unfortunately the /doc directory is currently empty, to view documentation 
  (such as it is) visit http://rx4rdf.sf.net or run the local copy of the site 
  in the /site directory:
  
  cd <unzip dir>/site
  python ../rx/racoon.py -a site-config.py
  browse to http://localhost:8000 (edit server.cfg to change the port).

  Or you can view the raw content in site/content.
  
  Licensing
  ---------

  This software is licensed under GPL. It can be found in the file
  named "COPYING" in this directory.
 
  Feedback
  --------
  
  Questions? Comments? Bug reports? Any feedback is greatly appreciated --
  send them to rx4rdf-discuss@lists.sf.net