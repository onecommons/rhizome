<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:wf='http://rx4rdf.sf.net/ns/racoon/xpath-ext#'
        xmlns:f = 'http://xmlns.4suite.org/ext'
        xmlns:response-header='http://rx4rdf.sf.net/ns/racoon/http-response-header#'
        xmlns:previous = 'http://rx4rdf.sf.net/ns/racoon/previous#'
        xmlns:session = 'http://rx4rdf.sf.net/ns/racoon/session#'
        exclude-result-prefixes = "f wf a wiki rdf response-header previous session" >		
    <xsl:param name="_contents" />		
    <xsl:param name="previous:title" />		
    <xsl:param name="_name" />		
    <xsl:param name="_prevnode" />		    
    <xsl:param name="session:login" />
    <xsl:param name="session:message" />
    <xsl:param name="_url" />		 
    <xsl:param name="response-header:content-type"/>
    
    <xsl:output method='html' indent='no' />
    
<xsl:template match="/">
<!-- this page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />
<xsl:variable name='title' select="f:if($previous:title, $previous:title, f:if($_prevnode/wiki:title, $_prevnode/wiki:title, $_name) )" />
<!-- html template based on http://www.projectseven.com/tutorials/css_t/example.htm 
    (well, not much anymore, gave up and started using nested tables)
-->
<html>
<head>
<title><xsl:value-of select="$title" /></title>
<link href="basestyles.css" rel="stylesheet" type="text/css" />
<link rel="icon" href="favicon.ico" />
</head>
<body id="bd">

<!-- Main Layout Table -->
<table align="center" cellpadding="0" cellspacing="0" id="mainTable">
<tr>
<!-- Header -->
<td id="header" width="100%" colspan="2">
<div style='float: right'> 
         <xsl:choose>
            <xsl:when test="$session:login">
Welcome <xsl:value-of select="$session:login" />
<form action='logout' method='POST' >
<input TYPE="hidden" NAME="redirect" value="{$_url}" />
<input type="submit" value="logout" name="logout"/>    
</form>            
            </xsl:when>
            <xsl:otherwise>
Login&#xa0;
<form action='login' method='POST' >
<input TYPE="text" NAME="loginname" />
<input TYPE="password" NAME="password" />
<input TYPE="hidden" NAME="redirect" value="{$_url}" />
<input type="submit" value="login" name="login"/>    
</form>            
<br />Or <a href="users-guest?action=new">signup</a>
           </xsl:otherwise>
        </xsl:choose>
<xsl:value-of select="$session:message" disable-output-escaping='yes' />
</div>    
<a href="index"><img border="0" src="{/*[wiki:name='site-template']/wiki:header-image}" /></a><xsl:value-of disable-output-escaping='yes' select="/*[wiki:name='site-template']/wiki:header-text" />
</td>
</tr>

<tr  id="titlerow">
<!-- Sidebar -->
<td id="sidebar" height="400" width="120" >
    <table width="150" height="100%" cellpadding = "0" cellspacing="20">
    <tr>
    <td valign="top">
    <xsl:value-of disable-output-escaping='yes' select="wf:openurl('site://sidebar')" />
    </td>
    </tr>

    <tr>
    <td valign="bottom">
    <a href='http://rx4rdf.sf.net'><img width='100' height='33' style="padding: 0px" src='rhizome.gif' alt='Powered by Rhizome' /></a>
    </td>
    </tr>
    </table>
</td>

<td id='contentTableCell' width="75%" cellpadding="0" cellspacing="0" padding='0'>
    <!-- nested table -->
    <table id='contentTable' height="100%" width="100%">
    <!-- title bar -->
    <tr>
    <td valign="top" height='1' id="titlebar">
    <xsl:value-of select="$title" />
    </td>
    </tr>

    <!-- Main Content -->
    <tr>
    <td valign="top" id="maincontent">
         <xsl:choose>
            <xsl:when test="$response-header:content-type='text/plain' or $_prevnode/a:contents/a:ContentTransform/a:transformed-by = 'http://rx4rdf.sf.net/ns/wiki#item-format-text'">
            <pre>
            <xsl:value-of disable-output-escaping='no' select="$_contents" />
            </pre>
            </xsl:when>
            <xsl:otherwise>
            <xsl:value-of disable-output-escaping='yes' select="$_contents" />
            </xsl:otherwise>
        </xsl:choose>

    </td>
    </tr>
    </table>
</td>
</tr>
<!-- Footer -->
<tr>
<td id="footer" width="100%" colspan="2">
<p>
<div style='float: right'><a href="edit">New</a>&#xa0;<a href="list?type=all">List</a></div>

<a href="{$_name}">View</a>&#xa0;<a href="{$_name}?action=edit">Edit</a>&#xa0;<a href="{$_name}?action=showrevisions">Revisions</a>
&#xa0;<a href="{$_name}?action=edit-metadata">Metadata</a>&#xa0;<a href="{$_name}?action=confirm-delete">Delete</a>
</p><p>       
<form action='search'>

      Search <input TYPE="text" NAME="search" VALUE="" SIZE="60" />
Type<select name="searchType">
    <option value="simple" selected='selected'>Simple</option>
    <option value="rxpath" >RxPath</option>
    <option value="regex" >Regex</option>
    </select>
&#xa0;View<select name="view">
    <option value="html" selected='selected'>HTML</option>
    <option value="rss91" >RSS .91</option>
    </select>
&#xa0;<input type="submit" value="search" name="Search"/>    

</form></p>
</td>
</tr>
</table>
<xsl:comment>(c) 2003 by Adam Souzis (asouzis@users.sourceforge.net) All rights reserved</xsl:comment>
</body>
</html>
    
</xsl:template>
</xsl:stylesheet>