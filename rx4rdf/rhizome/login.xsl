<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf="http://rx4rdf.sf.net/ns/racoon/xpath-ext#" xmlns:response-header="http://rx4rdf.sf.net/ns/racoon/http-response-header#" xmlns:session="http://rx4rdf.sf.net/ns/racoon/session#" xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:f="http://xmlns.4suite.org/ext" xmlns:x="http://www.w3.org/1999/XSL/Transform" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" exclude-result-prefixes="f wf a wiki rdf" version="1.0">
  <x:param name="redirect"/>
  <x:param name="password"/>
  <x:param name="loginname"/>
  <x:param name="__passwordHashProperty"/>
  <x:template match="/">
    <x:variable name="dummy" select="wf:if(wf:secure-hash($password) = /*[wiki:login-name = $loginname]/*[uri(.)=$__passwordHashProperty],  &quot;wf:assign-metadata('session:login', $loginname) and wf:assign-metadata('session:message', '')&quot;,  &quot;wf:assign-metadata('session:message', 'login attempt failed!')&quot;)"/>
    <x:variable name="dummy2" select="wf:assign-metadata('response-header:status', 302)"/>
    <x:variable name="dummy3" select="wf:assign-metadata('response-header:Location', $redirect)"/>You should be redirected shortly... </x:template>
</x:stylesheet>

