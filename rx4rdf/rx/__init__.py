"""
    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
__all__ = ["racoon", "RDFDom", "DomTree", "utils", 
           "rxml", "rhizome", "rhizml", "rhizmltokenize",
           "Server", "XUpdate", "glock", "metakitdriver"]
try:
    import Ft
except ImportError:
    raise 'Rx4RDF requires the 4Suite package from Fourthought. It can be found at http://4suite.org'

import sys
if sys.version_info < (2, 3):
    import logging22 as logging
else:
    import logging
logging = logging #for python 2.2 compatibility use 'from rx import logging'