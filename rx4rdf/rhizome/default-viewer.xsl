<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wf="http://rx4rdf.sf.net/ns/racoon/xpath-ext#" 
xmlns:response-header="http://rx4rdf.sf.net/ns/racoon/http-response-header#" 
 xmlns:f="http://xmlns.4suite.org/ext" xmlns:x="http://www.w3.org/1999/XSL/Transform" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" exclude-result-prefixes="f wf a wiki rdf" version="1.0">  
  <x:param name="__resource"/>
  <x:output method='text' />
  <x:template match="/">
    <x:variable name="dummy" select="wf:get-rdf-as-rhizml($__resource)"/>
    <x:variable name="dummy2" select="wf:assign-metadata('response-header:content-type', 'text/plain')"/>
</x:stylesheet>