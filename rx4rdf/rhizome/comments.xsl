<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:response-header = 'http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
		xmlns:auth="http://rx4rdf.sf.net/ns/auth#"
		xmlns:foaf="http://xmlns.com/foaf/0.1/"
		xmlns:dc='http://purl.org/dc/elements/1.1/'		
		exclude-result-prefixes = "rdfs f wf dc foaf a wiki rdf response-header auth" >
<xsl:import href='search.xsl' />
<xsl:param name='__account'/>
<xsl:param name='parent'/>

<xsl:output method='html' encoding="UTF-8" indent='no' />

<xsl:template match="/" >
<xsl:variable name='rss-url' select="concat('site:///search?searchType=RxPath&amp;view=rss&amp;search=', 
     f:escape-url(concat('/*[wiki:comments-on=&quot;', $parent, '&quot;]')) )" />

<html>

<head>
<title>Comments for <xsl:value-of select='/*[.=$parent]/wiki:name'/></title>

<link href="site:///basestyles.css" rel="stylesheet" type="text/css" />
<link href="site:///{/*[wiki:name='site-template']/wiki:uses-theme/*/wiki:uses-css-stylesheet/*/wiki:name}" rel="stylesheet" type="text/css" />
   
  <link rel="alternate" type="application/rss+xml" title="RSS" href="{$rss-url}" />
  
<xsl:comment>(c) 2003-5 by Adam Souzis (asouzis at users.sourceforge.net) All rights reserved.</xsl:comment>
</head>

<body>
<xsl:variable name='comments' select='/*[wiki:comments-on = $parent]'/>

<xsl:for-each select='$comments' >
    <xsl:call-template name='make-summary'>
      <xsl:with-param name='showedit' select='false()' />
    </xsl:call-template>
</xsl:for-each>

<xsl:if test='not($comments)'>
No comments yet.
</xsl:if>
    
<br clear='all' />

<form name="edit" method="POST" accept-charset="UTF-8" action="site:///save" enctype="multipart/form-data">    

<input type='hidden' name='itemname' value='' />
<input type='hidden' name='title' value='' />
<input type='hidden' name='startTime' value='1' />
<input type='hidden' name='disposition'  value='http://rx4rdf.sf.net/ns/wiki#item-disposition-entry'  />

<xsl:variable name='metadata' select='concat("#this#: {http://rx4rdf.sf.net/ns/wiki#comments-on}: {", $parent, "}")' />
<input type='hidden' name='metadata' value='{$metadata}' />
<hr/>
<xsl:if test="$__account/foaf:accountName = 'guest'">
    Not logged in, enter guest info:
    <p>Name: <br />
      <input name="user-name" type="text" size="38" value="" /><br />
    Email: <br />
      <input name="email" type="text" size="38" value="" />
      <br />
      URL: <br />
      <input name="user-url" type="text" size="38" value="" />
      <br />
    </p>    
</xsl:if>
          Comment:<br/>
          <textarea name="contents" rows="12" cols="38"></textarea>
          <br />Format: 
          <input type="radio" name="format" checked="checked" value="http://rx4rdf.sf.net/ns/wiki#item-format-text" />Text 
          <input type="radio" name="format" value="http://rx4rdf.sf.net/ns/wiki#item-format-xml"  />HTML          
          <input type="radio" name="format" value="http://rx4rdf.sf.net/ns/wiki#item-format-zml"  />ZML          
          | <a target="rhizome-main" 
             href="site:///edit?title=Add%20Comment&amp;metadata={f:escape-url($metadata)}">Advanced Edit</a>
          <br/>
          <input name="submit" type="submit" value="OK" /> 
          
</form>
<a href='{$rss-url}' type="application/rss+xml">
  <img border='0' src='site:///rss.png' alt='RSS .91 of this search'/>
</a>

</body>
</html>
</xsl:template>
</xsl:stylesheet>