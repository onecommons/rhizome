"""
    Authorization functionality for Rhizome.

    Copyright (c) 2004-5 by Adam Souzis <asouzis@users.sf.net>
    All rights reserved, see COPYING for details.
    http://rx4rdf.sf.net    
"""
from rx.RhizomeBase import *

def authorizeDynamicContent(self, contents, formatType, kw,
                            dynamicFormat, accessToken=None):
    '''see rhizome-config.py for usage'''
    if dynamicFormat:
        assert accessToken
        if not kw['__server__'].evalXPath(
'''$__account/auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser' or
/*[.='%s'][.=$__account/auth:has-rights-to/* or
.=$__account/auth:has-role/*/auth:has-rights-to/*]'''
            % accessToken, kw2vars(__account=kw.get('__account',[]))):
           raise raccoon.NotAuthorized(
'You are not authorized to create dynamic content with this format: %s' 
                % (formatType))            
    
    if self.__class__.authorize:
        return self.__class__.authorize(self, contents, formatType,
                                        kw, dynamicFormat)
    elif (kw.get('__server__') and
          kw['__server__'].authorizeContentProcessorsDefault):
        return kw['__server__'].authorizeContentProcessorsDefault(
            contents, formatType, kw, dynamicFormat)

def authorizationValueMatch(context, predicates, value):
    '''
    Determines whether an access token with a sub-property of
    auth:with-value should be applied to the action.
    '''
    for node in predicates:
        predicate = node.stmt.predicate
        object = node.stmt.object
        if predicate == 'http://rx4rdf.sf.net/ns/auth#with-value': 
            if object == raccoon.StringValue(value):
                return raccoon.XTrue
        elif predicate == 'http://rx4rdf.sf.net/ns/auth#with-value-greater-than':
            if raccoon.NumberValue(value) > float(object):
                return raccoon.XTrue
        elif predicate == 'http://rx4rdf.sf.net/ns/auth#with-new-resource-value':
            newResourceUris = [raccoon.StringValue(x)
               for x in context.varBindings.get((None, '_newResources'), [])]
            if raccoon.StringValue(value) in newResourceUris:
                return raccoon.XTrue
        elif predicate == 'http://rx4rdf.sf.net/ns/auth#auth:with-value-instance-of':
            if RxPath.isInstanceOf(context, value, object):
                return raccoon.XTrue
        elif predicate == 'http://rx4rdf.sf.net/ns/auth#auth:with-value-subclass-of':
            if RxPath.isType(context, value, object):
                return raccoon.XTrue
        elif predicate == 'http://rx4rdf.sf.net/ns/auth#auth:with-value-subproperty-of':
            if RxPath.isProperty(context, value, object):
                return raccoon.XTrue
        elif predicate == 'http://rx4rdf.sf.net/ns/auth#with-value-account-has-via-this-property':            
            #assumes value is a resource, matches if the account in the context
            #can reach that same resource via the property which is the object of the token
            vars = kw2vars(
                __account=context.varBindings.get((None, '__account'),[]),
                __context = value)
            cnxt = raccoon.XPath.Context.Context(context.node,
                    varBindings = vars,
                    processorNss = {'auth': "http://rx4rdf.sf.net/ns/auth#"})                                
            exp = '''($__account | $__account/auth:has-role/*)/*[@uri='%s']
                        = $__context''' % object
            compExpr = raccoon.RequestProcessor.expCache.getValue(exp)
            queryCache=getattr(context.node.ownerDocument, 'queryCache', None)
            if queryCache:
                result = queryCache.getValue(compExpr, cnxt)         
            else:
                result = compExpr.evaluate(cnxt)
            if result:
                return raccoon.XTrue
        else:
            raise raccoon.NotAuthorized(
'''Authorization failed because an unrecognized
sub-property of auth:with-value was encountered: %s ''' % predicate)
    return raccoon.XFalse

def authorizationValueMatchCacheKey(field, context, notCacheableXPathFunctions):
    if context.node: 
        #these variables maybe referenced by authorizationValueMatch 
        referencedVars = ['_newResources', '__account']
        values = [context.varBindings.get((None, name),[])
                     for name in referencedVars]
        return tuple([raccoon.getKeyFromValue(v) for v in values])
    else: #not specified when getting XSLT (which relying on params)
        return ()
    
def _addPredicates(l, n):
    #its a resource
    if getattr(n, 'uri', None):
        l.extend(n.childNodes)
    else:
        l.append(n)
    return l

