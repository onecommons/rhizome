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
   
<xsl:variable name='_doctype' select="wf:assign-metadata('_doctype',
                      'http://rx4rdf.sf.net/ns/wiki#doctype-faq')" />

<xsl:template match='/' >
  <faqs>
        <xsl:for-each select="$__resource">
           <xsl:call-template name='make-faq' />
        </xsl:for-each>                    
  </faqs>     
</xsl:template>

  <xsl:template name='make-faq'>
    <faq>
        <question>
            <xsl:value-of disable-output-escaping='yes' select="./wiki:question"/>
        </question>

        <answer>
            <xsl:value-of disable-output-escaping='yes' select="./wiki:answer"/>
        </answer>
    </faq>
  </xsl:template>

</xsl:stylesheet>