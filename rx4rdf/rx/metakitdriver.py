'''
    Work-around to avoid the assumption Ft.Rdf.Drivers.MetaKit
    makes about the filepaths MetaKit uses

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
'''
import metakit
from Ft.Rdf.Drivers import MetaKit


def GetDb(dbName,modelName='default'):
    db =  MetaKit.DbAdapter("", modelName)
    db._fName = dbName            
    return db
    
def CreateDb(dbName, modelName='default'):
    # database version
    db = metakit.storage(dbName, 1)
    vw = db.getas(MetaKit.VERSION_VIEW)
    vw.append(version=MetaKit.VERSION)
    db.commit()
    return GetDb(dbName, modelName)