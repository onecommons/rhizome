"""
    Config file for Rhizome

    Copyright (c) 2003-4 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""

#see docs/RaccoonConfig for documentation on config file settings

import rx.rhizome
from rx import rxml, __version__

#create a new Rhizome app object
rhizome = rx.rhizome.Rhizome(__server__)
__server__.rhizome = rhizome

#don't change APP_ID unless you have a good reason:
RHIZOME_APP_ID = "Rhizome " + __version__ 

#check locals() so this can be set before including this config file
rhizome.BASE_MODEL_URI = locals().get('BASE_MODEL_URI', 
                               __server__.BASE_MODEL_URI)
MAX_MODEL_LITERAL = 0 #will save all content to disk

#Raccoon performance settings:
FILE_CACHE_SIZE=1000000
MAX_CACHEABLE_FILE_SIZE=10000
LIVE_ENVIRONMENT=0

##############################################################################
##the core of Rhizome: here we define the pipeline for handling http requests
##############################################################################

#first map the request to a resource in the model (context is root)
resourceQueries=[
'/*[.=$about]',  #view any resource by its RDF URI reference
'/a:NamedContent[wiki:name=$_name]',  #give NamedContent priority 
'/*[wiki:name=$_name]',  #view any other type by its wiki:name
'/*[wiki:alias=$_name]',  #view the resource
#name not found, see if there's an external file on the Raccoon path 
#with this name:
'''f:if(wf:file-exists($_name), 
     /*[.='http://rx4rdf.sf.net/ns/wiki#ExternalResource'])''',
#no match, raise an error that will invoke the not found page
"wf:error(concat('page not found: ', $_name), 404)",  
]
#todo: retry all with concat($_name,'/', $_defaultName)

rhizome.findResourceAction = findResourceAction = Action(resourceQueries)
#we want the first Action to set the $__account variable
findResourceAction.assign("__account", 
                         "$__account", #for nested requests
                         '/*[foaf:accountName=$session:login]',
                         "/*[foaf:accountName='guest']")
findResourceAction.assign("__resource", '.', post=True)
#if we matched a resource via an alias, reassign the _name to the main name not the alias 
findResourceAction.assign("_name", "string(self::*[wiki:alias=$_name]/wiki:name)", 
                                                           "$_name", post=True)
findResourceAction.assign("externalfile", 
  "f:if(self::* = 'http://rx4rdf.sf.net/ns/wiki#ExternalResource', $_name)", 
   post=True, assignEmpty=False)

#now see if we're authorized to handle this request:

#select all the resource's access tokens:
rhizome.findTokens = '''( (.| $__authCommonChecks)/auth:guarded-by/auth:AccessToken)'''
rhizome.findClassTokens = '''((./rdf:type/* | ./rdf:type/*//rdfs:subClassOf/*)
 /auth:type-guarded-by/auth:AccessToken)'''

#select all tokens the user or one of its roles has rights to
rhizome.accountTokens = '''($__account/auth:has-rights-to/* | 
 $__account/auth:has-role/*/auth:has-rights-to/*)'''

#this let's us associate special priviledges with individual resources
rhizome.minPriority = '''wf:max($__extraPrivilegeResources/auth:grants-rights-to
 /*[auth:has-permission=$__authAction]/auth:priority,0)'''

#authorization query: select the highest priority token associated with 
#the resource and applies to the current action
#then filter out those tokens the user is granted rights, 
#and finally compare priorities
rhizome.authorizationQueryTemplate = '''$__authResources[wf:max(%(required)s
 /auth:priority, 0) > wf:max(%(required)s[.=$__accountTokens]/auth:priority, 
 %(minpriority)s)]'''

rhizome.resourceAuthorizationAction = Action([
 #super-user can always get in
 '''f:if($__account/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser', 
    $STOP)''', 
 '''wf:if(%s, "wf:error('Not Authorized', 401)")''' % 
 (rhizome.authorizationQueryTemplate % {'minpriority': '0', 'required' : 
            "("+rhizome.findTokens+"|"+rhizome.findClassTokens+
            ")[auth:has-permission=$__authAction]"}),
 ])
       
#default __authAction to 'view' if not specified
rhizome.resourceAuthorizationAction.assign("__authAction", 
    'concat("http://rx4rdf.sf.net/ns/wiki#action-",$action)', 
     "'http://rx4rdf.sf.net/ns/wiki#action-view'")       
     
#__authCommonChecks is a minor optimization: 
#by breaking this out of the auth expression it will cached much more often
rhizome.resourceAuthorizationAction.assign("__authCommonChecks", 
        "/*[.='%scommon-access-checks']" % rhizome.BASE_MODEL_URI)
rhizome.resourceAuthorizationAction.assign("__authResources", '.')
rhizome.resourceAuthorizationAction.assign("__accountTokens", 
                                            rhizome.accountTokens)

#now find a resource that will be used to display the resource
contentHandlerQueries= [
#don't do anything with external files:
"f:if(self::*='http://rx4rdf.sf.net/ns/wiki#ExternalResource', $STOP)", 
#if the request has an action associated with it:
#find the action that handles the most derived subtype of the resource
#(or of the resource itself (esp. for the case where the context is a class resource))
#here's simplifed version of the expression: 
#/*[action-for-type = ($__context_subtypes[.= action-for-type])[1] ]
'''/*[wiki:handles-action=$__authAction][wiki:action-for-type = 
   (($__context | $__context/rdf:type/* | ($__context | $__context/rdf:type/*)
     //rdfs:subClassOf/*)
   [.= /*[wiki:handles-action=$__authAction]/wiki:action-for-type])[1]]''',
#get the action default handler (this is a separate rule because 
#we don't yet support inferencing of rdfs:Resource as the base subtype)
'''/*[wiki:handles-action=$__authAction]
  [wiki:action-for-type='http://www.w3.org/2000/01/rdf-schema#Resource']''', 
#select self if the resource type is content
'self::a:NamedContent',
#default if nothing else matches
"/*[wiki:name='default-resource-viewer']"
]

contentHandlerAction = Action(contentHandlerQueries)
contentHandlerAction.assign("__handlerResource", '.', post=True)

#context will now be a content resource
#now set the context to a version of the resource
revisionQueries=[
#highest priority to explicitly requested revision e.g. mypage.html?revision=3
'(wiki:revisions/*/rdf:first/*)[number($revision)]', 
#next, view a particular label if specified
'(wiki:revisions/*/rdf:first/*)[wiki:has-label/*/rdfs:label=$_label][last()]', 
#otherwise, get the released version
'(wiki:revisions/*/rdf:first/*)[wiki:has-label/*/wiki:is-released][last()]', 
#no released revision yet, get the last version that isn't a draft 
#(we need the next rule because some users might not have 
# the right to set a release label 
# but some applications might want to raise an error 
# instead of displaying an unreleased revision
'(wiki:revisions/*/rdf:first/*)[not(wiki:has-label/*/wiki:is-draft)][last()]', 
#looks like they're all drafts, just get the last revision
#(again, some application might want to raise an error instead)
'(wiki:revisions/*/rdf:first/*)[last()]', 
]

rhizome.findRevisionAction = Action(revisionQueries)
rhizome.findRevisionAction.assign("_label", '$label', 
                        '$session:label', "'Released'")

#finally have a resource, get its content
contentQueries=[
#external file
'wf:openurl(wf:ospath2pathuri($externalfile))', 
#content stored in model
'.//a:contents/text()', 
#contents externally editable 
'wf:openurl( .//a:contents/a:ContentLocation/wiki:alt-contents)', 
#contents stored externally
'wf:openurl( .//a:contents/a:ContentLocation)', 
]

rhizome.findContentAction = Action(contentQueries, 
  lambda result, kw, contextNode, retVal, 
    StringValue = rx.rhizome.raccoon.StringValue:
     isinstance(result, str) and result or StringValue(result), 
  requiresContext = True) 

#looks for content encodings, finds ALL matches in order, context is resource
encodingQueries=[
#to get the source, we assume the first tranform is dynamic 
#and all the deeper ones either a patch or a base64 decode
'f:if($action="view-source", (.//a:contents/a:ContentTransform/a:transformed-by/*)[position()!=last()])',
#we need the 'if' check below because the previous query 
#may return an empty nodeset yet still be the result we want
'''f:if(not(wf:get-metadata("action")="view-source"),
 .//a:contents/a:ContentTransform/a:transformed-by/*)''',
]
#process the content                                   
rhizome.processContentAction = Action(encodingQueries, __server__.processContents,
             canReceiveStreams=True, matchFirst = False, forEachNode = True) 

# we're done processing request, see if there are any template resources 
#we want to pass the results onto.
templateQueries=[
#'''$REDIRECT''', #todo: set this to the resource you want to redirect to
#short circuit -- $STOP is a magic variable that stops the evaluation of the queries
'''f:if($externalfile,$STOP)''', 
'''f:if($action="view-source",$STOP)''', #todo: fix this hack
'f:if($_doctype, /*[wiki:handles-doctype/*=$_doctype])',
'''f:if($_disposition='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete', $STOP)''', #short circuit
'''f:if($_disposition='http://rx4rdf.sf.net/ns/wiki#item-disposition-template', $STOP)''', #short circuit
'f:if($_disposition, /*[wiki:handles-disposition=$_disposition])',
#if your application needs a default template:
#'''/*[wiki:name='_default-template']''', 
]

templateAction = Action(templateQueries, rhizome.processTemplateAction)

#set up these variables to give content a chance to dynamically set them
templateAction.assign("_doctype", '$_doctype', "wiki:doctype/*")

#a bit hackish, but we want to preserve the initial _disposition until 
#we encounter the disposition template itself and then use its disposition
#thus we check for the wiki:handles-disposition property
#even more hackish: added $_dispositionDisposition to allow a disposition
#template to dynamically set its own disposition
templateAction.assign("_disposition", 'f:if($previous:_template/'
                        'wiki:handles-disposition,$_dispositionDisposition)',
                    'f:if($previous:_template/wiki:handles-disposition,' 
                    'wiki:item-disposition/*)', 
                    '$_disposition', 
                    "wiki:item-disposition/*")
#Raccoon may set response-header:content-type based on the extension, 
#so we check for that, unless we're the template resource
#(always let the template set the content type)
templateAction.assign('response-header:content-type', '$_contenttype', 
   'f:if($action="view-source", "text/plain")', #todo: hack
   'string(/*[.=$_doctype]/a:content-type)', 
   #only set if we're not a template resource:
   '''f:if(not(wf:has-metadata('previous:_template')), 
        $response-header:content-type)''', 
   'string(/*[.=$__lastFormat]/a:content-type)')

handleRequestSequence = [ findResourceAction, #first map the request to a resource
      rhizome.resourceAuthorizationAction, #see if the user is authorized to access it                          
      contentHandlerAction, #find a resource that can display this resource
      rhizome.findRevisionAction, #get the appropriate revision
      rhizome.findContentAction,#then get its content
      rhizome.processContentAction, #process the content            
      templateAction, #invoke a template
    ]

rhizome.handleRequestSequence = handleRequestSequence

###############################################################################
##define the error handler for http requests
###############################################################################
errorAction = Action( [ 
    #by assigning a XPath expression to '_errorhandler' a script can set its 
    #own custom error handler
    #(disable for now -- until we authorize this resource, this is a security hole)
    #'wf:evaluate($previous:_errorhandler)', 
    #invoke the not found page:     
    '''f:if($error:name='XPathUserError' and $error:errorCode=404, 
                                        /*[wiki:name='_not_found'])''', 
    #invoke the not authorized page     
    '''f:if($error:name='XPathUserError' and $error:errorCode=401, 
                                /*[wiki:name='_not_authorized'])''',
    #this is a bit of hack: this is raised when trying to 
    #directly view an XSLT page
    '''f:if($error:name='KeyError' and $error:message="'_contents'", 
                                /*[wiki:name='xslt-error-handler'])''',
    "/*[wiki:name='default-error-handler']",    
])
errorAction.assign("__resource", '.', post=True)               

#we assign the $error:userMsg variable to errors messages that are "expected" 
#and should be shown to the user:
from rx import XUpdate
from Ft.Xml.Xslt import Error
errorAction.assign('error:userMsg', 
  "f:if($error:name='NotAuthorized', $error:message)",
  "f:if($error:name='ZMLParseError' or $error:name='RxMLError', $error:message)",
  """f:if($error:errorCode = %d, $error:message)""" % 
        XUpdate.XUpdateException.STYLESHEET_REQUESTED_TERMINATION, 
  """f:if($error:errorCode = %d, $error:message)""" % 
        Error.STYLESHEET_REQUESTED_TERMINATION, 
  "''")

###############################################################################
##define the various authorization actions invoked when committing changes
###############################################################################

classAuthenticateNewResourceAction = Action( [ 
'''f:if($__account/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser', $STOP)''',
rhizome.authorizationQueryTemplate % {'minpriority': rhizome.minPriority, 
 'required': "("+rhizome.findClassTokens+")[auth:has-permission=$__authAction]"},
], rhizome.raiseClassUnAuthorized)
classAuthenticateNewResourceAction.assign("__authAction", 
  "'http://rx4rdf.sf.net/ns/auth#permission-new-resource-statement'") 
classAuthenticateNewResourceAction.assign("__authResources", '$_newResources')
classAuthenticateNewResourceAction.assign("__extraPrivilegeResources", 
   '$previous:__handlerResource','/..') #/.. selects an empty nodeset

import copy
classAuthenticateAddsAction = copy.deepcopy(classAuthenticateNewResourceAction)
classAuthenticateAddsAction.assign("__authAction", 
  "'http://rx4rdf.sf.net/ns/auth#permission-add-statement'") 
classAuthenticateAddsAction.assign("__authResources", 
  '($_added/..)[not(.=$_newResources)]')

classAuthenticateRemovesAction = copy.deepcopy(classAuthenticateNewResourceAction)
classAuthenticateRemovesAction.assign("__authAction", 
 "'http://rx4rdf.sf.net/ns/auth#permission-remove-statement'") 
classAuthenticateRemovesAction.assign("__authResources", 
 '($_removed/..)[not(.=$_newResources)]')

##when an auth:requires-authorization-for property is added,
##we reauthorize all the statements down the whole transitive
##authorization tree for the object of the property, even statements
##that have been added in a previous transaction by a user with greater
##rights. We want to do this because by adding or removing these
##relationships we are essentially creating new objects and these
##statements may have different meaning in the system so we need to
##check if the user has the right to (re)assert them.
recheckAuthorizations = Action([ 
 '''f:if($__account/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser', $STOP)''',
 '$_added/self::auth:requires-authorization-for', 
  ], lambda result, kw, contextNode, retVal, rhizome=rhizome: 
       rhizome.recheckAuthorizations(result, kw))
recheckAuthorizations.assign("__extraPrivilegeResources", 
  '$previous:__handlerResource','/..')

shredders = [
    rx.rhizome.raccoon.ContentProcessors.XSLTContentProcessor(),
    rx.rhizome.raccoon.ContentProcessors.RxUpdateContentProcessor(),
    rhizome.zmlContentProcessor,
    rx.rhizome.XMLShredder(rhizome,'xml-shred.xsl'), 
    #this should work for all XML-based RDF formats:
    rx.rhizome.raccoon.ContentProcessors.RDFShredder(), 
    rx.rhizome.raccoon.ContentProcessors.RDFShredder(
        'http://rx4rdf.sf.net/ns/wiki#item-format-ntriples',
              mimetype='text/plain', label='NTriples', rdfFormat='ntriples'),
    #PythonSourceCodeShredder(), #todo
]
        
shredderRequestSequence = [ 
  Action(['$_format'],
         lambda result, kw, contextNode, contents, rhizome=rhizome:
            rhizome.server.processContents(result, kw, 
     rhizome.server.domStore.dom, contents, contentProcessors=rhizome.shredders))
]

###############################################################################
##associate all these Action sequences with the appropriate request triggers
###############################################################################                                    
actions = { 
    'http-request' : handleRequestSequence,
    'http-request-error': [errorAction] + handleRequestSequence[3:],

    'shred' : shredderRequestSequence, #rhizome-specific trigger
    
    #rhizome adds two command line options: --import and --export
    'run-cmds' : [ Action(["$import", '$i'], 
                    lambda result, kw, contextNode, retVal, rhizome=rhizome: 
                      rhizome.doImport(result, **kw)),
                   Action(['$export', '$e'], 
                    lambda result, kw, contextNode, retVal, rhizome=rhizome: 
                      rhizome.doExport(result, kw)),
                ],
    'load-model' : [ FunctorAction(rhizome.initIndex) ],
    
    'before-add': [ Action(['''wf:authorize-statements($_added,
      "http://rx4rdf.sf.net/ns/auth#permission-add-statement", 
      $_newResources, wf:get-metadata('previous:__handlerResource',/..))''',
      #authorize-statements should either return true or raise an exception
      "wf:error('Authorization check unexpectedly failed.')"]), 
                  ],
                     
    'before-remove': [ Action(['''wf:authorize-statements($_removed,
      "http://rx4rdf.sf.net/ns/auth#permission-remove-statement", 
      $_newResources, wf:get-metadata('previous:__handlerResource',/..))''',
      #authorize-statements should either return true or raise an exception                         
      "wf:error('Authorization check unexpectedly failed.')"]),
                     ],

     #'before-new'     
     #new resource was created (available through $_newResources). 
     #This trigger is called before its statements are added. You could use it, 
     #for example, to prevent reserved identifiers from being used.
        
    'before-prepare': [ 
        Action(['''wf:request('update-triggers', '_noErrorHandling', 1,
                '_added', $_added, '_removed', $_removed)''']),
        recheckAuthorizations,
        classAuthenticateNewResourceAction,
#        classAuthenticateAddsAction,
#        classAuthenticateRemovesAction,                            
        #invoke the validatation schematron document on the changes
        Action(['''wf:request('validate-schema', '_noErrorHandling', 1,
         'phase', 'incremental', '_added', $_added, '_removed', $_removed)''']),
        ],

    #'before-commit' 
    #'after-commit'  #todo: notifications, e.g. emails 
}

#if any of the parameters listed here exist they will preserved 
#during template processing (see rhizome.processTemplateAction)
globalRequestVars = ['__account', '__accountTokens', '_static', '_disposition']

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
          'dataview': 'http://www.w3.org/2003/g/data-view'
         }
rhizome.nsMap = nsMap

_rhizomeConfigPath = __configpath__[-1]
    
cmd_usage = '''\n\nrhizome-config.py specific:
--import [dir or filepath] [--recurse] [--dest path] [--xupdate url] 
         [--format format] [--disposition disposition]
--export dir [--static]'''

# we define a couple of content processors here instead of in Raccoon because
# they make assumptions about the underlying schema 
contentProcessors = [
    rx.rhizome.RhizomeXMLContentProcessor(sanitizeToken=
               rhizome.BASE_MODEL_URI+'create-unsanitary-content-token',
               nospamToken=rhizome.BASE_MODEL_URI+'create-nospam-token'),
    rx.rhizome.raccoon.ContentProcessors.XSLTContentProcessor(),
    rhizome.zmlContentProcessor,
    rx.rhizome.PatchContentProcessor(rhizome),   
    rx.rhizome.raccoon.ContentProcessors.StreamingNoOpContentProcessor(
        'http://rx4rdf.sf.net/ns/wiki#item-format-ntriples',
                     mimetype='text/plain', label='NTriples'),        
]

try:
   import RDF
   contentProcessors.append(
    rx.rhizome.raccoon.ContentProcessors.StreamingNoOpContentProcessor(
        'http://rx4rdf.sf.net/ns/wiki#item-format-turtle',
                     mimetype='text/plain', label='Turtle'))   
   shredders.append(
      rx.rhizome.raccoon.ContentProcessors.RDFShredder(
        'http://rx4rdf.sf.net/ns/wiki#item-format-turtle',
        mimetype='text/plain', label='Turtle', rdfFormat='turtle')) 
except ImportError: pass

authorizeContentProcessors = {
    #when content is being created dynamically 
    #(e.g. via the raccoon-format XML processing instruction)
    #make sure the user has same access tokens that she would need 
    #when creating the content
    'http://rx4rdf.sf.net/ns/wiki#item-format-python': 
     lambda self, contents, formatType, kw, dynamicFormat, rhizome=rx.rhizome, 
                    accessToken=rhizome.BASE_MODEL_URI+'execute-python-token': 
        rhizome.authorizeDynamicContent(self, contents, formatType, kw, 
                                    dynamicFormat, accessToken=accessToken),
}
                  
extFunctions = {
(RXWIKI_XPATH_EXT_NS, 'get-contents'): rhizome.getContents,
(RXWIKI_XPATH_EXT_NS, 'truncate-contents'): rhizome.truncateContents,
(RXWIKI_XPATH_EXT_NS, 'save-rdf'): __server__.saveRDF,
(RXWIKI_XPATH_EXT_NS, 'generate-patch'): rhizome.generatePatch,
(RXWIKI_XPATH_EXT_NS, 'save-contents'): rhizome.saveContents,
(RXWIKI_XPATH_EXT_NS, 'get-nameURI'): rhizome.getNameURI,
(RXWIKI_XPATH_EXT_NS, 'has-page'): rhizome.hasPage,
(RXWIKI_XPATH_EXT_NS, 'secure-hash'): rhizome.getSecureHash,
(RXWIKI_XPATH_EXT_NS, 'get-zml'): rhizome.getZML,
(RXWIKI_XPATH_EXT_NS, 'process-contents'): __server__.processContentsXPath,
(RXWIKI_XPATH_EXT_NS, 'search'): rhizome.searchIndex,
(RXWIKI_XPATH_EXT_NS, 'authorize-statements'): rhizome.authorizeOperation,
(RXWIKI_XPATH_EXT_NS, 'auth-value-matches'): rx.rhizome.authorizationValueMatch,
(RXWIKI_XPATH_EXT_NS, 'request') :  rhizome.makeRequest,
(RXWIKI_XPATH_EXT_NS, 'fixup-urls'): __server__.site2http,

(RXWIKI_XPATH_EXT_NS, 'shred') :  rhizome.startShredding,
(RXWIKI_XPATH_EXT_NS, 'shred-with-xslt') :  rhizome.shredWithStylesheet,
(RXWIKI_XPATH_EXT_NS, 'is-spam') :  rhizome.isSpam,
(RXWIKI_XPATH_EXT_NS, 'name-from-url'): rhizome.nameFromURL,
}

NOT_CACHEABLE_FUNCTIONS = {
    (RXWIKI_XPATH_EXT_NS, 'generate-patch'): 0,
    (RXWIKI_XPATH_EXT_NS, 'save-rdf'): 0,
    (RXWIKI_XPATH_EXT_NS, 'save-contents'): 0,
    (RXWIKI_XPATH_EXT_NS, 'process-contents'): 0,
    (RXWIKI_XPATH_EXT_NS, 'request') : 0,
    (RXWIKI_XPATH_EXT_NS, 'auth-value-matches'): 
        rx.rhizome.authorizationValueMatchCacheKey,
    (RXWIKI_XPATH_EXT_NS, 'shred') : 0,
    (RXWIKI_XPATH_EXT_NS, 'shred-with-xslt') : 0,
}

#this function is called by rhizome.authorizeXPathFunc to dynamically 
#authorize XPath function calls based on the context and arguments
#It should return a list of access token resource URIs to authorize 
#or raise NotAuthorized
authFunctionFunc = lambda name, context, args, rhizome=rhizome: (
        ['%sexecute-function-token'% rhizome.BASE_MODEL_URI], args)

authorizedExtFunctions = {
    #require authorization for these functions because they modify 
    #the local file system
    (RXWIKI_XPATH_EXT_NS, 'generate-patch') : (authFunctionFunc, 0),
    (RXWIKI_XPATH_EXT_NS, 'save-contents')  : (authFunctionFunc, 0),
    #these don't require authorization but need to make sure the user 
    #isn't trying to change $__account, etc.
    (RXWIKI_XPATH_EXT_NS, 'process-contents'): 
     (rhizome.validateXPathFuncArgs, rhizome.getValidateXPathFuncArgsCacheKey),
    (RXWIKI_XPATH_EXT_NS, 'request'): 
     (rhizome.validateXPathFuncArgs, rhizome.getValidateXPathFuncArgsCacheKey),
}

STORAGE_PATH = "./wikistore.nt"
#STORAGE_PATH = "./wikistore.bdb"
#from rx import RxPath
#initModel = RxPath.initRedlandHashBdbModel

MODEL_RESOURCE_URI = rhizome.BASE_MODEL_URI

configHook = rhizome.configHook
getPrincipleFunc = lambda kw: kw.get('__account', '')
authorizeMetadata=rhizome.authorizeMetadata
validateExternalRequest=rhizome.validateExternalRequest
authorizeXPathFuncs=rhizome.authorizeXPathFuncs

##############################################################################
## Define the template for a Rhizome site
##############################################################################

templateList = [rhizome._addItemTuple('_not_found',loc='path:_not_found.xsl', format='rxslt', disposition='entry',
                    handlesAction=['view'], actionType='wiki:MissingPage'),
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
rhizome._addItemTuple('process-rdfsandbox',loc='path:process-rdfsandbox.xsl', format='rxslt', disposition='complete'),
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
#added in 0.5.0:
rhizome._addItemTuple('schematron-skeleton', loc='path:skeleton1-5.xsl', format='http://www.w3.org/1999/XSL/Transform'),
rhizome._addItemTuple('schematron-rxpath', loc='path:schematron-rxpath.xsl', format='http://www.w3.org/1999/XSL/Transform', handlesDoctype='schematron'),
rhizome._addItemTuple('validate-schema', loc='path:validate-schema.xml', disposition='complete', doctype='schematron', format='xml'), 
rhizome._addItemTuple('site-theme', loc='path:site-theme.xsl', disposition='complete', format='rxslt'), 
#added in 0.6.0:
rhizome._addItemTuple('xml-shred.xsl', loc='path:xml-shred.xsl', format='http://www.w3.org/1999/XSL/Transform'),
rhizome._addItemTuple('faq-shredder.xsl', loc='path:faq-shredder.xsl', format='http://www.w3.org/1999/XSL/Transform',
        extraProps=[('dataview:doctypeTransformation','wiki:doctype-faq')] ),
rhizome._addItemTuple('faqviewer', loc='path:faqviewer.xsl', disposition='entry', format='rxslt',
            handlesAction=['view'], actionType='wiki:faq'), 
rhizome._addItemTuple('edit-bookmark', loc='path:edit-bookmark.zml', disposition='complete', format='zml',
                        handlesAction=['edit','new'], actionType='wiki:Bookmark'),
rhizome._addItemTuple('view-bookmark', loc='path:view-bookmark.xsl', disposition='complete', format='rxslt',
            handlesAction=['view'], actionType='wiki:Bookmark'), 
rhizome._addItemTuple('save-bookmark', format='rxupdate', disposition='handler', loc='path:save-bookmark.xml',
                      handlesAction=['save', 'creation'], actionType='wiki:Bookmark'),
rhizome._addItemTuple('replacetags.xml', loc='path:replacetags.xml', disposition='complete', format='xml'),
rhizome._addItemTuple('edit-tags.xsl', loc='path:edit-tags.xsl', disposition='complete', format='xml'),
rhizome._addItemTuple('update-triggers',loc='path:update-triggers.xml', format='rxupdate', disposition='complete'),
#rhizome._addItemTuple('todo2document.xsl', loc='path:changes2document.xsl', format='http://www.w3.org/1999/XSL/Transform', 
#                disposition='template', doctype='document', handlesDoctype='todo'),
#rhizome._addItemTuple('s5-template',loc='path:s5-template.xsl', format='rxslt', 
#                        disposition='complete', handlesDisposition='s5-template'), 
    
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
    disposition='template', doctype='document', handlesDoctype='docbook'),
]
  
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

#css skins
templateList += [
 rhizome._addItemTuple('skin-lightblue.css',format='text', 
        loc='path:skin-lightblue.css', keywords=['skin']),
 rhizome._addItemTuple('skin-nocolor.css',format='text', 
        loc='path:skin-allwhite.css', keywords=['skin']),
 rhizome._addItemTuple('skin-olive.css',format='text', 
        loc='path:skin-olive.css',keywords=['skin']),
 rhizome._addItemTuple('skin-lava.css',format='text', 
        loc='path:skin-lava.css',keywords=['skin']),
 rhizome._addItemTuple('skin-brownbasic.css',format='text', 
        loc='path:skin-brownbasic.css', keywords=['skin']),
]

#themes:
templateList += [
    rhizome._addItemTuple('default/theme.xsl', loc='path:themes/default/theme.xsl', 
       format='http://www.w3.org/1999/XSL/Transform', disposition='template'),
    rhizome._addItemTuple('default/theme.css', loc='path:themes/default/theme.css',  
       format='text', disposition='complete'),
    rhizome._addItemTuple('classic/theme.xsl', loc='path:themes/classic/theme.xsl', 
       format='http://www.w3.org/1999/XSL/Transform', disposition='template'),
    rhizome._addItemTuple('classic/theme.css', loc='path:themes/classic/theme.css',  
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

 base:classic-theme:
  a: wiki:SiteTheme
  wiki:uses-site-template-stylesheet: {%(base)sclassic/theme.xsl}
  wiki:uses-css-stylesheet: {%(base)sclassic/theme.css}
  rdfs:comment: `the original theme

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
  wiki:header-text: `Header, site title goes here:<br />edit the <a href="site:///site-template?action=edit-metadata">site template's metadata</a>
  wiki:footer-text: `your footer text goes here &#169; 2005 by you &#xa0;&#xa0;Footer | Links | Here | Etc. 
  wiki:uses-theme: base:default-theme
  wiki:uses-skin:  base:skin-lightblue.css
'''
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
}

#rxml
authStructure =\
"""
 #######################################
 #auth schema and base resources 
 #######################################
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

 auth:permission-new-resource-statement
  rdf:type: auth:Permission

 auth:permission-execute
  rdf:type: auth:Permission
 
 #auth:with-value predicates:
 auth:with-value-greater-than: rdfs:subPropertyOf: auth:with-value
 auth:with-new-resource-value: rdfs:subPropertyOf: auth:with-value
 auth:with-value-instance-of: rdfs:subPropertyOf: auth:with-value
 auth:with-value-subclass-of: rdfs:subPropertyOf: auth:with-value
 auth:with-value-subproperty-of: rdfs:subPropertyOf: auth:with-value
 auth:with-guard-that-user-can-assign: rdfs:subPropertyOf: auth:with-value
 
 #######################################
 # pre-defined users and roles
 #######################################
 
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
  # even though the super-user role doesn't need these tokens to assign guards 
  # we add these here so they shows up in the Sharing dropdown on the edit page
  auth:can-assign-guard: base:write-structure-token 
  auth:can-assign-guard: base:save-only-token
  #if you want to use release labels it is convenient to add this next property
  #which is user by edit.xsl
  #wiki:default-edit-label: wiki:label-released  
    
 auth:role-default:
  rdfs:comment: `this role automatically assigned to new users (see signup-handler.xml)
  rdf:type: auth:Role
  rdfs:label: `Default User Role
  #remove this property if you don't want this 
  auth:has-rights-to: base:create-nospam-token 
  auth:has-rights-to: base:change-accesstoken-guard
 
 #######################################
 #access tokens 
 #######################################
   
 #access token to protect structural resources from modification
 #(assign (auth:has-rights-to) to adminstrator users or roles to give access)
 base:write-structure-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Admin Write/Public Read
  auth:has-permission: wiki:action-delete     
  auth:has-permission: wiki:action-save
  auth:has-permission: wiki:action-save-metadata
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-new-resource-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:priority: 90

 base:write-structural-directory-token:
  rdf:type: auth:AccessToken
  rdfs:comment: `Overrides write-structure-token to let children be added to a folder
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-new-resource-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:with-property: wiki:has-child
  auth:priority: 90

 wiki:ItemDisposition:
  auth:type-guarded-by: base:write-structure-token
  
 wiki:DocType:
  auth:type-guarded-by: base:write-structure-token

 wiki:Label:
  auth:type-guarded-by: base:write-structure-token
  #if you allow non-administrators to create labels you probably want to add an accesstoken 
  #here to prevent users from adding or removing wiki:is-released properties  
  
 base:save-only-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Admin Write/Public Read & Save-Only
  auth:has-permission: wiki:action-delete     
  auth:has-permission: wiki:action-save-metadata
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:priority: 19
  rdfs:comment:  '''this token lets resources be modified through the edit/save UI
 but prevents users from modifying the metadata directly or deleting the resource
 (useful for resources you want to let users edit in a controlled fashion)'''

 base:save-only-override-token:
  rdf:type: auth:AccessToken
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:priority: 19
  rdfs:comment:  '''use this token to override save-only-token 
  by associating it with a trusted resource via auth:grants-rights-to'''

 base:execute-function-token:
  rdf:type: auth:AccessToken
  auth:has-permission: auth:permission-execute
  auth:priority: 1
  rdfs:comment:  "default token used by authorizedExtFunctions to authorize XPath functions"
  
 base:save: 
    auth:grants-rights-to: base:save-only-override-token
    auth:grants-rights-to: base:execute-function-token

 base:save-user: 
    auth:grants-rights-to: base:write-structural-directory-token
  
 base:released-label-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Public but Private Release
  auth:has-permission: wiki:action-delete     
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:with-property: wiki:has-label
  auth:with-value:    wiki:label-released
  auth:priority: 20
  rdfs:comment: '''Users or roles with this access-token can set pages as released (and delete pages). 
Note that if you create more labels with the wiki:is-released property you'll want to add a <auth:with-value> property to this token
'''
 
 base:create-unsanitary-content-token:
  rdfs:comment: `If the content creator has this token, rhizome.processMarkup() will not try to sanitize the HTML or XML.
  rdf:type: auth:AccessToken  
  auth:priority: 10

 base:create-nospam-token:
  rdfs:comment: '''If the content creator has this token, she is trusted not 
  to be a spammer and rhizome.processMarkup() will not add rel='nofollow' to 
  links.'''
  rdf:type: auth:AccessToken  
  auth:priority: 10

 ###############################################
 # access tokens guards common to all resources
 ###############################################

 #notes: 
 # * though several of these tokens are specific to particular types of resources
 # we need to associate them all resources because class access tokens don't check with-property
 # * even though base:released-label-token guards all resources, 
 # users can still create unreleased pages that are visible until an editor/administrator marks a revision as released
 # because if no revision has been labeled released that latest revision is displayed   
 base:common-access-checks:
   auth:guarded-by: base:guard-guard 
   auth:guarded-by: base:change-schema-token
   auth:guarded-by: base:released-label-token
   auth:guarded-by: base:execute-python-token
   auth:guarded-by: base:user-guard
   auth:guarded-by: base:account-guard
   auth:guarded-by: base:change-accesstoken-guard
   auth:guarded-by: base:limit-priority-guard
   
 base:execute-python-token:
  rdf:type: auth:AccessToken  
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-new-resource-statement
  auth:with-property: a:transformed-by
  auth:with-value: wiki:item-format-python      
  auth:priority: 100
    
 base:role-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all Roles from being modified
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement  
   auth:priority: 100

 auth:Role:
  auth:type-guarded-by: base:role-guard

 base:user-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all Users from having their association with their account changed
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement  
   auth:with-property:  foaf:holdsAccount
   auth:priority: 100

 base:account-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all OnlineAccounts from having their roles and access tokens changed
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement  
   auth:has-permission: auth:permission-new-resource-statement   
   auth:with-property:  auth:has-rights-to
   auth:with-property:  auth:has-role
   auth:with-property:  auth:can-assign-guard
   auth:priority: 100
        
 base:access-token-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all AccessTokens from being being modified
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement
   auth:priority: 100

 auth:AccessToken:
  auth:type-guarded-by: base:access-token-guard
    
 base:guard-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects every resource from having its access tokens added or removed
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement
   auth:with-property:  auth:guarded-by
   auth:with-property:  auth:type-guarded-by   
   auth:with-property:  auth:grants-rights-to   
   auth:priority: 100
      
 #for now only let the administrator change the schema
 base:change-schema-token:
  rdf:type: auth:AccessToken
  rdfs:label: `guards any statements that changes the schema
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:has-permission: auth:permission-new-resource-statement
  auth:with-property: rdfs:subClassOf
  auth:with-property: rdfs:subPropertyOf
  auth:with-property: rdfs:domain
  auth:with-property: rdfs:range
  auth:priority: 100

 base:change-accesstoken-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: "users with this token can add or remove guards tokens that we have can-assign-guard rights to"
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement
   auth:with-property:  auth:guarded-by
   auth:with-property:  auth:type-guarded-by
   auth:with-guard-that-user-can-assign: 1
   auth:priority: 100  

 base:limit-priority-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `this token prevents access tokens to be created over a certain priority:
   auth:has-permission: auth:permission-new-resource-statement
   auth:with-property:  auth:priority
   auth:with-value-greater-than: 9
   auth:priority: 100
