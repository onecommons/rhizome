#see site/content/RaccoonConfig.txt for documentation on config file settings
BASE_MODEL_URI='http://rx4rdf.sf.net/site/'
__include__('../rhizome/rhizome-config.py')

externalLinkIndicator=False
interWikiLinkIndicator=False

#override default template by adding or replacing pages
__addItem__('RxPathSpec',loc='path:content/RxPathSpec.zml', format='zml', 
            disposition='complete', doctype='specification')

__addSiteVars__(
'''
 base:site-template:
  wiki:header-image: `Rx4RDFlogo.gif
  wiki:header-text: `

 base:ZML:
  wiki:alias: `zml

 base:Rhizome:
  wiki:alias: `rhizome
 
 ;rhizome leaves the index and sidebar pages publicly editable, lock them down:
 base:index:
   auth:needs-token: base:write-structure-token
   wiki:alias: `rx4rdf
   wiki:alias: `Rx4RDF

 bnode:index1Item:
   wiki:title: `Rx4RDF
   
 base:sidebar:
   auth:needs-token: base:write-structure-token 
''')


