<?xml version="1.0" encoding="ISO-8859-1"?>
<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
        xmlns:f = 'http://xmlns.4suite.org/ext'
        xmlns:response-header='http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
        xmlns:previous = 'http://rx4rdf.sf.net/ns/raccoon/previous#'
        xmlns:session = 'http://rx4rdf.sf.net/ns/raccoon/session#'
        exclude-result-prefixes = "f wf a wiki rdf response-header previous session" >		

<!-- this template references templates in site-template.xsl and assumes it is imported by it -->
<xsl:template name="theme-body" >

<body class="page">
	<table id="body-table">
  		<tr>
  			<td colspan="3" id="header-container-row" class="header">
  			<table id="header-table">
  			<tr>
	  			<td id="header-cell-left">
	  				<xsl:variable name='header-image' select="/*[wiki:name='site-template']/wiki:header-image"/>
					<xsl:if test="$header-image">
					<a href="site:///index"><img src="site:///{/*[wiki:name='site-template']/wiki:header-image}" alt="logo" id="logo"/></a> 
					</xsl:if>
				</td>
				<td>
					<div id="header-title">
						<xsl:value-of disable-output-escaping='yes' select="/*[wiki:name='site-template']/wiki:header-text" />
					</div>
				</td>
				<td id="header-cell-right">
					<xsl:call-template name="login-form" ></xsl:call-template>
				</td>
			</tr>
			</table>
			</td>
		</tr>
		<tr>
			<td id="navbar-column" class="sidebar">
			<img src="site:///spacer.gif" alt="" class="column-spacer"/>
			    <div id="navbar" class="sidebar navbar">
    				<xsl:value-of disable-output-escaping='yes' select="wf:openurl('site:///sidebar')" />
    			    </div>
			</td>
			<td id="main-table-column" class="sidebar"><div class="shortmessage"><xsl:if test="$message"><div class="alert"><xsl:value-of select="$message" disable-output-escaping='yes' /></div></xsl:if></div><table id="main-table">
					<tr>
						<td id="actionsbar" class="header">
							<xsl:if test="not($_static)" >
							<xsl:call-template name='actions-bar' />
							</xsl:if>
						</td>
					</tr>
					<tr>
						<td id="page-title" class="page-title">
							<xsl:value-of select="$title" />
						</td>
					</tr>
					<tr>	
						<td id="content" class="content">
						<table id="content-body-table">
						<tr>
							<td>
								<img src="site:///spacer.gif" alt="" class="column-spacer-height"/>
							</td>
							<td id="content-display-cell"><xsl:call-template name="display-content" ></xsl:call-template>    
							</td>
						</tr>
						<tr>
							<td colspan="2">
								<img src="site:///spacer.gif" alt="" class="row-spacer"/>
							</td>
						</tr>
						</table>
						</td>
					</tr>
				</table>
			</td>
			<td id="linksbar-column" class="sidebar">
				<img src="site:///spacer.gif" alt="" class="column-spacer"/>				
				<xsl:if test="not($_static)" >
    				<br/>
    				<h3>Global Links</h3>
    				<div id="quicklinks" class="quicklinks">
    					<xsl:call-template name='quicklinks-bar' />
    				</div>
    				<br/>
    				<div id="searchform">
    					<xsl:call-template name='search-form' />
    				</div>
				</xsl:if>
			</td>
		</tr>
		<tr>
			<td id="footer-row" colspan="3" class="footer">
			    <xsl:value-of disable-output-escaping='yes' select="/*[wiki:name='site-template']/wiki:footer-text" />
			</td>
		</tr>
	</table>
</body>
  
</xsl:template>
</xsl:stylesheet>