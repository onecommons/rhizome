actions = { 'test-error-request' : [
        Action(
            ["wf:error('pretend a page was not found', 404)", ],
                lambda result, kw, contextNode, retVal: 'this function should never be called!'
            ),
        ],
        'test-error-request-error': [
        Action( [ 
    "f:if($error:name='XPathUserError' and $error:errorCode=404, '404 not found')",
    "'503 unhandled error'"],
        lambda result, kw, contextNode, retVal: result
                    )]
        }

APPLICATION_MODEL='''<http://rx4rdf.sf.net/test/resource> <http://www.w3.org/2000/01/rdf-schema#label> "foo" .
<http://rx4rdf.sf.net/test/resource> <http://www.w3.org/2000/01/rdf-schema#comment> "page content." .
'''