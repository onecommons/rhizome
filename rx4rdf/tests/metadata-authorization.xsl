<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf="http://rx4rdf.sf.net/ns/racoon/xpath-ext#" xmlns:response-header="http://rx4rdf.sf.net/ns/racoon/http-response-header#" xmlns:session="http://rx4rdf.sf.net/ns/racoon/session#" xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:f="http://xmlns.4suite.org/ext" xmlns:x="http://www.w3.org/1999/XSL/Transform" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" exclude-result-prefixes="f wf a wiki rdf" version="1.0">
  <!-- when running rhizome, each of these assign-metdata calls should fail with an NotAuthorized exception -->
  <x:template match="/">    
    <x:variable name="dummy" select="wf:assign-metadata('session:login', 'foo')"/>
    <x:variable name="dummy2" select="wf:assign-metadata('__user', 'foo')"/>
</x:template>
</x:stylesheet>