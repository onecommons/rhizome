<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:previous = 'http://rx4rdf.sf.net/ns/raccoon/previous#' 
		exclude-result-prefixes = "rdfs f wf a wiki rdf previous" >		
<xsl:param name='previous:about' />
<xsl:param name='_name' />
<!-- for process-contents.xsl: -->
<xsl:param name="previous:contents" />
<xsl:param name="previous:file" />
<xsl:param name="previous:format" />
<xsl:output omit-xml-declaration='yes' encoding="UTF-8" indent='no' />

<xsl:template match="/" >
Error: You have attempted to view a XSLT page without specifying the content source to transform. Mostly likely you've tried to directly view a page that is designed to be used as template or document converter. Otherwise:
<ul>
<li>If the page isn't designed to transform a content source, edit the page and change the Source Format to RxSLT.</li>
<li>Or you can enter the source content here:</li>
</ul>

<form method="POST" action="site:///{$_name}{f:if($previous:about,concat('?about=', $previous:about))}" accept-charset='UTF-8' enctype="multipart/form-data">	         
	<textarea name="_contents" rows="30" cols="75" style="width:100%" wrap="off">
	<xsl:text> </xsl:text>
	</textarea>
	<input TYPE="hidden" name='contents' value='{$previous:contents}' />
	<input TYPE="hidden" name='file' value='{$previous:file}' />
	<input TYPE="hidden" name='format' value='{$previous:format}' />
	<input TYPE="submit" value='Run XSLT' />
</form>
</xsl:template>
</xsl:stylesheet>