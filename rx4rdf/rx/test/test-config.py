try:
    rhizomedir=__argv__[__argv__.index("--rhizomedir")+1]
except (IndexError, ValueError):
    rhizomedir='../rhizome'
__include__(rhizomedir + '/rhizome-config.py')

__addItem__('assert', format='xml', disposition='entry', contents=
'''
<form method="POST" action="site:///run-assert" enctype="multipart/form-data">	         
	<textarea NAME="code" ROWS="15" COLS="75" STYLE="width:100%" WRAP="off"></textarea>
	<input TYPE="submit" NAME="process" VALUE="Execute" />
</form>
''')

__addItem__('run-assert', format='python', disposition='complete', contents=
r'''
exec __kw__['code'].replace('\r', '\n')+'\n'
''')

__addRxML__(replace = '@sitevars', contents = """
 base:site-template:
  wiki:header-text: '''<h1>Be The Media</h1>
<h2>Independent Media Begins With You!</h2>'''
  wiki:uses-theme: base:movabletype-theme
  
 #unfortunately we also have to add this alias in addition to setting wiki:uses-theme
 #because site-template.xsl can only statically import an URL
 {%smovabletype/theme.xsl}:
    wiki:alias: `theme.xsl
"""% rhizome.BASE_MODEL_URI ) 

useIndex = False #for startup speed for testing, disable indexing 

LIVE_ENVIRONMENT=1

#disable Python content authorization
authorizeContentProcessors['http://rx4rdf.sf.net/ns/wiki#item-format-python'] = lambda *args: 1

if __argv__.count('--testplayback'):
    #make these variables visible to all requests  
    globalRequestVars = globalRequestVars + ['_noErrorHandling', '__noConflictDetection']
    rhizome.findResourceAction.assign('_noErrorHandling', '1') #we want errors to propagate up to the unittest framework
    rhizome.findResourceAction.assign('__noConflictDetection', '1') #used by save.xml so we can recreate pages using old edit requests
    #replace the page not found rule so that we don't invoke an error for not found pages:
    resourceQueries[-1]="/*[wiki:name='_not_found']"