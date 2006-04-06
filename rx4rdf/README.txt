                            README

                         Rx4RDF and Rhizome
                         Version 0.6.0
                         Mar 31, 2006
 
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
  Major changes since last announced release (0.5.1):
  
  Rhizome: 
  * major performance enhancements: several times faster
  * supports GRDDL and "shredding", a framework for extracting
    RDF from content and maintaining the relationship over time.
  * better support for viewing and editing RDF directly with most RDF formats (RDF/XML, NTriples, Turtle).
  * new UI for editing users and roles
  * more Wiki features (including tracking missing pages)
  * page and comment spam detection via Akismet service    

  Rx4RDF:
  * much faster: now uses a simple but optimizing query engine
  * support for RDF named graphs (RDF contexts)    
  * better support for using RxPath in XML contexts (e.g. an XSLT page)
  * better support 3rd party RDF libraries and RDF stores

  Plus many other enhancements and bug fixes.
      
  For a detailed list of all major changes see docs/changelog.txt.
          
  Requirements
  ------------
    
  Rx4RDF requires Python 2.2 or later (2.4 recommended) and the 4Suite 
  XML and RDF libraries (at [http://4Suite.org], version 1.0a1 or later).
   
  Rx4RDF and Rhizome are known to run on Linux and Windows 2000/XP 
  and should work on any platform that supports Python and 4Suite. 
      
  Optional Packages:
  
  If Lupy is installed (http://www.divmod.org/Home/Projects/Lupy), Rhizome will
  perform full-text indexing of content (requires Python 2.3). 
  See the Rhizome manual for more info.
    
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
  * RxSLT's implementation of xsl:key is extremely slow and should be avoided.
  * Using Ft.Xml.PrettyPrint with the RxPath DOM will only work some of the time.
    
  Raccoon
  * When using file-based sessions, the files aren't deleted when the session ends.
  * On Windows and Cygwin, lock files are not deleted with the process ends.

  Rhizome
  * You should not import files directly into the directory specified in the 
    ALTSAVE_DIR setting (the default is "content") -- if you do the first 
    revision of a file will overwrite the initial version. Instead import 
    files into the directory specified by SAVE_DIR (the default is 
    "content/.rzvs").
  * Deleting a page doesn't delete its file or remove its contents from the index.
    Note that this can be a security concern, because those files will be still 
    accessible.
  
  Feedback
  --------
  
  Questions? Comments? Bug reports? Any feedback is greatly appreciated --
  send them to rx4rdf-discuss@lists.sf.net