class RhizomeAuth(RhizomeBase):

    def validateExternalRequest(self, kw):
        '''
        Disallow (form variables, etc.) from starting with '__' 
        '''        
        for name in kw:
            if name.startswith('__'):
               raise raccoon.NotAuthorized(
    '%s: form variable names can not start with "__"' % (name))        
                
    def authorizeMetadata(self, operation, namespace, name, value, kw):
        '''
        Because XPath functions may be made available in contexts
        where little access control is desired, we provide a simple
        access control mechanism for assign-metadata() and
        remove-metadata(): Any variable whose name that starts with 2
        leading underscores is considered read-only and can not be
        assigned or removed.
        Also, 'session:login' can only be assigned if
        $password is present and its SHA1 digest matches the user's
        digest.
        '''
        if name.startswith('__') and operation in ['assign', 'remove']:
            return False
        elif (operation == 'assign' and
              namespace == raccoon.RXIKI_SESSION_NS and name == 'login'):
            #for security
            #we only let session:login be set in the context
            #where $password is present
            if not kw.has_key('password'):
                return False

            vars = kw2vars(password = kw['password'], login=value,
                           hashprop = self.passwordHashProperty)
            userResource = self.server.evalXPath(                
"/*[foaf:accountName=$login][*[uri(.)=$hashprop] = wf:secure-hash($password)]",
                vars=vars)
            if not userResource:
                return False
        return True
        
    def authorizeOperation(self, context, nodes, op, newResources=None,
                           extraPrivileges=None):
        '''
        Tests if the current account is authorized to perform the
        given action on the statements implied by the given predicate
        and/or resource nodes.
        '''
        account = context.varBindings.get( (None, '__account'))
        accountTokens = context.varBindings.get( (None, '__accountTokens'),[])
        if not account:
            return raccoon.XFalse
        #super user check:
        if self.server.evalXPath(
            "auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser'",
            node=account[0]):
            return raccoon.XTrue
        
        for node in reduce(_addPredicates, nodes, []):
            assert getattr(node, 'stmt') #assert it's a predicate node
            authorizingResources = self.getAuthorizingResources(
                node.parentNode )
            self._authorizeUpdate(account, accountTokens,authorizingResources, op,
                node.stmt.subject, node.stmt.predicate,node.stmt.object,
                newResources=newResources,extraPrivileges=extraPrivileges)
        return raccoon.XTrue
            
    def getAuthorizingResources(self, node, membershipList = None):
        '''
        Check authorization on all the applicable nodes: find all
        the subject resources that are reachable by inverse
        transitively following the subject of the statement and
        applying the authorization expression to them. Equivalent to:
        (.//auth:requires-authorization-for[* = $resource]/ancestors::*/..)[authquery] '''
        
        #but for now its more efficient to manually find the ancestors:    
        rdfDom = node.ownerDocument
        nodeset = [ node ]
        authresources = [ node ]
        while nodeset:
            #nodeset = self.server.evalXPath(
            #   '/*/auth:requires-authorization-for[. = $nodeset]',
            #   vars = kw2vars(nodeset = nodeset) )
            #is replaced with:
            oldnodeset = nodeset[:]
            nodeset = []
            for node in oldnodeset:
                for stmt in rdfDom.model.getStatements(None,None,node.uri,
                                          objecttype=OBJECT_TYPE_RESOURCE):
                    if rdfDom.schema.isCompatibleProperty(stmt.predicate, 
                    'http://rx4rdf.sf.net/ns/auth#requires-authorization-for'):
                        subject = rdfDom.findSubject(stmt.subject)
                        #assert subject, "subject of %s not found" % str(stmt)
                        if subject:
                            nodeset.append(subject)
                        else:
                            pass#self.log.warning(
                            #    "subject of %s not found" % str(stmt) )

            nodeset = [p for p in nodeset
                        if (not membershipList or p in membershipList) 
                            and p not in authresources] #avoid circularity
            nodeset = RxPath.Set.Unique(nodeset) 
            authresources.extend(nodeset)        
        return authresources

    def recheckAuthorizations(self, requiresAuthorizationPredicates, kw):        
        def uniqueRes(l,p):
            resNode = p.firstChild #the object resource node
            #if its text node, not a resource
            if resNode.nodeType != resNode.ELEMENT_NODE: 
                return l            
            if resNode not in l:
                #get the authorizingResources for the subject of the predicate
                #todo: as an optimization we could skip new resources
                authorizingResources = self.getAuthorizingResources(
                                        p.parentNode)
                l[resNode] = authorizingResources
                #we also want to re-authorize the properties of any resources
                #that depend on this resource for authorization
                dependentResources = p.ownerDocument.evalXPath(
                    './/auth:requires-authorization-for/*',
                    nsMap = self.server.nsMap,
                    node = resNode)                
                for r in dependentResources:
                    dependentAuthorizingResources = authorizingResources[:]
                    #we don't need to get every authorizing resource
                    #for these dependent resources, just the ones
                    #along the authorization path, which is "recorded"
                    #in the hierarchy of the resultset nodes
                    parent = r                    
                    while 1:                        
                        parent = parent.parentNode.parentNode
                        if parent and parent != resNode:
                            dependentAuthorizingResources.append(parent)
                        else:
                            break
                    if r in l:
                        #this resource might be require authorization
                        #through more than one path so combine them
                        l[r].extend(dependentAuthorizingResources)
                    else:
                        l[r] = dependentAuthorizingResources                        
            return l
        recheckResources = reduce(uniqueRes,
                                  requiresAuthorizationPredicates, {})
        for resNode, authorizingResources in recheckResources.items():
            authorizingResources = RxPath.Set.Unique(authorizingResources)
            for pred in resNode.childNodes:                    
                self._authorizeUpdate(kw['__account'], kw['__accountTokens'],
                    authorizingResources,
                    'http://rx4rdf.sf.net/ns/auth#permission-add-statement',
                    pred.stmt.subject, pred.stmt.predicate,pred.stmt.object,
                    newResources=kw.get('_newResources'),
                    extraPrivileges=kw.get('__extraPrivilegeResources'))
        
    def _authorizeUpdate(self, account, accountTokens, authorizingResources,
            action, subject, predicate=0, object=0,
            noraise=False, newResources=None,extraPrivileges=None):
        
        forAllResources = []
        commonResourceAnchor = self.server.domStore.dom.findSubject(
                 self.BASE_MODEL_URI + 'common-access-checks')
        if commonResourceAnchor:
            forAllResources.append(commonResourceAnchor)

        if newResources:
            if self.server.domStore.dom.findSubject(subject) in newResources:
                action = 'http://rx4rdf.sf.net/ns/auth#permission-new-resource-statement'

        if action == 'http://rx4rdf.sf.net/ns/auth#permission-new-resource-statement':
            #don't do class-based authorization while an resource is being constructed
            #instead we do that in seperate action in before-prepare
            findTokens = self.findTokens 
        else:
            findTokens = "("+self.findTokens+"|"+self.findClassTokens+")"
            
        required = findTokens + '''[auth:has-permission=$__authAction]
            [not($__authProperty) or not(auth:with-property)
             or is-subproperty-of($__authProperty,auth:with-property)]
            [not($__authValue) or not(auth:with-value)
              or wf:auth-value-matches(auth:with-value,$__authValue)]'''

        def kw2dict(**kw): return kw #for python 2.2 compatibility
        
        authkw = kw2dict(__authAction=action, __account=account,
            __accountTokens=accountTokens,            
            __authResources = authorizingResources,
            __authProperty=predicate, __authValue=object,
            _newResources=newResources or [],
            __authCommonChecks=forAllResources,
            __extraPrivilegeResources=extraPrivileges or [],
            __server__ = self.server)
        vars, extFunMap = self.server.mapToXPathVars(authkw)

        authQuery = self.authorizationQueryTemplate % { 'minpriority':
                                    self.minPriority, 'required':required}
        result = self.server.evalXPath(authQuery ,vars, extFunMap)

        if result:
            requires = []
            has = []
            for node in authorizingResources+forAllResources:
                requires.extend( self.server.evalXPath(
                    required,vars, extFunMap,node=node) )
                has.extend( self.server.evalXPath(
                    required+'[.=$__accountTokens]',
                    vars, extFunMap, node=node) )
            self.log.info('authentication failed, need tokens: %s'
                % RxPath.Set.Not(RxPath.Set.Unique(requires),
                                 RxPath.Set.Unique(has)))
            
        #if any of the authresources requires an auth token that the
        #user doesn't have access to, the nodeset will not be empty
        if result and not noraise:
            if action=='http://rx4rdf.sf.net/ns/auth#permission-add-statement':
                actionName = 'add'
            elif action=='http://rx4rdf.sf.net/ns/auth#permission-new-resource-statement':
                actionName = 'add to a new resource'
            elif action=='http://rx4rdf.sf.net/ns/auth#permission-remove-statement':
                actionName = 'remove'
            else:
                actionName = action
            raise raccoon.NotAuthorized(
                'You are not authorized to %s this statement: %s %s %s'
                    % (actionName, subject, predicate,object))
        #return the nodes of the resources that user
        #isn't authorized to perform this action on 
        return result

    def _getRequiredAccountValues(self, vars):
            return [vars.get( (None,name),
                    self.server.requestContext[-1].get(name, []))
                    for name in ['__account', '__accountTokens']]
        
    def validateXPathFuncArgs(self,name,context,args, isSuperUser):
        #by appending these to args we override any attempts to pass in
        #a different __account
        #also do this if we're the super user and didn't specify another account
        args = list(args)
        if not isSuperUser or '__account' not in args:
            values = self._getRequiredAccountValues(context.varBindings)
            args.extend(['__account', values[0], '__accountTokens', values[1]])
        return [], args

    def getValidateXPathFuncArgsCacheKey(self, cacheFuncName, cacheFunc):
        if not cacheFunc: #not cacheable
            return cacheFunc        
        def validateXPathFuncArgsCacheKey(field, context, notCacheableXPathFunctions):
            if cacheFunc != -1: 
                key = cacheFunc(field, context, notCacheableXPathFunctions)
            else:
                key = ()

            values = self._getRequiredAccountValues(context.node and
                                                    context.varBindings or {})
            return key + tuple([raccoon.getKeyFromValue(v) for v in values])
        return validateXPathFuncArgsCacheKey
        
    def authorizeXPathFunc(self, name,func, authFunc,context,args):
        '''
        Authorize the XPath function call using authFunc.        
        '''
        account = context.varBindings.get( (None, '__account'))
        if not account:
            raise raccoon.NotAuthorized(
                'No account found when authorizing of %s' % name[1])

        isSuperUser = self.server.evalXPath(
            "auth:has-role='http://rx4rdf.sf.net/ns/auth#role-superuser'",
            node=account[0])
        tokenUris, args = authFunc(name,context,args,isSuperUser)
        if not isSuperUser:
            #if not superuser, check authorization:
            if tokenUris:
                tokenUris, args = authFunc(name,context,args)
                tokens = [context.node.ownerDocument.findSubject(res)
                          for res in tokenUris]
                notFound = [t[1] for t in zip(tokens,tokenUris) if not t[0]]
                if notFound:
                    raise raccoon.NotAuthorized(
                    'Unexpected error authorizing %s: resources %s not found'
                        % (name[1], notFound) )
                accountTokens = context.varBindings.get(
                            (None, '__accountTokens'),[])            
                extraPrivilegesRes = context.varBindings.get(
                            (None, '__handlerResource'),
                            context.varBindings.get(
    ('http://rx4rdf.sf.net/ns/raccoon/previous#','__handlerResource'), []))
                
                authkw = kw2vars(__authAction=
                    'http://rx4rdf.sf.net/ns/auth#permission-execute',
                    __accountTokens=accountTokens,
                    #'required' predicate is independent of this,
                    #so it can be any resource
                    __authResources=account,
                    #used by minpriority:
                    __extraPrivilegeResources=extraPrivilegesRes, 
                    required=tokens)
                xpath = self.authorizationQueryTemplate % {'minpriority':
                                self.minPriority, 'required':'$required'}
                result = self.server.evalXPath(xpath, authkw)
                if result:
                    raise raccoon.NotAuthorized(
            'You are not authorized to execute this function: '+ name[1])
        else:
            pass #print 'super user!' 
        return func(context, *args)

    def authorizeXPathFuncs(self, extFuncDict, extFuncCacheDict):
        '''
        Where necessary, update extFuncDict and extFuncCacheDict with
        functions that do an authorization before invoking the XPath
        function. The updated versions of these dictionary will be
        used in contexts where XPath function calls need to be
        authorized (e.g. the XSLT or XUpdate content processors).
        '''
        
        for name, (authFunc, cacheFunc) in self.authorizedExtFunctions.items():
            func = extFuncDict.get(name)
            if func:
                def curryFunc(name, func, authFunc):
                    #we need this inner func to create new local var bindings
                    #for each iteration of the loop
                    return lambda context, *args: self.authorizeXPathFunc(
                                name, func, authFunc, context, args)                
                extFuncDict[name] = curryFunc(name, func, authFunc)
                if cacheFunc:
                    #pass -1 if not in the notcachable dict
                    cacheFunc = cacheFunc(name, extFuncCacheDict.get(name,-1))
                #-1 means it shouldn't be in notcacheable dict
                if cacheFunc != -1: #if either 0 or a function
                    extFuncCacheDict[name] = cacheFunc
                elif extFuncCacheDict.has_key(name):
                    del extFuncCacheDict[name] #rare case, for correctness

    def raiseClassUnAuthorized(self, results, kw, *args):
        action = kw['__authAction']
        if action == 'http://rx4rdf.sf.net/ns/auth#permission-add-statement':
            actionName = 'add'
        elif action == 'http://rx4rdf.sf.net/ns/auth#permission-remove-statement':
            actionName = 'remove'
        elif action == 'http://rx4rdf.sf.net/ns/auth#permission-new-resource-statement':
            actionName = 'create'
        else:
            actionName = action                    
       
        raise raccoon.NotAuthorized(
            'You are not authorized to %s properties for one or more'
            ' of these resources:\n'% actionName
            + '\n'.join([r.uri for r in kw['__authResources']]))
 