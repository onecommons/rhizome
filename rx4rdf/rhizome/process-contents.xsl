<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:response-header = 'http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
		exclude-result-prefixes = "rdfs f wf a wiki rdf response-header" >		

<xsl:output omit-xml-declaration='yes' indent='no' />
<xsl:param name="contents" />
<xsl:param name="file" />
<xsl:param name="format" />
<xsl:param name="__user"/>
<xsl:param name="_contents" />

<xsl:template match="/" >

<xsl:choose>
<xsl:when test='false()'>
    <xsl:value-of disable-output-escaping='yes' 
        select="wf:process-contents(f:if($file, $file, $contents), $format,'__user', $__user,'_contents', $_contents)" />
</xsl:when>

<xsl:otherwise>
    <xsl:value-of disable-output-escaping='yes' 
        select="wf:process-contents(f:if($file, $file, $contents), $format,'__user', $__user)" />
</xsl:otherwise>
</xsl:choose>

</xsl:template>
</xsl:stylesheet>