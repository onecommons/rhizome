<?xml version="1.0"?>
<!-- $Id$ -->

<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

 <!-- <xsl:import href="docv102html.xsl"/> -->
 <!--xsl:include href="sbk:/style/stylesheets/toc.xsl"/-->

 <xsl:param name="stylebook.project"/>
 <xsl:param name="copyright"/>
 <xsl:param name="name"/>
 <xsl:param name="id"/>
 
 <xsl:template match="specification">
  <html>
      <head>
         <!-- <script language="JavaScript" type="text/javascript" src="resources/script.js"/> -->
         <title><xsl:value-of select="header/title"/></title>
      </head>

      <body text="#1E1446"
            topmargin="0" leftmargin="0" marginwidth="0" marginheight="0"
            bgcolor="#EFEFEF" alink="#0F4CC8" vlink="#0F4CC8" link="#0F4CC8">

         <!-- THE MAIN PANEL (SIDEBAR AND CONTENT) -->
         <table cellspacing="0" cellpadding="0" border="0" width="100%">
            <tr>
            <h1 align="center"><xsl:value-of select="header/title"/></h1>
            <!-- THE CONTENT PANEL -->
            <td valign="top" align="left" width="100%">
               <table border="0" cellspacing="0" cellpadding="5" width="100%">
                  
                  <tr><td>
                     <xsl:apply-templates select="header"/>
                     <xsl:call-template name="createTOC"/>
                     <xsl:apply-templates select="body"/>
                     <xsl:apply-templates select="appendices"/>
                     <xsl:apply-templates select="footer"/>
                  </td></tr>
               </table>
               <xsl:comment>end content panel</xsl:comment>
            </td>

            </tr>
         </table>
                           
      </body>      
      </html>
   </xsl:template>
    
  <xsl:template match="header">
  <div align="center">
   <table width="60%" border="0" cellspacing="0" cellpadding="0" align="center">
   <tbody>
   <tr><td bgcolor="#64697C">
   <table width="100%" border="0" cellspacing="1" cellpadding="1">
    <tr>
     <td bgcolor="#A8ADD5" valign="center" align="center">
      <font color="#000000" size="-1" face="arial,helvetica,sanserif">
       <b>Authors</b>
      </font>
     </td>
    </tr>
    <xsl:for-each select="authors/person">
     <tr>
      <td bgcolor="#C5CADD" valign="center" align="left">
       <font color="#000000" size="-1" face="arial,helvetica,sanserif">
        <b><xsl:value-of select="@name"/></b> - <xsl:value-of select="@email"/>
       </font>
      </td>
     </tr>
    </xsl:for-each>
    <tr>
     <td bgcolor="#A8ADD5" valign="center" align="center">
      <font color="#000000" size="-1" face="arial,helvetica,sanserif">
       <b>Status</b>
      </font>
     </td>
    </tr>
    <tr>
     <td bgcolor="#C5CADD" valign="center" align="left">
      <font color="#000000" size="-1" face="arial,helvetica,sanserif">
       <b><xsl:value-of select="type"/> - <xsl:value-of select="version"/></b>
      </font>
     </td>
    </tr>
    <tr>
     <td bgcolor="#A8ADD5" valign="center" align="center">
      <font color="#000000" size="-1" face="arial,helvetica,sanserif">
       <b>Notice</b>
      </font>
     </td>
    </tr>
    <tr>
     <td bgcolor="#C5CADD" valign="center" align="left">
      <font color="#000000" size="-1" face="arial,helvetica,sanserif">
       <xsl:value-of select="notice"/>
      </font>
     </td>
    </tr>
    <tr>
     <td bgcolor="#A8ADD5" valign="center" align="center">
      <font color="#000000" size="-1" face="arial,helvetica,sanserif">
       <b>Abstract</b>
      </font>
     </td>
    </tr>
    <tr>
     <td bgcolor="#C5CADD" valign="center" align="left">
      <font color="#000000" size="-1" face="arial,helvetica,sanserif">
       <xsl:value-of select="abstract"/>
      </font>
     </td>
    </tr>
   </table>
   </td></tr>
   </tbody>
   </table>
  </div>
  <br/>
  </xsl:template>

