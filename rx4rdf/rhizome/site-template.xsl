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
    <xsl:import href="site:///site-theme" /> 
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
    <xsl:param name="previous:__resource" />
    
<xsl:output method='xhtml' omit-xml-declaration="yes" encoding="UTF-8" indent='no' 
doctype-public="-//W3C//DTD XHTML 1.0 Transitional//EN" 
doctype-system="http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd" 
/>

<xsl:variable name='prev-content-type' select="$response-header:content-type" />
<xsl:variable name='title' select="f:if($previous:title, $previous:title, f:if($_originalContext/wiki:title, $_originalContext/wiki:title, $_name) )" />
<xsl:variable name='message' select="$session:message" />
<!-- hack -->
<xsl:variable name='removeMessage' select="wf:remove-metadata('session:message')" /> 

<xsl:template match="/">
<html>
<head>
<title><xsl:value-of select="$title" /></title>

<link href="site:///basestyles.css" rel="stylesheet" type="text/css" />
<link href="site:///{$previous:_template/wiki:uses-theme/*/wiki:uses-css-stylesheet/*/wiki:name}" rel="stylesheet" type="text/css" />
<link href="site:///user.css" rel="stylesheet" type="text/css" />

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

   <div id='page-content' class='content_style'>
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
     <xsl:value-of disable-output-escaping='yes' 
        select="f:replace('&#10;','&lt;br />', f:escape-xml($contents))"/>      
      <!--
        <pre>
        <xsl:value-of disable-output-escaping='no' select="$contents" />
        </pre>
      -->
     </xsl:otherwise>
    </xsl:choose>    
  </div>
</xsl:template>

<xsl:template name="login-form" >
<xsl:if test="not($_static)" >
         <xsl:choose>
            <xsl:when test="$session:login">
<form action='site:///logout' method='post' accept-charset='UTF-8' >&#xa0;Welcome <a href="site:///accounts/{$session:login}?action=edit"><xsl:value-of select="$session:login" /></a>&#xa0;<input TYPE="hidden" NAME="redirect" value="{$_url}" /><input type="submit" value="Log Out" name="logout"/><br/>
</form>            
            </xsl:when>
            <xsl:otherwise>
<form action='site:///login' method='post' accept-charset='UTF-8'><div id="login-div" class="form_style"><div id="login-div-left">Name<input TYPE="text" NAME="loginname" SIZE="10" /><br/>Password<input TYPE="password" NAME="password" SIZE="10" /><input TYPE="hidden" NAME="redirect" value="{$_url}" /></div><div id="login-div-right"><input type="submit" value="Log in" name="login"/><br/><a href="site:///accounts/?about={f:escape-url('http://xmlns.com/foaf/0.1/OnlineAccount')}&amp;action=new" class="form_style">Register</a></div></div></form>            
           </xsl:otherwise>
        </xsl:choose>        
</xsl:if>
</xsl:template>


<xsl:template name="search-form" >
<xsl:param name="edit-width" select="40" />
<form action='site:///search' accept-charset='UTF-8' method="get" class="form_style">
<label for="search" class="bold">Search</label><br/><input type="text" name="search" value="{$previous:search}" size="$edit-width" /><br/><label for="searchType">Type</label>&#xa0;<select name="searchType"><option value="Simple"><xsl:if test='not($previous:searchType) or $previous:searchType = "Simple"'><xsl:attribute name='selected'>selected</xsl:attribute></xsl:if>Simple</option><option value="RxPath" ><xsl:if test='$previous:searchType = "RxPath"'><xsl:attribute name='selected'>selected</xsl:attribute></xsl:if>RxPath</option><option value="RegEx" ><xsl:if test='$previous:searchType = "RegEx"'><xsl:attribute name='selected'>selected</xsl:attribute></xsl:if>Regex</option></select><br/><label for="view">View</label>&#xa0;&#xa0;<select name="view"><option value="list" selected='selected'>List</option><option value="summary">Summary</option><option value="rss20" >RSS 2.0</option><option value="rxml" >RxML</option><option value="rdf" >RDF/XML</option><option value="edit" >Edit</option><option value="rxpathdom" >RxPathDOM</option></select><br/><input type="submit" value="Search" name="Search"/></form></xsl:template>

<xsl:template name="quicklinks-bar" >
    <!-- note: keep in sync with the recent-items template below -->
    <xsl:variable name="recent-pages-query" select=
