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

<body id="bd">

<!-- Main Layout Table -->
<table align="center" cellpadding="0" cellspacing="0" id="mainTable">
<tr>
<!-- Header -->
<td id="header" width="100%" colspan="2">
<div id="login-box" > 
      	<xsl:call-template name="login-form" >
     	</xsl:call-template>         	
</div>    

<xsl:variable name='header-image' select="/*[wiki:name='site-template']/wiki:header-image"/>
<xsl:if test="$header-image">
<a href="index"><img height="45" border="0" src="site:///{/*[wiki:name='site-template']/wiki:header-image}" /></a> 
</xsl:if>
<xsl:value-of disable-output-escaping='yes' select="/*[wiki:name='site-template']/wiki:header-text" />
</td>
</tr>

<tr  id="titlerow"  >
<!-- Sidebar -->
<td id="sidebar" height="400" width="10" >
    <table width="100%" height="100%" cellpadding = "0" cellspacing="10">
    <tr>
    <td valign="top">
    <xsl:value-of disable-output-escaping='yes' select="wf:openurl(concat('site:///sidebar?_docpath=',$_path))" />
    </td>
    </tr>

    <tr>
    <td valign="bottom">
    <a href='http://rx4rdf.sf.net'><img width='100' height='33' style="padding: 0px" src='site:///rhizome.gif' alt='Powered by Rhizome' /></a>
    </td>
    </tr>
    </table>
</td>

<td id='contentTableCell' width="100%" cellpadding="0" cellspacing="0" padding='0'>
    <!-- nested table -->
    <table id='contentTable' cellpadding="0" cellspacing="0" padding='0' height="100%" width="100%">
    <!-- title bar -->
    <tr>
    <td valign="top" height='1' id="titlebar">
    <xsl:value-of select="$title" />
    </td>
    </tr>

    <!-- Main Content -->
    <tr>
    <td valign="top">        
      	<xsl:call-template name="display-content" >
     	</xsl:call-template>    
    </td>
    </tr>
    </table>
</td>
</tr>
<!-- Footer -->
<tr>
<td id="footer" width="100%" colspan="2">
<xsl:if test="not($_static)" >
<p>
<div style='float: right'>
    <xsl:call-template name='actions-bar' />    
</div>
&#xa0;<xsl:call-template name='quicklinks-bar' />    
</p>

<p>    
<xsl:call-template name='search-form' />    
</p>

</xsl:if>
</td>
</tr>
</table>
</body>

</xsl:template>
</xsl:stylesheet>