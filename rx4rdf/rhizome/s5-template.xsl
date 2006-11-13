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
    <xsl:param name="_name" />		
    <xsl:param name="previous:title" />	
    <xsl:param name="previous:_template" />
    <xsl:param name="previous:__resource" />
    <xsl:param name="_originalContext" /> <!-- this will be the resource's revision -->

<xsl:output method='xhtml' omit-xml-declaration="yes" encoding="UTF-8" indent='yes' 
doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" 
doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd" 
/>

<xsl:variable name='title' select="f:if($previous:title, $previous:title, $_originalContext/wiki:title)" />

<xsl:template match="/">
<html>
<head>
<title><xsl:value-of select="f:if($title, $title, $_name)" /></title>
<!-- metadata -->
<meta name="generator" content="S5" />
<meta name="version" content="S5 1.1" />

<!-- style sheet links -->
<link href="site:///basestyles.css" rel="stylesheet" type="text/css" />
<link rel="stylesheet" href="s5/ui/default/slides.css" type="text/css" media="projection" id="slideProj" />
<link rel="stylesheet" href="s5/ui/default/outline.css" type="text/css" media="screen" id="outlineStyle" />
<link rel="stylesheet" href="s5/ui/default/print.css" type="text/css" media="print" id="slidePrint" />
<link rel="stylesheet" href="s5/ui/default/opera.css" type="text/css" media="projection" id="operaFix" />
<!-- S5 JS -->
<script src="s5/ui/default/slides.js" type="text/javascript"></script>
</head>
<body>

<div class="layout">
<div id="controls"><!-- DO NOT EDIT --></div>
<div id="currentSlide"><!-- DO NOT EDIT --></div>
<div id="header">
    <xsl:variable name='header' select="f:if($previous:__resource/wiki:header-text, $previous:__resource/wiki:header-text, $previous:_template/wiki:header-text)" />
    <xsl:if test="$header">
        <h1><xsl:value-of disable-output-escaping='yes' select="$header"/></h1>
    </xsl:if>
</div>
<div id="footer">
    <xsl:if test="$title">
        <h1><xsl:value-of disable-output-escaping='yes' select="$title"/></h1>
    </xsl:if>
    
    <xsl:variable name='footer' select="f:if($previous:__resource/wiki:footer-text, $previous:__resource/wiki:footer-text, $previous:_template/wiki:footer-text)" />
    <xsl:if test="$footer">
        <h2><xsl:value-of disable-output-escaping='yes' select="$footer"/></h2>
    </xsl:if>
</div>
</div>

<div class="presentation">
<xsl:value-of disable-output-escaping='yes' select="$_contents" />
</div>

</body>
</html>
</xsl:template>
</xsl:stylesheet>