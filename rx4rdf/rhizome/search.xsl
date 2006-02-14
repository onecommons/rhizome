<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:auth="http://rx4rdf.sf.net/ns/auth#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:response-header = 'http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
		xmlns:foaf="http://xmlns.com/foaf/0.1/"
		xmlns:dc='http://purl.org/dc/elements/1.1/'
		exclude-result-prefixes = "rdfs rdf f wf dc foaf a wiki auth response-header" >

<xsl:param name="search" />
<xsl:param name="view" />
<xsl:param name="searchType" />
<xsl:param name="_base-url" />
<xsl:param name="_url" />
<xsl:param name="_name" />
<xsl:param name="BASE_MODEL_URI" />
<xsl:param name="editFormat" select="'rxml_zml'" />
<xsl:param name="sortKey" select="'position()'" />
<xsl:param name="sortKeyType" select="'text'" />
<xsl:param name="sortKeyOrder" select="'ascending'" />
<xsl:param name="sortKeyCaseOrder" select="'upper-first'" />

<!-- 
<f:output method="{f:if($view='ntriples', 'text', 'xhtml')}" indent='yes' omit-xml-declaration="yes" encoding="UTF-8" />
-->
<xsl:output method="xhtml" indent='yes' omit-xml-declaration="yes" encoding="UTF-8" />
<xsl:variable name="searchExp">     
     <xsl:choose>
        <xsl:when test="$searchType='Simple'">                     
        wf:search($search)
        </xsl:when>
        <xsl:when test="$searchType='RegEx'">   
             /a:NamedContent[
                wiki:revisions/*/rdf:first/wiki:Item[
                    (.//a:contents/*/a:transformed-by !='http://rx4rdf.sf.net/ns/wiki#item-format-binary'
                    and f:match( wf:get-contents(.), $search))
                    or f:match(wiki:title,$search)] ]
        </xsl:when>
         <!-- rxpath -->
        <xsl:otherwise> 
            <!-- if the result isn't a node-set convert it to a string and then convert that to a nodeset with a text node -->
            wf:if(wf:instance-of(wf:evaluate($search), 'node-set'), 'wf:evaluate($search)', 'wf:string-to-nodeset(string(wf:evaluate($search)) )')
        </xsl:otherwise>
    </xsl:choose> 
</xsl:variable>

<xsl:template name="add-summary-javascript">
<xsl:param name='maxHeight' select='200'/>
<script language="JavaScript">
<xsl:comment>
function resizeForIframe(iframeWin, iframeId)
{	
    var width = iframeWin.document.body.scrollWidth
    var height = iframeWin.document.body.scrollHeight

    var newheight = <xsl:value-of select='$maxHeight'/>
    if (newheight > height) {
       newheight = height + 10
    }
    document.getElementById(iframeId).style.height=newheight;//change the height of the iframe
    	       
    if (width + 30 > document.getElementById('fixeddiv').style.width) {
        document.getElementById('fixeddiv').style.width = width + 30;
    }
        
}
//</xsl:comment>
</script>
</xsl:template>

