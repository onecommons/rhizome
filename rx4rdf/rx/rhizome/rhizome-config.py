"""
    Config file for Rhizome

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

##############################################################################
## the core of Rhizome: here we define the pipeline for handling requests
##############################################################################
#find 1st match, context is root
resourceQueries=[
'/*[wiki:name=$action]', #invoke action, e.g. mypage.html?action=edit
'/*[wiki:name=$_name]',  #view the resource
#name not found, see if there's an external file on the Racoon path with this name:
'''wf:if(wf:file-exists($_name), "wf:assign-metadata('externalfile', wf:string-to-nodeset($_name))")''',
"$NOTFOUND", #just a debugging hack to generate a message "warning: variable $NOTFOUND not defined"
"/*[wiki:name='_not_found']", #invoke the not found page 
]

#context is now the resource, now set the context to a version of the resource
revisionQueries=[
'wiki:revisions/*[number($revision)]', #view a particular revision e.g. mypage.html?revision=3
#todo: select the released version if not specified and owner isn't current user
'wiki:revisions/*[last()]', #get the latest if not specified
]

#now see if we're authorized to handle this request
#simple authorization system for now: 'system' owned resources are read-only
authorizationQueries=['''xf:if(wiki:item-disposition='http://rx4rdf.sf.net/ns/wiki#item-disposition-handler'
   and /*[wiki:name=$itemname]/wiki:owned_by='http://rx4rdf.sf.net/ns/wiki#owner-system',
   /*[wiki:name='_not_authorized'])''', #if not authorized, set the context to the _not_authorized page
   '.', #if we made it here, we're authorized - don't change the context
]

#finally have a resource, get its content
contentQueries=[
'''wf:if(a:contents/a:ContentCollection, "wf:assign-metadata('REDIRECT', 'dir.xsl')")''', #todo
'.//a:contents/text()', 
'wf:openurl(.//a:contents/a:ContentLocation)', #contents stored externally
'wf:openurl(wf:ospath2pathuri($externalfile))', #external file
]

#looks for content encodings, finds ALL matches in order, context is resource
encodingQueries=[
'.//a:contents/a:ContentTransform/a:transformed-by/*',
]

# we're done processing request, see if there are any template resources we want to pass the results onto.
templateQueries=[
'''$REDIRECT''', #set this to the resource you want to redirect to
'''xf:if($externalfile,$STOP)''', #short circuit -- $STOP is a magic variable that stops the evaluation of the queries
'/*[wiki:handles-doctype/*=$_context/wiki:doctype/*]',
'''xf:if(wiki:item-disposition/*='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete', $STOP)''', #short circuit
'''xf:if(wiki:item-disposition/*='http://rx4rdf.sf.net/ns/wiki#item-disposition-template', $STOP)''', #short circuit
'/*[wiki:handles-disposition=$_context/wiki:item-disposition]',
#'''/*[wiki:name='_default-template']''', #todo??
]

import rx.rhizome
if not hasattr(__server__, 'rhizome') or not __server__.rhizome: #make executing this config file idempotent
    rhizome = rx.rhizome.Rhizome(__server__)
    __server__.rhizome = rhizome
else:
    rhizome = __server__.rhizome
rhizome.BASE_MODEL_URI = locals().get('BASE_MODEL_URI', __server__.BASE_MODEL_URI)

rhizome.getRevisionAction = Action(revisionQueries)
rhizome.getContentAction = Action(contentQueries, lambda result, kw, contextNode, retVal, self=__server__:\
                                  self.getStringFromXPathResult(result), requiresContext = True) #get its content
rhizome.processContentAction = Action(encodingQueries, __server__.processContents, matchFirst = False, forEachNode = True) #process the content 

handleRequestSequence = [ Action(resourceQueries), rhizome.getRevisionAction, #first find the resource
      Action(authorizationQueries), #see if the user is authorized to access it
      rhizome.getContentAction,#then get its content
      rhizome.processContentAction, #process the content            
      Action(templateQueries, rhizome.getResourceAction), #invoke a templates
    ]

rhizome.handleRequestSequence = handleRequestSequence

actions = { 'handle-request' : handleRequestSequence,
            #rhizome adds two command line options: --import and --export
            'run-cmds' : [ Action(["$import", '$i'], lambda result, kw, contextNode, retVal, rhizome=rhizome: rhizome.doImport(result[0], **kw)),
                           Action(['$export', '$e'], lambda result, kw, contextNode, retVal, rhizome=rhizome: rhizome.doExport(result[0], **kw)),
                        ]
          }

##############################################################################
## other config settings
##############################################################################
nsMap = {'a' : 'http://rx4rdf.sf.net/ns/archive#',
        'dc' : 'http://purl.org/dc/elements/1.1/#',
        'wiki' : "http://rx4rdf.sf.net/ns/wiki#",
         }

import os 
PATH= __server__.PATH + os.pathsep + os.path.split(__configpath__[-1])[0]

cmd_usage = '''--import [dir or filepath] [--recurse] [--dest path] [--xupdate url] [--format format] [--disposition disposition]
            --export dir [--static]'''

# we define a couple of content processor here instead of in Racoon because
# they make assumptions about the underlying schema 
import rhizml
contentProcessors = {
    'http://rx4rdf.sf.net/ns/content#pydiff-patch-transform':
        lambda self, contents, kw, result, context, rhizome=rhizome: rhizome.processPatch(contents, kw, result),     
    'http://www.w3.org/1999/XSL/Transform' : lambda self, contents, kw, result, context:\
        self.processXslt(contents, kw['_contents'], kw, self.evalXPath( #this stylesheet transforms kw['_contents'] not the rdf model
            'concat("site:///", (/a:NamedContent[wiki:revisions/*[.=$_context]]/wiki:name)[1])',node=context) ), 
    'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml' :
        lambda self, contents, kw, result, context, rhizml=rhizml, mmf=rx.rhizome.MarkupMapFactory(): rhizml.rhizmlString2xml(contents,mmf)
    #'http://rx4rdf.sf.net/ns/wiki#item-format-wikiml-akara' : lambda self, contents, *args: rhizome.processAkaraMarkup(contents),
}

def getrxrxity(context, resultset = None, comment = ''):
      import rxml
      if resultset is None:
            [ node ] = context.node
      return rxml.getRXAsRhizmlFromNode(resultset, rescomment = comment)
     
extFunctions = {
(RXWIKI_XPATH_EXT_NS, 'get-rdf-as-rhizml'): getrxrxity,
}

STORAGE_PATH = "./wikistore.nt"
STORAGE_TEMPLATE_PATH = "./wikistore-template.nt"

##############################################################################
## Define the template for a Rhizome site
##############################################################################
templateList = rhizome.addItemTuple('_not_found',loc='path:_not_found.xsl', format='rxslt', disposition='entry')\
+ rhizome.addItemTuple('edit',loc='path:edit.xsl', format='rxslt', disposition='entry')\
+ rhizome.addItemTuple('save',loc='path:save-handler.py', format='python', disposition='handler')\
+ rhizome.addItemTuple('delete', loc='path:delete.xml', format='rxupdate', disposition='handler')\
+ rhizome.addItemTuple('basestyles.css',format='text', loc='path:basestyles.css')\
+ rhizome.addItemTuple('edit-icon.png',loc='path:edit.png')\
+ rhizome.addItemTuple('list',loc='path:list-page.py', format='python', disposition='entry')\
+ rhizome.addItemTuple('showrevisions',loc='path:showrevisions.xsl', format='rxslt', disposition='entry')\
+ rhizome.addItemTuple('dump.xml', contents="print __requestor__.server.dump()", format='python')\
+ rhizome.addItemTuple('item-disposition-handler-template',format='python', disposition='entry', handlesDisposition='handler',
          contents="print '''<div class='message'>Completed <b>%(_name)s</b> of <a href='%(itemname)s'><b>%(itemname)s<b></a>!</div>'''%locals()")\
+ rhizome.addItemTuple('metadata_save',contents="__requestor__.server.rhizome.metadata_save(about, metadata)", format='python', disposition='handler')\
+ rhizome.addItemTuple('edit-metadata',loc='path:edit-metadata.xsl', format='rxslt', disposition='entry')\
+ rhizome.addItemTuple('_not_authorized',contents="<div class='message'>Error. You are not authorized to perform this operation on this page.</div>",
                  format='xml', disposition='entry')
#+ rhizome.addItemTuple('_default-template',loc='path:_default_template.xsl', disposition='template', format='rxslt')\

#forrest templates, essentially recreates forrest/src/resources/conf/sitemap.xmap 
templateList += rhizome.addItemTuple('faq2document.xsl', loc='path:faq2document.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='faq')\
+ rhizome.addItemTuple('document2html.xsl', loc='path:document2html.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='entry', handlesDoctype='document')\
+ rhizome.addItemTuple('site-template',loc='path:site-template.xsl', disposition='template', format='rxslt',handlesDisposition='entry')\
+ rhizome.addItemTuple('spec2html.xsl', loc='path:spec2html.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='complete', handlesDoctype='specification')\
+ rhizome.addItemTuple('docbook2document.xsl', loc='path:docbook2document.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='docbook')
#+ rhizome.addItemTuple('todo2document.xsl', loc='path:todo2document.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='todo')\
  
#help and sample pages
templateList += rhizome.addItemTuple('index',loc='path:index.txt', format='rhizml', disposition='entry', owner=None)\
+rhizome.addItemTuple('sidebar',loc='path:sidebar.txt', format='rhizml', owner=None)\
+rhizome.addItemTuple('TextFormattingRules',loc='path:TextFormattingRules.txt', format='rhizml', disposition='entry')\
+rhizome.addItemTuple('MarkupFormattingRules',loc='path:MarkupFormattingRules.txt', format='rhizml', disposition='entry')\
+rhizome.addItemTuple('RhizML',loc='path:RhizML.rz', format='rhizml', disposition='entry')\
+rhizome.addItemTuple('SandBox', format='rhizml', disposition='entry', owner=None,
	contents="Feel free to [edit|?action=edit] this page to experiment with [RhizML]...")

templateMap = dict(templateList) #create a map so derived sites can replace pages: for example, see site-config.py
STORAGE_TEMPLATE = "".join(templateMap.values()) #create a NTriples string

def addStructure(type, structure):
    n3 = ''
    for name, label in structure:
        n3 += '''<%s> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <%s> .\n''' % (name, type)
        n3 += '''<%s> <http://www.w3.org/2000/01/rdf-schema#label> "%s" .\n''' % (name, label)
    return n3

itemFormats = [ ('http://rx4rdf.sf.net/ns/wiki#item-format-binary', 'Binary'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-text', 'Text'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-xml', 'XML/XHTML'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-rxslt', 'RxSLT'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate', 'RxUpdate'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-python', 'Python'),
                ('http://www.w3.org/1999/XSL/Transform', 'XSLT'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-rhizml', 'RhizML'),
              ]

itemDispositions = [ ('http://rx4rdf.sf.net/ns/wiki#item-disposition-complete', 'Page'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-entry', 'Entry'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-template', 'Template'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-handler', 'Handler'),            
              ]

docTypes = [ ('http://rx4rdf.sf.net/ns/wiki#doctype-faq', 'FAQ'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-xhtml', 'XHTML'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-document', 'Document'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-specification', 'Specification'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-docbook', 'DocBook'),
              ]

APPLICATION_MODEL= addStructure('http://rx4rdf.sf.net/ns/wiki#ItemFormat', itemFormats)\
                   + addStructure('http://rx4rdf.sf.net/ns/wiki#ItemDisposition', itemDispositions)\
                  + addStructure('http://rx4rdf.sf.net/ns/wiki#DocType', docTypes)

