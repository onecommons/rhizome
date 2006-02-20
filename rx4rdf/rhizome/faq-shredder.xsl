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

   <xsl:param name='__resource' />
   
   <xsl:template match='/' >
     <!-- create RxUpdate output -->
     <xupdate:modifications >
      <xsl:apply-templates />
     </xupdate:modifications>
   </xsl:template>

<xsl:template match='faq' >
  <xupdate:append select='/'>
    <wiki:faq rdf:about="{f:if(@id, concat($__resource, '#', @id), wf:generate-bnode())}">

      <wiki:question>
      <xsl:text disable-output-escaping='yes'>&lt;![CDATA[</xsl:text>
         <xsl:copy-of select="question/node()"/>
      <xsl:text disable-output-escaping='yes'>]]&gt;</xsl:text>
      </wiki:question>

      <wiki:answer>
      <xsl:text disable-output-escaping='yes'>&lt;![CDATA[</xsl:text>
         <xsl:copy-of select="answer/node()"/>
      <xsl:text disable-output-escaping='yes'>]]&gt;</xsl:text>
      </wiki:answer>

   </wiki:faq>
 </xupdate:append>
</xsl:template>

</xsl:stylesheet>