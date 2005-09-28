<?xml version="1.0" ?>
<xsl:stylesheet
   version="1.0"
   xmlns:sch="http://www.ascc.net/xml/schematron"
   xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
   xmlns:axsl="http://www.w3.org/1999/XSL/TransformAlias">
<xsl:import href="skeleton1-5.xsl"/>

<xsl:template name="process-prolog">
<!-- process the result as a RxSLT template -->
 <xsl:processing-instruction name='raccoon-format'>
 http://rx4rdf.sf.net/ns/wiki#item-format-rxslt
 </xsl:processing-instruction>  
</xsl:template>

<xsl:template name="process-assert">
   <xsl:param name="role" />
   <xsl:param name="pattern" />
   <xsl:variable name='message'>
     <xsl:apply-templates mode="text"/>
   </xsl:variable>

   <axsl:variable name='dummy'
     select="wf:error('Validation Error: {$message}')" />          
</xsl:template>

<!-- override default -->
<xsl:template name="process-report" />

</xsl:stylesheet>
