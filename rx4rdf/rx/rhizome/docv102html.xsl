<?xml version="1.0"?>
<xsl:stylesheet version="1.0"
        xmlns:a="http://rx4rdf.sf.net/ns/archive#"
        xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
        xmlns:wf='http://rx4rdf.sf.net/ns/racoon/xpath-ext#'
        xmlns:f = 'http://xmlns.4suite.org/ext'
        exclude-result-prefixes = "f wf a wiki rdf" >	

   <xsl:param name="stylebook.project"/>
   <xsl:param name="copyright"/>
   <xsl:param name="name"/>
   <xsl:param name="id"/>

<!-- ====================================================================== -->
<!-- document section -->
<!-- ====================================================================== -->

   <xsl:template match="/">
   <!-- checks if this is the included document to avoid neverending loop -->

         <!-- THE MAIN PANEL (SIDEBAR AND CONTENT) -->
         <table cellspacing="0" cellpadding="0" border="0" width="100%">
            <tr>

            <!-- THE CONTENT PANEL -->
            <td valign="top" align="left" width="100%">
               <table border="0" cellspacing="0" cellpadding="5" width="100%">
                  <tr><td/></tr><tr><td/></tr><tr><td/></tr>
                  <tr><td><xsl:apply-templates/></td></tr>
               </table>
               <xsl:comment>end content panel</xsl:comment>
            </td>

            </tr>
         </table>

         <br/>
  </xsl:template>
<!-- ====================================================================== -->
<!-- body section -->
<!-- ====================================================================== -->

   <xsl:template match="s1">
      <div align="right">

      <table border="0" cellspacing="0" cellpadding="1" width="98%">
         <tr>
         <td width="100%" bgcolor="#C5CADD">
            <font size="+1" color="#000000" face="Arial, Helvetica, sans-serif">
              <img src="resources/void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b><xsl:value-of select="@title"/></b></i>
            </font>
         </td>
         </tr>
      </table>

      <br/><br/>
      
      <table border="0" cellspacing="0" cellpadding="0" width="98%">
         <tr>
            <td>
               <font color="#000000"  face="Arial, Helvetica, sans-serif">
               <xsl:apply-templates/>
               </font>
            </td>
         </tr>
      </table>
   
      </div>
   
      <br/>

      <xsl:comment>end s1</xsl:comment>
   
   </xsl:template>

   <xsl:template match="s2">
      <div align="right">

      <table border="0" cellspacing="0" cellpadding="1" width="95%">
         <tr>
         <td width="100%" bgcolor="#C5CADD">
            <font color="#000000"  face="Arial, Helvetica, sans-serif">
               <img src="resources/void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b><xsl:value-of select="@title"/></b></i>
            </font>
         </td>
         </tr>
      </table>

      <br/><br/>
      
      <table border="0" cellspacing="0" cellpadding="0" width="95%">
         <tr>
         <td>
            <font color="#000000"  face="Arial, Helvetica, sans-serif">
            <xsl:apply-templates/>
            </font>
         </td>
         </tr>
      </table>

      </div>
      
      <br/>
      
      <xsl:comment>end s2</xsl:comment>
   
   </xsl:template>

   <xsl:template match="s3">
      <div align="right">
    
      <table border="0" cellspacing="0" cellpadding="1" width="90%">
         <tr>
         <td width="100%" bgcolor="#C5CADD">
            <font size="-1" color="#000000" face="Arial, Helvetica, sans-serif">
               <img src="resources/void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b><xsl:value-of select="@title"/></b></i>
            </font>
         </td>
         </tr>
         
      </table>
         <br/><br/>
         <table border="0" cellspacing="0" cellpadding="0" width="90%">
            <tr>
            <td>
               <font color="#000000"  face="Arial, Helvetica, sans-serif">
               <xsl:apply-templates/>
               </font>
            </td>
            </tr>
      </table>
      
      </div>
      
      <br/>
      
      <xsl:comment>end s3</xsl:comment>
   
   </xsl:template>

   <xsl:template match="s4">
      <div align="right">
      
      <table border="0" cellspacing="0" cellpadding="1" width="85%">
         <tr>
         <td width="100%" bgcolor="##C5CADD">
            <font size="-2" color="#000000" ace="Arial, Helvetica, sans-serif">
               <img src="resources/void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b><xsl:value-of select="@title"/></b></i>
            </font>
         </td>
         </tr>
      </table>

      <br/><br/>
     
      <table border="0" cellspacing="0" cellpadding="0" width="85%">
         <tr>
         <td>
            <font color="#000000"  face="Arial, Helvetica, sans-serif">
            <xsl:apply-templates/>
            </font>
         </td>
         </tr>
      </table>
      
      </div>
   
      <br/>
      <xsl:comment>end s4</xsl:comment>
   </xsl:template>
    
