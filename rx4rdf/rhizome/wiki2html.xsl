<x:stylesheet version="1.0" xmlns:x="http://www.w3.org/1999/XSL/Transform" 
xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" 
xmlns:f="http://xmlns.4suite.org/ext" 
xmlns:previous = 'http://rx4rdf.sf.net/ns/raccoon/previous#'
exclude-result-prefixes="previous f wf">
<!--
note: this template is only called if the 'wiki' doctype is set. 
As an optimization it only set when one of these config options are set: 
'undefinedPageIndicator', 'externalLinkIndicator', 'interWikiLinkIndicator'
 (see rhizome.processZMLSideEffects() )
-->
<x:output method='html' encoding="UTF-8" indent='no' />

<x:template match='a'>
<!--
if not found
    text<a copy-attributes>?</a>
otherwise
    <a copy-attributes><img>text</a>
-->
    <x:choose>
    <x:when test='@undefined and not(wf:has-page(@href))'>        
        <a>
        <x:copy-of select="@node()[.!='IgnorableMetadata']" />
        <x:apply-templates/>?</a>
    </x:when>
    
    <x:otherwise>
      <a>
      <x:copy-of select="@node()[.!='IgnorableMetadata']" />
      <x:choose>
        <x:when test='@interwiki'>
        <img border='0' src='site:///moin-inter.png'/>
        </x:when>
        
        <x:when test='@external'>
        <img border='0' src='site:///moin-www.png'/>
        </x:when>
      </x:choose>
      <x:apply-templates />
      </a>
    </x:otherwise>
    </x:choose>    
</x:template>

<x:template match="node()|@*">
    <x:copy>
        <x:apply-templates select="node()|@*"/>
    </x:copy>
</x:template>

</x:stylesheet>