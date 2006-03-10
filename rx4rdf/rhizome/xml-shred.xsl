<xsl:stylesheet version="1.0" 
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
  xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" 
  xmlns:f="http://xmlns.4suite.org/ext" 
  xmlns:html = 'http://www.w3.org/1999/xhtml'
  xmlns:xupdate="http://www.xmldb.org/xupdate"
  xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
  xmlns:dataview='http://www.w3.org/2003/g/data-view'
  xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
  exclude-result-prefixes="f wf dataview">

   <xsl:param name='__store' />
   <xsl:param name='__resource' />
   
   <xsl:variable name='doc' select='/' />

   <xsl:template name='set-doctype'>
      <xsl:param name='doctype' />
     <xsl:if test='$doctype' >
      <xupdate:remove select='($__resource/wiki:revisions/*/rdf:first)[last()]/*/wiki:doctype' />
      <xupdate:append select='($__resource/wiki:revisions/*/rdf:first)[last()]/*'>
         <wiki:doctype rdf:resource="{$doctype}"/>
      </xupdate:append>
     </xsl:if> 
   </xsl:template>

   <xsl:template match='/' >
     <xupdate:modifications >
      <xsl:apply-templates />
     </xupdate:modifications>
   </xsl:template>

<!-- support for XML vocabularies that don't use namespaces -->
   <xsl:template match='/faqs | /faq | /document | /section | /specification | 
                   /todo | /set | /book | /chapter | /article' >
   
      <xsl:variable name='doctype' 
         select="f:if(name(.)='faq' or name(.)='faqs', 'http://rx4rdf.sf.net/ns/wiki#doctype-faq',
         f:if(name(.)='document' or name(.)='section', 'http://rx4rdf.sf.net/ns/wiki#doctype-document',
         f:if(name(.)='todo', 'http://rx4rdf.sf.net/ns/wiki#doctype-todo',
         f:if(name(.)='specification', 'http://rx4rdf.sf.net/ns/wiki#doctype-specification',
         f:if(name(.)='set' or name(.)='book' or name(.)='chapter' or name(.)='article', 
                                    'http://rx4rdf.sf.net/ns/wiki#doctype-docbook')))))" />
       
       <xsl:call-template name='set-doctype'>
         <xsl:with-param name='doctype' select='$doctype' />     
       </xsl:call-template>
             
      <xsl:variable name='doctypeShredderName' 
           select='$__store/*[dataview:doctypeTransformation=$doctype]/wiki:name' />

      <xsl:if test='$doctypeShredderName'>      
        <xsl:variable name='dummy' 
          select="wf:shred-with-xslt(concat('site:///', $doctypeShredderName),$doc,$__resource)" />      
      </xsl:if>
      
      <xsl:call-template name='grddl-from-namespaces' />

      <!--
         the next shred will invoke the doc-handler xslt on this (faq2document.xsl), 
         whose reponse will invoke the XMLShredder which will invoke this spreadsheet again
         
        invoke dochandler xslt on $doc
            the response will be a <document> xml which will invoke the XML shredder which will invoke 
            this stylesheet on the xml
                this stylesheet will invoke step 1 and 2 again but with the document 
                handler and xhtml as the output.
                    the xml shredder will invoke this stylesheet again but fall into the HTML shredder
                    process this stylesheet's xupdate output
                process this stylesheet's xupdate output
            process this stylesheet's xupdate output
       continue processing this stylesheet and eventually its xupdate output        
      -->

      <xsl:variable name='doctypeTransformName' 
           select='$__store/*[wiki:handles-doctype=$doctype]/wiki:name' />

      <xsl:if test='$doctypeTransformName'>      
        <xsl:variable name='dummy1' 
          select="wf:shred-with-xslt(concat('site:///',$doctypeTransformName),$doc,$__resource)" />      
      </xsl:if>
      
   </xsl:template>
   
   <xsl:template match='/*' priority='-1' name='grddl-from-namespaces'>     
      <xsl:variable name='rootElementNS' select='namespace-uri(.)'/>
      <xsl:call-template name='set-doctype'>
         <xsl:with-param name='doctype' select='string(/wiki:Doctype[wiki:for-namespace=$rootElementNS])' />     
      </xsl:call-template>
     
      <!-- each namespace in the root node -->
      <xsl:for-each select='namespace::*'> 
          <xsl:variable name='currentns' select='.'/>
          <xsl:for-each select='$__store/*[.=$currentns]/dataview:namespaceTransformation/*'>
              <xsl:variable name='dummy2' select="wf:shred-with-xslt(
                    concat('site:///',./wiki:name),$doc,$__resource)" /> 
          </xsl:for-each>
      </xsl:for-each>      

      <xsl:apply-templates />      
   </xsl:template>
      
   <xsl:template match='/*/@dataview:transformation' >    
       <xsl:variable name='dummy3' select="wf:shred-with-xslt(.,$doc,$__resource)" /> 
        <xsl:apply-templates />
   </xsl:template>
       
   <xsl:template match='/html/head[@profile] | /html:html/html:head[@profile]' >
      <xsl:message terminate='no'>
        Invoking profile <xsl:value-of select="@profile"/>
      </xsl:message>
      
      <xsl:variable name='currentprofiles' select='@profile' />
      <xsl:for-each select='$__store/*[.=wf:split($currentprofiles)]/dataview:profileTransformation/*'>
         <xsl:variable name='dummy4' select="wf:shred-with-xslt(.,$doc,$__resource)" />
      </xsl:for-each>  
      <xsl:apply-templates />       
   </xsl:template>         
   
   <xsl:template match="/html/head[contains(@profile, 'http://www.w3.org/2003/g/data-view')]/link[@rel='transformation'] |
          /html:html/html:head[contains(@profile, 'http://www.w3.org/2003/g/data-view')]/html:link[@rel='transformation']">
      <xsl:message terminate='no'>
        Invoking <xsl:value-of select="@href"/>
      </xsl:message>

      <xsl:variable name='dummy5' select="wf:shred-with-xslt(@href,$doc,$__resource)" /> 
      
      <xsl:apply-templates />      
   </xsl:template>
   
   <!-- don't pass text thru -->
    <xsl:template match="text()|@*">
    </xsl:template>
   
 <xsl:template match='a | area'>
    <xsl:if test='@href'>
       <xsl:call-template name='add-urlref'>
        <xsl:with-param name='url' select='@href' />
       </xsl:call-template>
    </xsl:if>
    <xsl:apply-templates />
 </xsl:template>

 <xsl:template name='add-urlref'>
  <xsl:param name='pagename' select='$__resource/wiki:name' />
  <xsl:param name='url' select='.' />
  <xsl:param name='relation' select='"wiki:links-to"' />
  
  <xsl:variable name='absurl'>
    <xsl:choose>
     <!-- anchor: ignore -->
     <xsl:when test="starts-with($url,'#')"></xsl:when>

    <!-- absolute site:/// URL -->
    <xsl:when test="starts-with($url,'site:/')"><xsl:value-of select='$url' /></xsl:when>
        
     <!-- relative site: url, convert to absolute site: URL -->
     <xsl:when test="starts-with($url,'site:')"><xsl:value-of select=
       "f:resolve-url(concat('site:///', $pagename), substring($url,6))" /></xsl:when>

     <!-- when doesn't it contain a ':' assume it's a relative url -->
     <xsl:when test="not(contains($url,':'))"><xsl:value-of 
        select="f:resolve-url(concat('site:///', $pagename), $url)" /></xsl:when>     

      <!-- external -->
     <xsl:otherwise><xsl:value-of select="." /></xsl:otherwise>
    </xsl:choose>
  </xsl:variable>   

   <xsl:if test='$absurl'>     
     <xsl:if test="starts-with($absurl, 'site:')" >
       <xsl:variable name="name" select="wf:name-from-url($absurl)" />
       <xsl:if test="not(wf:has-page($name))" >
        <xupdate:append select='/'>
            <wiki:MissingPage rdf:about='{wf:get-nameURI($name)}'>
              <wiki:name><xsl:value-of select="$name" /></wiki:name>
            </wiki:MissingPage>
        </xupdate:append> 
       </xsl:if>
     </xsl:if>
    
     <xupdate:append select='$__resource'>
        <xsl:element name='{$relation}'> 
            <xsl:attribute name='rdf:resource'><xsl:value-of select="$absurl" /></xsl:attribute>
        </xsl:element>  
     </xupdate:append> 
   </xsl:if>
 </xsl:template>
   
   <xsl:template match='/testshredder' >
      <!-- used by the unit tests -->
      <xupdate:append select='$__resource'>
         <wiki:testprop>test success!</wiki:testprop>
       </xupdate:append>

      <xsl:message terminate='no'>
      match /testshredder
      </xsl:message>
       
       <xsl:call-template name='grddl-from-namespaces' />
       <xsl:apply-templates />    
   </xsl:template>   
</xsl:stylesheet>