<!-- ====================================================================== -->
<!-- paragraph section -->
<!-- ====================================================================== -->

   <xsl:template match="p">
      <p align="justify">
         <font face="Arial, Helvetica, sans-serif">
            <xsl:apply-templates/>
         </font>
      </p>
   </xsl:template>

   <xsl:template match="note">
      <p>
      <table width="100%" cellspacing="3" cellpadding="0" border="0">
         <tr>
         <td width="28" valign="top">
            <img src="resources/note.gif" width="28" height="29" vspace="0" hspace="0" border="0" alt="Note"/>
         </td>
         <td valign="middle">
            <font size="-1" color="#000000">
            <i>
               <xsl:apply-templates/>
            </i>
            </font>
         </td>
         </tr>  
      </table>
      </p>
   </xsl:template>

   <xsl:template match="source">
      <div align="center">
      <table cellspacing="4" cellpadding="0" border="0">
      <tr>
         <td bgcolor="#AAAAAA" width="1" height="1"><img src="resources/void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#AAAAAA" height="1"><img src="resources/void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#AAAAAA" width="1" height="1"><img src="resources/void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
      </tr>
      <tr>
         <td bgcolor="#AAAAAA" width="1"><img src="resources/void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#ffffff">
            <pre><xsl:apply-templates/></pre>
         </td>
         <td bgcolor="#AAAAAA" width="1"><img src="resources/void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
      </tr>
      <tr>
         <td bgcolor="#AAAAAA" width="1" height="1"><img src="resources/void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#AAAAAA" height="1"><img src="resources/void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#AAAAAA" width="1" height="1"><img src="resources/void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
      </tr>
      </table>
      </div>
   </xsl:template>
  
   <xsl:template match="fixme">
      <!-- ignore on documentation -->
   </xsl:template>

<!-- ====================================================================== -->
<!-- list section -->
<!-- ====================================================================== -->

   <xsl:template match="ul|ol|dl">
      <blockquote>
         <font face="Arial, Helvetica, sans-serif">
         <xsl:copy>
            <xsl:apply-templates select="li|sl|dt"/>
         </xsl:copy>
         </font>
      </blockquote>
   </xsl:template>
 
   <xsl:template match="li">
      <xsl:copy>
         <xsl:apply-templates/>
      </xsl:copy>
   </xsl:template>

   <xsl:template match="sl">
      <ul>
         <xsl:apply-templates/>
      </ul>
   </xsl:template>

   <xsl:template match="dt">
      <li>
         <strong><xsl:apply-templates/></strong>
         <xsl:text> - </xsl:text>
         <xsl:apply-templates select="following-sibling::dd[1]"/> 
      </li>
   </xsl:template>
 
   <xsl:template match="dd">
      <xsl:apply-templates/>
   </xsl:template>

   <xsl:template match="rl">
      <div align="center">
      <table width="100%" border="0" cellspacing="0" cellpadding="0" align="center">
      <tbody>
      <tr><td bgcolor="#64697C">
        <table width="100%" border="0" cellspacing="1" cellpadding="1">
        <tr>
          <td bgcolor="#A8ADD5" valign="center" align="center">
          <font color="#000000" face="arial,helvetica,sanserif">
          <b>Title</b></font>
          </td>
          <td bgcolor="#A8ADD5" valign="center" align="center">
          <font color="#000000" face="arial,helvetica,sanserif">
          <b>Authors</b></font>
          </td>
          <td bgcolor="#A8ADD5" valign="center" align="center">
          <font color="#000000" face="arial,helvetica,sanserif">
          <b>Date</b></font>
          </td>
          <td bgcolor="#A8ADD5" valign="center" align="center" width="35%">
          <font color="#000000" face="arial,helvetica,sanserif">
          <b>Description</b></font>
          </td>
        </tr>
        <xsl:apply-templates/>
        </table>
      </td></tr>
      </tbody>
      </table>
      </div>
   </xsl:template>

   <xsl:template match="ri">
      <tr>
         <td bgcolor="#C5CADD" valign="center" align="left">
         <font color="#000000" face="arial,helvetica,sanserif">
         <a href="{@href}" target="_blank"><xsl:value-of select="@title"/></a></font>
         </td>
         <td bgcolor="#C5CADD" valign="center" align="left">
         <font color="#000000" face="arial,helvetica,sanserif">
         <xsl:value-of select="@authors"/></font>
         </td>
         <td bgcolor="#C5CADD" valign="center" align="left">
         <font color="#000000" face="arial,helvetica,sanserif">
         <xsl:value-of select="@date"/></font>
         </td>
         <td bgcolor="#C5CADD" valign="center" align="left">
         <font color="#000000" face="arial,helvetica,sanserif">
         <xsl:value-of select="@description"/></font>
         </td>
      </tr>
   </xsl:template>

<!-- ====================================================================== -->
<!-- table section -->
<!-- ====================================================================== -->

   <xsl:template match="table">
     <xsl:if test="@border">
      <div align="center">
      <table width="100%" border="0" cellspacing="0" cellpadding="0" align="center">
      <tbody>
      <tr><td bgcolor="#64697C">
        <table width="100%" border="0" cellspacing="1" cellpadding="1">
        <caption><xsl:value-of select="caption"/></caption>
        <xsl:apply-templates/>
        </table>
      </td></tr>
      </tbody>
      </table>
      </div>
     </xsl:if>
     <xsl:if test="not(@border)">
      <table width="100%" border="0" cellspacing="1" cellpadding="2" bgcolor="#EFEFEF">
      <caption><xsl:value-of select="caption"/></caption>
      <xsl:apply-templates/>
      </table>
     </xsl:if>
