<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
		xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
		exclude-result-prefixes = "" >

<xsl:param name="_base-url" />

<xsl:template match="/" >
Rhizome includes a simple implementation of <a href="del.icio.us">Del.icio.us</a>-style collaborative bookmarks. By adding one of the "bookmarklets" below (aka "favlet" -- basically, a browser bookmark that invokes an action instead of going to a web page)
you can add a bookmark of the current page you are visiting to your Rhizome server. 

<h2>Setup and Use</h2>
<ol>
<li> Add the bookmarklet to your browser's Bookmarks tool bar or Favorites folder:
<h3>Firefox</h3>
Right click on this <a alt='Rhizome bookmarklet' href="javascript:q=location.href;p=document.title;e=encodeURIComponent;pw=open('{$_base-url}/edit-bookmark?url='+e(q)+'&amp;title='+e(p)+'&amp;notes='+e(getSelection()),'smallActionPopup', 'toolbar=no,width=500,height=550');T=setTimeout('pw.focus()',200);void(0);">Rhizome bookmarklet</a> and choose "Bookmark this link...".

<h3>Internet Explorer</h3>

Right click on this <a alt='Rhizome bookmarklet' href="javascript:q=location.href;d=document;p=d.title;e=encodeURIComponent;pw=open('{$_base-url}/edit-bookmark?url='+e(q)+'&amp;title='+e(p)+'&amp;notes='+e(d.selection?d.selection.createRange().text:''),'smallActionPopup','toolbar=no,width=500,height=500');void(0);">Rhizome bookmarklet</a> and choose "Add to Favorites...".
(You will get a message that says the link may be unsafe - click OK to accept this.)
</li>

<li>When visiting a page you want to bookmark, click on the bookmarklet -- this will invoke an <i>Add Bookmark</i> popup window. 
The current page's URL, title, and the text of the current selection (if there is one) will populate the form in the window.
</li>

<li>To find the bookmark after you've added it: if you've added keywords to your bookmark, you can find it through the <a href="site:///keyword-browser">Browse by Keyword</a> page, or  
you can view all bookmarks <a href="site:///search?search=%2F*%5Bis-instance-of%28.%2C%27http%3A//rx4rdf.sf.net/ns/wiki%23Bookmark%27%29%5D&amp;searchType=RxPath&amp;view=list">here</a>.
</li>
</ol>

</xsl:template>
</xsl:stylesheet>