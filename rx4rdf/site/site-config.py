BASE_MODEL_URI='http://rx4rdf.sf.net/site/'
__include__('../rx/rhizome/rhizome-config.py')

#override default template by adding or replacing pages
templateList =  rhizome.addItemTuple('RxPathSpec',loc='path:rxpathspec.txt', format='rhizml', doctype='specification')\
+ rhizome.addItemTuple('faq',loc='path:faq.txt', format='rhizml', doctype='faq')\
+ rhizome.addItemTuple('DocSample',loc='path:docsample.txt', format='rhizml', doctype='document')
#+ rhizome.addItemTuple('Todo',loc='path:todo.txt', format='rhizml', doctype='todo')\

templateMap.update( dict(templateList))
STORAGE_TEMPLATE = "".join(templateMap.values())
