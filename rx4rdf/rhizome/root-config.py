#root-config.py
#this application dispatches requests to different applications based on the path and hostname
#because this is just an application itself you can create an hierarchy of applications
#todo: allow an app to run with appBase=/ and another app with a different appBase on the same hostname
#todo: when the config file (and included config files) have changed the app will reload itself
#todo: option for tomcat like autodeployment: add rule that checks if directory exists and look for config file
                
from rx import rxml

nsMap = { 'config' : 'http://rx4rdf.sf.net/ns/raccoon/config#' }

#Each application resource can have zero or one appBase properties, but 0 or more hostnames
#the appBase applies to every host
#if appBase is missing it defaults default to '/'
#if appBase and hostname is missing the app matches any URL
#
#The resource URI is used the BASE_MODEL_URI of the app
#and appBase and appName correspond to equivalent config settings
#If any of these are set in the app's config file, those settings
#will override the value that appear here.
#
#APPLICATION_MODEL = rxml.zml2nt(nsMap = nsMap, contents='''
# {http://www.example.com/app1-baseuri}:
#   config:appBase: "/foo"
#   config:appName: 'foo'
#   config:config-path: "foo/blank-config.py"
#   config:path: "foo"
#   config:hostname: 'foo.net'
#   config:disabled: '' #not disabled
#''')

def delegateRequest(result, kw, contextNode, retVal): 
    if retVal:                
        result = retVal.handleHTTPRequest(kw['_name'], kw['_request'].paramMap)
        kw['_APP_BASE'] = retVal.appBase
        #response cookies must have their path at least equal to the appBase  
        for morsel in kw['_response'].simpleCookie.values():
            path = morsel['path']            
            if not path.startswith(retVal.appBase):
               morsel['path'] = retVal.appBase
        return result
    return None

actions = { 'http-request' : [
        Action(
            [
            '''/*[not(config:disabled)][config:config-path][not(config:appBase) or starts-with($_name, substring(config:appBase,2) )]
                                     [not(config:hostname) or config:hostname[f:ends-with(wf:split($request-header:host,':')[1], .)]]''',
                        
            "/*[config:default-app][not(config:disabled)]",            
            ],   
            action = lambda result, kw, contextNode, retVal, __argv__=__argv__: 
               RequestProcessor(a= kw['__server__'].evalXPath('string(config:config-path)', node=result[0]), 
                     p= os.path.abspath(kw['__server__'].evalXPath('string(config:path)', node=result[0])),
                     appBase = kw['__server__'].evalXPath('string(config:appBase)', node=result[0]),
                     appName=kw['__server__'].evalXPath('string(config:appName)', node=result[0]),
                     model_uri = str(StringValue(result)), argsForConfig=__argv__
                      ),
            cachePredicate = lambda resultNodeset, kw, contextNode, retVal: StringValue(resultNodeset),            
            ),

        FunctorAction(delegateRequest, [0,1,2,3]),        
        #note: if no match raccoon.default_not_found() will be invoked
    ] }
    
    
