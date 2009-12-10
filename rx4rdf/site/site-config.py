#see rhizome/help/RaccoonConfig.txt for documentation on config file settings
BASE_MODEL_URI='http://rx4rdf.sf.net/site/'
__include__('../rhizome/rhizome-config.py')

externalLinkIndicator=False
interWikiLinkIndicator=False
undefinedPageIndicator=False

#import all zml pages into the model template
#(this makes development easier -- we can always recreated the site on load)
importedPages = rhizome.doImport('content/.rzvs/*.zml', 
   label='wiki:label-released', fixedBaseURI='path:.rzvs/', 
   token='base:save-only-token', save=False)
templateMap.update(importedPages)

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

__addItem__('extreme2006.html',loc='path:.rzvs/extreme2006.html', format='xml', 
       accessTokens=['base:save-only-token'], disposition='complete')

__addItem__('www2006',loc='path:.rzvs/www2006.zml', format='zml', 
       title='Introducing Rhizome', 
       accessTokens=['base:save-only-token'], disposition='s5-template')

__addItem__('sri',loc='path:.rzvs/sri.zml', format='zml', 
       title='Semantic Wikis and Microformats', 
       accessTokens=['base:save-only-token'], disposition='s5-template')

__addItem__('codecon2006',loc='path:.rzvs/codecon.zml', format='zml',
       title='CodeCon 2006',
       accessTokens=['base:save-only-token'], disposition='s5-template')

__addRxML__(replace = '@sitevars', contents = '''
 base:site-template:
  wiki:header-image: `Rx4RDFlogo.gif
  wiki:header-text: `
  wiki:footer-text: `&#169; 2005 Liminal Systems All Rights Reserved
  wiki:uses-theme: base:default-theme
  wiki:uses-skin:  base:skin-lightblue.css

 bnode:FAQ1Item:
   wiki:doctype: wiki:doctype-faq   

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

 base:www2006:
    wiki:footer-text: "Adam Souzis &#8226; WWW2006"
''')

__addRxML__(replace = '@rx4rdfAliases', contents = '''
 base:index:
   wiki:alias: `rx4rdf
   wiki:alias: `Rx4RDF
   
 bnode:index1Item:
   wiki:title: `Rx4RDF   
''')

