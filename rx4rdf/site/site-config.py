#see site/content/RacoonConfig.txt for documentation on config file settings
BASE_MODEL_URI='http://rx4rdf.sf.net/site/'
__include__('../rhizome/rhizome-config.py')

#override default template by adding or replacing pages
__addItem__('RxPathSpec',loc='path:rxpathspec.txt', format='rhizml', doctype='specification')
__addItem__('faq',loc='path:faq.txt', format='rhizml', doctype='faq')
__addItem__('DocSample',loc='path:docsample.txt', format='rhizml', doctype='document')
#__addItem__('Todo',loc='path:todo.txt', format='rhizml', doctype='todo')

__addSiteVars__(
'''
 base:site-template:
  wiki:header-image: `Rx4RDFlogo.gif
  wiki:header-text: `
 
 ;rhizome leaves the index and sidebar pages publicly editable, lock them down:
 base:index:
   auth:needs-token: base:write-structure-token

 base:sidebar:
   auth:needs-token: base:write-structure-token 
''')


