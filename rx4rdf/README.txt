                            README

                         RxRDF and Rhizome
                         Version 0.1.3
                         Oct. 30, 2003
 
  Introduction
  ------------
  This is (nearly) the first public release of Rx4RDF and Rhizome.  It is 
  alpha quality: not many known bugs, but many missing features and not 
  extensively tested. Please send feedback to rx4rdf-discuss@lists.sf.net

  What is it?
  -----------
  Rx4RDF is a specification and reference implementation for           
  querying, transforming and updating RDF.
  Rhizome is a Wiki-like content management and delivery system        
  built on Rx4RDF.

  Known bugs
  ----------
  (Also see http://rx4rdf.sf.net/Status for more general infomation.)
  
  Rx4RDF
  * See comment at top of RDFDom.py for discrepancies with the RxPath
  specification. In particular, the descendant axis is greedy -- it 
  doesn't only follow transitive relations.
  * RxSLT doesn't handle xsl:copy as specified in the RxPath spec.
  
  Racoon
  * when saving a page or metadata the whole RDF model is reloaded but 
  the Action still has a reference to the old model which might lead 
  to expected behavior when developing custom applications.

  Rhizome
  * WARNING: Delete displays an error message but still deletes the
    item. There is currently no confirmation page!
  * Search doesn't work
  * You can only view the current and previous revisions, older ones 
    result in an error (but they're there).
    
  Documentation
  -------------

  Unfortunately the /doc directory is currently empty, to view documentation 
  (such as it is) visit http://rx4rdf.sf.net or run the local copy of the site 
  in the /site directory:
  
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