"""
    Facade for the modules that implement Rhizome functionality
    These classes includes functionality dependent on the Rhizome schemas
    and so aren't included in the Raccoon module.

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx.RhizomeBase import *
from rx.RhizomeAuth import *
from rx.RhizomeCmds import *
from rx.RhizomeContent import *

class Rhizome(RhizomeContent, RhizomeAuth, RhizomeCmds): pass
