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
<!-- 
  This template builds the basic structure of the page (html and head)
  and then creates the content by calling template named "theme-body",
  which must be defined in the imported theme stylesheet.
  
  It also defines several templates that your theme's template can call:
  * display-content
  * login-form
  * actions-bar
  * quicklinks-bar
  * search-form
  * recent-items  

  It references two css files:
    basestyles.css
  and 
    theme.css
-->     
    <xsl:import href="site:///theme.xsl?action=view-source" /> <!-- we need the action parameter so we don't try to invoke the transform -->
    <xsl:param name="_contents" />		
    <xsl:param name="previous:title" />		
    <xsl:param name="_name" />		
    <xsl:param name="_url" />		
    <xsl:param name="_path" />		 
    <xsl:param name="_base-url" />
    <xsl:param name="_originalContext" /> <!-- this will be the initial revision resource -->
    <xsl:param name="_previousContext" /> <!-- if multiple templates are chained this will be the previous template, not the initial revision resource -->
    <xsl:param name="session:login" />
    <xsl:param name="session:message" />
    <xsl:param name="response-header:content-type"/>    
    <xsl:param name="_static" />
    <xsl:param name="previous:about" />
    <xsl:param name="previous:itemname" />
    <xsl:param name="previous:search" />				
    <xsl:param name="previous:searchType" />				
    <xsl:param name='previous:_rsslink'/>
    <xsl:param name="previous:_robots" />
    <xsl:param name="previous:action" />        
    <xsl:param name="previous:_template" />
    
<xsl:output method='html' encoding="UTF-8" indent='no' />

<xsl:variable name='prev-content-type' select="$response-header:content-type" />
<xsl:variable name='title' select="f:if($previous:title, $previous:title, f:if($_originalContext/wiki:title, $_originalContext/wiki:title, $_name) )" />

<xsl:template match="/">
<!-- html template based on http://www.projectseven.com/tutorials/css_t/example.htm 
    (well, not much anymore, gave up and started using nested tables)    
-->
<html>
<head>
<title><xsl:value-of select="$title" /></title>

<link href="site:///basestyles.css" rel="stylesheet" type="text/css" />
<link href="site:///{$previous:_template/wiki:uses-theme/*/wiki:uses-css-stylesheet/*/wiki:name}" rel="stylesheet" type="text/css" />

<xsl:if test="wf:file-exists('favicon.ico')"> <!-- performance hack (assumes favicon.ico is external) -->
  <link rel="icon" href="site:///favicon.ico" />
</xsl:if>

<xsl:if test="$previous:_rsslink"> 
  <link rel="alternate" type="application/rss+xml" title="RSS" href="{$previous:_rsslink}" />
</xsl:if>
<xsl:if test="$previous:_robots"> 
  <meta name="robots" content="{$previous:_robots}" />
</xsl:if>
<xsl:comment>(c) 2003-4 by Adam Souzis (asouzis at users.sourceforge.net) All rights reserved.</xsl:comment>
</head>

<xsl:call-template name="theme-body" />

</html>
</xsl:template>

<xsl:template name="display-content" >
<xsl:param name="contents" select="$_contents" />
<xsl:param name="content-type" select="$prev-content-type" />
<xsl:param name="action" select="f:if($previous:action, $previous:action, 'view')" />

   <div id='maincontent'>
     <xsl:choose>
     <xsl:when test="(contains($content-type,'xml')
                  or starts-with($content-type,'text/html')) and $action != 'view-source'">
        <xsl:value-of disable-output-escaping='yes' select="$contents" />
     </xsl:when>         
    <!-- 
    we never get this far for binary content because xslt.Processor._normalizeParams calls to_unicode on $_contents
     <xsl:when test="$_previousContext/a:contents/a:ContentTransform/a:transformed-by = 'http://rx4rdf.sf.net/ns/wiki#item-format-binary'">         
         <xsl:variable name='aboutparam' select="f:if($previous:about, concat('&amp;about=', f:escape-url($previous:about)), '')" />
        <iframe height='100%' width='100%' 
  href='site:///{$_name}?_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-complete{$aboutparam}' />
     </xsl:when>           
    -->         
     <xsl:otherwise>             
        <pre>
        <xsl:value-of disable-output-escaping='no' select="$contents" />
        </pre>
     </xsl:otherwise>
    </xsl:choose>    
  </div>
</xsl:template>

<xsl:template name="login-form" >
<xsl:if test="not($_static)" >
         <xsl:choose>
            <xsl:when test="$session:login">
