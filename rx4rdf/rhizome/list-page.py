param = locals().get('param', None)
sort = locals().get('sort', None)
if type == 'search':
    searchTitle = "Search Results"
    if type == 'regex':
        #regex:test(., $param)
        xpath = '*[has-content/text()[contains(string(.),' +param+ ')]] | *[wiki:summary/text()[contains(string(.),' +param+ ')]]'
elif type == 'versions':
    searchTitle = "All Versions of " + param
    xpath = '*[@about=%s]/has-expression/*//prior-version/*' % param
elif type == 'recent':
    searchTitle = "Changes to Pages Since " + param
    xpath = 'NamedContent/has-expression/*[date(last-modified/text())>date(%s)]/../..' % param
elif type == 'all':
    searchTitle = "All Pages"
    xpath = '*[wiki:name]'
else:
    raise "<b>list</b> failed: unknown type" #how to invoke error handlers propery?
styleSheet = '''<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:regex="http://exslt.org/regular-expressions"
        exclude-result-prefixes = "regex a wiki rdf" 
        >
<xsl:template match="/">
    <div class="title">%(searchname)s</div>
    <br />
    <table>
    <xsl:for-each select="%(xpath)s">
        <tr><td><a href="{./wiki:name/text()}?action=edit" ><img border="0" src='edit-icon.png' /></a></td>
        <td><a href="{./wiki:name/text()}" ><xsl:value-of select='./wiki:name/text()' /></a></td></tr>        
    </xsl:for-each>
    </table>
</xsl:template>
</xsl:stylesheet>
''' %  { 'searchname' : searchTitle, 'xpath' : xpath }
title = 'Search'
print __requestor__.server.transform(styleSheet)
