<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
        xmlns:f = 'http://xmlns.4suite.org/ext'
        xmlns:response-header='http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
        xmlns:previous = 'http://rx4rdf.sf.net/ns/raccoon/previous#'
        xmlns:session = 'http://rx4rdf.sf.net/ns/raccoon/session#'
        exclude-result-prefixes = "f wf a wiki rdf response-header previous session" >		
  
    <xsl:import href="site:///site-theme" /> 
    <xsl:param name="_contents" />		
    <xsl:param name="previous:title" />		

<xsl:output method='xhtml' omit-xml-declaration="yes" encoding="UTF-8" indent='yes' 
doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" 
doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd" 
/>

<xsl:template match="/">
<html>
<head>
<title><xsl:value-of select="$previous:title" /></title>
<!-- metadata -->
<meta name="generator" content="S5" />
<meta name="version" content="S5 1.1" />


<!-- style sheet links -->
<link href="site:///basestyles.css" rel="stylesheet" type="text/css" />
<link rel="stylesheet" href="ui/default/slides.css" type="text/css" media="projection" id="slideProj" />
<link rel="stylesheet" href="ui/default/outline.css" type="text/css" media="screen" id="outlineStyle" />
<link rel="stylesheet" href="ui/default/print.css" type="text/css" media="print" id="slidePrint" />
<link rel="stylesheet" href="ui/default/opera.css" type="text/css" media="projection" id="operaFix" />
<!-- S5 JS -->
<script src="ui/default/slides.js" type="text/javascript"></script>
</head>
<body>

<div class="layout">
<div id="controls"><!-- DO NOT EDIT --></div>
<div id="currentSlide"><!-- DO NOT EDIT --></div>
<div id="header"></div>
<div id="footer">
<h1>Rhizome</h1>
<h2>Adam Souzis &#8226; WWW2006</h2>
</div>
</div>

<div class="presentation">
<xsl:value-of disable-output-escaping='yes' select="$_contents" />
</div>

</body>
</html>
</xsl:template>
</xsl:stylesheet>