<xsl:template name="make-summary" >
    <xsl:param name='maxwords' select='100' />
    <xsl:param name='maxlines' select='7' />
    <xsl:param name='showedit' select='true()' />
    <xsl:param name='target' select='"_blank"' />
    
    <xsl:variable name='revision' select="(./wiki:revisions/*/rdf:first/*)[last()]" />      
    <xsl:variable name='hasTitle' select="$revision/wiki:title or not(wiki:name-type = uri('wiki:name-type-anonymous'))"/>
    
    <xsl:choose>
        <xsl:when test="$revision/wiki:title or not(wiki:name-type = uri('wiki:name-type-anonymous'))">
    <div id='titlebar' style='line-height: 20px;'>
      <xsl:value-of select="f:if( $revision/wiki:title, $revision/wiki:title, f:if(wiki:name, wiki:name, .))" />
    </div>
        </xsl:when>
       <xsl:otherwise>       
          <hr/>
       </xsl:otherwise>       
    </xsl:choose>
        
    <xsl:variable name='contents' select="wf:truncate-contents($revision, $maxwords, $maxlines)" />      
    <xsl:choose>
        <xsl:when test='wf:instance-of($contents,"number")'> <!-- hack to check for failure -->
        <!-- can't display the contents so view it in an iframe -->
        <xsl:variable name='frameid' select='generate-id()' />
        <iframe width='100%' hspace='0' height='100' id='{$frameid}' frameborder='0' scrolling='yes' src="site:///{
            f:if(wiki:name, concat(wiki:name,'?'), concat('.?about=',f:escape-url(.), '&amp;') )
            }_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-short-display&amp;frameid={$frameid}">
            Your browser needs to support iframes!
        </iframe> 
       </xsl:when>
       <xsl:when test="$revision/a:contents/a:ContentTransform/a:transformed-by/* = 'http://rx4rdf.sf.net/ns/wiki#item-format-text'">
            <!-- note: this doesn't handle dynamically set text format -->
            <xsl:value-of disable-output-escaping='yes' 
                select="f:replace('&#10;','&lt;br />', f:escape-xml($contents))"/>      
       </xsl:when>
       <xsl:otherwise>       
          <xsl:value-of disable-output-escaping='yes' select="$contents" />  
       </xsl:otherwise>       
    </xsl:choose>
    <br clear='all' />
    <a href='site:///{wiki:name}' target='{$target}'>More...</a>&#xA0;<xsl:value-of select='wf:format-pytime( $revision/a:created-on, "%a, %d %b %Y %H:%M")' />
    by
    <!-- choose creator's url in this order: foaf:homepage, user's account url, email, account url (guest) -->
    <xsl:variable name='user-url' select='f:if($revision/dc:creator/*/foaf:homepage, $revision/dc:creator/*/foaf:homepage, 
          f:if($revision/dc:creator/*/foaf:holdsAccount, concat("site:///users/", $revision/dc:creator/*/foaf:holdsAccount/*/foaf:accountName),
          f:if($revision/dc:creator/*/foaf:mbox, $revision/dc:creator/*/foaf:mbox, concat("site:///accounts/", $revision/wiki:created-by/*/foaf:accountName)) ))' />
    <a href='{$user-url}' target='{$target}'>
    <!-- choose creator's name in this order: foaf:name, email, source ip, account name (guest) -->
    <xsl:value-of select='f:if($revision/dc:creator, 
                f:if($revision/dc:creator/*/foaf:name, $revision/dc:creator/*/foaf:name, $revision/dc:creator/*/foaf:mbox), 
                  f:if($revision/wiki:created-from, $revision/wiki:created-from, $revision/wiki:created-by/*/foaf:accountName) )'/>
    </a>
    <xsl:if test="$showedit">
        &#xA0;<a href='site:///{wiki:name}?action=edit' target='{$target}'>Edit</a>&#xA0;<a href='site:///{wiki:name}?action=edit-metadata' target='{$target}'>Edit Metadata</a>
    </xsl:if>
    <xsl:if test='wiki:about'>
     ( 
     <xsl:for-each select='wiki:about'>       
       <a taget='{$target}' href='site:///keywords/{local-name-from-uri(.)}?about={f:escape-url(.)}' >
       <xsl:value-of select='f:if(namespace-uri-from-uri(.)=concat($BASE_MODEL_URI,"kw#"),local-name-from-uri(.), name-from-uri(.))'/>
       </a>&#xa0;
     </xsl:for-each>
     )
    </xsl:if>
    
    <br/>
</xsl:template>

<xsl:template match="node()|@*" mode="dump">
<xsl:copy>
    <xsl:apply-templates select="node()|@*" mode="dump" />
</xsl:copy>
</xsl:template>
        
<xsl:template match="/" >
<xsl:variable name="results" select="wf:evaluate($searchExp)" />     
<!-- search result header -->
     <xsl:choose>

     <xsl:when test="starts-with($view,'rss')">
<xsl:variable name='content-type' select="wf:assign-metadata('_contenttype', 'application/xml')" />     
<xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete'])" />
<rss version="2.0">
<channel>
<title>Rhizome search for "<xsl:value-of select="$search" />"</title>
<generator>Rhizome 0.3 http://rhizome.liminalzone.org</generator>
<description>
This RSS feed is the result of applying the query "<xsl:value-of select="$search" />"
on <xsl:value-of select="$_base-url" />
</description>

<link><xsl:value-of select="$_url" /></link>

<xsl:for-each select="$results">
    <xsl:sort select="wf:evaluate($sortKey)" data-type="{$sortKeyType}" 
             order="{$sortKeyOrder}" case-order="{$sortKeyCaseOrder}"/> 
    <item>
       <xsl:variable name='relUrl' select="f:if(self::a:NamedContent, concat(./wiki:name, '?'), concat('.?about=', f:escape-url(.)))" />
       <title><xsl:value-of select="f:if(./wiki:name, ./wiki:name, f:if(./rdfs:label,./rdfs:label, name-from-uri(.)))" /></title>       
       <guid><xsl:value-of select="." /></guid>
       <link>       
       <xsl:value-of select="$_base-url" />site:///<xsl:value-of select="$relUrl" />
       </link>
    </item>
</xsl:for-each>    
    </channel>
</rss>
       </xsl:when>       

       <xsl:when test="$view = 'rxml'">