<!-- ====================================================================== -->
<!-- body section -->
<!-- ====================================================================== -->

    <xsl:template match="body">
        <xsl:apply-templates/>
    </xsl:template>
    

   <xsl:template match="s1">
      <div align="right">

      <table border="0" cellspacing="0" cellpadding="1" width="98%">
         <tr>
         <td width="100%" bgcolor="#C5CADD">
            <font size="+1" color="#000000" face="Arial, Helvetica, sans-serif">
              <img src="void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b><a name="{generate-id(.)}"><xsl:value-of select="@title"/></a></b></i>
            </font>
         </td>
         </tr>
      </table>

      <br/>
      
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
               <img src="void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b><a name="{generate-id(.)}"><xsl:value-of select="@title"/></a></b></i>
            </font>
         </td>
         </tr>
      </table>

      <br/>
      
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
               <img src="void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b><a name="{generate-id(.)}"><xsl:value-of select="@title"/></a></b></i>
            </font>
         </td>
         </tr>
         
      </table>
         <br/>
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
      <div align="center">
      
      <table border="0" cellspacing="0" cellpadding="1" width="85%">
         <tr>
         <td width="100%" bgcolor="#C5CADD">
            <font size="-2" color="#000000" ace="Arial, Helvetica, sans-serif">
               <img src="void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b><a name="{generate-id(.)}"><xsl:value-of select="@title"/></a></b></i>
            </font>
         </td>
         </tr>
      </table>

      <br/>
     
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
<!-- footer section -->
<!-- ====================================================================== -->

 <xsl:template match="footer">
  <!-- ignore on general documents -->
 </xsl:template>

<!-- ====================================================================== -->
<!-- paragraph section -->
<!-- ====================================================================== -->

  <xsl:template match="p">
    <p align="justify"><xsl:apply-templates/></p>
  </xsl:template>

  <xsl:template match="note">
   <p>
    <table width="100%" cellspacing="3" cellpadding="0" border="0">
      <tr>
        <td width="28" valign="top">
          <img src="note.gif" width="28" height="29" vspace="0" hspace="0" border="0" alt="Note"/>
        </td>
        <td valign="top">
          <font size="-1" face="arial,helvetica,sanserif" color="#000000">
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
         <td bgcolor="#AAAAAA" width="1" height="1"><img src="void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#AAAAAA" height="1"><img src="void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#AAAAAA" width="1" height="1"><img src="void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
      </tr>
      <tr>
         <td bgcolor="#AAAAAA" width="1"><img src="void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#ffffff">
            <pre><xsl:apply-templates/></pre>
         </td>
         <td bgcolor="#AAAAAA" width="1"><img src="void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
      </tr>
      <tr>
         <td bgcolor="#AAAAAA" width="1" height="1"><img src="void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#AAAAAA" height="1"><img src="void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
         <td bgcolor="#AAAAAA" width="1" height="1"><img src="void.gif" width="1" height="1" vspace="0" hspace="0" border="0"/></td>
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
   <xsl:copy>
    <xsl:apply-templates select="li|sl|dt"/>
   </xsl:copy>
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

<!-- ====================================================================== -->
<!-- table section -->
<!-- ====================================================================== -->

   <xsl:template match="table">
      <table width="100%" border="0" cellspacing="0" cellpadding="0" align="center">
      <tbody>
      <tr><td bgcolor="#c7d28c">
      <table width="100%" border="0" cellspacing="1" cellpadding="2">
         <caption><xsl:value-of select="caption"/></caption>
         <xsl:apply-templates/>
      </table>
      </td></tr>
      </tbody>
      </table>
   </xsl:template>

   <xsl:template match="tr">
      <tr><xsl:apply-templates/></tr>
   </xsl:template>

   <xsl:template match="th">
      <td bgcolor="#d7e29c" background="bg.jpg" colspan="{@colspan}" rowspan="{@rowspan}" valign="center" align="center">
      <font color="#000000" size="-1">
        <b><xsl:apply-templates/></b>&#160;
      </font>
      </td>
   </xsl:template>

   <xsl:template match="td">
      <td bgcolor="#eff4cb" colspan="{@colspan}" rowspan="{@rowspan}" valign="top" align="left">
      <font color="#000000" size="-1">
         <xsl:apply-templates/>&#160;
      </font>
      </td>
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
    <code><font face="courier, monospaced"><xsl:apply-templates/></font></code>
 </xsl:template>
 
<!-- ====================================================================== -->
<!-- images section -->
<!-- ====================================================================== -->

 <xsl:template match="figure">
  <p align="center"><img src="{@src}" alt="{@alt}" border="0" vspace="4" hspace="4"/></p>
 </xsl:template>
 
 <xsl:template match="img">
   <img src="{@src}" alt="{@alt}" border="0" vspace="4" hspace="4" align="right"/>
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
 
<!-- ====================================================================== -->
<!-- appendices section -->
<!-- ====================================================================== -->

 <xsl:template match="appendices">
  <xsl:apply-templates/>
 </xsl:template>

