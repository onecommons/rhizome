<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/racoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:response-header = 'http://rx4rdf.sf.net/ns/racoon/http-response-header#'
		exclude-result-prefixes = "rdfs f wf a wiki rdf response-header" >		

<xsl:output omit-xml-declaration='yes' indent='no' />
<xsl:param name="_name" />
<xsl:param name="_resource" />

<!-- this edit page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />
<xsl:variable name='item' select="$_resource" />
<xsl:variable name='revision' select="($item/wiki:revisions/*/rdf:first/*)[last()]" />
<xsl:variable name='transforms' select="$revision//a:contents/*" />	

<xsl:template match="/" >
<form METHOD="POST" ACTION="{$_name}" ENCTYPE="multipart/form-data">	
    <input TYPE="hidden" NAME="itemname" VALUE="{$_name}" />
    <input TYPE="hidden" NAME="action" VALUE="save-metadata" />    
	<input TYPE="hidden" NAME="about" VALUE="{$item}" />
        <input TYPE="hidden" NAME="about" VALUE="{$revision}" />
        <xsl:for-each select="$transforms">
        	<input TYPE="hidden" NAME="about" VALUE="{.}" />
        </xsl:for-each>
        Edit Metadata
         <br/>
	<textarea NAME="metadata" ROWS="30" COLS="75" STYLE="width:100%" WRAP="off">
	<xsl:value-of select="wf:get-rdf-as-rhizml($item | $revision | $transforms)" />
	</textarea>
	<br/>
	<input TYPE="submit" NAME="save" VALUE="Save" />
	
</form>
</xsl:template>
</xsl:stylesheet>