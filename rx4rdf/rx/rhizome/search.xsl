<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/racoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:response-header = 'http://rx4rdf.sf.net/ns/racoon/http-response-header#'
		exclude-result-prefixes = "rdfs f wf a wiki rdf response-header" >

<xsl:param name="search" />
<xsl:param name="view" />
<xsl:param name="searchType" />
<xsl:param name="_base-url" />
<xsl:param name="_url" />
<xsl:param name="ROOT_PATH" />

<xsl:variable name="searchExp">     
     <xsl:choose>
        <xsl:when test="$searchType='simple'">        
             /a:NamedContent[.//a:transformed-by !='http://rx4rdf.sf.net/ns/wiki#item-format-binary'][contains( wf:openurl(.//a:contents/a:ContentLocation),$search)]  | 
            /a:NamedContent[.//a:contents/text()[contains(.,$search)]] | /a:NamedContent[.//wiki:title/text()[contains(.,$search)]]
        </xsl:when>
        <xsl:when test="$searchType='regex'">                
            /a:NamedContent[.//a:transformed-by !='http://rx4rdf.sf.net/ns/wiki#item-format-binary'][f:match( wf:openurl(.//a:contents/a:ContentLocation),$search)]  | 
            /a:NamedContent[.//a:contents/text()[f:match(.,$search)]] | /a:NamedContent[.//wiki:title/text()[f:match(.,$search)]]
         </xsl:when>
         <!-- rxpath -->
        <xsl:otherwise> 
            f:evaluate($search)
        </xsl:otherwise>
    </xsl:choose> 
</xsl:variable>

<xsl:template match="/" >
<!-- search result header -->
     <xsl:choose>
     <xsl:when test="starts-with($view,'rss')">
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'application/xml')" />        
<rss version="0.91">
<channel>
<title>Rhizome search for "<xsl:value-of select="$search" />"</title>

<description>
This RSS feed is the result of applying this query <xsl:value-of select="$search" /> 
on <xsl:value-of select="$_base-url" />
</description>

<link><xsl:value-of select="$_url" /></link>

<xsl:for-each select="f:evaluate($searchExp)">
    <item>
       <title><xsl:value-of select="./wiki:name" /></title>
       <link>
       <!-- replace with link fixup extension function when completed -->   
       <xsl:value-of select="$_base-url" /><xsl:value-of select="./wiki:name" />
       </link>
    </item>
</xsl:for-each>    
    </channel>
</rss>
       </xsl:when>
       <xsl:otherwise>  
<xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-entry'])" />
<div class="title">Search Results for "<xsl:value-of select="$search" />"</div>
<br />   
<table>
<xsl:for-each select="f:evaluate($searchExp)">
<tr><td><a href="{./wiki:name/text()}?action=edit" ><img border="0" src='edit-icon.png' /></a></td>
<td><a href="{./wiki:name/text()}" ><xsl:value-of select='./wiki:name/text()' /></a></td>
</tr>        
</xsl:for-each>    
</table>
      </xsl:otherwise>
      </xsl:choose> 

</xsl:template>
</xsl:stylesheet>