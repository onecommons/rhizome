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

<xsl:output method='xhtml' omit-xml-declaration='yes' indent='no' encoding="UTF-8" />
<xsl:param name="fromFormat" select="'http://rx4rdf.sf.net/ns/wiki#rdfformat-rxml_zml'" />
<xsl:param name="toFormat" select="'http://rx4rdf.sf.net/ns/wiki#rdfformat-rdfxml'" />

<xsl:template name="add-option" >
<xsl:param name="text" />
<xsl:param name="value" />
<xsl:param name="selected" />
	<option value="{$value}">
	<xsl:if test='$selected'>
		<xsl:attribute name='selected'>selected</xsl:attribute>
	</xsl:if>
	<xsl:value-of select='$text' />
	</option>
</xsl:template>

<xsl:template match="/" >
<form method="POST" action="site:///process-rdfsandbox" target='results' accept-charset='UTF-8' enctype="multipart/form-data">	         
	<textarea name="contents" rows="20" COLS="75" style="width:100%" wrap="off">
	<xsl:text>
#a generic RxML template 
prefixes:
 wiki: `http://rx4rdf.sf.net/ns/wiki#
 a: `http://rx4rdf.sf.net/ns/archive#
 bnode: `bnode:
 default-ns: `http://rx4rdf.sf.net/ns/rxml#
 rdf: `http://www.w3.org/1999/02/22-rdf-syntax-ns#
 rdfs: `http://www.w3.org/2000/01/rdf-schema#
 auth: `http://rx4rdf.sf.net/ns/auth#
	
	</xsl:text>
	</textarea>
	<br/>
Convert from:
<select name="fromFormat" size="1" width="100">
<xsl:for-each select="/wiki:RDFFormat[wiki:can-parse]">
    <xsl:call-template name="add-option" >
        <xsl:with-param name="text" select="rdfs:label" />
        <xsl:with-param name="value" select="." />
        <xsl:with-param name="selected" select=". = $fromFormat" />
    </xsl:call-template>
</xsl:for-each>
</select>
to:
<select name="toFormat" size="1" width="100">
<xsl:for-each select="/wiki:RDFFormat[wiki:can-serialize]">
    <xsl:call-template name="add-option" >
        <xsl:with-param name="text" select="rdfs:label" />
        <xsl:with-param name="value" select="." />
        <xsl:with-param name="selected" select=". = $toFormat" />
    </xsl:call-template>    
</xsl:for-each>	
</select>

<input TYPE="submit" NAME="convert" VALUE="Convert" />

</form>

<h4>Results:</h4>
<iframe src='' name='results' width='100%' height='300px'/>

<div class="code" style='font-size: smaller'>
<p align='center'><b><a href="site:///RxML">RxML</a> Quick Reference</b></p>
<xsl:value-of disable-output-escaping='yes' 
  select="wf:openurl('site:///RxML?_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-complete')" />
</div>
</xsl:template>
</xsl:stylesheet>