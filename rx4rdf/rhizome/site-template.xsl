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
    <xsl:param name="_contents" />		
    <xsl:param name="previous:title" />		
    <xsl:param name="_name" />		
    <xsl:param name="_orginalContext" />		    
    <xsl:param name="_previousContext" />		        
    <xsl:param name="session:login" />
    <xsl:param name="session:message" />
    <xsl:param name="_url" />		 
    <xsl:param name="response-header:content-type"/>    
    <xsl:param name="_static" />
    <xsl:param name="previous:about" />
    <xsl:param name="previous:itemname" />
    <xsl:param name="previous:search" />				
    <xsl:param name="previous:searchType" />				
    <xsl:output method='html' indent='no' />
    
<xsl:template match="/">
<xsl:variable name='prev-content-type' select="$response-header:content-type" />

<xsl:variable name='title' select="f:if($previous:title, $previous:title, f:if($_orginalContext/wiki:title, $_orginalContext/wiki:title, $_name) )" />

<!-- html template based on http://www.projectseven.com/tutorials/css_t/example.htm 
    (well, not much anymore, gave up and started using nested tables)
    
-->
<html>
<head>
<title><xsl:value-of select="$title" /></title>
<link href="site:///basestyles.css" rel="stylesheet" type="text/css" />
<xsl:if test="wf:file-exists('favicon.ico')"> <!-- performance hack (assumes favicon.ico is external) -->
  <link rel="icon" href="site:///favicon.ico" />
</xsl:if>
</head>
<body id="bd">

<!-- Main Layout Table -->
<table align="center" cellpadding="0" cellspacing="0" id="mainTable">
<tr>
<!-- Header -->
<td id="header" width="100%" colspan="2">
<div id="login-box" > 

<xsl:if test="not($_static)" >
         <xsl:choose>
            <xsl:when test="$session:login">
<form action='site:///logout' method='POST' >
Welcome <a href="site:///users/{$session:login}?action=edit"><xsl:value-of select="$session:login" /></a>
<input TYPE="hidden" NAME="redirect" value="{$_url}" />
<input type="submit" style="font-size: 100%" value="logout" name="logout"/>    
<br/><xsl:value-of select="$session:message" disable-output-escaping='yes' />
</form>            
            </xsl:when>
            <xsl:otherwise>
<form action='site:///login' method='POST' >
Name<input TYPE="text" NAME="loginname" style="font-size: 100%" SIZE="10" />
Password<input TYPE="password" NAME="password" style="font-size: 100%" SIZE="10" />
<input TYPE="hidden" NAME="redirect" value="{$_url}" />
<input type="submit" value="login" style="font-size: 100%" name="login"/>    
Or <a href="site:///users/guest?action=new">signup</a>
<br/><xsl:value-of select="$session:message" disable-output-escaping='yes' />
</form>            
           </xsl:otherwise>
        </xsl:choose>
</xsl:if>
</div>    

<a href="index"><img height="45" border="0" src="site:///{/*[wiki:name='site-template']/wiki:header-image}" /></a> 
<!-- <xsl:value-of disable-output-escaping='yes' select="/*[wiki:name='site-template']/wiki:header-text" />
-->
</td>
</tr>

<tr  id="titlerow"  >
<!-- Sidebar -->
<td id="sidebar" height="400" width="10" >
    <table width="100%" height="100%" cellpadding = "0" cellspacing="10">
    <tr>
    <td valign="top">
    <xsl:value-of disable-output-escaping='yes' select="wf:openurl(concat('site:///sidebar?_docpath=',$_name))" />
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
    <td valign="top" id="maincontent">        
         <xsl:choose>
         <xsl:when test="contains($prev-content-type,'xml')
                      or starts-with($prev-content-type,'text/html')">
            <xsl:value-of disable-output-escaping='yes' select="$_contents" />
         </xsl:when>         
         <!-- we never get this far for binary content because xslt.Processor._normalizeParams calls to_unicode on $_contents
         <xsl:when test="$_previousContext/a:contents/a:ContentTransform/a:transformed-by = 'http://rx4rdf.sf.net/ns/wiki#item-format-binary'">         
             <xsl:variable name='aboutparam' select="f:if($previous:about, concat('&amp;about=', f:escape-url($previous:about)), '')" />
            <iframe height='100%' width='100%' 
      href='site:///{$_name}?_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-complete{$aboutparam}' />
         </xsl:when>           
        -->         
         <xsl:otherwise>             
            <pre>
            <xsl:value-of disable-output-escaping='no' select="$_contents" />
            </pre>
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
<xsl:if test="not($_static)" >
<p>
<div style='float: right'>
    <a href="site:///edit">New</a>
    &#xa0;<a href="site:///search?search=%2F*%5Bwiki%3Aname%5D&amp;searchType=RxPath&amp;view=html&amp;title=All%20Pages">List</a>
    &#xa0;<a href="site:///search?search=wf%3Asort%28%2Fa%3ANamedContent%2C%27%28wiki%3Arevisions%2F*%2Frdf%3Afirst%2F*%29%5Blast%28%29%5D%2Fa%3Acreated-on%27%2C%27number%27%2C%27descending%27%29&amp;searchType=RxPath&amp;view=html&amp;title=Recently%20Changed%20Pages">Recent</a>
    &#xa0;<a href="site:///administration">Admin</a>
    &#xa0;<a href="site:///help">Help</a>
</div>
<xsl:variable name='aboutparam' select="f:if($previous:about, concat('&amp;about=', f:escape-url($previous:about)), '')" />
<xsl:variable name='path' select="f:if($previous:itemname, $previous:itemname, $_name)" />
<a href="site:///{$path}?{$aboutparam}">View</a>
&#xa0;<a href="site:///{$path}?action=edit{$aboutparam}">Edit</a>
&#xa0;<a href="site:///{$path}?action=showrevisions">Revisions</a>
&#xa0;<a href="site:///{$path}?action=view-metadata{$aboutparam}">Metadata</a>
&#xa0;<a href="site:///{$path}?action=confirm-delete{$aboutparam}">Delete</a>
&#xa0;<a href="site:///{$path}?_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-print{$aboutparam}">Print</a>
</p>
<p>       
<form action='site:///search'>

      Search <input TYPE="text" NAME="search" VALUE="{$previous:search}" SIZE="40" />
Type<select name="searchType">    
    <option value="Simple">
	<xsl:if test='not($previous:searchType) or $previous:searchType = "Simple"'>
		<xsl:attribute name='selected'>selected</xsl:attribute>
	</xsl:if>    
    Simple</option>
    <option value="RxPath" >
	<xsl:if test='$previous:searchType = "RxPath"'>
		<xsl:attribute name='selected'>selected</xsl:attribute>
	</xsl:if>        
    RxPath</option>
    <option value="RegEx" >
	<xsl:if test='$previous:searchType = "RegEx"'>
		<xsl:attribute name='selected'>selected</xsl:attribute>
	</xsl:if>            
    Regex</option>
    </select>
&#xa0;View<select name="view">
    <option value="html" selected='selected'>HTML</option>
    <option value="rss91" >RSS .91</option>
    <option value="rxml" >RxML</option>
    <option value="edit" >Edit</option>
    <option value="rxpathdom" >RxPathDOM</option>    
    </select>
&#xa0;<input style="font-size: 80%" type="submit" value="search" name="Search"/>    

</form></p>
</xsl:if>
</td>
</tr>
</table>
<xsl:comment>(c) 2003-4 by Adam Souzis (asouzis@users.sourceforge.net) All rights reserved</xsl:comment>
</body>
</html>
    
</xsl:template>
</xsl:stylesheet>
