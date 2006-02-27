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
<xsl:import href='path:edit-tags.xsl' />
<xsl:output method='xhtml' omit-xml-declaration="yes" encoding="UTF-8" indent='no' />
<xsl:param name="about" />
<xsl:param name="_name" />
<xsl:param name="__account" />
<xsl:param name="action" />
<xsl:param name="BASE_MODEL_URI" />
<xsl:param name="metadata" />
<!-- todo: you can used these defaults to create a template -->
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

<xsl:variable name='namedContent' select="f:if($about, /*[.=$about], f:if($target, /*[wiki:name=$target]))" />
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

<!-- this edit page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />	

<xsl:variable name='_robots' select="wf:assign-metadata('_robots', 'nofollow,noindex')" />    

<script language="JavaScript">
<xsl:comment>
function resizeForIframe(iframeWin, iframeId, itemname)
{	
    var width = iframeWin.document.body.scrollWidth;
    var height = iframeWin.document.body.scrollHeight;    
    document.getElementById('previewFrame').style.height=(height+20)+'px';//change the height of the iframe
    if (iframeId != 'previewFrame')
    { //a gross little hack
      //save.xml sets the frameid variable used by the iframe-display-handler
      //with the new save time because save and reedit needs it so that there isn't a conflict when re-saving
      document.getElementById("startTime").value = iframeId;
      actionPageName = itemname;
      if (document.edit.itemname.type == 'text') {        
        //we must have just created the page, so change form to make the name immutable
        var title = document.getElementById('page-title');
        if (title) title.innerHTML = itemname;
        
        var newInput = null;
        if (document.all) {
            //IE won't let you change the "type" attribute on input elements 
            newInput = document.createElement("input type='hidden'");
        } else {
            newInput = document.createElement("input");        
            newInput.type = 'hidden';
        }        
        newInput.name = 'itemname';
        newInput.value = itemname;
        document.edit.replaceChild(newInput, document.edit.itemname);        

        var radio1 = document.edit.anonymous[0];        
        var radio2 = document.edit.anonymous[1];
        radio1.parentNode.removeChild(radio1);
        radio2.parentNode.removeChild(radio2);
        var anonLabel = document.getElementById('anonymous-label');
        anonLabel.parentNode.removeChild(anonLabel);        
        var nameLabel = document.getElementById('name-label');        
        nameLabel.parentNode.removeChild(nameLabel);
      }      
    }
}

var actionPageName = '<xsl:value-of select="f:if($item,$itemname,'save')"/>';

function OnSubmitEditForm()
{
  var actionField = document.getElementById("action")
  if (actionField != null)
     actionField.parentNode.removeChild(actionField);     

  if(document.editFormPressed == 'Preview') {
   document.edit.action ="site:///preview?frameid=previewFrame";
   document.edit.target ="preview";
  } else if(document.editFormPressed == 'Save' || 
        document.editFormPressed == 'Save (keep editing)') {	
    reedit = document.editFormPressed == 'Save (keep editing)'    
    document.edit.action ="site:///"+actionPageName;
    if (reedit) {    
        //goes in preview iframe
        document.edit.target ="preview";               
        document.edit.action += '?_itemHandlerDisposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-short-display' 
    } else {
        document.edit.target ="_self";
    }

    var newEditAction = document.getElementById("startTime").cloneNode(false)
    newEditAction.name = 'action'
    newEditAction.id = 'action'
    //if creating a page for the first time set action to 'creation'
    newEditAction.value = actionPageName == 'save' ? 'creation' : 'save'; 
    document.edit.appendChild(newEditAction);
  }
  return true;
}
//</xsl:comment>
</script>

