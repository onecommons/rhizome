actions = { 'http-request' : [
        Action(
            ["string(/*[rdfs:label=$_name]/rdfs:comment)", 
            "'not found!'"],
            lambda result, kw, contextNode, retVal: '<html><body>'+result+'</body></html>'
            ),
    ] }

APPLICATION_MODEL='''<http://rx4rdf.sf.net/test/resource> <http://www.w3.org/2000/01/rdf-schema#label> "foo" .
<http://rx4rdf.sf.net/test/resource> <http://www.w3.org/2000/01/rdf-schema#comment> "page content." .
'''