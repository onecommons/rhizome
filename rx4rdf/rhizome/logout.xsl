<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" xmlns:response-header="http://rx4rdf.sf.net/ns/raccoon/http-response-header#" xmlns:session="http://rx4rdf.sf.net/ns/raccoon/session#" xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:f="http://xmlns.4suite.org/ext" xmlns:x="http://www.w3.org/1999/XSL/Transform" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" exclude-result-prefixes="f wf a wiki rdf" version="1.0">
  <x:param name="redirect"/>
  <x:template match="/">
    <x:variable name="dummy" select="wf:remove-metadata('session:login')"/>
    <x:variable name="dummy2" select="wf:assign-metadata('response-header:status', 302)"/>
    <x:variable name="dummy3" select="wf:assign-metadata('response-header:Location', $redirect)"/>You should be redirected shortly... </x:template>
</x:stylesheet>