<div class="title"><xsl:value-of select="$searchType" /> Search Results for "<xsl:value-of select="$search" />"</div>
<xsl:if test='not($results)'>
No results found.
</xsl:if>
<pre>
<xsl:variable name='fixup' select="&quot;&lt;a href='site:///.?action=view-metadata&amp;amp;about=%(encodeduri)s'>%(res)s&lt;/a>&quot;" />
<xsl:value-of disable-output-escaping='yes' select="wf:serialize-rdf($results, 'rxml_zml', $fixup)" />
</pre>
       </xsl:when>
       <xsl:when test="$view = 'rdf'">
<xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete'])" />              
<!-- 'application/rdf+xml' is more correct but browser display the xml mimetype better --> 
<xsl:variable name='content-type' select="wf:assign-metadata('_contenttype', 'application/xml')" />               
<xsl:value-of select="wf:serialize-rdf($results, 'rdfxml')" disable-output-escaping='yes' />
       </xsl:when>
       <xsl:when test="$view = 'ntriples'">
<xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete'])" /> 
<xsl:variable name='_nextFormat' select="wf:assign-metadata('_nextFormat', 'http://rx4rdf.sf.net/ns/wiki#item-format-text')" />
<xsl:value-of select="wf:serialize-rdf($results,'ntriples')" disable-output-escaping='yes'/>
       </xsl:when>       
       <xsl:when test="$view = 'edit'">
<div class="title"><xsl:value-of select="$searchType" /> Search Results for "<xsl:value-of select="$search" />"</div>
<xsl:if test='not($results)'>
No results found.
</xsl:if>
<form method="POST" action="site:///save-metadata" accept-charset='UTF-8' enctype="multipart/form-data">	
    <input TYPE="hidden" NAME="itemname" VALUE="save-metadata" />
    <input TYPE="hidden" NAME="action" VALUE="save-metadata" />    
    <input type="hidden" name="rdfFormat" value="{$editFormat}"/>
    <xsl:for-each select="$results">    
        <input TYPE="hidden" NAME="resource" VALUE="{.}" />
    </xsl:for-each>
        Edit Metadata
         <br/>
	<textarea NAME="metadata" ROWS="30" COLS="75" STYLE="width:100%" WRAP="off">
	<xsl:value-of select="wf:serialize-rdf($results, $editFormat)" />
	</textarea>
	<br/>
	<input TYPE="submit" NAME="save" VALUE="Save" />	
</form>
       </xsl:when>
       <xsl:when test="$view = 'rxpathdom'">
<xsl:variable name='content-type' select="wf:assign-metadata('_contenttype', 'application/xml')" />               
<xsl:variable name='_disposition' select="wf:assign-metadata('_disposition', /*[.='http://rx4rdf.sf.net/ns/wiki#item-disposition-complete'])" />       
<RxPathDOM>       
<xsl:apply-templates select="$results" mode="dump" />
</RxPathDOM>       
       </xsl:when>       

       <xsl:when test="$view = 'summary'">
<div class="title"><xsl:value-of select="$searchType" /> Search Results for "<xsl:value-of select="$search" />" 
  (<xsl:value-of select="count($results)" /> found)</div>
<br />  
<xsl:call-template name='add-summary-javascript'/>
<div id='fixeddiv' >
<xsl:for-each select="$results">
  <xsl:sort select="wf:evaluate($sortKey)" data-type="{$sortKeyType}" 
       order="{$sortKeyOrder}" case-order="{$sortKeyCaseOrder}"/> 
  <xsl:call-template name='make-summary'/>
</xsl:for-each>
</div>
       </xsl:when>       
       <xsl:otherwise>         
<!-- html view -->
<div class="title"><xsl:value-of select="$searchType" /> Search Results for "<xsl:value-of select="$search" />" 
  (<xsl:value-of select="count($results)" /> found)</div>
<br />   
<xsl:choose> 
  <xsl:when test='count($results)=1 and count($results[self::text()])=1'>
  <!-- the result is just a text node -->
    <pre>
      <xsl:if test='string($results)'>
      <xsl:value-of select='$results' />
      </xsl:if>
      <xsl:if test='not(string($results))'>
      ""
      </xsl:if>
    </pre>
  </xsl:when>
  <xsl:otherwise>  
  <table>
    <xsl:variable name="properties-table" select="is-predicate($results[1])" />
    <xsl:variable name="long-table" select="$results[1][self::a:NamedContent]" />
    <xsl:if test='$long-table'>
        <tr><th></th><th>Name </th><th>Last Modified</th><th>By</th></tr> 
    </xsl:if>
    <xsl:if test='$properties-table'>
        <tr><th>Resource </th><th>Property</th><th>Value</th></tr> 
    </xsl:if>    
