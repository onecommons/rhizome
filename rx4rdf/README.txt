                            README

                         Rx4RDF and Rhizome
                         Version 0.5.0
                         Sep 28, 2005
 
  Introduction
  ------------
  This is the latest release of Rx4RDF and Rhizome. It is 
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
  Major changes since last announced release (0.4.3):

  Major changes to the Raccoon application server:
  * enable URL namespace to be mapped to multiple applications
  * allow applications to use XML (instead of RDF) data stores
  * added SQL-like triggers
  * added two-phase commit transaction coordinator
  Major changes to Rhizome:
  * Added a new, more polished and usable default theme.
  * Made fine-grained authentication of changes to the model ubiquitous, 
    made authorization schema much more flexible and expressive.
  * Now uses Schematron (via RxPath) to validate the RDF model.  
  Refactored and cleaned-up code base.
  Plus many other enhancements.
      
  For a detailed list of all major changes see docs/changelog.txt.
          
  Requirements
  ------------
    
  Rx4RDF requires Python 2.2 or later (2.3 recommended) and 4Suite 1.0a1 
  or later (http://4Suite.org).
   
  Rx4RDF and Rhizome are known to run on Linux and Windows 2000/XP 
  and should work on any platform that supports Python and 4Suite. 
      
  Optional Packages:
  
  If Lupy is installed (http://www.divmod.org/Home/Projects/Lupy), Rhizome will
  perform full-text indexing of content (requires Python 2.3). 
  See the Rhizome manual for more info.
  
  On Windows, the Python Win32 Extensions (http://python.org/windows/win32all) 
  must be installed or interprocess file locking will be disabled (You do not 
  need this unless you have multiple Raccoon processes simultaneously accessing 
  the same application instance).
  
  Redland RDF data stores can be used if Redland (http://www.redland.opensource.ac.uk)
  is installed. See the Raccoon manual for more info.
  
  RDFLib data stores can be used if RDFLib (http://www.rdflib.net)
  is installed. See the Raccoon manual for more info. In addition, if RDFLib is 
  installed, its RDF/XML parser will be used by default (since the 4Suite's 
  parser doesn't support the latest RDF/XML syntax). 

  Installation
  ------------

  This is a standard Python source distribution. To install:

  1. Unzip
  2. cd <unzip dir>
  2. python setup.py install     
  
  docs/Download contains a quick start guide.
  
  docs/Upgrading contains notes on upgrading from the previous version.

  Documentation
  -------------
  
  The /docs directory contains a static export of the Rx4RDF site.
  Alternatively, you can visit http://rx4rdf.sf.net for the latest content 
  or run the local copy of the site found in the /site directory:
  
  cd <unzip dir>/site
  <Python scripts dir>/run-raccoon -a site-config.py
  browse to http://localhost:8000 (edit server.cfg to change the port).
  
  where <Python scripts dir> is "<Python install dir>\Scripts" on 
  Windows systems or on Unix-like systems usually "/usr/bin", 
  "usr/local/bin", or "~/bin".
  
  License
  ---------

  This software is licensed under GPL. It can be found in the file
  named "COPYING" in this directory.

  Known (major) bugs
  ------------------
  (Also see docs/Status for more general information.)
  
  Rx4RDF
  * See comment at top of RxPathDom.py for discrepancies with the RxPath
  specification. 
  * RxSLT doesn't handle xsl:copy-of as specified in the RxPath spec.
  * Using Ft.Xml.PrettyPrint with the RxPath DOM will only work some of the time.
    
  Raccoon
  * The global write lock doesn't seem to work correctly on CygWin and is disabled 
  on that platform.
  * When using file-based sessions, the files aren't deleted when the session ends.
  * The ROOT_PATH config setting doesn't work properly.

  Rhizome
  * Dynamic pages might not behave as expected since Rhizome doesn't set headers
    such as Pragma NoCache or Expires -- if you need that you'll have set them 
    yourself (for example, by modifying site-template.xsl).
  * You should not import files directly into the directory specified in the 
    ALTSAVE_DIR setting (the default is "content") -- if you do the first 
    revision of a file will overwrite the initial version. Instead import 
    files into the directory specified by SAVE_DIR (the default is 
    "content/.rzvs").
  * Deleting a page doesn't delete its file or remove its contents from the index.
  * When searching, the RxML and Edit views only support queries that evaluate 
    to a resource list (as opposed to a list of statement predicates, for example). 
  
  Feedback
  --------
  
  Questions? Comments? Bug reports? Any feedback is greatly appreciated --
  send them to rx4rdf-discuss@lists.sf.net