actions = { 'http-request' : [
        Action(["/*[rdfs:label=$_name]"]), #find the context
        Action( ["string(rdfs:comment)", "'not found'"],
                 lambda result, *args: result), #return the content        
        Action(['rdfs:format', "'http://rx4rdf.sf.net/ns/wiki#item-format-text'"],
                   __server__.processContents), #process the content                         
        ]}

APPLICATION_MODEL='''<http://rx4rdf.sf.net/test/resource> <http://www.w3.org/2000/01/rdf-schema#label> "authorized" .
<http://rx4rdf.sf.net/test/resource> <http://www.w3.org/2000/01/rdf-schema#comment> "print 'authorized code executed'" .
<http://rx4rdf.sf.net/test/resource> <http://www.w3.org/2000/01/rdf-schema#format> <http://rx4rdf.sf.net/ns/wiki#item-format-python> .
<http://rx4rdf.sf.net/test/resource2> <http://www.w3.org/2000/01/rdf-schema#label> "unauthorized" .
<http://rx4rdf.sf.net/test/resource2> <http://www.w3.org/2000/01/rdf-schema#comment> "print 'unauthorized code executed'" .
<http://rx4rdf.sf.net/test/resource2> <http://www.w3.org/2000/01/rdf-schema#format> <http://rx4rdf.sf.net/ns/wiki#item-format-python> .
<http://rx4rdf.sf.net/test/resource3> <http://www.w3.org/2000/01/rdf-schema#label> "dynamic unauthorized" .
<http://rx4rdf.sf.net/test/resource3> <http://www.w3.org/2000/01/rdf-schema#comment> "<?raccoon-format http://rx4rdf.sf.net/ns/wiki#item-format-python?>print 'unauthorized code executed'" .
<http://rx4rdf.sf.net/test/resource3> <http://www.w3.org/2000/01/rdf-schema#format> <http://rx4rdf.sf.net/ns/wiki#item-format-xml> .
'''

#digest authorization is the default for python content
authorizationDigests = { 'KGGwJMBA2GCBaAieHj45IH5iZ4A=' : 1} 