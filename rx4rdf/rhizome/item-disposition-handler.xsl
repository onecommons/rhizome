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
    <xsl:param name="previous:action" />
    <xsl:param name="previous:itemname" />
    <xsl:param name="previous:error" />
    <xsl:param name="previous:about" />
    <xsl:param name="previous:redirect" />
    <xsl:param name="previous:_itemHandlerDisposition" />
    <xsl:param name="_contents" />	
    
    <xsl:output method="html" encoding="UTF-8" indent='no' />
    	
<xsl:template match="/">  
    <div class='message'>
    <xsl:choose>    
    <xsl:when test='$previous:error'>
    Error <b><xsl:value-of select='$previous:error'/></b> 
    </xsl:when>
    <xsl:when test='$previous:redirect'>
    <!-- allow handler page to redirect to another page-->
    <xsl:variable name='_dispositionDisposition' 
      select="wf:assign-metadata('_dispositionDisposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete'])" />       
    <xsl:variable name="dummy2" select="wf:assign-metadata('response-header:status', 302)"/>
    <xsl:variable name="dummy3" select="wf:assign-metadata('response-header:Location', $previous:redirect)"/>You should be redirected shortly...    
    </xsl:when>
    <xsl:otherwise>    
    <script>    
    //if we're in a popup window, close it
    if (window.name == 'small-action-popup')
       setTimeout('window.close()', 2000);
    </script>
    Completed <b><xsl:value-of select='$previous:action'/></b> of <a 
        href="{f:if($previous:about, 
                concat('site:///',$previous:itemname, '?about=',f:escape-url($previous:about)),
                concat('site:///',$previous:itemname))}" >
        <b><xsl:value-of select='$previous:itemname'/></b></a>.
    <xsl:if test='$_contents'>
    <p class='note'> 
         <xsl:value-of disable-output-escaping='yes' select="$_contents" />		
    </p>
    </xsl:if> 
    </xsl:otherwise>
    </xsl:choose>    
    </div>

    <!-- hack! add a parameter so we can override this item handler disposition (which is normally entry) -->
    <xsl:if test="$previous:_itemHandlerDisposition" >
      <xsl:variable name='_dispositionDisposition' 
         select="wf:assign-metadata('_dispositionDisposition', /*[.=$previous:_itemHandlerDisposition])" />       
    </xsl:if>     
</xsl:template>
</xsl:stylesheet>
