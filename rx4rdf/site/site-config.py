#see rhizome/help/RaccoonConfig.txt for documentation on config file settings
BASE_MODEL_URI='http://rx4rdf.sf.net/site/'
__include__('../rhizome/rhizome-config.py')

externalLinkIndicator=False
interWikiLinkIndicator=False
undefinedPageIndicator=False

#import all zml pages into the model template
#(this makes development easier -- we can always recreated the site on load)
templateMap.update(rhizome.doImport('content/.rzvs/*.zml', 
   label='wiki:label-released', fixedBaseURI='path:.rzvs/', 
   token='base:save-only-token', save=False))

#override default template by adding or replacing pages
__addItem__('RxPathSpec',loc='path:.rzvs/RxPathSpec.zml', format='zml', 
            title="RxPath Specification", accessTokens=['base:save-only-token'],
            disposition='complete', doctype='specification')

__addItem__('FOAFPaper',loc='path:.rzvs/FOAFPaper.zml', format='zml', 
            title="Rhizome Position Paper", accessTokens=['base:save-only-token'],
            disposition='entry', doctype='document')

__addItem__('archive-schema.rdf',loc='path:archive-schema.rdf', format='text', 
       accessTokens=['base:save-only-token'], disposition='complete')
__addItem__('changelog.txt',loc='path:.rzvs/changelog.txt', format='text', 
       accessTokens=['base:save-only-token'], disposition='complete')
__addItem__('xupdate-wd.html',loc='path:.rzvs/xupdate-wd.html', format='xml', 
       accessTokens=['base:save-only-token'], disposition='complete')

__addRxML__(replace = '@sitevars', contents = '''
 base:site-template:
  wiki:header-image: `Rx4RDFlogo.gif
  wiki:header-text: `
  wiki:footer-text: `&#169; 2005 Liminal Systems All Rights Reserved
  wiki:uses-theme: base:default-theme
  wiki:uses-skin:  base:skin-lightblue.css
  
 base:ZML:
  wiki:alias: `zml
  wiki:alias: `RhizML

 base:Rhizome:
  wiki:alias: `rhizome

 base:Raccoon: 
  wiki:alias: `Racoon
    
 #rhizome-config leaves the index and sidebar pages publicly editable, lock them down:
 base:index:
   auth:guarded-by: base:save-only-token
   
 base:sidebar:
   auth:guarded-by: base:save-only-token 
''')

__addRxML__(replace = '@rx4rdfAliases', contents = '''
 base:index:
   wiki:alias: `rx4rdf
   wiki:alias: `Rx4RDF
   
 bnode:index1Item:
   wiki:title: `Rx4RDF   
''')

