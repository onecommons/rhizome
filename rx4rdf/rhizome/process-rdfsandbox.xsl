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

<xsl:output method='text' />
<xsl:param name="contents" />
<xsl:param name="fromFormat" />
<xsl:param name="toFormat" />

<xsl:template match="/" >
<!--
<xsl:variable name='_nextFormat' select="wf:assign-metadata('_nextFormat', 'http://rx4rdf.sf.net/ns/wiki#item-format-text')" />
-->
<!-- hack: we want plain text output, setting _noErrorHandling will generate a plain text error stack -->
<xsl:variable name='_noErrorHandling' select="wf:assign-metadata('_noErrorHandling', true())" />
<xsl:value-of disable-output-escaping='yes' 
   select="wf:serialize-rdf(wf:parse-rdf($contents, $fromFormat), $toFormat)"/>      
</xsl:template>
</xsl:stylesheet>