""" % {'base' : rhizome.BASE_MODEL_URI }

#Allow users to create a new accounts that have the default role 
usersCanCreateAccount =\
'''     
 base:common-access-checks:
   auth:guarded-by: base:newaccount-guard
   auth:guarded-by: base:newaccount-guard2
   
 base:newaccount-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `allows new accounts to be created with the default role
   auth:has-permission: auth:permission-new-resource-statement
   auth:with-property:  auth:has-role
   auth:with-value:     auth:role-default
   auth:priority: 100   #overrides base:account-guard

 base:newaccount-guard2:
   rdf:type: auth:AccessToken   
   rdfs:comment: `allow new resources to be guarded-by or have rights to whatever new access tokens they create 
   auth:has-permission: auth:permission-new-resource-statement
   auth:with-property:  auth:has-rights-to
   auth:with-property:  auth:can-assign-guard
   auth:with-new-resource-value:     `1
   auth:priority: 100   #overrides base:account-guard
 
 auth:role-default: 
  auth:has-rights-to: base:newaccount-guard
  auth:has-rights-to: base:newaccount-guard2
'''

guestsCanCreateAccount = usersCanCreateAccount+\
'''     
 auth:role-guest: 
  auth:has-rights-to: base:newaccount-guard
  auth:has-rights-to: base:newaccount-guard2
'''

#add this if you want to protect all content from modification unless the user has logged-in
#to unprotect particular resources, guard them with the base:override-general-write-token
writeProtectAll =\
''' 
 base:common-access-checks:
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

#this enables guest users to signup for an account even when all resources 
#are write protected
createAccountOverride = guestsCanCreateAccount + \
'''
 #we need to keep foaf:OnlineAccount resources writable
 #note that this is not a class AccessToken but a guard on the class resource itself (used by findContentAction) 
 foaf:OnlineAccount:
   auth:guarded-by: base:override-general-write-token   

 auth:role-guest: 
  auth:has-rights-to: base:newaccount-guard
  auth:has-rights-to: base:newaccount-guard2
'''

#add this if you want to protect all resources (except the home page) 
#from being read unless the user has logged-in
#to unprotect particular resources, guard them with the base:override-general-read-token
#(You probably want to combine this with writeProtectAll)
readProtectAll =\
''' 
 base:common-access-checks:
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

 #overrides to enable the display of the default index page 
 #and related structural pages
 wiki:ExternalResource: auth:guarded-by: base:override-general-read-token 
 base:index: auth:guarded-by: base:override-general-read-token 
 base:login: auth:guarded-by: base:override-general-read-token 
 base:sidebar: auth:guarded-by: base:override-general-read-token 
 base:intermap.txt: auth:guarded-by: base:override-general-read-token  
 base:basestyle.css: auth:guarded-by: base:override-general-read-token 
 base:user.css: auth:guarded-by: base:override-general-read-token 
 {%(base)smovabletype/theme.css}: auth:guarded-by: base:override-general-read-token 
 {%(base)smovabletype/theme.xsl}: auth:guarded-by: base:override-general-read-token 
 {%(base)sdefault/theme.css}: auth:guarded-by: base:override-general-read-token 
 {%(base)sdefault/theme.xsl}: auth:guarded-by: base:override-general-read-token 
''' % {'base' : rhizome.BASE_MODEL_URI }
 
#add actions:
for action in ['view', 'edit', 'new', 'creation', 'save', 'delete',  
  'confirm-delete', 'showrevisions', 'edit-metadata', 'save-metadata', 
  'view-metadata', 'view-source']:
    authStructure += "\n wiki:action-%s: rdf:type: auth:Permission" % action

templateList.append( ('@auth', rxml.zml2nt(contents=authStructure, nsMap=nsMap)) )
templateList.append( ('@guestsCanCreateAccount', 
  rxml.zml2nt(contents=guestsCanCreateAccount, nsMap=nsMap)) )

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
  
templateList.append(('@model',rxml.zml2nt(contents=modelVars, nsMap=nsMap)))
   
def name2uri(name, nsMap=nsMap):
    '''
    If the name's prefix in nsMap it is expanded otherwise we assume its a URI 
    and return it as is.
    '''
    i = name.find(':')
    prefix = name[:i]
    if prefix in nsMap:
        return nsMap[prefix]+name[i+1:]
    else:
        return name
    
def addStructure(type, structure, extraProps=[], name2uri=name2uri):
    '''Structure is a sequence of tuples, each of which consists
     of at least the resource URI and a label, followed by one literal 
     for each extra property.'''
    n3 = ''
    type = name2uri(type)
    for props in structure:
        name, label = name2uri(props[0]), props[1]
        n3 += '''<%s> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <%s> .\n''' % (name, type)
        n3 += '''<%s> <http://www.w3.org/2000/01/rdf-schema#label> "%s" .\n''' % (name, label)
        for i in range(2, len(props)):
            #assume object is a literal
            if props[i]:
                n3 += '''<%s> <%s> "%s" .\n''' % (
                 name, name2uri(extraProps[i-2]), props[i])        
    return n3

#give readable names and descriptions to user-visible classes
userClasses = [ ('foaf:OnlineAccount', 'Account', ''),
   ('foaf:Person', 'User', ''), 
   ('wiki:Folder', 'Folder', ''), 
   ('auth:Role', 'Role', ''), ('auth:AccessToken', 'Access Token', ''),
   ('wiki:Label', 'Label', ''), ('wiki:DocType', 'Doc Type', ''), 
   ('wiki:Keyword', 'Keyword', ''), 
   ('wiki:ItemDisposition', 'Disposition', ''),
   ('a:NamedContent', 'Named Content', ''),
   ('wiki:SiteTheme', 'Site Theme','')]

templateList.append( ('@userClasses', 
  addStructure('rdfs:Class', userClasses, ['rdfs:comment'])) )

itemDispositions = [ 
     ('http://rx4rdf.sf.net/ns/wiki#item-disposition-complete', 'Page'),
     ('http://rx4rdf.sf.net/ns/wiki#item-disposition-entry', 'Entry'),
     ('http://rx4rdf.sf.net/ns/wiki#item-disposition-template', 'Template'),
     ('http://rx4rdf.sf.net/ns/wiki#item-disposition-handler', 'Handler'),            
     ('http://rx4rdf.sf.net/ns/wiki#item-disposition-rxml-template', 'RxML Template'), 
     ('http://rx4rdf.sf.net/ns/wiki#item-disposition-print', 'Printable'),
     ('http://rx4rdf.sf.net/ns/wiki#item-disposition-short-display', 'Summary'),
#     ('http://rx4rdf.sf.net/ns/wiki#item-disposition-s5-template', 'S5 Template'), 
]

docTypes = [ ('http://rx4rdf.sf.net/ns/wiki#doctype-faq', 'FAQ', 'text/xml'),
   ('http://rx4rdf.sf.net/ns/wiki#doctype-xhtml', 'XHTML', 'text/html'),
   ('http://rx4rdf.sf.net/ns/wiki#doctype-document', 'Document', 'text/xml'),
   ('http://rx4rdf.sf.net/ns/wiki#doctype-specification', 'Specification', 'text/xml'),
   ('http://rx4rdf.sf.net/ns/wiki#doctype-docbook', 'DocBook', 'text/xml'), 
   ('http://rx4rdf.sf.net/ns/wiki#doctype-schematron', 'Schematron', 'text/xml', 
                                             "http://www.ascc.net/xml/schematron"), 
   #('http://rx4rdf.sf.net/ns/wiki#doctype-todo', 'Todo', 'text/xml'),
   #todo: uncomment this when we can hide it from users
   #('http://rx4rdf.sf.net/ns/wiki#doctype-wiki', 'Wiki', 'text/html'), 
   ]

labels = [ ('http://rx4rdf.sf.net/ns/wiki#label-draft', 'Draft'),
            ('http://rx4rdf.sf.net/ns/wiki#label-released', 'Released'),
         ]

templateList.append( ('@dispositions', 
 addStructure('http://rx4rdf.sf.net/ns/wiki#ItemDisposition', itemDispositions)))
templateList.append( ('@doctypes', 
 addStructure('http://rx4rdf.sf.net/ns/wiki#DocType', 
 docTypes, ['http://rx4rdf.sf.net/ns/archive#content-type', 'wiki:for-namespace'])) )
templateList.append( ('@labels', 
 addStructure('http://rx4rdf.sf.net/ns/wiki#Label', labels)+
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

#create a map so derived sites can replace pages: for example, see site-config.py
templateMap = dict(templateList) 
#create a NTriples string
STORAGE_TEMPLATE = "".join(templateMap.values()) 

itemFormats = [
 cp.mimetype and (cp.uri, cp.label, cp.mimetype)  or (cp.uri, cp.label) 
 for cp in contentProcessors 
        + rx.rhizome.raccoon.ContentProcessors.DefaultContentProcessors
 if cp.label
]

_rfb = 'http://rx4rdf.sf.net/ns/wiki#rdfformat-'
rdfFormats = [(_rfb+'rdfxml', 'RDF/XML', 1, 1),(_rfb+'rxml_zml', 'RxML',1,1),
                                           (_rfb+'ntriples', 'NTriples',1,1)]
try:
   import RDF
   rdfFormats += [(_rfb+'turtle', 'Turtle',0,1)]
except ImportError: pass
   
#define the APPLICATION_MODEL (static, read-only statements in the 'context:application' scope)
APPLICATION_MODEL= (
  addStructure('http://rx4rdf.sf.net/ns/wiki#ItemFormat', itemFormats, 
                            ['http://rx4rdf.sf.net/ns/archive#content-type'])
  + addStructure('http://rx4rdf.sf.net/ns/wiki#RDFFormat', rdfFormats,
                                    ['wiki:can-serialize', 'wiki:can-parse'])
  + '''<%saccounts/admin> <%s> "%s" .\n''' % (rhizome.BASE_MODEL_URI, 
                                passwordHashProperty, adminShaPassword)
)

#add the "archive" schema to APPLICATION_MODEL
import os.path
from rx import RxPathUtils
#4Suite's RDF parser can't parse archive-schema.rdf 
#so we have to load a NTriples file instead
#schema = RxPathUtils.convertToNTriples(
#  os.path.split(_rhizomeConfigPath)[0]+'/archive-schema.nt')
schema = file(os.path.split(_rhizomeConfigPath)[0]+'/archive-schema.nt').read()
#to regenerate: change above to end in .rdf and uncomment this line:
#file(os.path.split(_rhizomeConfigPath)[0]+'/archive-schema.nt', 'w').write(schema)
APPLICATION_MODEL += schema

#add the "wiki" schema -- not much here right now
wikiSchema ='''
  wiki:links-to:   rdfs:subPropertyOf: wiki:references
  wiki:appendage-to:   rdfs:subPropertyOf: wiki:references
  #wiki:appendage-to is a property that indicates that 
  #a resource doesn't stand on its own
  #but rather is subordinate to the object of statement
  #we define the following content relationships as subproperties of this:
  wiki:comments-on:   rdfs:subPropertyOf: wiki:appendage-to
  wiki:attachment-of: rdfs:subPropertyOf: wiki:appendage-to
'''
APPLICATION_MODEL += rxml.zml2nt(contents=wikiSchema, nsMap=nsMap)

#we add these functions to the config namespace so that config files 
#that include this can access them
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

#this is deprecated:
def __addSiteVars__(siteVars, rxml=rxml, configlocals=locals()):
    return configlocals['__addRxML__'](siteVars, replace = '@sitevars')
    