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
		exclude-result-prefixes = "rdfs f wf a wiki rdf response-header auth" >
<xsl:output method='html' indent='no' />
<xsl:param name="about" />
<xsl:param name="_name" />
<xsl:param name="__user" />
<xsl:param name="action" />
<!-- todo: you can used these faults to create a template -->
<xsl:param name="nameDefault" />
<xsl:param name="titleDefault" />
<xsl:param name="contentsDefault" />
<xsl:param name="keywordsDefault" />
<xsl:param name="anonymousDefault" />
<xsl:param name="changeCommentDefault" />
<xsl:param name="sourceFormatDefault" select='"http://rx4rdf.sf.net/ns/wiki#item-format-zml"'/>
<xsl:param name="docTypeDefault" />
<xsl:param name="itemTypeDefault" select='"http://rx4rdf.sf.net/ns/wiki#item-disposition-entry"'/>
<xsl:param name="labelDefault" select='"http://rx4rdf.sf.net/ns/wiki#label-released"'/>
<xsl:param name="sharingDefault" />
<xsl:param name="minorEditDefault" />

<xsl:variable name='target'>
     <xsl:choose>
        <xsl:when test="$action='edit'"><xsl:value-of select="f:if($about, /*[.=$about]/wiki:name, $_name)" /></xsl:when>
        <xsl:otherwise></xsl:otherwise> <!-- no action, assume new item (set $target="") -->
    </xsl:choose> 
</xsl:variable>

<xsl:variable name='namedContent' select="f:if($about, /*[.=$about], /*[wiki:name=$target])" />
<xsl:variable name='item' select="($namedContent/wiki:revisions/*/rdf:first/*)[last()]" />

<xsl:template name="add-option" >
<xsl:param name="text" />
<xsl:param name="value" />
<xsl:param name="selected" />
	<option value="{$value}">
	<xsl:if test='$selected'>
		<xsl:attribute name='selected'>selected</xsl:attribute>
	</xsl:if>
	<xsl:value-of select='$text' />
	</option>
</xsl:template>

<xsl:template name="get-keywords">
<xsl:param name="topics" />
    <xsl:value-of select='$topics[1]' />
    <xsl:if test='$topics[2]'>,
        <xsl:call-template name="get-keywords">
        <xsl:with-param name="topics" select="$topics[position()!=1]" />
        </xsl:call-template>
    </xsl:if>
</xsl:template>
	
<xsl:template match="/" name="edit-main" >
<xsl:param name="itemname" select="$target" />
<!-- we duplicate these params so you can call this template from another 
     stylesheet with your own params -->
<xsl:param name="nameDefault" select='$nameDefault'/>
<xsl:param name="titleDefault" select='$titleDefault'/>
<xsl:param name="contentsDefault" select='$contentsDefault'/>
<xsl:param name="keywordsDefault" select='$keywordsDefault'/>
<xsl:param name="anonymousDefault" select='$anonymousDefault'/>
<xsl:param name="changeCommentDefault" select='$changeCommentDefault'/>
<xsl:param name="sourceFormatDefault" select='$sourceFormatDefault'/>
<xsl:param name="docTypeDefault" select='$docTypeDefault'/>
<xsl:param name="itemTypeDefault" select='$itemTypeDefault'/>
<xsl:param name="labelDefault" select='$labelDefault'/>
<xsl:param name="sharingDefault" select='$sharingDefault'/>
<xsl:param name="minorEditDefault" select='$minorEditDefault'/>

<script language="JavaScript">
function resizeForIframe(iframeWin, iframeId)
{	
    var width = iframeWin.document.body.scrollWidth
    var height = iframeWin.document.body.scrollHeight

    document.getElementById(iframeId).style.height=height+20;//change the height of the iframe
}

function OnSubmitEditForm()
{
  if(document.editFormPressed == 'Preview')
  {
   document.edit.action ="site:///preview";
   document.edit.target ="preview";
   var actionField = document.getElementById("action")
   if (actionField != null)
        actionField.parentNode.removeChild(actionField);     
  }
  else
  if(document.editFormPressed == 'Save')
  {	
    document.edit.action ="site:///<xsl:value-of select="f:if($item,$itemname,'save')"/>";
    document.edit.target ="_self";

    var newEditAction = document.getElementById("startTime").cloneNode(false)
    newEditAction.name = 'action'
    newEditAction.id = 'action'
    newEditAction.value = "<xsl:value-of select="f:if($item,'save','creation')"/>";
    document.edit.appendChild(newEditAction);
  }
  return true;
}
</script>

