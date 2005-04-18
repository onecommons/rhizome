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

<!-- this template references templates in site-template.xsl and assumes it is imported by it -->
<xsl:template name="theme-body" >

<body id='bd'>

<div id='container'>

<div id="banner">
<xsl:value-of disable-output-escaping='yes' select="/*[wiki:name='site-template']/wiki:header-text" />
</div>

<div id="pagebody">

<div id="left">

<div class="sidebar">
<xsl:value-of disable-output-escaping='yes' select="wf:openurl('site:///sidebar')" />

</div> <!-- /sidebar -->
</div> <!-- /left -->

<div id="center">

<xsl:call-template name="actions-bar" >
</xsl:call-template>         	

<div class="content">
<h3><xsl:value-of select="$title" /></h3>
<xsl:call-template name="display-content" >
</xsl:call-template>    
</div>

<br/>

<xsl:call-template name="search-form" >
<xsl:with-param name="edit-width" select="20" />
</xsl:call-template>    
<xsl:call-template name="quicklinks-bar" >
</xsl:call-template>    

</div>

<div id="right">
    <div class="sidebar">
    
    <xsl:call-template name="login-form" >
    </xsl:call-template>         	
   
    <h2>Recent Posts</h2>
    <xsl:call-template name="recent-items" >
    </xsl:call-template>    
    
    </div>
</div>

</div> <!-- pagebody -->

<div style="clear: both;">&#160;</div>
</div> <!-- container -->

</body>

</xsl:template>
</xsl:stylesheet>