<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
        xmlns:xf='http://xmlns.4suite.org/ext'
        exclude-result-prefixes = "a wiki rdf" 
        >
<xsl:param name="_name" />
<xsl:param name="__resource" />

<xsl:template match="/">
    <div class="title">All revisions for <xsl:value-of select='$_name'/></div>
    <br />
    <table>
    <tr><th>Revision </th><th>Created On</th><th>By</th><th>Label</th><th>Minor Edit?</th></tr> 
    <xsl:for-each select="$__resource/wiki:revisions/*/rdf:first/*">
        <tr><td><a href="site:///{$_name}?revision={position()}" ><xsl:value-of select='position()'/></a></td>
            <td><xsl:value-of select='xf:pytime-to-exslt(a:created-on/text())'/></td>
            <td><a href='site:///users/{wiki:created-by/*/wiki:login-name}'><xsl:value-of select='wiki:created-by/*/wiki:login-name'/></a></td>
            <td><xsl:value-of select='wiki:has-label/*/rdfs:label'/></td>
            <td><xsl:if test='wiki:minor-edit'>Yes</xsl:if></td>
        </tr>        
    </xsl:for-each>
    </table>
</xsl:template>
</xsl:stylesheet>