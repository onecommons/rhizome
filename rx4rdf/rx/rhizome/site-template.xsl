<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:wf='http://rx4rdf.sf.net/ns/racoon/xpath-ext#'
        xmlns:f = 'http://xmlns.4suite.org/ext'
        exclude-result-prefixes = "f wf a wiki rdf" >		
    <xsl:param name="_contents" />		
    <xsl:param name="title" />		
    <xsl:param name="_name" />		
    <xsl:param name="_prevnode" />		    
    <xsl:output method='html' indent='no' />
<xsl:template match="/">
<!-- html template based on http://www.projectseven.com/tutorials/css_t/example.htm -->
<html lang="en">
<head>
<title><xsl:value-of select="f:if($title, $title, $_name)" /></title>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<link href="basestyles.css" rel="stylesheet" type="text/css" />
<link rel="icon" href="favicon.ico" />
</head>
<body id="bd">

<!-- Main Layout Table -->
<table align="center" cellpadding="0" cellspacing="0" id="mainTable">
<tr>
<!-- Header -->
<td id="header" width="100%" colspan="2">
    <p>
<a href="index"><img border="0" src="underconstruction.gif" /></a> Header, site title goes here: edit the<a href="site-template?action=edit">site template</a>
    </p>
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
    <xsl:value-of select="f:if($title, $title, $_name)" />
    </td>
    </tr>

    <!-- Main Content -->
    <tr>
    <td valign="top" id="maincontent">
         <xsl:choose>
            <xsl:when test="$_prevnode/a:contents/a:ContentTransform/a:transformed-by = 'http://rx4rdf.sf.net/ns/wiki#item-format-text'">
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
&#xa0;<a href="{$_name}?action=edit-metadata">Metadata</a>&#xa0;<a href="{$_name}?action=delete">Delete</a>
</p><p>       
<form action='search'>

      Search <input TYPE="text" NAME="search" VALUE="" SIZE="60" />
Type<select name="searchType">
    <option value="simple" selected='selected'>Simple</option>
    <option value="rxpath" >RxPath</option>
    <option value="regex" >Regex</option>
    </select>
&#xa0;View<select name="view">
    <option value="compact" selected='selected'>Compact</option>
    <option value="long" >Long</option>
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