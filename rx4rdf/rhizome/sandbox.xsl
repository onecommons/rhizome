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

<xsl:output method='html' indent='no' />
<xsl:template match="/" >
<p>This page lets you execute content in Rhizome and see the results without having to save the content. </p>
<p>WARNING: even though the content isn't saved depending on the Source Format it may modify the system (e.g. using Python or RxUpdate).</p>
<p>Note: Resulting content is displayed without invoking any templates, so the resulting page may be blank (e.g. with RxUpdate).</p>
<form METHOD="POST" ACTION="site:///process-contents" ENCTYPE="multipart/form-data">	         
    Upload File:<input TYPE='file' name='file' /> OR enter text here:<br />
	<textarea NAME="contents" ROWS="25" COLS="75" STYLE="width:100%" WRAP="off" />
	Source Format:
	<select name="format" size="1" width="100">
        <xsl:for-each select="/wiki:ItemFormat">
            <xsl:variable name="i" select="./@rdf:about" />
        	<option value="{./@rdf:about}">
            <xsl:value-of select='rdfs:label/text()' />
            </option>            
     	</xsl:for-each>
	</select>
	<br/>
	<input TYPE="submit" NAME="process" VALUE="Execute" />
</form>
</xsl:template>
</xsl:stylesheet>