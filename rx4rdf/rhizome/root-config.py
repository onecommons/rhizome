#root-config.py
#this application dispatches requests to different applications based on the path and hostname
#because this is just an application itself you can create an hierarchy of applications
#todo: allow an app to run with appBase=/ and another app with a different appBase on the same hostname
#todo: when the config file (and included config files) have changed the app will reload itself
#todo: option for tomcat like autodeployment: add rule that checks if directory exists and look for config file

try:
    serverConfig =__argv__[__argv__.index("-s")+1]
    STORAGE_TEMPLATE =  file(serverConfig).read()
    xmlConfig = True
except (IndexError, ValueError):        
    pass #no XML config file specified
                
reloadAppConfig = False

from rx import rxml
                
nsMap = { 'config' : 'http://rx4rdf.sf.net/ns/raccoon/config#' }

#Each application resource can have zero or one appBase properties, but 0 or more hostnames
#the appBase applies to every host
#if appBase is missing it defaults default to '/'
#if appBase and hostname is missing the app matches any URL
#
#The resource URI is used as the BASE_MODEL_URI of the app
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
#   config:hostname: 'foo.org'
#   config:disabled: '' #not disabled
#''')
#
# If the -x <server.xml> option is used, an XML file can be specified instead. 
# Here is a server.xml file equivalent to the above example:
#<server xmlns='http://rx4rdf.sf.net/ns/raccoon/config#' >
#  <host model-uri='http://www.foo.com/'
#     config-path="test-links.py"
#     path="."
#     appBase="/bar"
#     appName="bar" >
#   <hostname>foo.net</hostname>
#   <hostname>foo.org</hostname>
# </host>
#</server>

if locals().get('xmlConfig'):
    from rx.DomStore import XMLDomStore
    domStoreFactory = XMLDomStore 
     
    findAppQueries = ['''/config:server/config:host[not(@disabled)][@config-path]
            [not(@appBase) or starts-with($_name, substring(@appBase,2) )]
            [not(config:hostname) or 
            config:hostname[f:ends-with(wf:split($request-header:host,':')[1], .)]]''', 
        "/config:server/config:host[@default-app][not(@disabled)]", ]
    
    def getRequestProcessorArgs(result, kw, contextNode):
        root = kw['__server__']
        node = result[0]
        return dict(a= root.evalXPath('string(@config-path)', node=node), 
             p= os.path.abspath(root.evalXPath('string(@path)', node=node)),
             appBase = root.evalXPath('string(@appBase)', node=node),
             appName=root.evalXPath('string(@appName)', node=node),                     
             model_uri = str(root.evalXPath('string(@model-uri)', node=node))
             )    

    cachePredicate = lambda resultNodeset, kw, contextNode, retVal: \
        kw['__server__'].evalXPath('string(@model-uri)', node=resultNodeset[0])
else:
    findAppQueries = [
    #find the application that matches the URI's hostname and/or base path
    '''/*[not(config:disabled)][config:config-path]
          [not(config:appBase) or starts-with($_name, substring(config:appBase,2))]
          [not(config:hostname) or 
           config:hostname[f:ends-with(wf:split($request-header:host,':')[1], .)]
          ]''',                        
    "/*[config:default-app][not(config:disabled)]",
    ]

    def getRequestProcessorArgs(result, kw, contextNode):
        root = kw['__server__']
        node = result[0]
        return dict(a= root.evalXPath('string(config:config-path)', node=node), 
             p= os.path.abspath(root.evalXPath('string(config:path)', node=node)),
             appBase = root.evalXPath('string(config:appBase)', node=node),
             appName=root.evalXPath('string(config:appName)', node=node),                     
             model_uri = str(StringValue(result))
             )

    cachePredicate = lambda resultNodeset, kw, contextNode, retVal: StringValue(resultNodeset)
    
def getRequestProcessor(result, kw, contextNode, retVal,
        __argv__=__argv__, reloadAppConfig=reloadAppConfig,
        getRequestProcessorArgs=getRequestProcessorArgs):    
    args = getRequestProcessorArgs(result, kw, contextNode)
    args['argsForConfig']=__argv__    
    retVal = HTTPRequestProcessor(**args)
    return retVal
                 
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
 
_findAppAction = Action(
    findAppQueries,  
    #create a HTTPRequestProcessor for the app 
    action = getRequestProcessor,
    #cache the HTTPRequestProcessor using the app's model URI as the key 
    cachePredicate = cachePredicate    
    )

actions = { 'http-request' : [
        _findAppAction, #find the associated app (i.e. the HTTPRequestProcessor)
        Action(action=delegateRequest), #delegate the request to it
        #note: if no match raccoon.default_not_found() will be invoked
    ] }
    
defaultPageName = '/' #so each app can use its own defaultPageName    
