<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/racoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		exclude-result-prefixes = "f wf a wiki rdf" >
<xsl:import href="search.xsl" />
<xsl:param name="__resource" />
<xsl:param name="search" select="'/wiki:Folder[.=$__resource]/wiki:has-child/*'" />
<xsl:param name="view" select="'html'"/>
<xsl:param name="searchType" select="'rxpath'"/>
<xsl:param name="title" select="wf:assign-metadata('title', concat('Directory of ', /wiki:Folder[.=$__resource]/wiki:name))"/>
</xsl:stylesheet>