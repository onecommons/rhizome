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

<body>
	<table id="body-table">
  		<tr>
  			<td colspan="4" id="header-container-row">
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
			<td id="spacer-column">
				<img src="site:///spacer.gif" alt="" class="column-spacer-height"/>
			</td>
			<td id="navbar-column">
			<img src="site:///spacer.gif" alt="" class="column-spacer"/>
			    <div id="navbar">
    				<xsl:value-of disable-output-escaping='yes' select="wf:openurl('site:///sidebar')" />
    			    </div>
			</td>
			<td id="content-table-column">
				<xsl:if test="$session:message">
			  	<div class="alert message">
					<xsl:value-of select="$session:message" disable-output-escaping='yes' />
				</div>
				</xsl:if>
				<table id="content-table">
					<tr>
						<td id="actionsbar">
							<xsl:if test="not($_static)" >
							<xsl:call-template name='actions-bar' />
							</xsl:if>
						</td>
					</tr>
					<tr>
						<td id="page-title">
							<xsl:value-of select="$title" />
						</td>
					</tr>
					<tr>
						<td id="spacer-row">
							<img src="site:///spacer.gif" alt="" class="contentspacer"/>
						</td>
					</tr>
					<tr>	
						<td id="content">

							<xsl:call-template name="display-content" ></xsl:call-template>    
						</td>
					</tr>
					<tr>
						<td id="spacer-row">
							<img src="site:///spacer.gif" alt="" class="contentspacer"/>
						</td>
					</tr>
				</table>
			</td>
			<td id="linksbar-column">
				<img src="site:///spacer.gif" alt="" class="column-spacer"/>
				<br/>
				<h3>Global Links</h3>
				<div id="quicklinks">
					<xsl:if test="not($_static)" ><xsl:call-template name='quicklinks-bar' /></xsl:if>
				</div>
				<br/>
				<div id="searchform">
					<xsl:if test="not($_static)" ><xsl:call-template name='search-form' /></xsl:if>
				</div>
			</td>
		</tr>
		<tr>
			<td id="footer-row" colspan="4">
			<!--
				<xsl:value-of disable-output-escaping='yes' select="wf:openurl('site:///footer')" />
		      -->
			</td>
		</tr>
	</table>
</body>
  
</xsl:template>
</xsl:stylesheet>