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
<xsl:param name="_contents" />		
<xsl:param name="BASE_MODEL_URI" />

<!-- this edit page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />	

<xsl:template match="/" >
<form METHOD="POST" ACTION="site:///{$_name}" ENCTYPE="multipart/form-data">	
    <input TYPE="hidden" NAME="action" VALUE="save-metadata" />    
    <input TYPE="hidden" NAME="itemname" VALUE="{$_name}" />
        Create New Resources from Template
         <br/>
	<textarea NAME="metadata" ROWS="30" COLS="75" STYLE="width:100%" WRAP="off">
	<xsl:value-of select="f:replace('%(base)s',$BASE_MODEL_URI,$_contents)" />
	</textarea>
	<br/>
	<input TYPE="submit" NAME="save" VALUE="Save" />
	
</form>
</xsl:template>
</xsl:stylesheet>