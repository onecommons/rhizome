<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:auth="http://rx4rdf.sf.net/ns/auth#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:response-header = 'http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
		exclude-result-prefixes = "rdfs f wf a wiki auth rdf response-header" >

<xsl:param name="search" />
<xsl:param name="view" />
<xsl:param name="searchType" />
<xsl:param name="_base-url" />
<xsl:param name="_url" />
<xsl:param name="_name" />

<xsl:variable name="searchExp">     
     <xsl:choose>
        <xsl:when test="$searchType='Simple'">                     
             /a:NamedContent[
                wiki:revisions/*/rdf:first/wiki:Item[
                    (.//a:contents/*/a:transformed-by !='http://rx4rdf.sf.net/ns/wiki#item-format-binary'
                    and contains( wf:get-contents(.), $search))
                    or contains(wiki:title,$search)] ] 
        </xsl:when>
        <xsl:when test="$searchType='RegEx'">   
             /a:NamedContent[
                wiki:revisions/*/rdf:first/wiki:Item[
                    (.//a:contents/*/a:transformed-by !='http://rx4rdf.sf.net/ns/wiki#item-format-binary'
                    and f:match( wf:get-contents(.), $search))
                    or f:match(wiki:title,$search)] ]
        </xsl:when>
         <!-- rxpath -->
        <xsl:otherwise> 
            f:evaluate($search)
        </xsl:otherwise>
    </xsl:choose> 
</xsl:variable>

<xsl:variable name="results" select="f:evaluate($searchExp)" />     

<xsl:template match="node()|@*" mode="dump">
<xsl:copy>
    <xsl:apply-templates select="node()|@*" mode="dump" />
</xsl:copy>
</xsl:template>
        
<xsl:template match="/" >
<!-- search result header -->
     <xsl:choose>
     <xsl:when test="starts-with($view,'rss')">
<xsl:variable name='content-type' select="wf:assign-metadata('_contenttype', 'application/xml')" />        
<rss version="0.91">
<channel>
<title>Rhizome search for "<xsl:value-of select="$search" />"</title>

<description>
This RSS feed is the result of applying the query "<xsl:value-of select="$search" />"
on <xsl:value-of select="$_base-url" />
</description>

<link><xsl:value-of select="$_url" /></link>

<xsl:for-each select="$results">
    <item>
       <xsl:variable name='relUrl' select="f:if(self::a:NamedContent, concat(./wiki:name, '?'), concat('.?about=', f:escape-url(.)))" />
       <title><xsl:value-of select="f:if(./wiki:name, ./wiki:name, f:if(./rdfs:label,./rdfs:label, name-from-uri(.)))" /></title>       
       <link>       
       <xsl:value-of select="$_base-url" />site:///<xsl:value-of select="$relUrl" />
       </link>
    </item>
</xsl:for-each>    
    </channel>
</rss>
       </xsl:when>       
       <xsl:when test="$view = 'rxml'">
<xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-entry'])" />       
<div class="title"><xsl:value-of select="$searchType" /> Search Results for "<xsl:value-of select="$search" />"</div>
<xsl:if test='not($results)'>
No results found.
</xsl:if>
<pre>
<xsl:variable name='fixup' select="&quot;&lt;a href='site:///.?action=view-metadata&amp;amp;about=%(encodeduri)s'>%(res)s&lt;/a>&quot;" />
<xsl:value-of disable-output-escaping='yes' select="wf:get-rdf-as-rxml($results, '', $fixup)" />
</pre>
       </xsl:when>
       <xsl:when test="$view = 'edit'">
<xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-entry'])" />       
<div class="title"><xsl:value-of select="$searchType" /> Search Results for "<xsl:value-of select="$search" />"</div>
<xsl:if test='not($results)'>
No results found.
</xsl:if>
<form METHOD="POST" ACTION="site:///save-metadata" ENCTYPE="multipart/form-data">	
    <input TYPE="hidden" NAME="itemname" VALUE="save-metadata" />
    <input TYPE="hidden" NAME="action" VALUE="save-metadata" />    
    <xsl:for-each select="$results">
        	<input TYPE="hidden" NAME="resource" VALUE="{.}" />
    </xsl:for-each>
        Edit Metadata
         <br/>
	<textarea NAME="metadata" ROWS="30" COLS="75" STYLE="width:100%" WRAP="off">
	<xsl:value-of select="wf:get-rdf-as-rxml($results)" />
	</textarea>
	<br/>
	<input TYPE="submit" NAME="save" VALUE="Save" />	
