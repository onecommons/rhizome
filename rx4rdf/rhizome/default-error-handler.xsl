<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:previous = 'http://rx4rdf.sf.net/ns/raccoon/previous#'     
        xmlns:error = 'http://rx4rdf.sf.net/ns/raccoon/error#'     
        xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" 
        xmlns:f = 'http://xmlns.4suite.org/ext' 
        xmlns:response-header="http://rx4rdf.sf.net/ns/raccoon/http-response-header#"   
        exclude-result-prefixes = "f a wiki rdf previous wf response-header error" 
        >
    <xsl:param name="error:userMsg" />
    <xsl:param name="error:name" />
    <xsl:param name="error:message" />
    <xsl:param name="error:details" />
    <xsl:param name="_previousContext" />
    
<xsl:template match="/">  
    <xsl:variable name='_robots' select="wf:assign-metadata('_robots', 'nofollow,noindex')" />
    <!-- use the same item template as the page that contained the error; 
      if $_disposition has not have been set yet, get the wiki:item-disposition 
      Hack: if the disposition is handler than use $_itemHandlerDisposition or entry instead
    -->
    <xsl:variable name='dispStep1' select="f:if(wf:has-metadata('_disposition'), 
        wf:get-metadata('_disposition'), $_previousContext/wiki:item-disposition/*)" />       
    <xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', 
        f:if($dispStep1 = 'http://rx4rdf.sf.net/ns/wiki#item-disposition-handler', 
        /*[.=wf:get-metadata('previous:_itemHandlerDisposition', 
             'http://rx4rdf.sf.net/ns/wiki#item-disposition-entry')], $dispStep1))" />       

    <div class='message'>
    <xsl:choose>    
    <xsl:when test='$error:userMsg'>        
    <!--todo: hmm, why did the replace stop working? -->
    <b><pre>Error: <xsl:value-of disable-output-escaping='yes' 
        select="f:replace('\n','&lt;br />', f:escape-xml($error:userMsg))"/>
    </pre></b>
    </xsl:when>
    <xsl:otherwise>    
    <!-- set 500 internal server error -->
    <xsl:variable name='status500' select="wf:assign-metadata('response-header:status', 500)" />
    <p>
    Unexpected Error 
    <br/>
    Type: <tt><xsl:value-of select='$error:name'/></tt>
    <br/>
    Message: <pre><xsl:value-of select='$error:message'/></pre>
    </p>
    Details:
    <pre> 
    <xsl:value-of select='$error:details'/>
    </pre>
    </xsl:otherwise>
    </xsl:choose>    
    </div>
</xsl:template>
</xsl:stylesheet>
