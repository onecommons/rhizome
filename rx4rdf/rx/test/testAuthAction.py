#raccoon config file used by raccoonTest.py
startAction = Action(['$start'])

filterTokens = '''auth:guarded-by/auth:AccessToken[auth:has-permission=$__authAction]
  [not($__authProperty) or not(auth:with-property) or auth:with-property=$__authProperty]
  [not($__authValue) or not(auth:with-value) or auth:with-value=$__authValue]'''

findTokens = '''(./%(filterTokens)s  | ./rdf:type/*/%(filterTokens)s)''' % locals()

#authorizationQuery = '''not($__user/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser') and
#%(findTokens)s and not(%(findTokens)s[.=$__user/auth:has-rights-to/* or .=$__user/auth:has-role/*/auth:has-rights-to/*])''' % locals()

authorizationQuery = '''not($__user/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser') and
  wf:max(%(findTokens)s/auth:priority, 0) > wf:max(%(findTokens)s[.=$__user/auth:has-rights-to/* or .=$__user/auth:has-role/*/auth:has-rights-to/*]/auth:priority,0)''' % locals()

resourceAuthorizationAction = Action( ['''f:if(%s, /auth:Unauthorized)''' % authorizationQuery] )

#default to 'view' if not specified
resourceAuthorizationAction.assign("__authAction", 'concat("http://rx4rdf.sf.net/ns/wiki#action-",$action)', "'http://rx4rdf.sf.net/ns/wiki#action-view'") 
resourceAuthorizationAction.assign("__authProperty", '0')
resourceAuthorizationAction.assign("__authValue", '0')
resourceAuthorizationAction.assign("test1", findTokens, post=True)
resourceAuthorizationAction.assign("test2", 
 '$__user/auth:has-rights-to/*', post=True)
resourceAuthorizationAction.assign("test4", 'not($test1[.=$__user/auth:has-rights-to/* or .=$__user/auth:has-role/*/auth:has-rights-to/*])', post=True)
resourceAuthorizationAction.assign("test3", '(%(findTokens)s)[. = $__user/auth:has-rights-to/*]' % locals(), post=True)
#resourceAuthorizationAction.assign("test2", 
# '%(findTokens)s[.=$__user/auth:has-rights-to/* or .=$__user/auth:has-role/*/auth:has-rights-to/*]'%locals(), post=True)

finishAction = Action(['.'], lambda result, kw, contextNode, retVal: contextNode ) 

actions = { 'test' : [startAction, resourceAuthorizationAction, finishAction] }

BASE_MODEL_URI = 'test://authtest#'

nsMap = {'a' : 'http://rx4rdf.sf.net/ns/archive#',
        'dc' : 'http://purl.org/dc/elements/1.1/#',
         'rdf' : 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
         'rdfs' : 'http://www.w3.org/2000/01/rdf-schema#',
        'wiki' : "http://rx4rdf.sf.net/ns/wiki#",
         'auth' : "http://rx4rdf.sf.net/ns/auth#",
         'base' : BASE_MODEL_URI
         }

authStructure =\
'''
 auth:Unauthorized:
  rdf:type: auth:Unauthorized
 
 auth:permission-remove-statement
  rdf:type: auth:Permission
 
 auth:permission-add-statement
  rdf:type: auth:Permission

 #define two built-in users and their corresponding roles
 rx:resource id='%(base)susers/guest':
  rdf:type: wiki:User
  wiki:login-name: `guest
  wiki:name: `users/guest
  auth:has-role: wiki:role-guest

 rx:resource id='%(base)susers/admin':
  rdf:type: wiki:User
  wiki:login-name: `admin
  wiki:name: `users/admin
  auth:has-role: auth:role-superuser
  #note: we set the password in the application model below so its not hardcoded into the datastore
  #and can be set in the config file

 wiki:role-guest:
  rdf:type: auth:Role
  rdfs:label: `Guest
  
 auth:role-superuser:
  rdf:type: auth:Role
  rdfs:label: `Super User

 # add access token to protect structural pages from modification
 # (assign (auth:has-rights-to) to adminstrator users or roles to give access )
 base:write-structure-token:
  rdf:type: auth:AccessToken
  rdfs:label: `Administrator Write/Public Read
  auth:has-permission: wiki:action-delete     
  auth:has-permission: wiki:action-save
  auth:has-permission: wiki:action-save-metadata
  auth:has-permission: auth:permission-add-statement
  auth:has-permission: auth:permission-remove-statement   
  auth:priority: 10
  
 # some class level access tokens to globally prevent dangerous actions
 a:ContentTransform:
  auth:guarded-by: base:execute-python-token
  auth:guarded-by: base:execute-rxupdate-token
      
 base:execute-python-token:
  rdf:type: auth:AccessToken  
  auth:has-permission: auth:permission-add-statement
  auth:with-property: a:transformed-by
  auth:with-value: wiki:item-format-python      
  auth:priority: 10
  
 base:execute-rxupdate-token:
  rdfs:comment: `we need this since we don't yet support fine-grained authentication processing RxUpdate 
  rdf:type: auth:AccessToken  
  auth:has-permission: auth:permission-add-statement
  auth:with-property: a:transformed-by 
  auth:with-value: wiki:item-format-rxupdate        
  auth:priority: 10

 auth:Role:
  auth:guarded-by: base:role-guard

 base:role-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all Roles from being being modified
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement  
   auth:priority: 10
      
 auth:AccessToken:
  auth:guarded-by: base:access-token-guard
  
 base:access-token-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all AccessTokens from being being modified
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement
   auth:priority: 10
 
 # if we supported owl we could have owl:Thing as the subject instead 
 # and we wouldn't need a seperate check in the authorizationQuery
 base:common-access-checks:
  auth:guarded-by: base:all-resources-guard
  
 base:all-resources-guard:
   rdf:type: auth:AccessToken   
   rdfs:comment: `protects all resource from having its access tokens added or removed
   auth:has-permission: auth:permission-add-statement
   auth:has-permission: auth:permission-remove-statement
   auth:with-property:  auth:guarded-by
   auth:priority: 10

 # test stuff
 base:test-resource1:
   auth:guarded-by: base:test-token1

 base:test-token1:
  rdf:type: auth:AccessToken
  auth:has-permission: wiki:action-view     
  auth:priority: 1
  
''' % {'base' : BASE_MODEL_URI }

#add actions:
for action in ['view', 'edit', 'new', 'creation', 'save', 'delete', 'confirm-delete',
               'showrevisions', 'edit-metadata', 'save-metadata']:
    authStructure += "\n wiki:action-%s: rdf:type: auth:Permission" % action

from rx import rxml
STORAGE_TEMPLATE = rxml.zml2nt(contents=authStructure, nsMap=nsMap) 
STORAGE_PATH = 'dummmy'