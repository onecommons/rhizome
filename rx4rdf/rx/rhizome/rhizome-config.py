"""
    Config file for Rhizome

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

#see site/content/RacoonConfig.txt for documentation on config file settings

import rx.rhizome
if not hasattr(__server__, 'rhizome') or not __server__.rhizome: #make executing this config file idempotent
    rhizome = rx.rhizome.Rhizome(__server__)
    __server__.rhizome = rhizome
else:
    rhizome = __server__.rhizome

rhizome.BASE_MODEL_URI = locals().get('BASE_MODEL_URI', __server__.BASE_MODEL_URI)
MAX_MODEL_LITERAL = 0 #will save all content to disk
##############################################################################
## the core of Rhizome: here we define the pipeline for handling requests
##############################################################################

#map the request to a resource in the model, finds 1st match, context is root
resourceQueries=[
'/*[wiki:name=$_name]',  #view the resource
"xf:if(starts-with($_name,'users-'), /*[wiki:login-name=substring($_name, 7)] )", #treat anything under /users/ as user
#name not found, see if there's an external file on the Racoon path with this name:
'''wf:if(wf:file-exists($_name), "wf:assign-metadata('externalfile', wf:string-to-nodeset($_name))")''',
"/*[wiki:name='_not_found']", #invoke the not found page 
]

#now see if we're authorized to handle this request
#if we're not, the resource context will be set to _not_authorized
#2 checks:
#1. super-user can always get in
#2. if either the resource or an authorization group it belongs to requires an auth token,
#   make sure the user or one of its roles has that token
authorizationQuery = '''xf:if ( not($_user/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser') and 
    count(./auth:needs-token/auth:AccessToken[auth:has-permission=$authAction] | ./auth:member-of/*/auth:needs-token/auth:AccessToken[auth:has-permission=$authAction])
!= count( (./auth:needs-token/auth:AccessToken[auth:has-permission=$authAction] | ./auth:member-of/*/auth:needs-token/auth:AccessToken[auth:has-permission=$authAction])
    [.=$_user/auth:has-token/* or .=$_user/auth:has-role/*/auth:has-token/*] ), %s)'''

#now find a resource that will be used to display the resource
contentHandlerQueries= [
#if the request has an action associated with it
'/*[wiki:handles-action=$authAction][wiki:action-for-type = $_context/rdf:type]', #[compatibleTypes(wiki:action-for-type/*,$_context/rdf:type/*)]',
#if the resource is content
'self::a:NamedContent',
#if the resource is set to the Unauthorized resource select the unauthorized page
"xf:if(self::auth:Unauthorized, /*[wiki:name='_not_authorized'])",
#default for any real resource (i.e. an resource element)
"xf:if(not(self::text()), /*[wiki:name='default-resource-viewer'])"
]

#context is now a content resource, now set the context to a version of the resource
revisionQueries=[
'wiki:revisions/*[number($revision)]', #view a particular revision e.g. mypage.html?revision=3
'wiki:revisions/*[wiki:has-label=$label]', #view a particular label if specified
'wiki:revisions/*[last()]', #get the last revision
]

#todo: revision queries to support draft/release workflow
##select the last one with a released label if not otherwise specified unless the current user is the owner of the last revision
#'''xf:if(wiki:revisions/*[last()]/wiki:owned_by[$user], wiki:revisions/*[last()],
#      (wiki:revisions/*[wiki:has-label='_released'])[last()] )''',
##none labeled released: just choose the last non-draft version (so we don't require this release label feature to be used)
#"(wiki:revisions/*[wiki:has-label!='_draft'])[last()]",
##no viewable revisions found, what to do??: invoke edit page? what if you don't have permission for that?
#"???" REDIRECT(not-viewable)?

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
#'''$REDIRECT''', #set this to the resource you want to redirect to
'''xf:if($externalfile,$STOP)''', #short circuit -- $STOP is a magic variable that stops the evaluation of the queries
'/*[wiki:handles-doctype/*=$_doctype]',
'''xf:if($_disposition='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete', $STOP)''', #short circuit
'''xf:if($_disposition='http://rx4rdf.sf.net/ns/wiki#item-disposition-template', $STOP)''', #short circuit
'/*[wiki:handles-disposition=$_disposition]',
#'''/*[wiki:name='_default-template']''', #todo??
]

findResourceAction = Action(resourceQueries)
#we want the first Action to set the $_user variable
findResourceAction.assign("_user", '/wiki:User[wiki:login-name=$session:login]',
                         "/wiki:User[wiki:login-name='guest']")
findResourceAction.assign("_resource", '.', post=True)

resourceAuthorizationAction = Action( [authorizationQuery % '/auth:Unauthorized'] )
#default to 'view' if not specified
resourceAuthorizationAction.assign("authAction", 'concat("http://rx4rdf.sf.net/ns/wiki#action-",$action)', "'http://rx4rdf.sf.net/ns/wiki#action-view'") 

#revisionAuthorizationAction = Action( [authorizationQuery % "/*[wiki:name='_not_authorized']/wiki:revisions/*[last()]"] )

rhizome.findRevisionAction = Action(revisionQueries)
rhizome.findContentAction = Action(contentQueries, lambda result, kw, contextNode, retVal, self=__server__:\
                                  self.getStringFromXPathResult(result), requiresContext = True) #get its content
rhizome.processContentAction = Action(encodingQueries, __server__.processContents, matchFirst = False, forEachNode = True) #process the content 

templateAction = Action(templateQueries, rhizome.processTemplateAction)
#setup these variables to give content a chance to have dynamically set them
templateAction.assign("_doctype", '$_doctype', "wiki:doctype/*")
templateAction.assign("_disposition", '$_disposition', "wiki:item-disposition/*")

handleRequestSequence = [ findResourceAction, #first map the request to a resource
      resourceAuthorizationAction, #see if the user is authorized to access it                          
      Action(contentHandlerQueries), #find a resource that can display this resource
      rhizome.findRevisionAction, #get the appropriate revision
      #revisionAuthorizationAction, #see if the user is authorized for this revision #todo
      rhizome.findContentAction,#then get its content
      rhizome.processContentAction, #process the content            
      templateAction, #invoke a template
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
         'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
         'rdfs' : 'http://www.w3.org/2000/01/rdf-schema#',
        'wiki' : "http://rx4rdf.sf.net/ns/wiki#",
         'auth' : "http://rx4rdf.sf.net/ns/auth#",
         'base' : rhizome.BASE_MODEL_URI
         }
rhizome.nsMap = nsMap

import os 
PATH= __server__.PATH + os.pathsep + os.path.split(__configpath__[-1])[0]

cmd_usage = '''\n\nrhizome-config.py specific:
--import [dir or filepath] [--recurse] [--dest path] [--xupdate url] [--format format] [--disposition disposition]
--export dir [--static]'''

# we define a couple of content processor here instead of in Racoon because
# they make assumptions about the underlying schema 
import rhizml
contentProcessors = {
    'http://rx4rdf.sf.net/ns/content#pydiff-patch-transform':
        lambda self, contents, kw, result, context, rhizome=rhizome: rhizome.processPatch(contents, kw, result),
    #this stylesheet transforms kw['_contents'] not the rdf model
    'http://www.w3.org/1999/XSL/Transform' : lambda self, contents, kw, result, context:\
        self.processXslt(contents, kw['_contents'], kw, uri=self.evalXPath( 
            'concat("site:///", (/a:NamedContent[wiki:revisions/*[.=$_context]]/wiki:name)[1])',node=context) ), 
    'http://rx4rdf.sf.net/ns/wiki#item-format-rhizml' :
        lambda self, contents, kw, result, context, rhizml=rhizml, mmf=rx.rhizome.MarkupMapFactory(): rhizml.rhizmlString2xml(contents,mmf)
}

import rxml
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
+ rhizome.addItemTuple('edit',loc='path:edit.xsl', format='rxslt', disposition='entry', handlesAction=['edit'])\
+ rhizome.addItemTuple('save',loc='path:save-handler.py', format='python', disposition='handler', handlesAction=['save', 'creation'])\
+ rhizome.addItemTuple('confirm-delete',loc='path:confirm-delete.xsl', format='rxslt', disposition='entry', handlesAction=['confirm-delete'])\
+ rhizome.addItemTuple('delete', loc='path:delete.xml', format='rxupdate', disposition='handler', handlesAction=['delete'])\
+ rhizome.addItemTuple('basestyles.css',format='text', loc='path:basestyles.css')\
+ rhizome.addItemTuple('edit-icon.png',format='binary',loc='path:edit.png')\
+ rhizome.addItemTuple('list',loc='path:list-page.py', format='python', disposition='entry')\
+ rhizome.addItemTuple('showrevisions',loc='path:showrevisions.xsl', format='rxslt', disposition='entry',handlesAction=['showrevisions'])\
+ rhizome.addItemTuple('dump.xml', contents="print __requestor__.server.dump()", format='python')\
+ rhizome.addItemTuple('item-disposition-handler-template',format='python', disposition='entry', handlesDisposition='handler',
          contents="print '''<div class='message'>Completed <b>%(action)s</b> of <a href='%(itemname)s'><b>%(itemname)s<b></a>!</div>'''% _prevkw")\
+ rhizome.addItemTuple('save-metadata',contents="__requestor__.server.rhizome.metadata_save(about, metadata)",
                       format='python', disposition='handler', handlesAction=['save-metadata'])\
+ rhizome.addItemTuple('edit-metadata',loc='path:edit-metadata.xsl', format='rxslt', disposition='entry', handlesAction=['edit-metadata'])\
+ rhizome.addItemTuple('_not_authorized',contents="<div class='message'>Error. You are not authorized to perform this operation on this page.</div>",
                  format='xml', disposition='entry')\
+rhizome.addItemTuple('search', format='rxslt', disposition='complete', loc='path:search.xsl')\
+rhizome.addItemTuple('login', format='rxslt', disposition='complete', loc='path:login.xsl')\
+rhizome.addItemTuple('logout', format='rxslt', disposition='complete', loc='path:logout.xsl')\
+rhizome.addItemTuple('signup', format='rxslt', disposition='entry', loc='path:signup.xsl',
                      handlesAction=['edit', 'new'], actionType='http://rx4rdf.sf.net/ns/wiki#User')\
+rhizome.addItemTuple('save-user', format='rxupdate', disposition='handler', loc='path:signup-handler.xml',
                      handlesAction=['save', 'creation'], actionType='http://rx4rdf.sf.net/ns/wiki#User')\
+ rhizome.addItemTuple('default-resource-viewer',format='python', disposition='entry',
          contents="import rxml; _response.headerMap['content-type']='text/plain'; print rxml.getRXAsRhizmlFromNode(_resource)")
#+ rhizome.addItemTuple('_default-template',loc='path:_default_template.xsl', disposition='template', format='rxslt')\

#forrest templates, essentially recreates forrest/src/resources/conf/sitemap.xmap 
templateList += rhizome.addItemTuple('faq2document.xsl', loc='path:faq2document.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='faq')\
+ rhizome.addItemTuple('document2html.xsl', loc='path:document2html.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='entry', handlesDoctype='document')\
+ rhizome.addItemTuple('site-template',loc='path:site-template.xsl', disposition='template', format='rxslt',handlesDisposition='entry')\
+ rhizome.addItemTuple('spec2html.xsl', loc='path:spec2html.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='complete', handlesDoctype='specification')\
+ rhizome.addItemTuple('docbook2document.xsl', loc='path:docbook2document.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='docbook')
#+ rhizome.addItemTuple('todo2document.xsl', loc='path:todo2document.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='todo')\
  
#help and sample pages
templateList += rhizome.addItemTuple('index',loc='path:index.txt', format='rhizml', disposition='entry', accessTokens=None)\
+rhizome.addItemTuple('sidebar',loc='path:sidebar.txt', format='rhizml', accessTokens=None)\
+rhizome.addItemTuple('TextFormattingRules',loc='path:TextFormattingRules.txt', format='rhizml', disposition='entry')\
+rhizome.addItemTuple('MarkupFormattingRules',loc='path:MarkupFormattingRules.txt', format='rhizml', disposition='entry')\
+rhizome.addItemTuple('RhizML',loc='path:RhizML.rz', format='rhizml', disposition='entry')\
+rhizome.addItemTuple('SandBox', format='rhizml', disposition='entry', accessTokens=None,
	contents="Feel free to [edit|?action=edit] this page to experiment with [RhizML]...")\

#add the authorization and authentification structure
#uses one of two config settings: ADMIN_PASSWORD or ADMIN_PASSWORD_SHA (use the latter if you don't want to store the password in clear text)
#otherwise default password is 'admin'

adminShaPassword = locals().get('ADMIN_PASSWORD_SHA') #hex encoding of the sha1 digest
if not adminShaPassword:
    import sha
    adminShaPassword = sha.sha( locals().get('ADMIN_PASSWORD','admin') ).hexdigest()    
#rxml
authStructure =\
'''
 rx:resource
   rdf:type: auth:Unauthorized
   
 rx:resource id='%(base)susers-guest':
  rdf:type: wiki:User
  wiki:login-name: `guest
  auth:has-role: wiki:role-guest

 rx:resource id='%(base)susers-admin':
  rdf:type: wiki:User
  wiki:login-name: `admin
  wiki:sha1-password: `%(adminShaPassword)s
  auth:has-role: auth:role-superuser

 wiki:role-guest:
  rdf:type: auth:Role
  
 auth:role-superuser:
  rdf:type: auth:Role
  auth:has-token: base:write-structure-token

 ; add access token to protect structural pages from modification
 ; (assign (auth:has-token) to adminstrator users or roles to give access )
 base:write-structure-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Administrator Write/Public Read
  auth:has-permission: wiki:action-delete     
  auth:has-permission: wiki:action-save
  auth:has-permission: wiki:action-save-metadata

''' % {'base' : rhizome.BASE_MODEL_URI, 'adminShaPassword' : adminShaPassword }

#add actions:
for action in ['view', 'edit', 'new', 'creation', 'save', 'delete', 'confirm-delete',
               'showrevisions', 'edit-metadata', 'save-metadata']:
    authStructure += "\n wiki:action-%s: rdf:type: auth:Permission" % action

templateList.append( (None, rxml.rhizml2nt(contents=authStructure, nsMap=nsMap)) )

siteVars =\
'''
 base:site-template:
  wiki:header-image: `underconstruction.gif
  wiki:header-text: `Header, site title goes here: edit the<a href="site-template?action=edit-metadata">site template</a>
''' 
templateList.append( ('@sitevars', rxml.rhizml2nt(contents=siteVars, nsMap=nsMap)) )
   
templateMap = dict(templateList) #create a map so derived sites can replace pages: for example, see site-config.py
STORAGE_TEMPLATE = "".join(templateMap.values()) #create a NTriples string

#define the APPLICATION_MODEL (static, read-only statements in the 'application' scope)
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

