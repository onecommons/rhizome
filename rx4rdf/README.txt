                            README

                         Rx4RDF and Rhizome
                         Version 0.3.0
                         May 12, 2004
 
  Introduction
  ------------
  This is the latest release of Rx4RDF and Rhizome.  It is 
  alpha quality: not many known bugs, but many missing features and not 
  extensively tested. Please send feedback to rx4rdf-discuss@lists.sf.net

  What is it?
  -----------
  Rx4RDF is a specification and reference implementation for           
  querying, transforming and updating RDF.
  
  Rhizome is a Wiki-like content management and delivery system built on 
  Rx4RDF that treats everything as RDF and generalizes the Wiki concept 
  in several ways.
  
  What's new in this release?
  ---------------------------  
  This release is focused on making Rhizome usable for running small-scale 
  web sites:
  
  * Much improved documentation, including manuals for Rhizome, Raccoon and ZML.

  * Many features added to Rhizome -- it now has (nearly) all the functionality 
  you'd expect in a full-featured Wiki. It also much easier to browse and edit
  the underlying RDF model (and the default template is less ugly).

  * Raccoon's security has been enhanced by disabling potentially dangerous 
  settings by default and by the creation of an audit log of changes to the 
  database. Rhizome now supports fine-grained authorization of the changes 
  to the RDF model and provides a secure default authorization schema.
  
  For a listing of all the major changes see changelog.txt for more details.

  Known (major) bugs
  ----------
  (Also see http://rx4rdf.liminalzone.org/Status for more general information.)
  
  Rx4RDF
  * See comment at top of RxPathDom.py for discrepancies with the RxPath
  specification. 
  * RxSLT doesn't handle xsl:copy-of as specified in the RxPath spec.
  
  Raccoon
  * The stand-alone http server sometimes throws socket exceptions with the message 
  "(10053, 'Software caused connection abort')", but this appears to be harmless
  (I think it only happens when the browser aborts the connection).
  * The global write lock doesn't seem to work correctly on CygWin and is disabled 
  on that platform.
  * When using file-based sessionsm, the files aren't deleted when the session ends.
  
  Rhizome
  * dynamic pages might not behave as expected since Rhizome doesn't set headers
    such as Pragma NoCache or Expires -- if you need that you'll have set them 
    yourself (for example, by modifying site-template.xsl).
    
  Requirements
  ------------
    
  Rx4RDF requires Python 2.2 or later and 4Suite 1.0a1 or later (4Suite.org).
   
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
  <python scripts dir>/run-raccoon -a site-config.py
  browse to http://localhost:8000 (edit server.cfg to change the port).
   
  Licensing
  ---------

  This software is licensed under GPL. It can be found in the file
  named "COPYING" in this directory.
 
  Feedback
  --------
  
  Questions? Comments? Bug reports? Any feedback is greatly appreciated --
  send them to rx4rdf-discuss@lists.sf.net