<!--
      <xsl:if test="@border">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" align="center">
        <tbody>
        <tr><td bgcolor="#64697C">
        <table width="100%" border="0" cellspacing="1" cellpadding="2">
        <caption><xsl:value-of select="caption"/></caption>
        <xsl:apply-templates/>
        </table>
        </td></tr>
        </tbody>
        </table>
      </xsl:if>
      <xsl:if test="not(@border)">
        <table width="100%" border="0" cellspacing="1" cellpadding="2" bgcolor="#EFEFEF">
        <caption><xsl:value-of select="caption"/></caption>
        <xsl:apply-templates/>
        </table>
      </xsl:if>
-->
   </xsl:template>

   <xsl:template match="tr">
      <tr><xsl:apply-templates/></tr>
   </xsl:template>

   <xsl:template match="th">
      <td bgcolor="#A8ADD5" colspan="{@colspan}" rowspan="{@rowspan}" valign="center" align="center">
      <font color="#000000" size="-1">
        <b><xsl:apply-templates/></b>&#160;
      </font>
      </td>
   </xsl:template>

   <xsl:template match="td">
      <xsl:choose>
      <xsl:when test="@width">
         <xsl:choose>
         <xsl:when test="../../@border">
          <td bgcolor="#C5CADD" colspan="{@colspan}" rowspan="{@rowspan}" valign="top" align="left" width="{@width}">
          <font color="#000000" size="-1">
             <xsl:apply-templates/>&#160;
          </font>
          </td>
         </xsl:when>
         <xsl:otherwise>
          <td colspan="{@colspan}" rowspan="{@rowspan}" valign="top" align="left" width="{@width}"> 
          <font color="#000000" size="-1">
             <xsl:apply-templates/>&#160;
          </font>
          </td>
         </xsl:otherwise>
         </xsl:choose>
      </xsl:when>
      <xsl:otherwise>
         <xsl:choose>
         <xsl:when test="../../@border">
         <td bgcolor="#C5CADD" colspan="{@colspan}" rowspan="{@rowspan}" valign="top" align="left">
         <font color="#000000" size="-1">
            <xsl:apply-templates/>&#160;
         </font>
         </td>
         </xsl:when>
         <xsl:otherwise>
         <td colspan="{@colspan}" rowspan="{@rowspan}" valign="top" align="left">
         <font color="#000000" size="-1">
            <xsl:apply-templates/>&#160;
         </font>
         </td>
         </xsl:otherwise>
         </xsl:choose>
      </xsl:otherwise>
      </xsl:choose>
   </xsl:template>

   <xsl:template match="tn">
      <td bgcolor="#ffffff" colspan="{@colspan}" rowspan="{@rowspan}">
         &#160;
      </td>
   </xsl:template>
  
   <xsl:template match="caption">
      <!-- ignore since already used -->
   </xsl:template>

<!-- ====================================================================== -->
<!-- markup section -->
<!-- ====================================================================== -->

   <xsl:template match="strong">
      <b><xsl:apply-templates/></b>
   </xsl:template>

   <xsl:template match="em">
      <i><xsl:apply-templates/></i>
   </xsl:template>

   <xsl:template match="code">
      <code>
         <font face="courier, monospaced">
            <xsl:apply-templates/>
         </font>
      </code>
   </xsl:template>
 
<!-- ====================================================================== -->
<!-- images section -->
<!-- ====================================================================== -->

   <xsl:template match="figure">
      <p align="center"><img src="{@src}" alt="{@alt}" border="0" vspace="4" hspace="4"/></p>
   </xsl:template>
 
   <xsl:template match="img">
      <img src="{@src}" alt="{@alt}" border="0" vspace="4" hspace="4"/>
   </xsl:template>

   <xsl:template match="icon">
      <img src="{@src}" alt="{@alt}" border="0" align="absmiddle"/>
   </xsl:template>

<!-- ====================================================================== -->
<!-- links section -->
<!-- ====================================================================== -->

   <xsl:template match="link">
      <a href="{@href}"><xsl:apply-templates/></a>
   </xsl:template>

   <xsl:template match="connect">
      <xsl:apply-templates/>
   </xsl:template>

   <xsl:template match="jump">
      <a href="{@href}#{@anchor}"><xsl:apply-templates/></a>
   </xsl:template>

   <xsl:template match="fork">
      <a href="{@href}" target="_blank"><xsl:apply-templates/></a>
   </xsl:template>

   <xsl:template match="anchor">
      <a name="{@id}"><xsl:comment>anchor</xsl:comment></a>
   </xsl:template>  

<!-- ====================================================================== -->
<!-- specials section -->
<!-- ====================================================================== -->

   <xsl:template match="br">
      <br/>
   </xsl:template>

   <xsl:template match="sup">
      <sup><font size="-2">
        <xsl:apply-templates/>
      </font></sup>
   </xsl:template>

</xsl:stylesheet>
