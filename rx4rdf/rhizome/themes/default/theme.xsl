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

<body class="page_style">
	<table id="body-table">
  		<tr>
  			<td colspan="3" id="header-container-row" class="header_style">
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
			<td id="navbar-column" class="sidebar_style">
			<img src="site:///spacer.gif" alt="" class="column-spacer"/>
			    <div id="navbar" class="sidebar_style navbar_style">
    				<xsl:value-of disable-output-escaping='yes' select="wf:openurl('site:///sidebar')" />
    			    </div>
			</td>
			<td id="main-table-column" class="sidebar_style">
				<xsl:if test="$message">
			  	<div class="alert shortmessage">
					<xsl:value-of select="$message" disable-output-escaping='yes' />
				</div>
				</xsl:if>
				<table id="main-table">
					<tr>
						<td id="actionsbar" class="header_style">
							<xsl:if test="not($_static)" >
							<xsl:call-template name='actions-bar' />
							</xsl:if>
						</td>
					</tr>
					<tr>
						<td id="page-title" class="page-title_style">
							<xsl:value-of select="$title" />
						</td>
					</tr>
					<tr>	
						<td id="content" class="content_style">
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
			<td id="linksbar-column" class="sidebar_style">
				<img src="site:///spacer.gif" alt="" class="column-spacer"/>
				<br/>
				<h3>Global Links</h3>
				<div id="quicklinks" class="quicklinks_style">
					<xsl:if test="not($_static)" ><xsl:call-template name='quicklinks-bar' /></xsl:if>
				</div>
				<br/>
				<div id="searchform">
					<xsl:if test="not($_static)" ><xsl:call-template name='search-form' /></xsl:if>
				</div>
			</td>
		</tr>
		<tr>
			<td id="footer-row" colspan="3" class="footer_style">
				<xsl:value-of disable-output-escaping='yes' select="wf:openurl('site:///footer')" />
			</td>
		</tr>
	</table>
</body>
  
</xsl:template>
</xsl:stylesheet>