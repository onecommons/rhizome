<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" 
xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" 
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" 
xmlns:a="http://rx4rdf.sf.net/ns/archive#" 
xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" 
xmlns:x="http://www.w3.org/1999/XSL/Transform" 
xmlns:f="http://xmlns.4suite.org/ext" 
exclude-result-prefixes="f wf a wiki rdf rdfs" version="1.0">
  <x:param name="format"/>
  <x:param name="contents"/>
  <x:template match="/">
    <x:variable name='frameid' select="wf:assign-metadata('frameid', 'previewFrame')" /> <!-- used by iframe-display-handler -->    
        <x:choose>
          <x:when test="$format='http://rx4rdf.sf.net/ns/wiki#item-format-zml'">
            <!-- we add this PI in case the ZML contains a raccoon-format instruction - we want to suppress that in preview -->
            <x:processing-instruction name="raccoon-ignore" />            
            <x:value-of disable-output-escaping="yes" select="wf:get-zml($contents)"/>
          </x:when>
          <x:otherwise>You can only preview content in the ZML format </x:otherwise>
        </x:choose>
  </x:template>
</x:stylesheet>