</form>
       </xsl:when>
       <xsl:when test="$view = 'rxpathdom'">
<RxPathDOM>       
<xsl:apply-templates select="$results" mode="dump" />
</RxPathDOM>       
       </xsl:when>       
       <xsl:otherwise>  
       
<xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-entry'])" />
<div class="title"><xsl:value-of select="$searchType" /> Search Results for "<xsl:value-of select="$search" />" 
  (<xsl:value-of select="count($results)" /> found)</div>
<br />   
<table>
    <xsl:variable name="properties-table" select="is-predicate($results[1])" />
    <xsl:variable name="long-table" select="$results[1][self::a:NamedContent]" />
    <xsl:if test='$long-table'>
        <tr><th></th><th>Name </th><th>Last Modified</th><th>By</th></tr> 
    </xsl:if>
    <xsl:if test='$properties-table'>
        <tr><th>Resource </th><th>Property</th><th>Value</th></tr> 
    </xsl:if>    
<xsl:for-each select="$results">
  <xsl:if test='not($properties-table)'>
    <xsl:variable name='relUrl' select="f:if(self::a:NamedContent, concat(./wiki:name, '?'), concat('.?about=', f:escape-url(.)))" />
    <xsl:variable name='resName' select="f:if(./wiki:name, ./wiki:name, f:if(./rdfs:label,./rdfs:label, name-from-uri(.)))" />
    
    <tr>
    <td><a href="site:///{$relUrl}&amp;action=edit" title='edit'><img border="0" alt='edit' src='site:///edit-icon.png' /></a></td>
    <td><a href="site:///{$relUrl}" ><xsl:value-of select='$resName' /></a></td>    
    <xsl:if test='$long-table'>
    <td><xsl:value-of select='f:pytime-to-exslt( (./wiki:revisions/*/rdf:first/*)[last()]/a:created-on)' /></td>
    <td><a href='site:///users/{(./wiki:revisions/*/rdf:first/*)[last()]/wiki:created-by/*/wiki:login-name}'>
        <xsl:value-of select='(./wiki:revisions/*/rdf:first/*)[last()]/wiki:created-by/*/wiki:login-name'/></a></td>    
    </xsl:if>
    <xsl:if test='not($long-table)'>    
    <td><a href='site:///search?search=%2F*%2F*%5B.%3D%27{f:escape-url(.)}%27%5D&amp;searchType=RxPath&amp;view=html'>Used By</a></td>        
    </xsl:if>
    </tr>        
  </xsl:if>    
  
  <xsl:if test='$properties-table'>        
    <xsl:variable name='subjectUrl' select="f:if(parent::a:NamedContent, concat(../wiki:name, '?'), concat('.?about=', f:escape-url(..)))" />
    <xsl:variable name='subjectName' select="f:if(../wiki:name, ../wiki:name, f:if(../rdfs:label,../rdfs:label, name-from-uri(..)))" />

    <xsl:variable name='predicateName' select="name(.)" />

    <xsl:variable name='isLiteral' select="boolean(text())" />
  
    <tr>    
    <td><a href="site:///{$subjectUrl}" ><xsl:value-of select='$subjectName' /></a></td>    

    <td><a href='site:///search?search=%2F*%2F*%5B%40uri%3D%27{f:escape-url(./@uri)}%27%5D&amp;searchType=RxPath&amp;view=html&amp;title=Property%20Usage'>
        <xsl:value-of select='$predicateName' /></a>
    </td>        
    
    <xsl:if test='$isLiteral'>        
        <td><xsl:value-of select='substring(text(),1,100)' /></td>    
    </xsl:if>        
    <xsl:if test='not($isLiteral)'>        
        <xsl:variable name='objectUrl' select="f:if(a:NamedContent, concat(wiki:name, '?'), concat('.?about=', f:escape-url(*)))" />
        <xsl:variable name='objectName' select="f:if(wiki:name,  wiki:name, f:if( rdfs:label, rdfs:label, name-from-uri(*)))" />        
        <td><a href="site:///{$objectUrl}" ><xsl:value-of select='$objectName' /></a></td>    
    </xsl:if>            
    </tr>        
  </xsl:if>    
</xsl:for-each>    
</table>
<xsl:if test='not($results)'>
No results found.
</xsl:if>


      </xsl:otherwise>
      </xsl:choose> 

</xsl:template>
</xsl:stylesheet>