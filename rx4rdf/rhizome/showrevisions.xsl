<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
        xmlns:f='http://xmlns.4suite.org/ext'
        xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
        exclude-result-prefixes = "a wiki rdf rdfs f wf" 
        >
<xsl:param name="_name" />
<xsl:param name="__resource" />

<xsl:template match="/">
    <div class="title">All revisions for <xsl:value-of select='$_name'/></div>
    <br />
    <form name="diff" METHOD="GET" ACTION="site:///diff-revisions" ENCTYPE="multipart/form-data">
    <table>
    <tr><th>Revision </th><th>Created On</th><th>By</th><th>Label</th><th>Minor Edit?</th><th>Comments</th></tr> 
    <xsl:for-each select="$__resource/wiki:revisions/*/rdf:first/*">
        <tr><td><input TYPE="checkbox" NAME="rev" VALUE="{position()}" />
                <a href="site:///{$_name}?revision={position()}" ><xsl:value-of select='position()'/></a></td>
            <td><xsl:value-of select='wf:format-pytime( a:created-on, "%a, %d %b %Y %H:%M")'/></td>
            <td>
            <xsl:choose>
             <xsl:when test="wiki:created-by/*[wiki:login-name = 'guest'] and wiki:created-from">
                <xsl:value-of select='wiki:created-from'/>
            </xsl:when>
            <xsl:otherwise>
                <a href='site:///users/{wiki:created-by/*/wiki:login-name}'><xsl:value-of select='wiki:created-by/*/wiki:login-name'/></a>
            </xsl:otherwise>
            </xsl:choose>
            </td>
            <td><xsl:value-of select='wiki:has-label/*/rdfs:label'/></td>
            <td><xsl:if test='wiki:minor-edit'>Yes</xsl:if></td>
            <td><xsl:value-of select='rdfs:comment'/></td>
        </tr>        
    </xsl:for-each>
    </table>
    <input TYPE="HIDDEN" name="name" value="{$_name}" />	
    <input TYPE="SUBMIT" name="diff"  VALUE="diff" />	
    </form>
</xsl:template>
</xsl:stylesheet>