"""
    Config file for Rhizome

    Copyright (c) 2003-4 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

#see docs/RaccoonConfig for documentation on config file settings

import rx.rhizome
from rx import rxml, __version__

if not hasattr(__server__, 'rhizome') or not __server__.rhizome: #make executing this config file idempotent
    rhizome = rx.rhizome.Rhizome(__server__)
    __server__.rhizome = rhizome
else:
    rhizome = __server__.rhizome

RHIZOME_APP_ID = "Rhizome " + __version__ #don't change this unless you have a good reason

rhizome.BASE_MODEL_URI = locals().get('BASE_MODEL_URI', __server__.BASE_MODEL_URI)
MAX_MODEL_LITERAL = 0 #will save all content to disk

#Raccoon performance settings:
FILE_CACHE_SIZE=1000000
MAX_CACHEABLE_FILE_SIZE=10000
LIVE_ENVIRONMENT=0

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
#if it matches, the context will be a text node
'''f:if(wf:file-exists($_name), /*[.='http://rx4rdf.sf.net/ns/wiki#ExternalResource'])''',
#by treating not found as an error, we prevent an endless loop from happening when the not found page includes a resource that is not found
"wf:error(concat('page not found: ', $_name), 404)", #invoke the not found page 
]

#now see if we're authorized to handle this request
#2 checks:
#1. super-user can always get in
#2. select all the resource's access tokens that apply to the current action 
#   and see if the user or one of its roles has rights to any of them

filterTokens = '''auth:guarded-by/auth:AccessToken[auth:has-permission=$__authAction]
  [not($__authProperty) or not(auth:with-property) or is-subproperty-of($__authProperty,auth:with-property)]
  [not($__authValue) or not(auth:with-value) or auth:with-value=$__authValue]'''

findTokens = '( (.| $__authCommonChecks | ./rdf:type/* | ./rdf:type/*//rdfs:subClassOf/*)/%(filterTokens)s)'% locals()
#findTokens = '''(./%(filterTokens)s  | ./rdf:type/*/%(filterTokens)s | ./rdf:type/*//rdfs:subClassOf/*/%(filterTokens)s)''' % locals()

#note: save.xml and edit.xsl have expressions that you may need to change if you change this expression
rhizome.authorizationQuery = locals().get('unAuthorizedExpr', '''not($__account/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser') and
  wf:max(%(findTokens)s/auth:priority, 0) > 
  wf:max(%(findTokens)s[.=$__account/auth:has-rights-to/* or .=$__account/auth:has-role/*/auth:has-rights-to/*]/auth:priority,0)''' % locals())
 
#now find a resource that will be used to display the resource
contentHandlerQueries= [
#if the resource is set to the Unauthorized resource select the unauthorized page
"f:if(self::*='http://rx4rdf.sf.net/ns/auth#Unauthorized', /a:NamedContent[wiki:name='_not_authorized'])",
#don't do anything with external files:
"f:if(self::*='http://rx4rdf.sf.net/ns/wiki#ExternalResource', $STOP)", 
#if the request has an action associated with it:
#find the action that handles the most derived subtype of the resource
#(or of the resource itself (esp. for the case where the context is a class resource))
#here's simplifed version of the expression: /*[action-for-type = ($__context_subtypes[.= action-for-type])[1] ]
'''/*[wiki:handles-action=$__authAction][wiki:action-for-type = 
   (($__context | $__context/rdf:type/* | ($__context | $__context/rdf:type/*)//rdfs:subClassOf/*)
    [.= /*[wiki:handles-action=$__authAction]/wiki:action-for-type])[1]]''',
#get the action default handler (we don't yet support inferencing of rdfs:Resource as the base subtype, so we need this as a separate rule)
"/*[wiki:handles-action=$__authAction][wiki:action-for-type='http://www.w3.org/2000/01/rdf-schema#Resource']", 
#if the resource is content
'self::a:NamedContent',
#default if nothing matches for any real resource (i.e. an resource element)
"/*[wiki:name='default-resource-viewer']"
]

#context is now a content resource, now set the context to a version of the resource
revisionQueries=[
'(wiki:revisions/*/rdf:first/*)[number($revision)]', #view a particular revision e.g. mypage.html?revision=3
'(wiki:revisions/*/rdf:first/*)[wiki:has-label/*/rdfs:label=$_label][last()]', #view a particular label if specified
'(wiki:revisions/*/rdf:first/*)[wiki:has-label/*/wiki:is-released][last()]', #get the released version
#no released revision yet, get the last version that isn't a draft 
#(we need the next rule because some users might not have the right to set a release label 
# but we want a way for them to avoid "commiting" their edits)
#some applications might just want to raise an error instead of displaying an unreleased revision
'(wiki:revisions/*/rdf:first/*)[not(wiki:has-label/*/wiki:is-draft)][last()]', 
'(wiki:revisions/*/rdf:first/*)[last()]', #looks like they're all drafts, just get the last revision
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
#to get the source, we assume the first tranform is dynamic and all the deeper ones either a patch or a base64 decode
'f:if($action="view-source", (.//a:contents/a:ContentTransform/a:transformed-by/*)[position()!=last()])',
#we need the 'if' check below because the previous query may return an empty nodeset yet still be the result we want
'f:if(not(wf:get-metadata("action")="view-source"), .//a:contents/a:ContentTransform/a:transformed-by/*)',
]

# we're done processing request, see if there are any template resources we want to pass the results onto.
templateQueries=[
#'''$REDIRECT''', #set this to the resource you want to redirect to
'''f:if($externalfile,$STOP)''', #short circuit -- $STOP is a magic variable that stops the evaluation of the queries
'''f:if($action="view-source",$STOP)''', #todo: fix this hack
'f:if($_doctype, /*[wiki:handles-doctype/*=$_doctype])',
'''f:if($_disposition='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete', $STOP)''', #short circuit
'''f:if($_disposition='http://rx4rdf.sf.net/ns/wiki#item-disposition-template', $STOP)''', #short circuit
'f:if($_disposition, /*[wiki:handles-disposition=$_disposition])',
#'''/*[wiki:name='_default-template']''',
]

rhizome.findResourceAction = findResourceAction = Action(resourceQueries)
#we want the first Action to set the $__account variable
findResourceAction.assign("__account", '/*[foaf:accountName=$session:login]',
                         "/*[foaf:accountName='guest']")
findResourceAction.assign("__resource", '.', post=True)
#if we matched a resource via an alias, reassign the _name to the main name not the alias 
findResourceAction.assign("_name", "string(self::*[wiki:alias=$_name]/wiki:name)", "$_name", post=True)
findResourceAction.assign("externalfile", "f:if(self::* = 'http://rx4rdf.sf.net/ns/wiki#ExternalResource', $_name)", post=True, assignEmpty=False)

#if we're not authorized, the resource context will be set to _not_authorized
rhizome.resourceAuthorizationAction = Action( ['''f:if (%s, /*[.='http://rx4rdf.sf.net/ns/auth#Unauthorized'])''' % rhizome.authorizationQuery] )
#default to 'view' if not specified
rhizome.resourceAuthorizationAction.assign("__authAction", 
    'concat("http://rx4rdf.sf.net/ns/wiki#action-",$action)', 
     "'http://rx4rdf.sf.net/ns/wiki#action-view'") 
rhizome.resourceAuthorizationAction.assign("__authProperty", '0')
rhizome.resourceAuthorizationAction.assign("__authValue", '0')
#__authCommonChecks is a minor optimization: by breaking this out of the auth expression it will cached much more often
rhizome.resourceAuthorizationAction.assign("__authCommonChecks", "/*[.='http://www.w3.org/2000/01/rdf-schema#Resource']")
#revisionAuthorizationAction = Action( [authorizationQuery % "/*[wiki:name='_not_authorized']/wiki:revisions/*[last()]"] )

rhizome.findRevisionAction = Action(revisionQueries)
rhizome.findRevisionAction.assign("_label", '$label', '$session:label', "'Released'")

#get the content
rhizome.findContentAction = Action(contentQueries, lambda result, kw, contextNode,
                             retVal, StringValue = rx.rhizome.raccoon.StringValue:
                             isinstance(result, str) and result or StringValue(result), requiresContext = True) 
#process the content                                   
rhizome.processContentAction = Action(encodingQueries, __server__.processContents,
                   canReceiveStreams=True, matchFirst = False, forEachNode = True) 

templateAction = Action(templateQueries, rhizome.processTemplateAction)

#set up these variables to give content a chance to dynamically set them
templateAction.assign("_doctype", '$_doctype', "wiki:doctype/*")

#a bit hackish, but we want to preserve the initial _disposition until we encounter 
#the disposition template itself and then use its disposition
#thus we check for the wiki:handles-disposition property
#even more hackish: added $_dispositionDisposition to allow a disposition template to dynamically set its own disposition
templateAction.assign("_disposition", 'f:if($previous:_template/wiki:handles-disposition, $_dispositionDisposition)',
                    'f:if($previous:_template/wiki:handles-disposition, wiki:item-disposition/*)', 
                    '$_disposition', 
                    "wiki:item-disposition/*")
#Raccoon may set response-header:content-type based on the extension, so we check that unless we're the template resource
#(always let the template set the content type)
templateAction.assign('response-header:content-type', '$_contenttype', 'f:if($action="view-source", "text/plain")', #todo: hack
   'string(/*[.=$_doctype]/a:content-type)', 
   "f:if(not(wf:has-metadata('previous:_template')), $response-header:content-type)", #check if we're a template resource
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

errorAction = Action( [ 
    #by assigning a XPath expression to '_errorhandler' a script can set its own custom error handler:
    #'wf:evaluate($previous:_errorhandler)', #disable for now -- unless we authorize this resource this is a security hole
    "f:if($error:name='XPathUserError' and $error:errorCode=404, /*[wiki:name='_not_found'])", #invoke the not found page     
    '''f:if($error:name='KeyError' and $error:message="'_contents'", /*[wiki:name='xslt-error-handler'])''',
    "/*[wiki:name='default-error-handler']",    
])
errorAction.assign("__resource", '.', post=True)               
#map errors messages that are "expected" and should be shown to the user:
from rx import XUpdate
from Ft.Xml.Xslt import Error
errorAction.assign('error:userMsg', 
    "f:if($error:name='NotAuthorized', $error:message)",
    "f:if($error:name='ZMLParseError' or $error:name='RxMLError', $error:message)",    
    """f:if($error:errorCode = %d, $error:message)""" % XUpdate.XUpdateException.STYLESHEET_REQUESTED_TERMINATION, 
    """f:if($error:errorCode = %d, $error:message)""" % Error.STYLESHEET_REQUESTED_TERMINATION, 
    "''")
               
actions = { 'http-request' : handleRequestSequence,
            #rhizome adds two command line options: --import and --export
            'run-cmds' : [ Action(["$import", '$i'], lambda result, kw, contextNode, retVal, rhizome=rhizome: rhizome.doImport(result, **kw)),
                           Action(['$export', '$e'], lambda result, kw, contextNode, retVal, rhizome=rhizome: rhizome.doExport(result, **kw)),
                        ],
            'load-model' : [ FunctorAction(rhizome.initIndex) ],
            'on-error': [errorAction] + handleRequestSequence[3:]
          }

#if any of the parameters listed here exist they will preserved during template processing (see rhizome.processTemplateAction)
globalRequestVars = [ '__account', '_static', '_disposition']

##############################################################################
## other config settings
##############################################################################
nsMap = {'a' : 'http://rx4rdf.sf.net/ns/archive#',
        'dc' : 'http://purl.org/dc/elements/1.1/',
         'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
         'rdfs' : 'http://www.w3.org/2000/01/rdf-schema#',
        'wiki' : "http://rx4rdf.sf.net/ns/wiki#",
         'auth' : "http://rx4rdf.sf.net/ns/auth#",
         'base' : rhizome.BASE_MODEL_URI,
         'bnode' : "bnode:",
         'kw' : rhizome.BASE_MODEL_URI + 'kw#',
         'foaf' : "http://xmlns.com/foaf/0.1/",
         }
rhizome.nsMap = nsMap

_rhizomeConfigPath = __configpath__[-1]
    
cmd_usage = '''\n\nrhizome-config.py specific:
--import [dir or filepath] [--recurse] [--dest path] [--xupdate url] [--format format] [--disposition disposition]
--export dir [--static]'''

# we define a couple of content processors here instead of in Raccoon because
# they make assumptions about the underlying schema 
contentProcessors = [
    rx.rhizome.RhizomeXMLContentProcessor(sanitizeToken=rhizome.BASE_MODEL_URI+'create-unsanitary-content-token',
              nospamToken=rhizome.BASE_MODEL_URI+'create-nospam-token'),
    rx.rhizome.raccoon.ContentProcessors.XSLTContentProcessor(),
    rhizome.zmlContentProcessor,
    rx.rhizome.PatchContentProcessor(rhizome),   
]

authorizeContentProcessors = {
    #when content is being created dynamically (e.g. via the raccoon-format XML processing instruction)
    #make sure the user has same access tokens that she would need when creating the content (see save.xml)
    'http://rx4rdf.sf.net/ns/wiki#item-format-python': 
        lambda self, contents, formatType, kw, dynamicFormat, rhizome=rx.rhizome, 
                    accessToken=rhizome.BASE_MODEL_URI+'execute-python-token': 
        rhizome.authorizeDynamicContent(self, contents, formatType, kw, 
                                       dynamicFormat, accessToken=accessToken),

    'http://rx4rdf.sf.net/ns/wiki#item-format-rxupdate': 
        lambda self, contents, formatType, kw, dynamicFormat, rhizome=rx.rhizome, 
                accessToken=rhizome.BASE_MODEL_URI+'execute-rxupdate-token': 
        rhizome.authorizeDynamicContent(self, contents, formatType, kw, 
                                      dynamicFormat, accessToken=accessToken)
}
                  
extFunctions = {
(RXWIKI_XPATH_EXT_NS, 'get-rdf-as-rxml'): rhizome.getRxML,
(RXWIKI_XPATH_EXT_NS, 'get-contents'): rhizome.getContents,
(RXWIKI_XPATH_EXT_NS, 'truncate-contents'): rhizome.truncateContents,
(RXWIKI_XPATH_EXT_NS, 'save-metadata'): __server__.saveRxML,
(RXWIKI_XPATH_EXT_NS, 'generate-patch'): rhizome.generatePatch,
(RXWIKI_XPATH_EXT_NS, 'save-contents'): rhizome.saveContents,
(RXWIKI_XPATH_EXT_NS, 'get-nameURI'): rhizome.getNameURI,
(RXWIKI_XPATH_EXT_NS, 'has-page'): rhizome.hasPage,
(RXWIKI_XPATH_EXT_NS, 'secure-hash'): rhizome.getSecureHash,
(RXWIKI_XPATH_EXT_NS, 'get-zml'): rhizome.getZML,
(RXWIKI_XPATH_EXT_NS, 'process-contents'): __server__.processContentsXPath,
(RXWIKI_XPATH_EXT_NS, 'search'): rhizome.searchIndex,
(RXWIKI_XPATH_EXT_NS, 'find-unauthorized'): rhizome.findUnauthorizedActions,
}

NOT_CACHEABLE_FUNCTIONS = {
    (RXWIKI_XPATH_EXT_NS, 'generate-patch'): 0,
    (RXWIKI_XPATH_EXT_NS, 'save-metadata'): 0,
    (RXWIKI_XPATH_EXT_NS, 'save-contents'): 0,
    (RXWIKI_XPATH_EXT_NS, 'process-contents'): 0,
}

STORAGE_PATH = "./wikistore.nt"
#STORAGE_PATH = "./wikistore.bdb"
#from rx import RxPath
#initModel = RxPath.initRedlandHashBdbModel

MODEL_RESOURCE_URI = rhizome.BASE_MODEL_URI
MODEL_UPDATE_PREDICATE = 'http://rx4rdf.sf.net/ns/wiki#model-update-id'

configHook = rhizome.configHook
getPrincipleFunc = lambda kw: kw.get('__account', '')
authorizeMetadata=rhizome.authorizeMetadata
validateExternalRequest=rhizome.validateExternalRequest
authorizeAdditions=rhizome.authorizeAdditions
authorizeRemovals=rhizome.authorizeRemovals
authorizeXPathFuncs=rhizome.authorizeXPathFuncs

##############################################################################
## Define the template for a Rhizome site
##############################################################################

templateList = [rhizome._addItemTuple('_not_found',loc='path:_not_found.xsl', format='rxslt', disposition='entry'),
 rhizome._addItemTuple('edit',loc='path:edit.xsl', format='rxslt', disposition='entry', handlesAction=['edit', 'new']),
 rhizome._addItemTuple('save',loc='path:save.xml', format='rxupdate', disposition='handler', handlesAction=['save', 'creation']),
 rhizome._addItemTuple('confirm-delete',loc='path:confirm-delete.xsl', format='rxslt', disposition='entry', 
                        handlesAction=['confirm-delete'], actionType='rdfs:Resource'),
 rhizome._addItemTuple('delete', loc='path:delete.xml', format='rxupdate', disposition='handler', 
                        handlesAction=['delete'], actionType='rdfs:Resource'),
 rhizome._addItemTuple('basestyles.css',format='text', loc='path:basestyles.css'),
 rhizome._addItemTuple('edit-icon.png',format='binary',loc='path:edit.png'),
 #rhizome._addItemTuple('list',loc='path:list-pages.xsl', format='rxslt', disposition='entry'),
 rhizome._addItemTuple('showrevisions',loc='path:showrevisions.xsl', format='rxslt', disposition='entry',handlesAction=['showrevisions']),
 rhizome._addItemTuple('item-disposition-handler-template',loc='path:item-disposition-handler.xsl', format='rxslt', 
                        disposition='entry', handlesDisposition='handler'),
 rhizome._addItemTuple('save-metadata',loc='path:save-metadata.xml', format='rxupdate', 
      disposition='handler', handlesAction=['save-metadata'], actionType='rdfs:Resource'),
 rhizome._addItemTuple('edit-metadata',loc='path:edit-metadata.xsl', format='rxslt', disposition='entry', 
            handlesAction=['edit-metadata', 'edit'], actionType='rdfs:Resource'),
 rhizome._addItemTuple('_not_authorized',contents="<div class='message'>Error. You are not authorized to perform this operation on this page.</div>",
                  format='xml', disposition='entry'),
rhizome._addItemTuple('search', format='rxslt', disposition='entry', loc='path:search.xsl'),
rhizome._addItemTuple('login', format='zml', disposition='complete', loc='path:login.zml'),
rhizome._addItemTuple('logout', format='rxslt', disposition='complete', loc='path:logout.xsl'),
rhizome._addItemTuple('signup', format='zml', disposition='entry', loc='path:signup.zml',
                      handlesAction=['edit', 'new'], actionType='http://xmlns.com/foaf/0.1/OnlineAccount'),
rhizome._addItemTuple('save-user', format='rxupdate', disposition='handler', loc='path:signup-handler.xml',
                      handlesAction=['save', 'creation'], actionType='http://xmlns.com/foaf/0.1/OnlineAccount'),
rhizome._addItemTuple('default-resource-viewer',format='rxslt', disposition='entry', loc='path:default-resource-viewer.xsl',
                    handlesAction=['view-metadata'], actionType='rdfs:Resource'),
rhizome._addItemTuple('preview', loc='path:preview.xsl', disposition='short-display', format='rxslt'),
rhizome._addItemTuple('wiki2html.xsl', loc='path:wiki2html.xsl', format='http://www.w3.org/1999/XSL/Transform', handlesDoctype='wiki'),
rhizome._addItemTuple('intermap.txt',format='text', loc='path:intermap.txt'),
rhizome._addItemTuple('dir', format='rxslt', disposition='entry', loc='path:dir.xsl',
                      handlesAction=['view'], actionType='http://rx4rdf.sf.net/ns/wiki#Folder'),
rhizome._addItemTuple('rxml-template-handler',loc='path:rxml-template-handler.xsl', format='rxslt', 
                        disposition='entry', handlesDisposition='rxml-template'),               
rhizome._addItemTuple('generic-new-template', loc='path:generic-new-template.txt', handlesAction=['new'], actionType='rdfs:Resource',
            disposition='rxml-template', format='text', title='Create New Resource'), 
rhizome._addItemTuple('rxml2rdf',loc='path:rxml2rdf.py', format='python', disposition='complete'),
rhizome._addItemTuple('default-error-handler', loc='path:default-error-handler.xsl', disposition='entry', doctype='xhtml', format='rxslt'), 
rhizome._addItemTuple('xslt-error-handler', loc='path:xslt-error-handler.xsl', disposition='entry', doctype='xhtml', format='rxslt'), 
rhizome._addItemTuple('short-display-handler',loc='path:short-display-handler.xsl', format='rxslt', 
                        disposition='complete', handlesDisposition='short-display'),               
rhizome._addItemTuple('keyword-browser', loc='path:KeywordBrowser.zml', disposition='entry', format='zml', 
    title="Keyword Browser", handlesAction=['view'], actionType='http://rx4rdf.sf.net/ns/wiki#Keyword'),                         
rhizome._addItemTuple('keywords', loc='path:keywords.zml', disposition='entry', format='zml', 
    title="Show All Keywords"),                         
rhizome._addItemTuple('diff-revisions',loc='path:diff-revisions.py', format='python', disposition='entry'),
rhizome._addItemTuple('comments',loc='path:comments.xsl', format='rxslt', disposition='complete'),

#administration pages
rhizome._addItemTuple('administration', loc='path:administer.xsl', disposition='entry', format='rxslt', title="Administration"), 
rhizome._addItemTuple('new-role-template', loc='path:new-role-template.txt', handlesAction=['new'], actionType='auth:Role',
            disposition='rxml-template', format='text', title='Create New Role'), 
rhizome._addItemTuple('new-accesstoken-template', loc='path:new-accesstoken-template.txt', handlesAction=['new'], actionType='auth:AccessToken',
            disposition='rxml-template', format='text', title='Create New Access Token'), 
rhizome._addItemTuple('new-folder-template', loc='path:new-folder-template.txt', handlesAction=['new'], actionType='wiki:Folder',
            disposition='rxml-template', format='text', title='Create New Folder'), 
rhizome._addItemTuple('new-label-template', loc='path:new-label-template.txt', handlesAction=['new'], actionType='wiki:Label',
            disposition='rxml-template', format='text', title='Create New Label'), 
rhizome._addItemTuple('new-disposition-template', loc='path:new-disposition-template.txt', handlesAction=['new'], actionType='wiki:ItemDisposition',
            disposition='rxml-template', format='text', title='Create New Disposition'), 
rhizome._addItemTuple('new-doctype-template', loc='path:new-doctype-template.txt', handlesAction=['new'], actionType='wiki:DocType',
            disposition='rxml-template', format='text', title='Create New DocType'), 
rhizome._addItemTuple('new-keyword-template', loc='path:new-keyword-template.txt', handlesAction=['new'], actionType='wiki:Keyword',
            disposition='rxml-template', format='text', title='Create New Keyword'), 
rhizome._addItemTuple('new-sitetheme-template', loc='path:new-sitetheme-template.txt', handlesAction=['new'], actionType='wiki:SiteTheme',
            disposition='rxml-template', format='text', title='Create New Site Theme'),             
rhizome._addItemTuple('Sandbox',loc='path:sandbox.xsl', format='rxslt', disposition='entry'),               	
rhizome._addItemTuple('process-contents',loc='path:process-contents.xsl', format='rxslt', 
                        disposition='complete'),               	
]

#forrest templates, essentially recreates forrest/src/resources/conf/sitemap.xmap 
templateList += [rhizome._addItemTuple('faq2document.xsl', loc='path:faq2document.xsl', 
    format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='faq'),
rhizome._addItemTuple('document2html.xsl', loc='path:document2html.xsl', 
    format='http://www.w3.org/1999/XSL/Transform', disposition='entry', handlesDoctype='document'),
rhizome._addItemTuple('site-template',loc='path:site-template.xsl', 
    disposition='template', format='rxslt',handlesDisposition='entry'),
rhizome._addItemTuple('print-template',loc='path:print-template.xsl', 
    disposition='template', format='rxslt',handlesDisposition='print'),    
rhizome._addItemTuple('spec2html.xsl', loc='path:spec2html.xsl', format='http://www.w3.org/1999/XSL/Transform', 
    disposition='complete', handlesDoctype='specification'),
rhizome._addItemTuple('docbook2document.xsl', loc='path:docbook2document.xsl', format='http://www.w3.org/1999/XSL/Transform', 
    disposition='template', doctype='document', handlesDoctype='docbook')]
#+ rhizome._addItemTuple('todo2document.xsl', loc='path:todo2document.xsl', format='http://www.w3.org/1999/XSL/Transform', disposition='template', doctype='document', handlesDoctype='todo'),
  
#sample pages
templateList += [rhizome._addItemTuple('index',loc='path:index.zml', format='zml', label=None, 
                title="Home", disposition='entry', accessTokens=None, keywords=None),
rhizome._addItemTuple('sidebar',loc='path:sidebar.zml', format='zml', label=None, accessTokens=None, keywords=None),
rhizome._addItemTuple('ZMLSandbox', format='zml', label=None, disposition='entry', accessTokens=None, keywords=None,
	contents="Feel free to [edit|?action=edit] this page to experiment with [ZML]..."),
rhizome._addItemTuple('RxMLSandbox',loc='path:RxMLSandbox.xsl', format='rxslt', label=None, keywords=None,
                        disposition='entry', title="RxML Sandbox"),               	

#help pages
rhizome._addItemTuple('help',loc='path:help/help.zml', format='zml', disposition='entry', keywords=['help']),
rhizome._addItemTuple('ZML',loc='path:help/ZML.zml', format='zml', disposition='entry', keywords=['help']),
rhizome._addItemTuple('TextFormattingRules',loc='path:help/TextFormattingRules.zml', format='zml', disposition='entry',keywords=['help']),
rhizome._addItemTuple('ZMLMarkupRules',loc='path:help/ZMLMarkupRules.zml', format='zml', disposition='entry',keywords=['help']),
rhizome._addItemTuple('RxML',loc='path:help/RxML.html', format='xml', disposition='entry',doctype='document',keywords=['help'],
                       title='RxML Quick Reference'),
rhizome._addItemTuple('RxMLSpecification',loc='path:help/RxMLSpecification.zml', format='zml', disposition='entry',
                       title='RxML 1.0 Specification', doctype='document',keywords=['help']),
rhizome._addItemTuple('RhizomeManual',loc='path:help/RhizomeDoc.zml', disposition='entry', format='zml', 
     keywords=['help'], title="Rhizome Manual", doctype='document'),
rhizome._addItemTuple('RaccoonManual',loc='path:help/RaccoonDoc.zml', disposition='entry', 
     format='zml', title="Raccoon Manual", doctype='document',keywords=['help']),
rhizome._addItemTuple('RaccoonConfig',loc='path:help/RaccoonConfig.txt', disposition='entry', 
     format='text', title="Raccoon Config Settings", keywords=['help']),
]

#themes:
templateList += [
    rhizome._addItemTuple('default/theme.xsl', loc='path:themes/default/theme.xsl', 
       format='http://www.w3.org/1999/XSL/Transform', disposition='template'),
    rhizome._addItemTuple('default/theme.css', loc='path:themes/default/theme.css',  
       format='text', disposition='complete'),
    rhizome._addItemTuple('movabletype/theme.xsl', loc='path:themes/movabletype/theme.xsl', 
       format='http://www.w3.org/1999/XSL/Transform', disposition='template'),
    rhizome._addItemTuple('movabletype/theme.css', loc='path:themes/movabletype/theme.css',  
       format='text', disposition='complete'),
    ]

themes =\
'''
 base:default-theme:
  a: wiki:SiteTheme
  wiki:uses-site-template-stylesheet: {%(base)sdefault/theme.xsl}
  wiki:uses-css-stylesheet: {%(base)sdefault/theme.css}
  rdfs:comment: `the default theme

 base:movabletype-theme:
  a: wiki:SiteTheme
  wiki:uses-site-template-stylesheet: {%(base)smovabletype/theme.xsl}
  wiki:uses-css-stylesheet: {%(base)smovabletype/theme.css}
  rdfs:comment: `looks like movabletype
''' % {'base' : rhizome.BASE_MODEL_URI }

templateList.append( ('@themes', rxml.zml2nt(contents=themes, nsMap=nsMap)) )

siteVars =\
'''
 base:site-template:
  wiki:header-image: `underconstruction.gif
  wiki:header-text: `Header, site title goes here: edit the <a href="site:///site-template?action=edit-metadata">site template's metadata</a>
  wiki:uses-theme: base:default-theme
  
 #unfortunately we also have to add this alias in addition to setting wiki:uses-theme
 #because site-template.xsl can only statically import an URL
 {%(base)sdefault/theme.xsl}:
   wiki:alias: `theme.xsl
'''% {'base' : rhizome.BASE_MODEL_URI }
templateList.append( ('@sitevars', rxml.zml2nt(contents=siteVars, nsMap=nsMap)) )

#add the authorization and authentification structure

#secureHashSeed is a string that is combined with plaintext when generating a secure hash of passwords
#You really should set your own private value. If it is compromised, it will be much
#easier to mount a dictionary attack on the password hashes.
#If you change this all previously generated password hashes will no longer work.
secureHashSeed = locals().get('SECURE_HASH_SEED', rhizome.defaultSecureHashSeed)

passwordHashProperty  = locals().get('passwordHashProperty', rhizome.BASE_MODEL_URI+'password-hash')

#uses one of two config settings: ADMIN_PASSWORD or ADMIN_PASSWORD_HASH
#(use the latter if you don't want to store the password in clear text)
#otherwise default password is 'admin'
adminShaPassword = locals().get('ADMIN_PASSWORD_HASH') #hex encoding of the sha1 digest
if not adminShaPassword:
    import sha
    adminShaPassword = sha.sha( locals().get('ADMIN_PASSWORD',rhizome.defaultPassword)+ secureHashSeed ).hexdigest()    

authorizationDigests = { 
    'My4pn2M3AXwU9vro1UIoBnELsS0=' : 1, #for diff-revisions.py
    'pXao2iheSFZspAFb0v/GtDbSGGM=' : 1, #for rxml2rdf.py
}

#rxml
authStructure =\
'''
 auth:Unauthorized:
  rdf:type: rdfs:Resource

 wiki:ExternalResource:
  rdf:type: rdfs:Resource
  
 #we make these properties subproperties of "auth:requires-authorization-for"
 #for Rhizome's fine-grained authentication routine which
 #inverse transitively follows those relations to find authorizing resources 
 #to test whether a statement can be added or removed 
 rdfs:member: rdfs:subPropertyOf: auth:requires-authorization-for
 rdf:first: rdfs:subPropertyOf: auth:requires-authorization-for
 wiki:revisions: rdfs:subPropertyOf: auth:requires-authorization-for
 a:contents: rdfs:subPropertyOf: auth:requires-authorization-for
 
 auth:permission-remove-statement
  rdf:type: auth:Permission
 
 auth:permission-add-statement
  rdf:type: auth:Permission
 
 {%(base)susers/}:
  rdf:type: wiki:Folder
  wiki:name: `users
  auth:guarded-by: base:write-structure-token

 {%(base)saccounts/}:
  rdf:type: wiki:Folder
  wiki:name: `accounts
  wiki:has-child: 
    {%(base)saccounts/admin}
  wiki:has-child: 
    {%(base)saccounts/guest}
  auth:guarded-by: base:write-structure-token
     
 #define two built-in accounts and their corresponding roles
 {%(base)saccounts/guest}:
  rdf:type: foaf:OnlineAccount
  foaf:accountName: `guest
  wiki:name: `accounts/guest
  auth:has-role: auth:role-guest
  auth:guarded-by: base:write-structure-token
  rdfs:comment: `this account is used before the user signs in
  
 {%(base)saccounts/admin}:
  rdf:type: foaf:OnlineAccount
  foaf:accountName: `admin
  wiki:name: `accounts/admin
  auth:has-role: auth:role-superuser
  #note: we set the password in the application model below so its not hardcoded into the datastore
  #and can be set in the config file
  auth:guarded-by: base:write-structure-token
  
 auth:role-guest:
  rdf:type: auth:Role
  rdfs:label: `Guest
 
 auth:role-superuser:
  rdfs:comment: `the superuser role is a special case that always has permission to do anything
  rdf:type: auth:Role
  rdfs:label: `Super User   
  # even though the super-user role doesn't need these tokens for authentication 
  # we add these here so they shows up in the Sharing dropdown on the edit page
  auth:has-rights-to: base:write-structure-token 
  auth:has-rights-to: base:save-only-token
  #if you want to use release labels it is convenient to add this next property
  #which is user by edit.xsl
  #wiki:default-edit-label: wiki:label-released  
    
 auth:role-default:
  rdfs:comment: `this role automatically assigned to new users (see signup-handler.xml)
  rdf:type: auth:Role
  rdfs:label: `Default User
  #remove this property if you don't want this 
  auth:has-rights-to: base:create-nospam-token 
    
 #access token to protect structural resources from modification
 #(assign (auth:has-rights-to) to adminstrator users or roles to give access)
 base:write-structure-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Admin Write/Public Read
  auth:has-permission: wiki:action-delete     
  auth:has-permission: wiki:action-save
  auth:has-permission: wiki:action-save-metadata
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:priority: 100

 base:save-only-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Admin Write/Public Read & Save-Only
  auth:has-permission: wiki:action-delete     
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:priority: 100
  rdfs:comment:  """this token lets resources be modified through the edit/save UI
 but prevents users from modifying the metadata directly or deleting the resource
 (useful for resources you want to let users to edit in a controlled fashion)"""
  
 #users or roles with this access-token can set pages as released 
 #(and delete pages).
 #note that if you create more labels with the wiki:is-released property
 #you'll want to add a <auth:with-value> property to this token
 base:released-label-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Public but Private Release
  auth:has-permission: wiki:action-delete     
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:with-property: wiki:has-label
  auth:with-value:    wiki:label-released
  auth:priority: 10

 #some class level access tokens to globally prevent dangerous actions:
  
 #to make this global for all pages, we attach it (auth:guarded-by) to a:NamedContent  
 #note that if no revision has been labeled released that latest one is displayed, 
 #so users can still create pages that are visible until an editor/administrator marks one released
 a:NamedContent:
  auth:guarded-by: base:released-label-token
    
 wiki:ItemDisposition:
  auth:guarded-by: base:write-structure-token
  
 wiki:DocType:
  auth:guarded-by: base:write-structure-token

 wiki:Label:
  auth:guarded-by: base:write-structure-token
  #if you allow non-administrators to create labels you probably want to add an accesstoken 
  #here to prevent users from adding or removing wiki:is-released properties
  
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

 base:create-unsanitary-content-token:
  rdfs:comment: `If the content creator has this token, rhizome.processMarkup() will not try to sanitize the HTML or XML.
  rdf:type: auth:AccessToken  
  auth:priority: 100

 base:create-nospam-token:
  rdfs:comment: `If the content creator has this token, she is trusted not to be a spammer and rhizome.processMarkup() will not add rel='nofollow' to links.
  rdf:type: auth:AccessToken  
  auth:priority: 100
  
 auth:Role:
  auth:guarded-by: base:role-guard

 base:role-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all Roles from being modified
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement  
   auth:priority: 100

 foaf:Person:
   auth:guarded-by: base:user-guard

 base:user-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all Users from having their association with their account changed
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement  
   auth:with-property:  foaf:holdsAccount
   auth:priority: 100

 foaf:OnlineAccount:
   auth:guarded-by: base:account-guard

 base:account-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all OnlineAccounts from having their roles and access tokens changed
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

 # access tokens guards common to all resources
 # (currently only fine-grained authentication checks this)
 # if we supported owl, the subject could be owl:Thing
 # and we wouldn't need a seperate check in the authorizationQuery
 rdfs:Resource:
   auth:guarded-by: base:all-resources-guard 
   auth:guarded-by: base:change-schema-token   
  
 base:all-resources-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects every resource from having its access tokens added or removed
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement
   auth:with-property:  auth:guarded-by
   auth:priority: 100

 #for now only let the administrator change the schema
 base:change-schema-token:
  rdf:type: auth:AccessToken
  rdfs:label: `guards any statements that changes the schema
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:with-property: rdfs:subClassOf
  auth:with-property: rdfs:subPropertyOf
  auth:with-property: rdfs:domain
  auth:with-property: rdfs:range
  auth:priority: 100
''' % {'base' : rhizome.BASE_MODEL_URI }

#add this if you want to protect all content from modification unless the user has logged-in
#to unprotect particular resources, guard them with the base:override-general-write-token
writeProtectAll =\
''' 
 rdfs:Resource:
   auth:guarded-by: base:general-write-token
   
 base:general-write-token:
    auth:has-permission: 
        wiki:action-confirm-delete
    auth:has-permission: 
        wiki:action-creation
    auth:has-permission: 
        wiki:action-delete
    auth:has-permission: 
        wiki:action-edit
    auth:has-permission: 
        wiki:action-edit-metadata
    auth:has-permission: 
        wiki:action-new
    auth:has-permission: 
        wiki:action-save
    auth:has-permission: 
        wiki:action-save-metadata
    auth:priority: `1
    a: 
        auth:AccessToken

 base:override-general-write-token:
    auth:has-permission: 
        wiki:action-confirm-delete
    auth:has-permission: 
        wiki:action-creation
    auth:has-permission: 
        wiki:action-delete
    auth:has-permission: 
        wiki:action-edit
    auth:has-permission: 
        wiki:action-edit-metadata
    auth:has-permission: 
        wiki:action-new
    auth:has-permission: 
        wiki:action-save
    auth:has-permission: 
        wiki:action-save-metadata
    auth:priority: `10
    a: 
        auth:AccessToken

 #this enables any non-guest user to modify resources (unless otherwise guarded)
 auth:role-default:
    auth:has-rights-to: base:general-write-token
    auth:has-rights-to: base:override-general-write-token 
    
 #everyone, even guests, needs this token
 auth:role-guest:
   auth:has-rights-to: base:override-general-write-token
'''

#to enable guest users to signup for an account even when all resources are write protected
createAccountOverride =\
'''
 #we need to keep foaf:OnlineAccount resources writable
 foaf:OnlineAccount:
   auth:guarded-by: base:override-general-write-token   
'''

#add this if you want to protect all resources (except the home page) from being read unless the user has logged-in
#to unprotect particular resources, guard them with the base:override-general-read-token
#you probably want to combine this with writeProtectAll
readProtectAll =\
''' 
 rdfs:Resource:
   auth:guarded-by: base:general-read-token
   
 base:general-read-token:
    auth:has-permission: 
        wiki:action-showrevisions
    auth:has-permission: 
        wiki:action-view
    auth:has-permission: 
        wiki:action-view-metadata
    auth:has-permission: 
        wiki:action-view-source
    auth:priority: `1
    a: 
        auth:AccessToken

 base:override-general-read-token:
    auth:has-permission: 
        wiki:action-showrevisions
    auth:has-permission: 
        wiki:action-view
    auth:has-permission: 
        wiki:action-view-metadata
    auth:has-permission: 
        wiki:action-view-source
    auth:priority: `10
    a: 
        auth:AccessToken

 #this enables any non-guest user to modify resources (unless otherwise guarded)
 auth:role-default:
    auth:has-rights-to: base:general-read-token    
    auth:has-rights-to: base:override-general-read-token 
    
 #everyone, even guests, needs this token
 auth:role-guest:
   auth:has-rights-to: base:override-general-read-token

 #overrides to enable the display the default index page and related structural pages
 wiki:ExternalResource: auth:guarded-by: base:override-general-read-token 
 base:index: auth:guarded-by: base:override-general-read-token 
 base:login: auth:guarded-by: base:override-general-read-token 
 base:sidebar: auth:guarded-by: base:override-general-read-token 
 base:intermap.txt: auth:guarded-by: base:override-general-read-token  
 base:basestyle.css: auth:guarded-by: base:override-general-read-token 
 {%(base)smovabletype/theme.css}: auth:guarded-by: base:override-general-read-token 
 {%(base)smovabletype/theme.xsl}: auth:guarded-by: base:override-general-read-token 
 {%(base)sdefault/theme.css}: auth:guarded-by: base:override-general-read-token 
 {%(base)sdefault/theme.xsl}: auth:guarded-by: base:override-general-read-token 
''' % {'base' : rhizome.BASE_MODEL_URI }
 
#add actions:
for action in ['view', 'edit', 'new', 'creation', 'save', 'delete', 'confirm-delete',
               'showrevisions', 'edit-metadata', 'save-metadata', 'view-metadata', 'view-source']:
    authStructure += "\n wiki:action-%s: rdf:type: auth:Permission" % action

templateList.append( ('@auth', rxml.zml2nt(contents=authStructure, nsMap=nsMap)) )

import sys, time
currentTime = "%.3f" % time.time() 
platform = 'python ' + sys.version.replace('\n','').replace('\r','')

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
    '''
    if the name's prefix in nsMap it is expanded otherwise we assume its a URI and return it as is.
    '''
    i = name.find(':')
    prefix = name[:i]
    if prefix in nsMap:
        return nsMap[prefix]+name[i+1:]
    else:
        return name
    
def addStructure(type, structure, extraProps=[], name2uri=name2uri):
    '''Structure is a sequence consisting of at least the resource URI and a label, followed by one literal for each extra property.'''
    n3 = ''
    type = name2uri(type)
    for props in structure:
        name, label = name2uri(props[0]), props[1]
        n3 += '''<%s> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <%s> .\n''' % (name, type)
        n3 += '''<%s> <http://www.w3.org/2000/01/rdf-schema#label> "%s" .\n''' % (name, label)
        for i in range(2, len(props)):
            #assume object is a literal
            if props[i]:
                n3 += '''<%s> <%s> "%s" .\n''' % (name, name2uri(extraProps[i-2]), props[i])        
    return n3

#give readable names and descriptions to user-visible classes
userClasses = [ ('foaf:OnlineAccount', 'Account', ''),
   ('foaf:Person', 'User', ''), 
   ('wiki:Folder', 'Folder', ''), 
   ('auth:Role', 'Role', ''), ('auth:AccessToken', 'Access Token', ''),
   ('wiki:Label', 'Label', ''), ('wiki:DocType', 'Doc Type', ''), ('wiki:Keyword', 'Keyword', ''),
   ('wiki:ItemDisposition', 'Disposition', ''), ('a:NamedContent', 'Named Content', ''),
   ('wiki:SiteTheme', 'Site Theme','')]

templateList.append( ('@userClasses', addStructure('rdfs:Class', userClasses, ['rdfs:comment'])) )

itemDispositions = [ ('http://rx4rdf.sf.net/ns/wiki#item-disposition-complete', 'Page'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-entry', 'Entry'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-template', 'Template'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-handler', 'Handler'),            
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-rxml-template', 'RxML Template'),            
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-print', 'Printable'),
                ('http://rx4rdf.sf.net/ns/wiki#item-disposition-short-display', 'Summary'),
              ]

docTypes = [ ('http://rx4rdf.sf.net/ns/wiki#doctype-faq', 'FAQ', 'text/xml'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-xhtml', 'XHTML', 'text/html'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-document', 'Document', 'text/xml'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-specification', 'Specification', 'text/xml'),
                ('http://rx4rdf.sf.net/ns/wiki#doctype-docbook', 'DocBook', 'text/xml'),                
                #('http://rx4rdf.sf.net/ns/wiki#doctype-wiki', 'Wiki', 'text/html'), #todo: uncomment this when we can hide it from users
              ]

labels = [ ('http://rx4rdf.sf.net/ns/wiki#label-draft', 'Draft'),
            ('http://rx4rdf.sf.net/ns/wiki#label-released', 'Released'),
         ]

templateList.append( ('@dispositions', addStructure('http://rx4rdf.sf.net/ns/wiki#ItemDisposition', itemDispositions)) )
templateList.append( ('@doctypes', addStructure('http://rx4rdf.sf.net/ns/wiki#DocType', 
                                       docTypes, ['http://rx4rdf.sf.net/ns/archive#content-type'])) )
templateList.append( ('@labels', addStructure('http://rx4rdf.sf.net/ns/wiki#Label', labels)+
    '''<http://rx4rdf.sf.net/ns/wiki#label-draft> <http://rx4rdf.sf.net/ns/wiki#is-draft> "" .\n'''
'''<http://rx4rdf.sf.net/ns/wiki#label-released> <http://rx4rdf.sf.net/ns/wiki#is-released> "" .\n''') )

templateList.append( ('@keywords', rxml.zml2nt(nsMap=nsMap, contents='''
 wiki:built-in:
  rdf:type: wiki:Keyword  
  rdfs:label: `built-in
  rdfs:comment: `for resources that are part of the Rhizome application
  wiki:name: `keywords/built-in

 wiki:help:
  rdf:type: wiki:Keyword  
  rdfs:label: `help
  rdfs:comment: `Rhizome help resources
  wiki:name: `keywords/help
''')) )


templateMap = dict(templateList) #create a map so derived sites can replace pages: for example, see site-config.py
STORAGE_TEMPLATE = "".join(templateMap.values()) #create a NTriples string

itemFormats = [cp.mimetype and (cp.uri, cp.label, cp.mimetype) or (cp.uri, cp.label) 
     for cp in contentProcessors + rx.rhizome.raccoon.ContentProcessors.DefaultContentProcessors 
                 if cp.label]

#define the APPLICATION_MODEL (static, read-only statements in the 'application' scope)
APPLICATION_MODEL= addStructure('http://rx4rdf.sf.net/ns/wiki#ItemFormat', itemFormats,
    ['http://rx4rdf.sf.net/ns/archive#content-type'])\
   + '''<%saccounts/admin> <%s> "%s" .\n''' % (rhizome.BASE_MODEL_URI, passwordHashProperty, adminShaPassword)

#add the schema to APPLICATION_MODEL
import os.path
from rx import utils
#4Suite's RDF parser can't parse archive-schema.rdf so we have to load a NTriples file instead
schema = utils.convertToNTriples(os.path.split(_rhizomeConfigPath)[0]+'/archive-schema.nt')
#to regenerate: change above to end in .rdf and uncomment this line:
#file(os.path.split(_rhizomeConfigPath)[0]+'/archive-schema.nt', 'w').write(schema)
APPLICATION_MODEL += schema

#add the wiki namespace schema -- not much here right now
wikiSchema ='''
  #wiki:appendage-to is a property that indicates that a resource doesn't stand on its own
  #but rather is subordinate to the object of statement
  #we define the following content relationships as subproperties of this:
  wiki:comments-on:   rdfs:subPropertyOf: wiki:appendage-to
  wiki:attachment-of: rdfs:subPropertyOf: wiki:appendage-to
'''
APPLICATION_MODEL += rxml.zml2nt(contents=wikiSchema, nsMap=nsMap)

#we add these functions to the config namespace so that config files that include this can access them
#making it easy to extend or override the rhizome default template
def __addItem__(name, rhizome=rhizome, configlocals=locals(), **kw):
    templateMap=configlocals['templateMap']
    templateMap[name] = rhizome.addItem(name, **kw)
    configlocals['STORAGE_TEMPLATE']= "".join(templateMap.values())

def __addRxML__(contents='', replace=None, rxml=rxml, configlocals=locals()):
    templateMap=configlocals['templateMap']
    if contents:
        nsMap=configlocals['nsMap']
        contents = rxml.zml2nt(contents=contents, nsMap=configlocals['nsMap'])
    if replace is None:
        replace = str(id(contents))
    templateMap[replace] = contents
    configlocals['STORAGE_TEMPLATE']= "".join(templateMap.values())
    
def __addTriples__(triples='', replace=None, configlocals=locals()):
    templateMap=configlocals['templateMap']
    if replace is None:
        replace = str(id(triples))
    templateMap[replace] = triples
    configlocals['STORAGE_TEMPLATE']= "".join(templateMap.values())

#this is deprecated 
def __addSiteVars__(siteVars, rxml=rxml, configlocals=locals()):
    return configlocals['__addRxML__'](siteVars, replace = '@sitevars')
    