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
<xsl:template match="/" >
<p>Use this page to experiment with the RxML syntax. If you want to save your RxML, click <a href='site:///generic-new-template'>here</a> instead.</p>
<form METHOD="POST" ACTION="site:///rxml2rdf" ENCTYPE="multipart/form-data">	         
	<textarea NAME="rxmlAsZML" ROWS="25" COLS="75" STYLE="width:100%" WRAP="off">
	<xsl:text>
;a generic RxML template 
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
	<input TYPE="submit" NAME="convert" VALUE="Convert To RDF/XML" />&#xA0;<a href='site:///RxML'>RxML Help</a> 	
</form>
</xsl:template>
</xsl:stylesheet>