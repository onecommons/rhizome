"""
    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
__all__ = ["raccoon", "RxPathDom", "RxPath", "utils", 
           "rxml", "rhizome", "zml",
           #3rd party libraries with varying degrees of modifications:
           "Server", "XUpdate", 'MRUCache', "DomTree", 
           "glock", "metakitdriver", "htmldiff" ]

__version__ = '0.3.1'

try:
    import Ft
except ImportError:
    raise 'Rx4RDF requires the 4Suite package from Fourthought. It can be found at http://4suite.org'

import sys
if sys.version_info < (2, 3):
    import logging22 as logging
else:
    import logging
#for python 2.2 compatibility use 'from rx import logging' instead of import logging
