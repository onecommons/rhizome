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
		exclude-result-prefixes = "rdfs f wf a wiki rdf response-header" >
<xsl:output method='html' indent='no' />
<xsl:param name="_name" />
<xsl:param name="action" />
<xsl:variable name='target'>
     <xsl:choose>
        <xsl:when test="$action"><xsl:value-of select="$_name" /></xsl:when>
        <xsl:otherwise></xsl:otherwise> <!-- no action, assume new item (set $target="") -->
    </xsl:choose> 
</xsl:variable>

<!-- this edit page is always html, not the content's mimetype -->
<xsl:variable name='content-type' select="wf:assign-metadata('response-header:content-type', 'text/html')" />

<xsl:variable name='item' select="/*[wiki:name/text()=$target]/wiki:revisions/*[last()]" />

<xsl:variable name="contents">
     <xsl:choose>
        <xsl:when test="$item//a:contents/text()"><xsl:value-of select="$item//a:contents/text()" /></xsl:when>
        <xsl:otherwise><xsl:value-of select="wf:openurl($item//a:contents/a:ContentLocation/@rdf:about)" /></xsl:otherwise>
    </xsl:choose> 
</xsl:variable>

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
<form METHOD="POST" ACTION="{f:if($item,$itemname, 'save')}" ENCTYPE="multipart/form-data">
    <input TYPE="hidden" NAME="action" VALUE="{f:if($item,'save','creation')}" />    
	<xsl:if test='string-length($itemname) > 0'>		
	    <input TYPE="hidden" NAME="itemname" VALUE="{$itemname}" />
	    <xsl:variable name='title' select="wf:assign-metadata('title', concat('Editing ', $itemname))" />
	</xsl:if>	
	<xsl:if test='string-length($itemname)=0'>
	    Name <input TYPE="text" NAME="itemname" VALUE="" SIZE="20" MAXLENGTH="100" />	    
	    <xsl:variable name='title' select="wf:assign-metadata('title', 'New Item')" />
    </xsl:if>
    Title <input TYPE="text" NAME="title" VALUE="{$item/wiki:title}" SIZE="80" MAXLENGTH="100" />
    <br/>
	<input TYPE="hidden" NAME="startTime" VALUE="{wf:current-time()}" />
	Upload File:<input TYPE='file' name='file' /><br /> OR edit text here: <br />
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
                <xsl:with-param name="selected" select="f:if($item, $item//a:transformed-by/*/@rdf:about[.=$i], $i='http://rx4rdf.sf.net/ns/wiki#item-format-rhizml')" />
            </xsl:call-template>
	</xsl:for-each>
	</select>
    <br />Output Document Type 
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
	<br />Item Type:
	<select name="disposition" size="1" width="100">	
        <xsl:for-each select="/wiki:ItemDisposition">
            <xsl:variable name="i" select="./@rdf:about" />
            <xsl:call-template name="add-option" >
                <xsl:with-param name="text" select="rdfs:label/text()" />
                <xsl:with-param name="value" select="$i" />
                <xsl:with-param name="selected" select="f:if($item, $item/wiki:item-disposition/*/@rdf:about[.=$i], $i='http://rx4rdf.sf.net/ns/wiki#item-disposition-entry')" />
            </xsl:call-template>
	</xsl:for-each>
	</select>
	<br />
	<input TYPE="checkbox" NAME="minor_edit" VALUE="on" />This change is a minor edit.<br/>
	<input TYPE="submit" NAME="save" VALUE="Save" />
		
	<!-- todo: <input TYPE="submit" NAME="preview" VALUE="Preview" /> -->	
</form>
<a href="RhizML">RhizML</a> Formatting Quick Reference (see <a href="TextFormattingRules">TextFormattingRules</a> for more info)
<pre class="code">
----             Horizontal ruler
[text|ann; link] Create a hyperlink. where "link" can be either an internal 
		 page name or an external link (e.g http://).  
		 Both annotation and text may be omitted.
*                Make a bulleted list (must be in first column). Use more (**) 
                 for deeper indentations.
#                Make a numbered list (must be in first column). Use more (##, ###) 
                 for deeper indentations.
:                Indent line
::		 (on a line by itself) Start (or end) a block quote.
+term=def        Defines 'term' with 'def'.  
!, !!, !!!       Start a line with an exclamation mark (!) to make a heading. 
                 !! makes a sub-heading, !!! a sub-sub-heading, etc. (up to 6)
__bold__         Makes text bold.
//italic//       Makes text in italics (notice that these are single quotes ('))
^^monospace^^    Makes text in monospaced font.
|text|more text| Makes a table. Double bars for a table heading.
\                If in-line: Use to escape these special formatting characters. 
                 At end of line: Treat next line as continuation of this line.                               
</pre>
</xsl:template>
</xsl:stylesheet>