try:
    includedir=__argv__[__argv__.index("--includedir")+1]
except (IndexError, ValueError):
    includedir='.'
__include__(includedir + '/test-config.py')

#use our sample theme
__addRxML__(replace = '@sitevars', contents = """
 base:site-template:
  wiki:header-text: '''<h1>Test Theme</h1>
<h2>Let's use the other theme!</h2>'''
  wiki:uses-theme: base:movabletype-theme
  
 #unfortunately we also have to add this alias in addition to setting wiki:uses-theme
 #because site-template.xsl can only statically import an URL
 {%smovabletype/theme.xsl}:
    wiki:alias: `theme.xsl
"""% rhizome.BASE_MODEL_URI ) 

#save all content into the model (no external files)
MAX_MODEL_LITERAL = -1