<xsl:for-each select="$results">
  <xsl:sort select="wf:evaluate($sortKey)" data-type="{$sortKeyType}" 
        order="{$sortKeyOrder}" case-order="{$sortKeyCaseOrder}"/> 

  <xsl:if test='not($properties-table)'>
    <xsl:variable name='relUrl' select="f:if(self::a:NamedContent, concat(./wiki:name, '?'), concat('.?about=', f:escape-url(.)))" />
    <xsl:variable name='resName' select="f:if(./wiki:name, ./wiki:name, f:if(./rdfs:label,./rdfs:label, name-from-uri(.)))" />
    
    <tr>
    <td><a href="site:///{$relUrl}&amp;action=edit" title='edit'><img border="0" alt='edit' src='site:///edit-icon.png' /></a></td>
    <td><a href="site:///{$relUrl}" ><xsl:value-of select='$resName' /></a></td>    
    <xsl:if test='$long-table'>
    <td><xsl:value-of select='wf:format-pytime( (./wiki:revisions/*/rdf:first/*)[last()]/a:created-on, "%a, %d %b %Y %H:%M")' /></td>
    <td>
        <xsl:choose>
         <xsl:when test="(./wiki:revisions/*/rdf:first/*)[last()]/wiki:created-by/*[foaf:accountName = 'guest']
                                               and (./wiki:revisions/*/rdf:first/*)[last()]/wiki:created-from">
            <xsl:value-of select='(./wiki:revisions/*/rdf:first/*)[last()]/wiki:created-from'/>
        </xsl:when>
        <xsl:otherwise>
            <a href='site:///accounts/{(./wiki:revisions/*/rdf:first/*)[last()]/wiki:created-by/*/foaf:accountName}'>
            <xsl:value-of select='(./wiki:revisions/*/rdf:first/*)[last()]/wiki:created-by/*/foaf:accountName'/></a>
        </xsl:otherwise>
        </xsl:choose>
    </td>    
    </xsl:if>
    <xsl:if test='not($long-table)'>    
    <td><a href='site:///search?search=%2F*%2F*%5B.%3D%27{f:escape-url(.)}%27%5D&amp;searchType=RxPath&amp;view=html'>Used By</a></td>        
    </xsl:if>
    </tr>        
  </xsl:if>    
  
  <xsl:if test='$properties-table'>        
    <xsl:variable name='subjectUrl' select="f:if(parent::a:NamedContent, concat(../wiki:name, '?'), concat('.?about=', f:escape-url(..)))" />
    <xsl:variable name='subjectName' select="f:if(../wiki:name, ../wiki:name, f:if(../rdfs:label,../rdfs:label, name-from-uri(..)))" />

    <xsl:variable name='predicateName' select="name(.)" />

    <xsl:variable name='isLiteral' select="boolean(text())" />
  
    <tr>    
    <td><a href="site:///{$subjectUrl}" ><xsl:value-of select='$subjectName' /></a></td>    

        <!-- /*/*[is-subproperty-of(@uri,'uri')] -->
    <td><a href='site:///search?search=%2F*%2F*%5Bis-subproperty-of%28%40uri%2C%27{f:escape-url(./@uri)}%27%29%5D&amp;searchType=RxPath&amp;view=html&amp;title=Property%20Usage'>
        <xsl:value-of select='$predicateName' /></a>
    </td>        
    
    <xsl:if test='$isLiteral'>        
        <td><xsl:value-of select='substring(text(),1,100)' /></td>    
    </xsl:if>        
    <xsl:if test='not($isLiteral)'>        
        <xsl:variable name='objectUrl' select="f:if(a:NamedContent, concat(wiki:name, '?'), concat('.?about=', f:escape-url(*)))" />
        <xsl:variable name='objectName' select="f:if(wiki:name,  wiki:name, f:if( rdfs:label, rdfs:label, name-from-uri(*)))" />        
        <td><a href="site:///{$objectUrl}" ><xsl:value-of select='$objectName' /></a></td>    
    </xsl:if>            
    </tr>        
  </xsl:if>    
</xsl:for-each>    
</table>
      </xsl:otherwise>
      </xsl:choose> 

<xsl:if test='not($results)'>
No results found.
</xsl:if>
<br/>
<!-- site-template.xsl uses $_rsslink -->
<a href='{wf:assign-metadata("_rsslink", concat($_base-url,"/search?view=rss&amp;search=", f:escape-url($search)) )}' type="application/rss+xml">
  <img border='0' src='site:///rss.png' alt='RSS .91 of this search'/></a>
      </xsl:otherwise>
      </xsl:choose> 

</xsl:template>
</xsl:stylesheet>