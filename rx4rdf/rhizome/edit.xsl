<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:a="http://rx4rdf.sf.net/ns/archive#"
		xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
		xmlns:wf='http://rx4rdf.sf.net/ns/racoon/xpath-ext#'
		xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
		xmlns:f = 'http://xmlns.4suite.org/ext'
		xmlns:response-header = 'http://rx4rdf.sf.net/ns/racoon/http-response-header#'
		xmlns:auth="http://rx4rdf.sf.net/ns/auth#"
		exclude-result-prefixes = "rdfs f wf a wiki rdf response-header auth" >
<xsl:output method='html' indent='no' />
<xsl:param name="_name" />
<xsl:param name="__user" />
<xsl:param name="action" />
<xsl:variable name='target'>
     <xsl:choose>
        <xsl:when test="$action"><xsl:value-of select="$_name" /></xsl:when>
        <xsl:otherwise></xsl:otherwise> <!-- no action, assume new item (set $target="") -->
    </xsl:choose> 
</xsl:variable>

<!-- this edit page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />

<xsl:variable name='namedContent' select="/*[wiki:name/text()=$target]" />
<xsl:variable name='item' select="($namedContent/wiki:revisions/*/rdf:first/*)[last()]" />

<xsl:variable name="contents" select="wf:get-contents($item)" />

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
	
<xsl:template match="/" name="edit-main" >
<xsl:param name="itemname" select="$target" />

<script language="JavaScript">
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
    var newEditAction = document.getElementById("startTime").cloneNode(false)
    newEditAction.name = 'action'
    newEditAction.id = 'action'
    newEditAction.value = "<xsl:value-of select="f:if($item,'save','creation')"/>"
    document.edit.appendChild(newEditAction)
    
    document.edit.action ="site:///<xsl:value-of select="f:if($item,$itemname, 'save')"/>";
    document.edit.target ="_self";
  }
  return true;
}
</script>

<form name="edit" METHOD="POST" onSubmit="return OnSubmitEditForm();" ACTION="site:///{f:if($item,$itemname, 'save')}" ENCTYPE="multipart/form-data">
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
	Upload File:<input TYPE='file' name='file' /> OR edit text here: <br />
	<textarea NAME="contents" ROWS="20" COLS="65" STYLE="width:100%" WRAP="virtual">
	<xsl:value-of select="$contents" />
	</textarea>
	<br />
	<br />Source Format:
	<select name="format" size="1" width="100">
        <xsl:for-each select="/wiki:ItemFormat">
            <xsl:variable name="i" select="./@rdf:about" />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label/text()" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" select="f:if($item, $item//a:contents/*/a:transformed-by/*/@rdf:about[.=$i], $i='http://rx4rdf.sf.net/ns/wiki#item-format-rhizml')" />
            </xsl:call-template>
	</xsl:for-each>
	</select>
    &#xa0;Output Document Type 
	<select name="doctype" size="1" width="100">
	    <xsl:call-template name="add-option" >
	        <xsl:with-param name="text">N/A</xsl:with-param>
	        <xsl:with-param name="value" />
	        <!-- select this only when the item exists and it has no doctype -->
	        <xsl:with-param name="selected" select="f:if($item, not($item/wiki:doctype))" />
	    </xsl:call-template>	
        <xsl:for-each select="/wiki:DocType">
            <xsl:variable name="i" select="./@rdf:about" />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label/text()" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" select="f:if($item/wiki:doctype[.=$i], true())" />
            </xsl:call-template>
	</xsl:for-each>
	</select>    
	Item&#xa0;Type:&#xa0;<select name="disposition" size="1" width="100">	
        <xsl:for-each select="/wiki:ItemDisposition">
            <xsl:variable name="i" select="./@rdf:about" />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label/text()" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" select="f:if($item, $item/wiki:item-disposition/*/@rdf:about[.=$i], $i='http://rx4rdf.sf.net/ns/wiki#item-disposition-entry')" />
            </xsl:call-template>
	</xsl:for-each>
	</select>
	Sharing
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
	        <!-- select this only when the item exists and it has no doctype -->
	        <xsl:with-param name="selected" select="f:if($item, not($item/wiki:label))" />
	    </xsl:call-template>		
        <xsl:for-each select="/wiki:Label">
            <xsl:variable name="i" select="./@rdf:about" />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" select="f:if($item, 
                    $item/wiki:has-label/*[.=$i], $i='http://rx4rdf.sf.net/ns/wiki#label-released')" />
            </xsl:call-template>
    	</xsl:for-each>
	</select>		
	<br />
	<input TYPE="checkbox" NAME="minor_edit" VALUE="on" />This change is a minor edit.<br/>

	<input TYPE="SUBMIT" name="preview" onClick="document.editFormPressed=this.value" VALUE="Preview" />
    &#xa0;<input TYPE="SUBMIT" name="save" onClick="document.editFormPressed=this.value" VALUE="Save" />
    </form>
    <iframe src='' name='preview' id='previewFrame' width='100%' height='0'/>

<a href="site:///RhizML">RhizML</a> Formatting Quick Reference (see <a href="site:///TextFormattingRules">TextFormattingRules</a> for more info)
<pre class="code">
----             Horizontal ruler
                 Blank line starts a new paragraph
[text|ann; link] Create a hyperlink. where "link" can be either an internal 
		 page name or an external link (e.g http://).  
		 Both annotation and text may be omitted.
*                Make a bulleted list (must be in first column). Use more (**) 
                 for deeper indentations.
#                Make a numbered list (must be in first column). Use more (##, ###) 
                 for deeper indentations.
:                Indent line (must be in first column). Use more (::, ::) 
                 for deeper indentations.
::		 (on a line by itself) Start (or end) a block quote.
+term=def        Defines 'term' with 'def'.  
!, !!, !!!       Start a line with an exclamation mark (!) to make a heading. 
                 !! makes a sub-heading, !!! a sub-sub-heading, etc. (up to 6)
__bold__         Makes text bold.
//italic//       Makes text in italics (notice that these are single quotes ('))
^^monospace^^    Makes text in monospaced font.
|text|more text| Makes a table. Double bars for a table heading.
~~               Creates a line break without starting a new paragraph
\                If in-line: Prints the next formatting character as is. 
                 At end of line: Treat next line as continuation of this line.  
</pre>
</xsl:template>
</xsl:stylesheet>