<form name="edit" method="POST" onSubmit="return OnSubmitEditForm();" action="site:///{f:if($item,$itemname, 'save')}" enctype="multipart/form-data">
    <!-- <input TYPE="hidden" NAME="action" VALUE="{f:if($item,'save','creation')}" />  -->
	<xsl:if test='string-length($itemname) > 0'>		
	    <input TYPE="hidden" NAME="itemname" VALUE="{$itemname}" />
	    <xsl:variable name='title' select="wf:assign-metadata('title', concat('Editing ', $itemname))" />
	</xsl:if>	
	<xsl:if test='string-length($itemname)=0'>
	    <input TYPE="radio" NAME="anonymous" checked="checked" VALUE="" /> 
	    <label for="itemname">Name</label><input TYPE="text" NAME="itemname" VALUE="" SIZE="20" MAXLENGTH="100" />	    
	    <input TYPE="radio" NAME="anonymous" VALUE="on" /><label for="anonymous">Anonymous</label>
	    <xsl:variable name='title' select="wf:assign-metadata('title', 'New Item')" />
	    <br/>
    </xsl:if>
    <label for='title'>Title</label> <input TYPE="text" NAME="title" VALUE="{$item/wiki:title}" SIZE="80" MAXLENGTH="100" />
    <br/>
	<input TYPE="hidden" NAME="startTime" id="startTime" VALUE="{wf:current-time()}" />
	Upload File:<input TYPE='file' name='file' />
	<xsl:choose>
    <xsl:when test="$item/a:contents/a:ContentTransform/a:transformed-by = 'http://rx4rdf.sf.net/ns/wiki#item-format-binary'">         	    
      <br/>The content of the item is in binary format and can not be edited. To modify the content, upload a replacement.
      If you don't want to modify the content, edit its metadata <a href='site:///{$itemname}?action=edit-metadata'>here</a> --
      saving this page without uploading a file will result in an item with no content!
    </xsl:when>
    <xsl:otherwise>
    	<xsl:variable name="contents" select="wf:get-contents($item)" />
    	 OR edit text here: <br />
    	<textarea NAME="contents" ROWS="20" COLS="65" STYLE="width:100%" WRAP="virtual">
    	<xsl:value-of select="$contents" />
    	</textarea>
	</xsl:otherwise>
	</xsl:choose>
	<br />
	<br />Source Format:
	<select name="format" size="1" width="100">
        <xsl:for-each select="/wiki:ItemFormat">
            <xsl:variable name="i" select="." />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" 
                  select="f:if($item, $item//a:contents/*/a:transformed-by[.=$i], 
                   $i='http://rx4rdf.sf.net/ns/wiki#item-format-zml')" />
            </xsl:call-template>
	</xsl:for-each>
	</select>
    &#xa0;Output Document Type: 
	<select name="doctype" size="1" width="100">
	    <xsl:call-template name="add-option" >
	        <xsl:with-param name="text">N/A</xsl:with-param>
	        <xsl:with-param name="value" />
	        <!-- select this only when the item exists and it has no doctype -->
	        <xsl:with-param name="selected" select="f:if($item, not($item/wiki:doctype))" />
	    </xsl:call-template>	
        <xsl:for-each select="/wiki:DocType">
            <xsl:variable name="i" select="." />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" select="f:if($item/wiki:doctype[.=$i], true())" />
            </xsl:call-template>
	</xsl:for-each>
	</select>    
	Item&#xa0;Type:&#xa0;<select name="disposition" size="1" width="100">	
        <xsl:for-each select="/wiki:ItemDisposition">
            <xsl:variable name="i" select="." />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" 
                  select="f:if($item, $item/wiki:item-disposition[.=$i], 
                       $i='http://rx4rdf.sf.net/ns/wiki#item-disposition-entry')" />
            </xsl:call-template>
	</xsl:for-each>
	</select>
	Sharing:
	<select name="authtoken" size="1" width="100">	
	    <xsl:variable name="tokens" select="$__user/auth:has-rights-to/* | $__user/auth:has-role/*/auth:has-rights-to/*" />
	    <xsl:call-template name="add-option" >
	        <xsl:with-param name="text">Public</xsl:with-param>
	        <xsl:with-param name="value" />
	    </xsl:call-template>		
        <xsl:for-each select="$tokens">
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label/text()" />
                <xsl:with-param name="value" select="." />
                <xsl:with-param name="selected" select=". = ($namedContent/auth:guarded-by/*)" />
            </xsl:call-template>
	    </xsl:for-each>
	</select>
	&#xa0;Label:&#xa0;<select name="label" size="1" width="100">	
	    <xsl:call-template name="add-option" >
            <xsl:with-param name="text" select="''" />
            <xsl:with-param name="value" select="''" />
	        <!-- select this only when the item exists and it has no label -->
	        <xsl:with-param name="selected" select="f:if($item, not($item/wiki:label))" />
	    </xsl:call-template>		
        <xsl:for-each select="/wiki:Label">
            <xsl:variable name="i" select="." />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" select="f:if($item, 
                    $i = $item/wiki:has-label, 
                    $i = f:if($__user/wiki:default-edit-label, $__user/wiki:default-edit-label, 
                        $__user/auth:has-role/*/wiki:default-edit-label))" />
            </xsl:call-template>
    	</xsl:for-each>
	</select>		
	<br />
	<input TYPE="checkbox" NAME="minor_edit" VALUE="on" />This is a minor edit.
	&#xa0;<label for='change_comment'>Change comment:&#xa0;</label><input TYPE="text" NAME="change_comment" VALUE="" SIZE="60" MAXLENGTH="200" />
    <br/>
    <xsl:variable name='keywords'>
         <xsl:for-each select='$namedContent/wiki:about'>          
           <xsl:value-of select='f:if(namespace-uri-from-uri(.)="http://rx4rdf.sf.net/ns/kw#",local-name-from-uri(.), name-from-uri(.))'/>
           <xsl:text> </xsl:text>
         </xsl:for-each>
    </xsl:variable>    
	&#xa0;<label for='keywords'><a href='site:///keywords'>Keywords:</a>&#xa0;</label><input TYPE="text" NAME="keywords" VALUE="{$keywords}" SIZE="80" MAXLENGTH="200" />
    <br/>
	<input TYPE="SUBMIT" name="preview" onClick="document.editFormPressed=this.value" VALUE="Preview" />	
    &#xa0;<input TYPE="SUBMIT" name="save" onClick="document.editFormPressed=this.value" VALUE="Save" />      
    </form>
    <iframe src='' name='preview' id='previewFrame' width='100%' height='0'/>

<a href="site:///ZML">ZML</a> Formatting Quick Reference (see <a href="site:///TextFormattingRules">TextFormattingRules</a> for more info)
<pre class="code">
----             Horizontal ruler
                 Blank line starts a new paragraph.
 text            A space at the beginning of a line continues the previous line.
[text|ann; link] Create a hyperlink. where "link" can be either an internal 
                 page name or an external link (e.g http://...).  
                 Both annotation and text may be omitted.
*                Make a bulleted list (must be in first column). Use more (**) 
                 for deeper indentations.
1.               Make a numbered list (must be in first column). Use more (11.)
                 for deeper indentations.
:                Indent line (must be in first column). Use more (::, :::) 
                 for deeper indentations.
::               (on a line by itself) Start (or end) a block quote.
+term=def        Defines 'term' with 'def'.  
!, !!, !!!       Start a line with an exclamation mark (!) to make a heading. 
                 !! makes a sub-heading, !!! a sub-sub-heading, etc. (up to 6)
__bold__         Makes text bold.
//italic//       Makes text in italics
^^monospace^^    Makes text in monospaced font.
|text|more text| Makes a table. Use double bars for a table heading.
~~               Creates a line break without starting a new paragraph
\                Prints the next formatting character as is. 
'''text'''       Plain text (no formatting). Can span across lines.       
p'''text'''      Plain text with spacing preserved. Can span across lines.
&lt;                (In first column) Create XML markup (see <a href="site:///ZML">ZML Markup Rules</a>).
</pre>
</xsl:template>
</xsl:stylesheet>