from rx import rxml
outdoc = rxml.zml2RDF_XML(contents=__kw__['rxmlAsZML'])
from Ft.Xml.Lib.Print import PrettyPrint
import sys
PrettyPrint(outdoc, stream=sys.stdout)