"concat('search=', f:escape-url('/a:NamedContent[not(wiki:appendage-to)][(wiki:revisions/*/rdf:first/*)[last()]/a:created-on != 1057919732.750]'),
'&amp;sortKey=', f:escape-url('(wiki:revisions/*/rdf:first/*)[last()]/a:created-on'),'&amp;sortKeyType=number&amp;sortKeyOrder=descending')"
    />

    <a href="site:///edit">New Page</a><br/><a href="site:///keyword-browser">Browse by Keyword</a><br/><a href=
"site:///search?{$recent-pages-query}&amp;searchType=RxPath&amp;view=list&amp;title=Recently%20Changed%20Pages">Recent Changes</a><br/><a href="site:///administration">Administration</a><br/><a href="site:///help">Help and FAQ</a>
</xsl:template>

<xsl:template name="actions-bar" >
    <xsl:variable name='aboutparam' select="f:if($previous:about, concat('&amp;about=', f:escape-url($previous:about)), '')" />
    <xsl:variable name='path' select="f:if($previous:itemname, $previous:itemname, $_name)" />
    <xsl:variable name='action' select="f:if($previous:action, $previous:action, 'view')" />
    <a href="site:///{$path}?{$aboutparam}" class="actionstab_style action-tab {f:if($action='view', ' selected-action-tab selected-action-tab_style', '')}" title="View">View</a>&#xa0;<!-- 
  --><a href="site:///comments?parent={f:escape-url($previous:__resource)}" onclick="window.open(this.href,'smallActionPopup','directories=0,height=500,width=550,location=0,resizable=1,scrollbars=1,toolbar=0');return false;" title="Comments" class="actionstab_style">Comments (<xsl:value-of select='count(/*[wiki:comments-on = $previous:__resource])'/>)</a>&#xa0;<!--  
  --><a rel='nofollow' href="site:///{$path}?action=edit{$aboutparam}" class="actionstab_style action-tab {f:if($action='edit', ' selected-action-tab selected-action-tab_style', '')}" title="Edit">Edit</a>&#xa0;<!--  
   --><a href="site:///{$path}?action=showrevisions" class="actionstab_style action-tab {f:if($action='showrevisions', ' selected-action-tab selected-action-tab_style', '')}" title="Revisions">Revisions</a>&#xa0;<!--  
    --><a href="site:///{$path}?action=view-metadata{$aboutparam}" class="actionstab_style action-tab {f:if($action='view-metadata', ' selected-action-tab selected-action-tab_style', '')}" title="Metadata">Metadata</a>&#xa0;<!--  
    --><a rel='nofollow' href="site:///{$path}?action=confirm-delete{$aboutparam}" class="actionstab_style action-tab {f:if($action='confirm-delete', ' selected-action-tab selected-action-tab_style', '')}" title="Delete">Delete</a>&#xa0;<!--  
    --><a href="site:///{$path}?action=view-source{$aboutparam}" class="actionstab_style action-tab {f:if($action='view-source', ' selected-action-tab selected-action-tab_style', '')}" title="Source">Source</a>&#xa0;<!--  
    --><a rel='nofollow' href="site:///{$path}?_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-print{$aboutparam}" title="Print" class="actionstab_style">Print</a>
</xsl:template>

<xsl:template name="recent-items" >
<xsl:param name="max" select="21" />
 <ul>
 <xsl:for-each select="/a:NamedContent[not(wiki:appendage-to)][(wiki:revisions/*/rdf:first/*)[last()]/a:created-on !=1057919732.750]">
   <xsl:sort select="(wiki:revisions/*/rdf:first/*)[last()]/a:created-on" data-type='number' order='descending' />
   <xsl:if test="position()&lt;$max">
     <li>
     <a href="{$_base-url}site:///{./wiki:name}">
     <xsl:value-of select='f:if( (./wiki:revisions/*/rdf:first/*)[last()]/wiki:title, 
                    (./wiki:revisions/*/rdf:first/*)[last()]/wiki:title,
                   f:if(./wiki:name-type = uri("wiki:name-type-anonymous")
                     and (./wiki:revisions/*/rdf:first/*)[last()]/wiki:auto-summary, 
                    (./wiki:revisions/*/rdf:first/*)[last()]/wiki:auto-summary, ./wiki:name))' />  
     </a>
     </li>
   </xsl:if>
 </xsl:for-each>
 </ul>
</xsl:template>
</xsl:stylesheet>
