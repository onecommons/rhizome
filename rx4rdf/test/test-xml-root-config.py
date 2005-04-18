try:
    rhizomedir=__argv__[__argv__.index("--rhizomedir")+1]
except (IndexError, ValueError):
    rhizomedir='../rhizome'

xmlConfig = True    
__include__(rhizomedir + '/root-config.py')

STORAGE_TEMPLATE='''<server xmlns='http://rx4rdf.sf.net/ns/raccoon/config#' >
  <host model-uri='http://www.foo.com/'
     config-path="test-links.py"
     path="." >
   <hostname>foo.com</hostname>
   <hostname>foo.org</hostname>
   <hostname>foo.bar.org</hostname>
 </host>
 
  <host model-uri='http://bar.org/bar/'
     config-path="test-links.py"
     path="." 
     appBase="/bar"
     appName="bar"
  />
</server>'''


