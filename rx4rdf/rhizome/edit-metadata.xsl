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

<xsl:output omit-xml-declaration='yes' encoding="UTF-8" indent='no' />
<xsl:param name="_name" />
<xsl:param name="__resource" />

<!-- this edit page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />

<xsl:variable name='revision' select="($__resource/wiki:revisions/*/rdf:first/*)[last()]" />
<xsl:variable name='transforms' select="$revision//a:contents/*" />	

<xsl:template match="/" >
<form METHOD="POST" ACTION="site:///{$_name}" accept-charset='UTF-8' ENCTYPE="multipart/form-data">	
    <input TYPE="hidden" NAME="itemname" VALUE="{$_name}" />
    <input type="hidden" name="about" value="{$__resource}"/>
    <input TYPE="hidden" NAME="action" VALUE="save-metadata" />    
	<input TYPE="hidden" NAME="resource" VALUE="{$__resource}" />
    <input TYPE="hidden" NAME="resource" VALUE="{$revision}" />
    <xsl:for-each select="$transforms">
        	<input TYPE="hidden" NAME="resource" VALUE="{.}" />
    </xsl:for-each>
        Edit Metadata
         <br/>
	<textarea NAME="metadata" ROWS="20" COLS="75" STYLE="width:100%" WRAP="off">
	<xsl:value-of select="wf:get-rdf-as-rxml($__resource | $revision | $transforms)" />
	</textarea>
	<br/>
	<input TYPE="submit" NAME="save" VALUE="Save" />
	
</form>

<div class="code" style='font-size: smaller'>
<p align='center'><b><a href="site:///RxML">RxML</a> Quick Reference</b></p>
<xsl:value-of disable-output-escaping='yes' 
  select="wf:openurl('site:///RxML?_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-complete')" />
</div>
</xsl:template>
</xsl:stylesheet>