<form name="edit" method="POST" accept-charset="UTF-8" onSubmit="return OnSubmitEditForm();" 
    action="site:///{f:if($item,$itemname, 'save')}" enctype="multipart/form-data">    
	<xsl:if test='string-length($itemname) > 0'>		
	    <input type="hidden" name="itemname" value="{$itemname}" />
	    <xsl:if test="not(wf:has-metadata('title'))">
	        <xsl:variable name='title' select="wf:assign-metadata('title', concat('Editing ', $itemname))" />
	    </xsl:if>
	</xsl:if>	
	<xsl:if test='string-length($itemname)=0'>
	    <input type="radio" name="anonymous" checked="checked" value="" /> 
	    <label id='name-label' for="itemname">name</label><input type="text" name="itemname" value="" size="20" MAXLENGTH="100" />	    
	    <input type="radio" name="anonymous" value="on" /><label id='anonymous-label' for="anonymous">Anonymous</label>
	    <xsl:if test="not(wf:has-metadata('title'))">
	        <xsl:variable name='title' select="wf:assign-metadata('title', 'New Item')" />
	    </xsl:if>
	    <br/>
    </xsl:if>
    <label for='title'>Title</label> <input type="text" name="title" value="{$item/wiki:title}" size="80" MAXLENGTH="100" />
    <br/>
	<input type="hidden" name="startTime" id="startTime" value="{wf:current-time()}" />
	Upload File:<input type='file' name='file' />
	<xsl:choose>
    <xsl:when test="$item/a:contents/a:ContentTransform/a:transformed-by = 'http://rx4rdf.sf.net/ns/wiki#item-format-binary'">         	    
      <br/>The content of the item is in binary format and can not be edited. To modify the content, upload a replacement.
      If you don't want to modify the content, edit its metadata <a href='site:///{$itemname}?action=edit-metadata'>here</a> --
      saving this page without uploading a file will result in an item with no content!
    </xsl:when>
    <xsl:otherwise>
    	<xsl:variable name="contents" select="wf:get-contents($item)" />
    	 OR edit text here: <br />
    	<textarea name="contents" rows="20" cols="65" style="width:100%" wrap="virtual">
    	<xsl:value-of select="$contents" />
    	</textarea>
	</xsl:otherwise>
	</xsl:choose>
	<br />
	<div style='font-size: smaller'>
	Source Format:
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
	&#xa0;<label for='keywords'><a href='site:///keywords'>Keywords:</a>&#xa0;</label>
		
    <xsl:call-template name='write-keywords'>
      <xsl:with-param name='topics' select='$namedContent/wiki:about' />
    </xsl:call-template>        
    <div id='less' style='border: 1px'><button type='button' onclick="document.getElementById('less').style.display='none'; 
    document.getElementById('more').style.display='block';">More>></button></div>
    <div id='more' style='border: 1px; display: none'>    
    <button type='button' onclick="document.getElementById('more').style.display='none'; 
    document.getElementById('less').style.display='block';">&lt;&lt;Less</button>
    <!--
    Output type: 
	<select name="doctype" size="1" width="100">
	    <xsl:call-template name="add-option" >
	        <xsl:with-param name="text">N/A</xsl:with-param>
	        <xsl:with-param name="value" />
	        <!-!- select this only when the item exists and it has no doctype -!->
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
	-->
	Item&#xa0;type:&#xa0;<select name="disposition" size="1" width="100">	
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
	    <xsl:variable name="tokens" select="($__account | $__account/auth:has-role/*)/auth:can-assign-guard/* | $namedContent/auth:guarded-by/*" />
	    <xsl:call-template name="add-option" >
	        <xsl:with-param name="text">Public</xsl:with-param>
	        <xsl:with-param name="value" />
	    </xsl:call-template>		
        <xsl:for-each select="$tokens">
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label/text()" />
                <xsl:with-param name="value" select="." />
                <xsl:with-param name="selected" select="f:if($namedContent, 
                    . = ($namedContent/auth:guarded-by/*), 
                    . = f:if($__account/wiki:default-edit-token, $__account/wiki:default-edit-token, 
                        $__account/auth:has-role/*/wiki:default-edit-token))" />                
            </xsl:call-template>
	    </xsl:for-each>
	</select>	
	&#xa0;<label for='label'>Label:&#xa0;</label><select name="label" size="1" width="100">	
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
                    $i = f:if($__account/wiki:default-edit-label, $__account/wiki:default-edit-label, 
                        $__account/auth:has-role/*/wiki:default-edit-label))" />
            </xsl:call-template>
    	</xsl:for-each>
	</select>		
    <br /><input type="checkbox" name="shred" value="on" checked='checked' /><label for='shred'>Shred.</label>
	&#xa0;<label for='change_comment'>Change comment:&#xa0;</label><input type="text" name="change_comment" value="" size="60" MAXLENGTH="200" />
	</div>
    </div>	
	<input type="SUBMIT" name="preview" onClick="document.editFormPressed=this.value" value="Preview" />	
    &#xa0;<input type="SUBMIT" name="save" onClick="document.editFormPressed=this.value" value="Save" />      
    &#xa0;<input type="SUBMIT" name="save" onClick="document.editFormPressed=this.value" value="Save (keep editing)" />      
    &#xa0;<input type="checkbox" name="minor_edit" value="on" /><label for='minor_edit'>This is a minor edit.</label>
    <xsl:if test="$metadata" >
        <input type="hidden" name="metadata" value="{$metadata}" />
    </xsl:if>
    </form>
    <iframe src='' name='preview' id='previewFrame' width='100%' height='0'/>

<a href="site:///ZML">ZML</a> Formatting Quick Reference (see <a href="site:///TextFormattingRules">TextFormattingRules</a> for more info)
<pre class="code">
----             Horizontal ruler
                 Blank line starts a new paragraph.
 text            A space at the beginning of a line continues the previous line.
[text|ann; link] Create a hyperlink where "link" can be either an internal 
                 page name or an external URL (e.g http://...) and "ann"  
                 is an annotation. Any of these parts may be omitted.
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
&lt;                (In first column) Create XML markup (see <a href="site:///ZMLMarkupRules">ZML Markup Rules</a>).
</pre>
</xsl:template>
</xsl:stylesheet>