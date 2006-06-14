<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
        xmlns:f='http://xmlns.4suite.org/ext'
        xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'        
        xmlns:response-header = 'http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
        xmlns:foaf="http://xmlns.com/foaf/0.1/"
        exclude-result-prefixes = "a wiki foaf rdf rdfs f wf response-header" 
        >
<xsl:output omit-xml-declaration='yes' indent='no' />
<xsl:param name="_name" />
<xsl:param name="__resource" />

<!-- this page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />	

<xsl:template match="/">
    <xsl:variable name='_robots' select="wf:assign-metadata('_robots', 'nofollow,noindex')" />
    
    <xsl:variable name='resName' select="f:if($__resource/wiki:name, $__resource/wiki:name, 
        f:if($__resource/rdfs:label, $__resource/rdfs:label, name-from-uri($__resource) ))" />
    
    <div class="title">All revisions for resource <b><xsl:value-of select='$resName'/></b></div>
    <br />
    <form name="diff" METHOD="GET" ACTION="site:///diff-revisions" ENCTYPE="multipart/form-data">
    <table>
    <tr><th>Revision </th><th>Created On</th><th>By</th><th>Label</th><th>Minor Edit?</th><th>Comments</th></tr> 
    <xsl:for-each select="get-revision-contexts-for-subject($__resource)">
        <tr><td> <input TYPE="checkbox" NAME="rev" VALUE="{position()}" />
                <a href="site:///{$__resource/wiki:name}?action=view-metadata&amp;about={f:escape-url($__resource)}&amp;revnum={position()}" ><xsl:value-of select='position()'/></a></td>
            <td><xsl:value-of select='wf:format-pytime( a:created-on, "%a, %d %b %Y %H:%M")'/></td>
            <td>
            <xsl:choose>
             <xsl:when test="wiki:created-by/*[foaf:accountName = 'guest'] and wiki:created-from">
                <xsl:value-of select='wiki:created-from'/>
            </xsl:when>
            <xsl:otherwise>
                <a href='site:///accounts/{wiki:created-by/*/foaf:accountName}'><xsl:value-of select='wiki:created-by/*/foaf:accountName'/></a>
            </xsl:otherwise>
            </xsl:choose>
            </td>
            <td><xsl:value-of select='wiki:has-label/*/rdfs:label'/></td>
            <td><xsl:if test='wiki:minor-edit'>Yes</xsl:if></td>
            <td><xsl:value-of select='rdfs:comment'/></td>
        </tr>        
    </xsl:for-each>
    </table>
    <input TYPE="HIDDEN" name="revres" value="{$__resource}" />
    Diff:	
    <input TYPE="SUBMIT" name="diff"  VALUE="Side By Side" />	
    &#xa0;<input TYPE="SUBMIT" name="diff"  VALUE="Context" />	    
    &#xa0;<label for="context">Number of context lines </label><input TYPE="text" NAME="context" VALUE="5" SIZE="1" MAXLENGTH="3" />	    
    </form>

</xsl:template>
</xsl:stylesheet>