<?xml version="1.0" encoding="ISO-8859-1"?>
<!-- this page is just a redirect to the site-template's default theme
  (we need this page because xsl:import's href must be a string not an
  attribute value template)
-->  
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:response-header='http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
		exclude-result-prefixes = "f wf a wiki rdf" >
<!-- we need these params so that 
they appear in the context passed to wf:request -->
    <xsl:param name="__account" />		
    <xsl:param name="__accountTokens" />		
  
<xsl:output method='text'/> <!-- just output the raw results of the template -->

<xsl:template match="/">

<xsl:value-of disable-output-escaping='yes' 
  select="wf:request(/*[wiki:name='site-template']
  /wiki:uses-theme/*/wiki:uses-site-template-stylesheet/*/wiki:name, 
  'action', 'view-source')" />
  
</xsl:template>        

</xsl:stylesheet>

