<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
        xmlns:f = 'http://xmlns.4suite.org/ext'
        xmlns:response-header='http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
        exclude-result-prefixes = "f wf a wiki rdf response-header" >		
    <xsl:param name="_contents" />		
    <xsl:param name="_previousContext" />		        
    <xsl:param name="response-header:content-type"/>    

    <xsl:output method='html' indent='no' />
    
<xsl:template match="/">

<xsl:variable name='prev-content-type' select="$response-header:content-type" />

<html>
<head>
<!-- we could have a different stylesheet for printing -->
<link href="site:///basestyles.css" rel="stylesheet" type="text/css" />

<script>
function wPrint() {if (window.print) window.print();}

window.onload = wPrint;
</script>
</head>
<body>
         <xsl:choose>
         <xsl:when test="contains($prev-content-type,'xml')
                      or starts-with($prev-content-type,'text/html')">
            <xsl:value-of disable-output-escaping='yes' select="$_contents" />
         </xsl:when>
         <xsl:otherwise>
            <pre>
            <xsl:value-of disable-output-escaping='no' select="$_contents" />
            </pre>
         </xsl:otherwise>
        </xsl:choose>
</body>
</html>
    
</xsl:template>
</xsl:stylesheet>

