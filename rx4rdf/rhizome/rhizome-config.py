"""
    Config file for Rhizome

    Copyright (c) 2003 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

#see docs/RaccoonConfig for documentation on config file settings

import rx.rhizome
from rx import rxml

if not hasattr(__server__, 'rhizome') or not __server__.rhizome: #make executing this config file idempotent
    rhizome = rx.rhizome.Rhizome(__server__)
    __server__.rhizome = rhizome
else:
    rhizome = __server__.rhizome

RHIZOME_APP_ID = "Rhizome 0.3" #don't change this unless you have a good reason

rhizome.BASE_MODEL_URI = locals().get('BASE_MODEL_URI', __server__.BASE_MODEL_URI)
MAX_MODEL_LITERAL = 0 #will save all content to disk

##############################################################################
## the core of Rhizome: here we define the pipeline for handling requests
##############################################################################

#map the request to a resource in the model, finds 1st match, context is root
resourceQueries=[
'/*[.=$about]',  #view any resource by its RDF URI reference
'/a:NamedContent[wiki:name=$_name]',  #give NamedContent priority 
'/*[wiki:name=$_name]',  #view any other type by its wiki:name
'/*[wiki:alias=$_name]',  #view the resource
#name not found, see if there's an external file on the Raccoon path with this name:
'''wf:if(wf:file-exists($_name), "wf:assign-metadata('externalfile', wf:string-to-nodeset($_name))")''',
"/*[wiki:name='_not_found']", #invoke the not found page 
]

#now see if we're authorized to handle this request
#2 checks:
#1. super-user can always get in
#2. select all the resource's access tokens that apply to the current action 
#   and see if the user or one of its roles has rights to any of them

filterTokens = '''auth:guarded-by/auth:AccessToken[auth:has-permission=$__authAction]
  [not($__authProperty) or not(auth:with-property) or auth:with-property=$__authProperty]
  [not($__authValue) or not(auth:with-value) or auth:with-value=$__authValue]'''

findTokens = '''(./%(filterTokens)s  | ./rdf:type/*/%(filterTokens)s)''' % locals()

#note: save.xml and edit.xsl have expressions that you may need to change if you change this expression
rhizome.authorizationQuery = locals().get('unAuthorizedExpr', '''not($__user/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser') and
  wf:max(%(findTokens)s/auth:priority, 0) > 
  wf:max(%(findTokens)s[.=$__user/auth:has-rights-to/* or .=$__user/auth:has-role/*/auth:has-rights-to/*]/auth:priority,0)''' % locals())
 
#now find a resource that will be used to display the resource
contentHandlerQueries= [
#if the request has an action associated with it
'/*[wiki:handles-action=$__authAction][wiki:action-for-type = $__context | $__context/rdf:type]', #[compatibleTypes(wiki:action-for-type/*,$__context/rdf:type/*)]',
"xf:if(not(self::text()), /*[wiki:handles-action=$__authAction][wiki:action-for-type='http://rx4rdf.sf.net/ns/wiki#Any'])", #get the default handler
#if the resource is content
'self::a:NamedContent',
#if the resource is set to the Unauthorized resource select the unauthorized page
"xf:if(self::auth:Unauthorized, /*[wiki:name='_not_authorized'])",
#default if nothing matches for any real resource (i.e. an resource element)
"xf:if(not(self::text()), /*[wiki:name='default-resource-viewer'])"
]

#context is now a content resource, now set the context to a version of the resource
revisionQueries=[
'(wiki:revisions/*/rdf:first/*)[number($revision)]', #view a particular revision e.g. mypage.html?revision=3
'(wiki:revisions/*/rdf:first/*)[wiki:has-label/*/rdfs:label=$_label][last()]', #view a particular label if specified
'(wiki:revisions/*/rdf:first/*)[wiki:has-label/*/wiki:is-released][last()]', #get the released version
'(wiki:revisions/*/rdf:first/*)[last()]', #get the last revision
]

#finally have a resource, get its content
contentQueries=[
#'''wf:if(a:contents/a:ContentCollection, "wf:assign-metadata('REDIRECT', 'dir.xsl')")''', #todo
'.//a:contents/text()', #content stored in model
'wf:openurl( .//a:contents/a:ContentLocation/wiki:alt-contents)', #contents externally editable (higher priority)
'wf:openurl( .//a:contents/a:ContentLocation)', #contents stored externally
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
#'''/*[wiki:name='_default-template']''',
]

rhizome.findResourceAction = findResourceAction = Action(resourceQueries)
#we want the first Action to set the $__user variable
findResourceAction.assign("__user", '/wiki:User[wiki:login-name=$session:login]',
                         "/wiki:User[wiki:login-name='guest']")
findResourceAction.assign("__resource", '.', post=True)
#if we matched a resource via an alias, reassign the _name to the main name not the alias 
findResourceAction.assign("_name", "string(self::*[wiki:alias=$_name]/wiki:name)", "$_name", post=True)

#if we're not authorized, the resource context will be set to _not_authorized
rhizome.resourceAuthorizationAction = Action( ['''xf:if (%s, /auth:Unauthorized)''' % rhizome.authorizationQuery] )
#default to 'view' if not specified
rhizome.resourceAuthorizationAction.assign("__authAction", 'concat("http://rx4rdf.sf.net/ns/wiki#action-",$action)', "'http://rx4rdf.sf.net/ns/wiki#action-view'") 
rhizome.resourceAuthorizationAction.assign("__authProperty", '0')
rhizome.resourceAuthorizationAction.assign("__authValue", '0')
#revisionAuthorizationAction = Action( [authorizationQuery % "/*[wiki:name='_not_authorized']/wiki:revisions/*[last()]"] )

rhizome.findRevisionAction = Action(revisionQueries)
rhizome.findRevisionAction.assign("_label", '$label', '$session:label', "'Released'")

rhizome.findContentAction = Action(contentQueries, lambda result, kw, contextNode, retVal, self=__server__:\
                                  self.getStringFromXPathResult(result), requiresContext = True) #get its content
rhizome.processContentAction = Action(encodingQueries, __server__.processContents,
                                      matchFirst = False, forEachNode = True) #process the content 

templateAction = Action(templateQueries, rhizome.processTemplateAction)

#setup these variables to give content a chance to dynamically set them
templateAction.assign("_doctype", '$_doctype', "wiki:doctype/*")
#a bit hackish, but we want to preserve the initial _disposition until we encounter 
#the disposition template itself and then use its disposition
#thus we check for the wiki:handles-disposition property
templateAction.assign("_disposition", 'xf:if($previous:_template/wiki:handles-disposition, wiki:item-disposition/*)', 
                    '$_disposition', "wiki:item-disposition/*")
#Raccoon may set response-header:content-type based on the extension, so we check that unless we're the template resource
#(always let the template set the content type)
templateAction.assign('response-header:content-type', '$_contenttype', 
   'string(/*[.=$_doctype]/a:content-type)', 
   "xf:if(not(wf:has-metadata('previous:_template')), $response-header:content-type)", 
   'string(/*[.=$__lastFormat]/a:content-type)')

handleRequestSequence = [ findResourceAction, #first map the request to a resource
      rhizome.resourceAuthorizationAction, #see if the user is authorized to access it                          
      Action(contentHandlerQueries), #find a resource that can display this resource
      rhizome.findRevisionAction, #get the appropriate revision
      #revisionAuthorizationAction, #see if the user is authorized for this revision #todo
      rhizome.findContentAction,#then get its content
      rhizome.processContentAction, #process the content            
      templateAction, #invoke a template
    ]

rhizome.handleRequestSequence = handleRequestSequence

actions = { 'http-request' : handleRequestSequence,
            #rhizome adds two command line options: --import and --export
            'run-cmds' : [ Action(["$import", '$i'], lambda result, kw, contextNode, retVal, rhizome=rhizome: rhizome.doImport(result, **kw)),
                           Action(['$export', '$e'], lambda result, kw, contextNode, retVal, rhizome=rhizome: rhizome.doExport(result, **kw)),
                        ]
          }

#if any of the parameters listed here exist they will preserved during template processing (see rhizome.processTemplateAction)
globalRequestVars = [ '__user', '_static', '_disposition' ]

##############################################################################
## other config settings
##############################################################################
nsMap = {'a' : 'http://rx4rdf.sf.net/ns/archive#',
        'dc' : 'http://purl.org/dc/elements/1.1/#',
         'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
         'rdfs' : 'http://www.w3.org/2000/01/rdf-schema#',
        'wiki' : "http://rx4rdf.sf.net/ns/wiki#",
         'auth' : "http://rx4rdf.sf.net/ns/auth#",
         'base' : rhizome.BASE_MODEL_URI,
         'bnode' : "http://4suite.org/rdf/anonymous/"
         }
rhizome.nsMap = nsMap

import os 
PATH= __server__.PATH + os.pathsep + os.path.split(__configpath__[-1])[0]

cmd_usage = '''\n\nrhizome-config.py specific:
--import [dir or filepath] [--recurse] [--dest path] [--xupdate url] [--format format] [--disposition disposition]
--export dir [--static]'''

# we define a couple of content processors here instead of in Raccoon because
# they make assumptions about the underlying schema 
from rx import zml
contentProcessors = {
    'http://rx4rdf.sf.net/ns/content#pydiff-patch-transform':
        lambda result, kw, contextNode, contents, rhizome=rhizome: rhizome.processPatch(contents, kw, result),
    #this stylesheet transforms kw['_contents'] not the rdf model
    'http://www.w3.org/1999/XSL/Transform' : lambda result, kw, contextNode, contents, self=__server__:\
        self.processXslt(contents, kw['_contents'], kw, uri=self.evalXPath( 
            'concat("site:///", (/a:NamedContent[wiki:revisions/*/*[.=$__context]]/wiki:name)[1])',node=contextNode) ), 
    'http://rx4rdf.sf.net/ns/wiki#item-format-zml' :
        lambda result, kw, contextNode, contents, rhizome=rhizome: rhizome.processZML(contextNode, contents, kw),
    'http://rx4rdf.sf.net/ns/wiki#item-format-custom': 
        lambda result, kw, contextNode, contents, rhizome=rhizome: rhizome.customProcessor(contents, kw),
}

customProcessor = rhizome.customProcessor

contentProcessorCachePredicates = {
    'http://www.w3.org/1999/XSL/Transform' : lambda result, kw, contextNode, contents, self=__server__:\
          self.partialXsltCacheKeyPredicate(contents, kw['_contents'], kw, contextNode, self.evalXPath( 
            'concat("site:///", (/a:NamedContent[wiki:revisions/*/*[.=$__context]]/wiki:name)[1])',
            node=contextNode)) , 
    
    'http://rx4rdf.sf.net/ns/wiki#item-format-zml' :
        lambda result, kw, contextNode, contents: contents #the key is just the contents
}

contentProcessorSideEffectsFuncs = {
    'http://www.w3.org/1999/XSL/Transform' : __server__.xsltSideEffectsFunc,  
    'http://rx4rdf.sf.net/ns/wiki#item-format-zml' :
    lambda cacheValue, sideEffects, resultNodeset, kw, contextNode, contents, \
        rhizome=rhizome: rhizome.processZMLSideEffects(contextNode, kw)
    }
    
contentProcessorSideEffectsPredicates = {
    'http://www.w3.org/1999/XSL/Transform' :  __server__.xsltSideEffectsCalc }

extFunctions = {
(RXWIKI_XPATH_EXT_NS, 'get-rdf-as-rxml'): rhizome.getRxML,
(RXWIKI_XPATH_EXT_NS, 'get-contents'): rhizome.getContents,
(RXWIKI_XPATH_EXT_NS, 'save-metadata'): __server__.saveRxML,
(RXWIKI_XPATH_EXT_NS, 'generate-patch'): rhizome.generatePatch,
(RXWIKI_XPATH_EXT_NS, 'save-contents'): rhizome.saveContents,
(RXWIKI_XPATH_EXT_NS, 'get-nameURI'): rhizome.getNameURI,
(RXWIKI_XPATH_EXT_NS, 'has-page'): rhizome.hasPage,
(RXWIKI_XPATH_EXT_NS, 'secure-hash'): rhizome.getSecureHash,
(RXWIKI_XPATH_EXT_NS, 'get-zml'): rhizome.getZML,
}

NOT_CACHEABLE_FUNCTIONS = {
    (RXWIKI_XPATH_EXT_NS, 'generate-patch'): 0,
    (RXWIKI_XPATH_EXT_NS, 'save-metadata'): 0,
    (RXWIKI_XPATH_EXT_NS, 'save-contents'): 0,
    (RXWIKI_XPATH_EXT_NS, 'has-page'): 0,
}

STORAGE_PATH = "./wikistore.nt"
#STORAGE_PATH = "./wikistore.bdb"
#from rx import RxPath
#initModel = RxPath.initRedlandHashBdbModel

MODEL_RESOURCE_URI = rhizome.BASE_MODEL_URI
MODEL_UPDATE_PREDICATE = 'http://rx4rdf.sf.net/ns/wiki#model-update-id'

configHook = rhizome.configHook
getPrincipleFunc = lambda kw: kw.get('__user', '')
authorizeMetadata=rhizome.authorizeMetadata
authorizeAdditions=rhizome.authorizeAdditions
authorizeRemovals=rhizome.authorizeRemovals
authPredicates=['http://www.w3.org/1999/02/22-rdf-syntax-ns#first', 
 'http://www.w3.org/1999/02/22-rdf-syntax-ns#li', 
 'http://rx4rdf.sf.net/ns/wiki#revisions', 
 'http://rx4rdf.sf.net/ns/archive#contents' ]
##############################################################################
## Define the template for a Rhizome site
##############################################################################

templateList = [rhizome.addItemTuple('_not_found',loc='path:_not_found.xsl', format='rxslt', disposition='entry'),
 rhizome.addItemTuple('edit',loc='path:edit.xsl', format='rxslt', disposition='entry', handlesAction=['edit', 'new']),
 rhizome.addItemTuple('save',loc='path:save.xml', format='rxupdate', disposition='handler', handlesAction=['save', 'creation']),
 rhizome.addItemTuple('confirm-delete',loc='path:confirm-delete.xsl', format='rxslt', disposition='entry', 
                        handlesAction=['confirm-delete'], actionType='http://rx4rdf.sf.net/ns/wiki#Any'),
 rhizome.addItemTuple('delete', loc='path:delete.xml', format='rxupdate', disposition='handler', 
                        handlesAction=['delete'], actionType='http://rx4rdf.sf.net/ns/wiki#Any'),
 rhizome.addItemTuple('basestyles.css',format='text', loc='path:basestyles.css'),
 rhizome.addItemTuple('edit-icon.png',format='binary',loc='path:edit.png'),
 #rhizome.addItemTuple('list',loc='path:list-pages.xsl', format='rxslt', disposition='entry'),
 rhizome.addItemTuple('showrevisions',loc='path:showrevisions.xsl', format='rxslt', disposition='entry',handlesAction=['showrevisions']),
 rhizome.addItemTuple('dump.xml', contents="dump", format='custom'),
 rhizome.addItemTuple('item-disposition-handler-template',loc='path:item-disposition-handler.xsl', format='rxslt', 
                        disposition='entry', handlesDisposition='handler'),
 rhizome.addItemTuple('save-metadata',loc='path:save-metadata.xml', format='rxupdate', 
      disposition='handler', handlesAction=['save-metadata'], actionType='http://rx4rdf.sf.net/ns/wiki#Any'),
 rhizome.addItemTuple('edit-metadata',loc='path:edit-metadata.xsl', format='rxslt', disposition='entry', 
            handlesAction=['edit-metadata', 'edit'], actionType='http://rx4rdf.sf.net/ns/wiki#Any'),
 rhizome.addItemTuple('_not_authorized',contents="<div class='message'>Error. You are not authorized to perform this operation on this page.</div>",
                  format='xml', disposition='entry'),
rhizome.addItemTuple('search', format='rxslt', disposition='complete', loc='path:search.xsl'),
rhizome.addItemTuple('login', format='rxslt', disposition='complete', loc='path:login.xsl'),
rhizome.addItemTuple('logout', format='rxslt', disposition='complete', loc='path:logout.xsl'),
rhizome.addItemTuple('signup', format='rxslt', disposition='entry', loc='path:signup.xsl',
                      handlesAction=['edit', 'new'], actionType='http://rx4rdf.sf.net/ns/wiki#User'),
rhizome.addItemTuple('save-user', format='rxupdate', disposition='handler', loc='path:signup-handler.xml',
                      handlesAction=['save', 'creation'], actionType='http://rx4rdf.sf.net/ns/wiki#User'),
rhizome.addItemTuple('default-resource-viewer',format='rxslt', disposition='entry', loc='path:default-resource-viewer.xsl',
                    handlesAction=['view-metadata'], actionType='http://rx4rdf.sf.net/ns/wiki#Any'),
rhizome.addItemTuple('preview', loc='path:preview.xsl', disposition='complete', format='rxslt'),
rhizome.addItemTuple('wiki2html.xsl', loc='path:wiki2html.xsl', format='http://www.w3.org/1999/XSL/Transform', handlesDoctype='wiki'),
rhizome.addItemTuple('intermap.txt',format='text', loc='path:intermap.txt'),
rhizome.addItemTuple('dir', format='rxslt', disposition='entry', loc='path:dir.xsl',
                      handlesAction=['view'], actionType='http://rx4rdf.sf.net/ns/wiki#Folder'),
rhizome.addItemTuple('rxml-template-handler',loc='path:rxml-template-handler.xsl', format='rxslt', 
                        disposition='entry', handlesDisposition='rxml-template'),               
rhizome.addItemTuple('generic-new-template', loc='path:generic-new-template.txt', handlesAction=['new'], actionType='wiki:Any',
            disposition='rxml-template', format='text', title='Create New Resource'), 
                        
#administration pages
rhizome.addItemTuple('administration', loc='path:administer.xsl', disposition='entry', format='rxslt', title="Administration"), 
rhizome.addItemTuple('new-role-template', loc='path:new-role-template.txt', handlesAction=['new'], actionType='auth:Role',
            disposition='rxml-template', format='text', title='Create New Role'), 
rhizome.addItemTuple('new-accesstoken-template', loc='path:new-accesstoken-template.txt', handlesAction=['new'], actionType='auth:AccessToken',
            disposition='rxml-template', format='text', title='Create New Access Token'), 
rhizome.addItemTuple('new-folder-template', loc='path:new-folder-template.txt', handlesAction=['new'], actionType='wiki:Folder',
            disposition='rxml-template', format='text', title='Create New Folder'), 
rhizome.addItemTuple('new-label-template', loc='path:new-label-template.txt', handlesAction=['new'], actionType='wiki:Label',
            disposition='rxml-template', format='text', title='Create New Label'), 
rhizome.addItemTuple('new-disposition-template', loc='path:new-disposition-template.txt', handlesAction=['new'], actionType='wiki:ItemDisposition',
            disposition='rxml-template', format='text', title='Create New Disposition'), 
rhizome.addItemTuple('new-doctype-template', loc='path:new-doctype-template.txt', handlesAction=['new'], actionType='wiki:DocType',
            disposition='rxml-template', format='text', title='Create New DocType'), 
]

#forrest templates, essentially recreates forrest/src/resources/conf/sitemap.xmap 
templateList += [rhizome.addItemTuple('faq2document.xsl', loc='path:faq2document.xsl', 
    format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='faq'),
rhizome.addItemTuple('document2html.xsl', loc='path:document2html.xsl', 
    format='http://www.w3.org/1999/XSL/Transform', disposition='entry', handlesDoctype='document'),
rhizome.addItemTuple('site-template',loc='path:site-template.xsl', 
    disposition='template', format='rxslt',handlesDisposition='entry'),
rhizome.addItemTuple('print-template',loc='path:print-template.xsl', 
    disposition='template', format='rxslt',handlesDisposition='print'),    
rhizome.addItemTuple('spec2html.xsl', loc='path:spec2html.xsl', format='http://www.w3.org/1999/XSL/Transform', 
    disposition='complete', handlesDoctype='specification'),
rhizome.addItemTuple('docbook2document.xsl', loc='path:docbook2document.xsl', format='http://www.w3.org/1999/XSL/Transform', 
    disposition='template', doctype='document', handlesDoctype='docbook')]
#+ rhizome.addItemTuple('todo2document.xsl', loc='path:todo2document.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='todo'),
  
#sample pages
templateList += [rhizome.addItemTuple('index',loc='path:index.txt', format='zml', disposition='entry', accessTokens=None),
rhizome.addItemTuple('sidebar',loc='path:sidebar.txt', format='zml', accessTokens=None),
rhizome.addItemTuple('SandBox', format='zml', disposition='entry', accessTokens=None,
	contents="Feel free to [edit|?action=edit] this page to experiment with [ZML]..."),
#help pages
rhizome.addItemTuple('help',loc='path:help/help.zml', format='zml', disposition='entry'),
rhizome.addItemTuple('TextFormattingRules',loc='path:help/TextFormattingRules.zml', format='zml', disposition='entry'),
rhizome.addItemTuple('ZML',loc='path:help/ZML.zml', format='zml', disposition='entry'),
rhizome.addItemTuple('RxML',loc='path:help/RxML.zml', format='zml', disposition='entry',doctype='document'),
rhizome.addItemTuple('RhizomeManual',loc='path:help/RhizomeDoc.zml', disposition='entry', format='zml', title="Rhizome Manual", doctype='document'),
rhizome.addItemTuple('RaccoonManual',loc='path:help/RaccoonDoc.zml', disposition='entry', format='zml', title="Raccoon Manual", doctype='document'),
rhizome.addItemTuple('RaccoonConfig',loc='path:help/RaccoonConfig.txt', disposition='entry', format='text', title="Raccoon Config Settings"),
]

#add the authorization and authentification structure

#secureHashSeed is a string that is combined with plaintext when generating a secure hash of passwords
#You really should set your own private value. If it is compromised, it will be much
#easier to mount a dictionary attack on the password hashes.
#If you change this all previously generated password hashes will no longer work.
secureHashSeed = locals().get('secureHashSeed', 'YOU REALLY SHOULD CHANGE THIS!')

passwordHashProperty  = locals().get('passwordHashProperty', rhizome.BASE_MODEL_URI+'password-hash')

#uses one of two config settings: ADMIN_PASSWORD or ADMIN_PASSWORD_HASH
#(use the latter if you don't want to store the password in clear text)
#otherwise default password is 'admin'
adminShaPassword = locals().get('ADMIN_PASSWORD_HASH') #hex encoding of the sha1 digest
if not adminShaPassword:
    import sha
    adminShaPassword = sha.sha( locals().get('ADMIN_PASSWORD','admin')+ secureHashSeed ).hexdigest()    

#rxml
authStructure =\
'''
 auth:Unauthorized:
  rdf:type: auth:Unauthorized

 auth:permission-remove-statement
  rdf:type: auth:Permission
 
 auth:permission-add-statement
  rdf:type: auth:Permission
 
 rx:resource id='%(base)susers/':
  rdf:type: wiki:Folder
  wiki:name: `users
  wiki:has-child: 
    rx:resource id='%(base)susers/admin'
  wiki:has-child: 
    rx:resource id='%(base)susers/guest'
  auth:guarded-by: base:write-structure-token
     
 ;define two built-in users and their corresponding roles
 rx:resource id='%(base)susers/guest':
  rdf:type: wiki:User
  wiki:login-name: `guest
  wiki:name: `users/guest
  auth:has-role: wiki:role-guest
  auth:guarded-by: base:write-structure-token
  
 rx:resource id='%(base)susers/admin':
  rdf:type: wiki:User
  wiki:login-name: `admin
  wiki:name: `users/admin
  auth:has-role: auth:role-superuser
  ;note: we set the password in the application model below so its not hardcoded into the datastore
  ;and can be set in the config file
  auth:guarded-by: base:write-structure-token

 wiki:role-guest:
  rdf:type: auth:Role
  rdfs:label: `Guest
 
 auth:role-superuser:
  rdfs:comment: `the superuser role is a special case that always has permission to do anything
  rdf:type: auth:Role
  rdfs:label: `Super User
  ; even though the super-user role doesn't need this token for authentication 
  ; we add it here so it shows up in the Sharing dropdown on the edit page
  auth:has-rights-to: base:write-structure-token 

 ; add access token to protect structural pages from modification
 ; (assign (auth:has-rights-to) to adminstrator users or roles to give access )
 base:write-structure-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Administrator Write/Public Read
  auth:has-permission: wiki:action-delete     
  auth:has-permission: wiki:action-save
  auth:has-permission: wiki:action-save-metadata
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:priority: 100

 wiki:ItemDisposition:
  auth:guarded-by: base:write-structure-token
  
 wiki:DocType:
  auth:guarded-by: base:write-structure-token

 wiki:Label:
  auth:guarded-by: base:write-structure-token
  
 ; some class level access tokens to globally prevent dangerous actions
 a:ContentTransform:
  auth:guarded-by: base:execute-python-token
  auth:guarded-by: base:execute-rxupdate-token
      
 base:execute-python-token:
  rdf:type: auth:AccessToken  
  auth:has-permission: auth:permission-add-statement
  auth:with-property: a:transformed-by
  auth:with-value: wiki:item-format-python      
  auth:priority: 100
  
 base:execute-rxupdate-token:
  rdfs:comment: `we need this since we don't yet support fine-grained authentication processing RxUpdate 
  rdf:type: auth:AccessToken  
  auth:has-permission: auth:permission-add-statement
  auth:with-property: a:transformed-by 
  auth:with-value: wiki:item-format-rxupdate        
  auth:priority: 100

 auth:Role:
  auth:guarded-by: base:role-guard

 base:role-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all Roles from being being modified
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement  
   auth:priority: 100

 wiki:User:
  auth:guarded-by: base:user-guard

 base:user-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all Users from having their roles and access tokens changed
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement  
   auth:with-property:  auth:has-rights-to
   auth:with-property:  auth:has-role
   auth:priority: 100
      
 auth:AccessToken:
  auth:guarded-by: base:access-token-guard
  
 base:access-token-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all AccessTokens from being being modified
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement
   auth:priority: 100

 ; access tokens guards common to all resources
 ; (currently only fine-grained authentication checks this)
 ; if we supported owl we could have owl:Thing as the subject instead 
 ; and we wouldn't need a seperate check in the authorizationQuery
 base:common-access-checks:
  auth:guarded-by: base:all-resources-guard 
  
 base:all-resources-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all resources from having its access tokens added or removed
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement
   auth:with-property:  auth:guarded-by
   auth:priority: 100
''' % {'base' : rhizome.BASE_MODEL_URI }

#add actions:
for action in ['view', 'edit', 'new', 'creation', 'save', 'delete', 'confirm-delete',
               'showrevisions', 'edit-metadata', 'save-metadata', 'view-metadata', 'view-source']:
    authStructure += "\n wiki:action-%s: rdf:type: auth:Permission" % action

templateList.append( ('@auth', rxml.zml2nt(contents=authStructure, nsMap=nsMap)) )

siteVars =\
'''
 base:site-template:
  wiki:header-image: `underconstruction.gif
  wiki:header-text: `Header, site title goes here: edit the<a href="site-template?action=edit-metadata">site template</a>
'''
templateList.append( ('@sitevars', rxml.zml2nt(contents=siteVars, nsMap=nsMap)) )

import sys, time
currentTime = "%.3f" % time.time() 
platform = 'python ' + sys.version

modelVars =\
'''
 rx:resource id='%(MODEL_RESOURCE_URI)s':
  rdf:type: wiki:Model
  wiki:created-by-app: `%(RHIZOME_APP_ID)s
  wiki:created-on: `%(currentTime)s
  wiki:initial-platform: `%(platform)s
  auth:guarded-by: base:write-structure-token
''' % locals()
#we could include the storage location, e.g.:
#  wiki:initial-location: `%(STORAGE_PATH)s
#but that might be sensitive information -- perhaps storage a hash instead?
  
templateList.append( ('@model', rxml.zml2nt(contents=modelVars, nsMap=nsMap)) )
   
def name2uri(name, nsMap = nsMap):
    i = name.find(':')
    prefix = name[:i]
    if prefix in nsMap:
        return nsMap[prefix]+name[i+1:]
    else:
        return name
    
def addStructure(type, structure, extraProps=[], name2uri=name2uri):
    n3 = ''
    type = name2uri(type)
    for props in structure:
        name, label = name2uri(props[0]), props[1]
        n3 += '''<%s> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <%s> .\n''' % (name, type)
        n3 += '''<%s> <http://www.w3.org/2000/01/rdf-schema#label> "%s" .\n''' % (name, label)
        for i in range(2, len(props)):
            #assume object is a literal
            n3 += '''<%s> <%s> "%s" .\n''' % (name, name2uri(extraProps[i-2]), props[i])        
    return n3

#give readable names and descriptions to user-visible classes
userClasses = [ ('wiki:User', 'User', ''), ('wiki:Folder', 'Folder', ''), 
   ('auth:Role', 'Role', ''), ('auth:AccessToken', 'Access Token', ''),
   ('wiki:Label', 'Label', ''), ('wiki:DocType', 'Doc Type', ''),
   ('wiki:ItemDisposition', 'Disposition', ''), ('a:NamedContent', 'Named Content', '')]

templateList.append( ('@userClasses', addStructure('rdfs:Class', userClasses, ['rdfs:comment'])) )

itemDispositions = [ ('http://rx4rdf.sf.net/ns/wiki#item-disposition-complete', 'Page'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-entry', 'Entry'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-template', 'Template'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-handler', 'Handler'),            
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-rxml-template', 'RxML Template'),            
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-print', 'Printable'),
              ]

docTypes = [ ('http://rx4rdf.sf.net/ns/wiki#doctype-faq', 'FAQ', 'text/xml'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-xhtml', 'XHTML', 'text/html'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-document', 'Document', 'text/xml'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-specification', 'Specification', 'text/xml'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-docbook', 'DocBook', 'text/xml'),                
              ]

labels = [ ('http://rx4rdf.sf.net/ns/wiki#label-draft', 'Draft'),
            ('http://rx4rdf.sf.net/ns/wiki#label-released', 'Released'),
         ]

templateList.append( ('@dispositions', addStructure('http://rx4rdf.sf.net/ns/wiki#ItemDisposition', itemDispositions)) )
templateList.append( ('@doctypes', addStructure('http://rx4rdf.sf.net/ns/wiki#DocType', docTypes, ['http://rx4rdf.sf.net/ns/archive#content-type'])) )
templateList.append( ('@labels', addStructure('http://rx4rdf.sf.net/ns/wiki#Label', labels)+\
    '''<http://rx4rdf.sf.net/ns/wiki#label-released> <http://rx4rdf.sf.net/ns/wiki#is-released> "" .\n''') )

templateMap = dict(templateList) #create a map so derived sites can replace pages: for example, see site-config.py
STORAGE_TEMPLATE = "".join(templateMap.values()) #create a NTriples string

itemFormats = [ ('http://rx4rdf.sf.net/ns/wiki#item-format-binary', 'Binary', 'application/octet-stream'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-text', 'Text', 'text/plain'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-xml', 'XML/XHTML', 'text/html'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-rxslt', 'RxSLT'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate', 'RxUpdate'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-python', 'Python'),
                ('http://www.w3.org/1999/XSL/Transform', 'XSLT'),
                ('http://rx4rdf.sf.net/ns/wiki#item-format-zml', 'ZML'),
              ]
#don't include disabled content processors:
itemFormats = [x for x in itemFormats if x[0] not in locals().get('disabledDefaultContentProcessors', 
                                            rhizome.server.defaultDisabledDefaultContentProcessors)]

#define the APPLICATION_MODEL (static, read-only statements in the 'application' scope)
APPLICATION_MODEL= addStructure('http://rx4rdf.sf.net/ns/wiki#ItemFormat', itemFormats,
    ['http://rx4rdf.sf.net/ns/archive#content-type'])\
   + '''<%susers/admin> <%s> "%s" .\n''' % (rhizome.BASE_MODEL_URI, passwordHashProperty, adminShaPassword)

#we add these functions to the config namespace so that config files that include this can access them
#making it easy to extend or override the rhizome default template
def __addItem__(name, rhizome=rhizome, configlocals=locals(), **kw):
    templateMap=configlocals['templateMap']
    templateMap[name] = rhizome.addItem(name, **kw)
    configlocals['STORAGE_TEMPLATE']= "".join(templateMap.values())

def __addSiteVars__(siteVars, rxml=rxml, configlocals=locals()):
    templateMap=configlocals['templateMap']
    templateMap['@sitevars'] = rxml.zml2nt(contents=siteVars, nsMap=configlocals['nsMap'])
    configlocals['STORAGE_TEMPLATE']= "".join(templateMap.values())

def __addRxML__(contents, rxml=rxml, configlocals=locals()):
    configlocals['STORAGE_TEMPLATE'] += rxml.zml2nt(contents=contents, nsMap=configlocals['nsMap'])

def __addTriples__(triples, configlocals=locals()):
    configlocals['STORAGE_TEMPLATE'] += triples