<form action='site:///logout' method='POST' accept-charset='UTF-8' >
Welcome <a href="site:///users/{$session:login}?action=edit"><xsl:value-of select="$session:login" /></a>
<input TYPE="hidden" NAME="redirect" value="{$_url}" />
<input type="submit" value="logout" name="logout"/>  
<br/><xsl:value-of select="$session:message" disable-output-escaping='yes' />  
</form>            
            </xsl:when>
            <xsl:otherwise>
<form action='site:///login' method='POST' accept-charset='UTF-8'>
Name<input TYPE="text" NAME="loginname" SIZE="10" />
Password<input TYPE="password" NAME="password" SIZE="10" />
<input TYPE="hidden" NAME="redirect" value="{$_url}" />
<input type="submit" value="login" name="login"/>    
Or <a href="site:///users/guest?action=new">signup</a>
<br/><xsl:value-of select="$session:message" disable-output-escaping='yes' />
</form>            
           </xsl:otherwise>
        </xsl:choose>        
</xsl:if>
</xsl:template>

<xsl:template name="search-form" >
<xsl:param name="edit-width" select="30" />
<form action='site:///search' accept-charset='UTF-8' method="GET">
<label for="search">Search</label><input type="text" name="search" value="{$previous:search}" size="$edit-width" />
<label for="searchType">Type</label><select name="searchType">    
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
<label for="view">View</label><select name="view">
    <option value="list" selected='selected'>List</option>
    <option value="summary">Summary</option>
    <option value="rss20" >RSS 2.0</option>
    <option value="rxml" >RxML</option>
    <option value="rdf" >RDF/XML</option>
    <option value="edit" >Edit</option>
    <option value="rxpathdom" >RxPathDOM</option>    
    </select>
&#xa0;<input type="submit" value="search" name="Search"/>    
</form>
</xsl:template>

<xsl:template name="quicklinks-bar" >
    <a href="site:///edit">New</a>
    &#xa0;<a href="site:///keyword-browser">Browse</a>
    &#xa0;<a href="site:///search?search=wf%3Asort%28%2Fa%3ANamedContent%2C%27%28wiki%3Arevisions%2F*%2Frdf%3Afirst%2F*%29%5Blast%28%29%5D%2Fa%3Acreated-on%27%2C%27number%27%2C%27descending%27%29&amp;searchType=RxPath&amp;view=list&amp;title=Recently%20Changed%20Pages">Recent</a>
    &#xa0;<a href="site:///administration">Admin</a>
    &#xa0;<a href="site:///help">Help</a>
</xsl:template>

<xsl:template name="actions-bar" >
    <xsl:variable name='aboutparam' select="f:if($previous:about, concat('&amp;about=', f:escape-url($previous:about)), '')" />
    <xsl:variable name='path' select="f:if($previous:itemname, $previous:itemname, $_name)" />
    <a href="site:///{$path}?{$aboutparam}">View</a>
    &#xa0;<a href="site:///{$path}?action=edit{$aboutparam}">Edit</a>
    &#xa0;<a href="site:///{$path}?action=showrevisions">Revisions</a>
    &#xa0;<a href="site:///{$path}?action=view-metadata{$aboutparam}">Metadata</a>
    &#xa0;<a href="site:///{$path}?action=confirm-delete{$aboutparam}">Delete</a>
    &#xa0;<a href="site:///{$path}?action=view-source{$aboutparam}">Source</a>
    &#xa0;<a href="site:///{$path}?_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-print{$aboutparam}">Print</a>
</xsl:template>

<xsl:template name="recent-items" >
<xsl:param name="max" select="21" />
<ul>
<xsl:for-each select="wf:sort(/a:NamedContent[not(wiki:about='http://rx4rdf.sf.net/ns/wiki#built-in')],
'(wiki:revisions/*/rdf:first/*)[last()]/a:created-on','number','descending')[position()&lt;$max]" >
<li>
<a href="{$_base-url}site:///{./wiki:name}">
<xsl:value-of select='f:if( (./wiki:revisions/*/rdf:first/*)[last()]/wiki:title, 
                (./wiki:revisions/*/rdf:first/*)[last()]/wiki:title,
               f:if(./wiki:name-type = uri("wiki:name-type-anonymous")
                 and (./wiki:revisions/*/rdf:first/*)[last()]/wiki:auto-summary, 
                (./wiki:revisions/*/rdf:first/*)[last()]/wiki:auto-summary, ./wiki:name))' />  
</a></li>
</xsl:for-each>
</ul>
</xsl:template>

</xsl:stylesheet>
