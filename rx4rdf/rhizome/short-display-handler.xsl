<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:previous = 'http://rx4rdf.sf.net/ns/raccoon/previous#'     
        xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" 
        xmlns:f = 'http://xmlns.4suite.org/ext' 
        xmlns:response-header="http://rx4rdf.sf.net/ns/raccoon/http-response-header#"   
        exclude-result-prefixes = "f a wiki rdf previous wf response-header" 
        >
<xsl:param name="_contents" />
<xsl:param name="response-header:content-type"/>    
<xsl:param name="_name" />
<xsl:param name="previous:about" />
<xsl:param name="previous:frameid" />
<xsl:param name="previous:itemname" />

<xsl:output method='html' encoding='UTF-8' indent='no' />
    
<xsl:template name="display-content" >
<xsl:param name="contents" />
<xsl:param name="content-type" />
   <div id='maincontent'>
     <xsl:choose>
     <xsl:when test="contains($content-type,'html')">     
        <xsl:value-of disable-output-escaping='yes' select="$contents" />
     </xsl:when>         
     <xsl:when test="starts-with($content-type,'text')">
        <pre>
        <!-- todo: count # of lines, if > max lines, display max lines substring -->
        <xsl:value-of disable-output-escaping='no' select="$contents" />
        </pre>
     </xsl:when>         
     <xsl:otherwise>
        <xsl:variable name='aboutparam' select="f:if($previous:about, concat('&amp;about=', f:escape-url($previous:about)), '')" />
        This page can not be displayed on this page, click <a href='site:///{$_name}?{$aboutparam}'>here</a> to view it.
        Content type          
        <xsl:value-of disable-output-escaping='no' select="$content-type" />
     </xsl:otherwise>
    </xsl:choose>    
  </div>
</xsl:template>

<xsl:template match="/">  
<html>
<head>

<link href="site:///basestyles.css" rel="stylesheet" type="text/css" />

</head>
<!-- we need scrolling on to get the correct content size, but then turn it off -->
<body onload="if (parent.resizeForIframe) parent.resizeForIframe(this, '{$previous:frameid}', '{$previous:itemname}');
              this.document.body.style.overflow='hidden'">

    <div class='short-display'>
      	<xsl:call-template name="display-content" >
		   <xsl:with-param name="contents" select="$_contents" />
		   <xsl:with-param name="content-type" select="$response-header:content-type" />
     	</xsl:call-template>    
    </div>
</body>
</html>  
</xsl:template>
</xsl:stylesheet>
