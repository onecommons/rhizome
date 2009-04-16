"""
    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
__all__ = ["raccoon", "utils", 'htmlfilter',
        "RxPath", 'RxPathSchema', "RxPathGraph", "RxPathModel", 'RxPathUtils',
       "rxml", "zml", 'ExtFunctions', 'XhtmlWriter','DomStore', "RxPathDom",
       'Caching', 'ContentProcessors', 'UriResolvers', 'transactions', 
       "rhizome", 'RhizomeBase', 'RhizomeContent','RhizomeAuth','RhizomeCmds',
       #3rd party libraries with varying degrees of modifications:
       "Server", "XUpdate", 'MRUCache', "DomTree", 'akismet',
       "glock", "metakitdriver", "htmldiff", 
       #globals:
       'hasFt' ]

__version__ = '0.7.0'

#XXX cleanup
try:
    import Ft
    hasFt = True
except ImportError:
    hasFt = False
    #raise 'Rx4RDF requires the 4Suite package from Fourthought. It can be found at http://4suite.org'

import logging

#for python 2.3 compatibility use "from rx import set"
try:
    set = set
    frozenset = frozenset
except NameError:
    import sets
    set = sets.Set
    frozenset = sets.ImmutableSet

#for pythons older than 2.5:
try:
    all = all
    any = any
except NameError:
    def all(iterable):
         for element in iterable:
             if not element:
                 return False
         return True

    def any(iterable):
         for element in iterable:
             if element:
                 return True
         return False