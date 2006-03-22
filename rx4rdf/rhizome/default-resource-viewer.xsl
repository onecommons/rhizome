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
		exclude-result-prefixes = "rdfs f wf a wiki rdf response-header" >		

<xsl:output omit-xml-declaration='yes' indent='no' />
<xsl:param name="__resource" />
<xsl:param name="_name" />
<xsl:param name="BASE_MODEL_URI" />

<xsl:template match="/" >
<!-- this page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />
<xsl:variable name='_robots' select="wf:assign-metadata('_robots', 'nofollow,noindex')" />

<xsl:variable name='shreddedContext' select="/*[a:from-source = ($__resource/wiki:revisions/*/rdf:first/*)[last()]/a:contents/*]/a:entails" />

<!-- note: the same template is used in search.xsl for the rxml output -->
<a href="site:///{$_name}?action=edit-metadata&amp;about={f:escape-url($__resource)}">Edit Metadata</a>
&#xa0;<a href='site:///search?search=%2F*%2F*%5B.%3D%27{f:escape-url($__resource)}%27%5D&amp;searchType=RxPath&amp;view=html'>Used By</a>
&#xa0;<a href='site:///search?search=%2F*%5B.%3D%27{f:escape-url($__resource)}%27%5D&amp;searchType=RxPath&amp;view=rdf'>RDF/XML</a>
&#xa0;<a href='site:///search?search=%2F*%5B.%3D%27{f:escape-url($__resource)}%27%5D&amp;searchType=RxPath&amp;view=ntriples'>NTriples</a>
<xsl:if test='$shreddedContext'>
&#xa0;<a href='site:///search?search=get-graph-predicates%28%2F*%5B.%3D%27{f:escape-url($shreddedContext)}%27%5D%29&amp;searchType=RxPath&amp;view=rxml'>Extracted Metadata</a>
</xsl:if>
<hr />
<xsl:if test='$__resource/wiki:about'>
 Keywords:&#xa0; 
 <xsl:for-each select='$__resource/wiki:about'>
   <a href='site:///keywords/{local-name-from-uri(.)}?about={f:escape-url(.)}' >
   <xsl:value-of select='f:if(namespace-uri-from-uri(.)=concat($BASE_MODEL_URI,"kw#"),local-name-from-uri(.), name-from-uri(.))'/>
   </a>&#xa0;
 </xsl:for-each>
 <hr />
</xsl:if>
<pre>
    <xsl:variable name='fixup' select="&quot;&lt;a href='site:///.?action=view-metadata&amp;amp;about=%(encodeduri)s'>%(res)s&lt;/a>&quot;" />
    <!-- there's an absurd level of string escaping going on here! XML escaping (twice!), URL encoding, and Python string interpolation
    The original string is:
    /*/*[is-subproperty-of(@uri,'%(encodeduri)s')]
    -->
    <xsl:variable name='fixupPredicate' select=
    "&quot;&lt;a href='site:///search?search=%%2F*%%2F*%%5Bis-subproperty-of%%28%%40uri%%2C%%27%(encodeduri)s%%27%%29%%5D&amp;amp;searchType=RxPath&amp;amp;view=html&amp;amp;title=Property%%20Usage'>%(predicate)s&lt;/a>&quot;" />
               
    <xsl:value-of disable-output-escaping='yes' select="wf:serialize-rdf($__resource, 'rxml_zml', $fixup, $fixupPredicate)" />
</pre>

</xsl:template>
</xsl:stylesheet>