<!-- ====================================================================== -->
<!-- bibliography -->
<!-- ====================================================================== -->

 <xsl:template match="bl">
  <ul>
   <xsl:apply-templates/>
  </ul>
 </xsl:template>

 <xsl:template match="bi">
  <li>
   <b>
    <a name="{@name}"/>
    <xsl:text>[</xsl:text>
     <a href="{@href}"><xsl:value-of select="@name"/></a>
    <xsl:text>]</xsl:text>
   </b>
   <xsl:text> &quot;</xsl:text>
   <xsl:value-of select="@title"/>
   <xsl:text>&quot;, </xsl:text>
   <xsl:value-of select="@authors"/>
   <xsl:if test="@date">
    <xsl:text>, </xsl:text>
    <xsl:value-of select="@date"/>
   </xsl:if>
  </li>
 </xsl:template>


<!-- ====================================================================== -->
<!-- book section -->
<!-- ====================================================================== -->

  <!-- INTERNAL LINK -->
  <xsl:template match="page|faqs|changes|todo|spec">
    <xsl:if test="@id=$id">
      <img src="graphics/{@id}-label-1.jpg" hspace="0" vspace="0" border="0" alt="{@label}"/>
    </xsl:if>
    <xsl:if test="@id!=$id">
      <a href="{@id}.html" onMouseOver="rolloverOn('side-{@id}');" onMouseOut="rolloverOff('side-{@id}');">
        <img onLoad="rolloverLoad('side-{@id}','graphics/{@id}-label-2.jpg','graphics/{@id}-label-3.jpg');"
             name="side-{@id}" src="graphics/{@id}-label-3.jpg" hspace="0" vspace="0" border="0" alt="{@label}"/>
      </a>
    </xsl:if>
    <br/>
  </xsl:template>

  <!-- EXTERNAL LINK -->
  <xsl:template match="external">
    <xsl:variable name="extid" select="concat('ext-',position())"/>
    <a href="{@href}" onMouseOver="rolloverOn('side-{$extid}');" onMouseOut="rolloverOff('side-{$extid}');">
      <img onLoad="rolloverLoad('side-{$extid}','graphics/{$extid}-label-2.jpg','graphics/{$extid}-label-3.jpg');"
           name="side-{$extid}" src="graphics/{$extid}-label-3.jpg" hspace="0" vspace="0" border="0" alt="{@label}"/>
    </a>
    <br/>
  </xsl:template>

  <xsl:template match="separator">
    <img src="menu_sep.jpg" border="0"/>
    <br/>
  </xsl:template>

  <xsl:template name="createTOC">
      <div align="right">
          <table border="0" cellspacing="0" cellpadding="1" width="98%">
              <tr>
              <td width="100%" bgcolor="#C5CADD">
                 <font size="+1" color="#000000" face="Arial, Helvetica, sans-serif">
                 <img src="void.gif" width="5" height="5" vspace="0" hspace="0" border="0"/><i><b>Table of Contents</b></i>
                 </font>
              </td>
              </tr>
          </table>

          <br/><br/>
          <table border="0" cellspacing="0" cellpadding="0" width="98%">
              <tr><td>
                  <xsl:for-each select="body">
                      <xsl:call-template name="toc">
                          <xsl:with-param name="format">1.1 </xsl:with-param>
                      </xsl:call-template>
                  </xsl:for-each>
                  <p/><font face="arial,helvetica,sanserif"><b>Appendices</b></font><p/>
                  <xsl:for-each select="appendices">
                      <xsl:call-template name="toc">
                          <xsl:with-param name="format">A.1 </xsl:with-param>
                      </xsl:call-template>
                  </xsl:for-each>
              </td></tr>
          </table>
          <br/><br/>
      </div>
  </xsl:template>
            
  
  <xsl:template name="toc">
      <xsl:param name="format">1.1 </xsl:param>
      <font color="#000000" face="arial,helvetica,sanserif">
      <xsl:for-each select=".//s1|.//s2|.//s3">
          <xsl:call-template name="toc-indent">
              <xsl:with-param name="width"
                      select="number(substring-after(name(.), 's'))-1"/>
          </xsl:call-template>
          <xsl:number level="multiple"
                  count="s1|s2|s3"
                  format="{$format}"/>
          <a href="#{generate-id()}">
              <xsl:value-of select="@title"/>
          </a><br/>
      </xsl:for-each>
      </font>
  </xsl:template>     

  
  <xsl:template name="toc-indent">
      <xsl:param name="width">1</xsl:param>
      <xsl:if test="$width > 0">
          <xsl:text>&#160;&#160;&#160;&#160;</xsl:text>
          <xsl:call-template name="toc-indent">
              <xsl:with-param name="width">
                  <xsl:value-of select="$width - 1"/>
              </xsl:with-param>
          </xsl:call-template>
      </xsl:if>
  </xsl:template>
    
</xsl:stylesheet>
