<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		exclude-result-prefixes = "f wf a wiki rdf" >
<xsl:import href="edit.xsl" />
<xsl:param name="_name" />

<xsl:template match="/">
	<div>"<xsl:value-of select='$_name'/>" Not Found - Create New Item?</div>
	<xsl:call-template name="edit-main" >
		<xsl:with-param name="itemname" select="$_name" />
	</xsl:call-template>
	<!-- override title -->
	<xsl:variable name='title' select="wf:assign-metadata('title', concat($_name,' Not Found'))" />
</xsl:template>        

</xsl:stylesheet>