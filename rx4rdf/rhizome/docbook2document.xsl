<?xml version="1.0"?>
<!--
A prototype Docbook-to-Forrest stylesheet.  Volunteers are needed to improve
this!

      This xsl should enable an easier conversion from docbook to forrest xdoc
      content model.  Templates that match on elements not yet seen by the
      developer have been left alone, as coded by the developers in the avalon
      project.
      NOTE:  html tags are probably better removed in favor of any _available_
      content model elements in the forrest document.dtd.

Further comments from the author:

>Is there any reason the stylesheet couldn't be used on the fly in a Cocoon
>pipeline, so pages can be authored in Docbook?

It could, it'll just need some continuous work until it is finally right.
There will also be some validity issues, i.e. text not allowed inside a section
without a <p>.  I'm sure you can setup the declarative stylesheet to handle
this, maybe with the use of the preceding:: axis on a match for a text() node.
I just didn't do it because I had only a few manageable issues after
transformation.  So, yes, I think it can be done with a little more work (and
it will need to continuously evolve for a while).

Credit: original from the jakarta-avalon project
Revision: Kevin.Ross@iVerticalLeap.com - Moving towards xml.apache.org/forrest document...not yet complete.
-->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
      <xsl:output method="xml" indent="yes" doctype-system="http://localhost/forrest/dtd/document-v11.dtd" doctype-public="-//APACHE//DTD Documentation V1.1//EN" encoding="UTF-8"/>
      <xsl:template match="/">
            <document>
                  <header>
                        <xsl:apply-templates select="/*/bookinfo/title"/>
                        <authors>
                              <xsl:apply-templates select="/*/bookinfo/author"/>
                        </authors>
                        <notice/>
                        <abstract/>
                  </header>
                  <body>
                        <xsl:apply-templates select="/*/node()[ local-name() != 'bookinfo' ]"/>
                  </body>
            </document>
      </xsl:template>
      <xsl:template match="author">
            <xsl:element name="person">
                  <xsl:attribute name="id"><xsl:value-of select="id"/></xsl:attribute>
                  <xsl:attribute name="name"><xsl:if test="honorific"><xsl:value-of select="honorific"/>. </xsl:if><xsl:if test="firstname"><xsl:value-of select="firstname"/></xsl:if><xsl:value-of select="surname"/></xsl:attribute>
                  <xsl:attribute name="email"><xsl:value-of select="address/email"/></xsl:attribute>
            </xsl:element>
      </xsl:template>
      <xsl:template match="chapter">
            <section>
                  <xsl:apply-templates/>
            </section>
      </xsl:template>
      <xsl:template match="docinfo">
            <xsl:apply-templates/>
      </xsl:template>
      <xsl:template match="cmdsynopsis">
            <!--
               <cmdsynopsis>
                  <command>xindice add_collection</command>
                  <arg choice="req">-c <replaceable>context</replaceable></arg>
                  <arg choice="req">-n <replaceable>name</replaceable></arg>
                  <arg choice="opt">-v <replaceable></replaceable></arg>
               </cmdsynopsis>
               -->
            <p>
                  <code>
                        <xsl:value-of select="command"/>
                        <xsl:apply-templates select="node()[ local-name() != 'command' ]"/>
                  </code>
            </p>
      </xsl:template>
      <xsl:template match="arg">
            <xsl:choose>
                  <xsl:when test="@choice = 'req' ">
                        <xsl:apply-templates/>
                  </xsl:when>
                  <xsl:otherwise>
                         [<xsl:apply-templates/>]
                  </xsl:otherwise>
            </xsl:choose>
      </xsl:template>
      <xsl:template match="replaceable">
            (or <xsl:value-of select="."/>)
      </xsl:template>
      <xsl:template match="bridgehead">
            <section>
                  <title>
                        <xsl:value-of select="."/>
                  </title>
            </section>
      </xsl:template>
      <xsl:template match="sect1">
            <section>
                  <xsl:apply-templates/>
            </section>
      </xsl:template>
      <xsl:template match="example">
            <section>
                  <xsl:apply-templates/>
            </section>
      </xsl:template>
      <xsl:template match="informaltable">
            <table>
                  <xsl:apply-templates/>
            </table>
      </xsl:template>
      <xsl:template match="anchor">
            <!--
            <a name="{.}"/>
            -->
            <xsl:element name="link">
                  <xsl:if test="@href">
                        <xsl:attribute name="href"><xsl:value-of select="@href"/></xsl:attribute>
                  </xsl:if>
                  <xsl:attribute name="id"><xsl:value-of select="."/></xsl:attribute>
            </xsl:element>
      </xsl:template>
      <xsl:template match="a">
            <link href="{@href}">
                  <xsl:value-of select="."/>
            </link>
      </xsl:template>
      <xsl:template match="subtitle"/>
      <xsl:template match="title">
            <title>
                  <xsl:value-of select="."/>
            </title>
      </xsl:template>
      <xsl:template match="affiliation">
            <li>
                  <xsl:text>[</xsl:text>
                  <xsl:value-of select="shortaffil"/>
                  <xsl:text>] </xsl:text>
                  <b>
                        <xsl:value-of select="jobtitle"/>
                  </b>
                  <i>
                        <xsl:value-of select="orgname"/>
                        <xsl:if test="orgdiv">
                              <xsl:text>/</xsl:text>
                              <xsl:value-of select="orgdiv"/>
                        </xsl:if>
                  </i>
            </li>
      </xsl:template>
      <xsl:template match="authorblurb">
            <section title="Bio">
                  <xsl:apply-templates/>
            </section>
      </xsl:template>
      <xsl:template match="honorific|firstname|surname|orgdiv|orgname|shortaffil|jobtitle"/>
      <xsl:template match="revhistory">
            <document>
                  <header>
                        <title>Revision History</title>
                  </header>
                  <body>
                        <section>
                              <table>
                                    <xsl:variable name="unique-revisions" select="revision[not(revnumber=preceding-sibling::revision/revnumber)]/revnumber"/>
                                    <xsl:variable name="base" select="."/>
                                    <xsl:for-each select="$unique-revisions">
                                          <tr>
                                                <td>
                                                      <b>Revision <xsl:value-of select="."/> 
                   (<xsl:value-of select="$base/revision[revnumber=current()]/date"/>)
                </b>
                                                </td>
                                          </tr>
                                          <tr>
                                                <td>
                                                      <font color="#000000" face="arial,helvetica,sanserif">
                                                            <br/>
                                                            <ul>
                                                                  <xsl:apply-templates select="$base/revision[revnumber=current()]"/>
                                                            </ul>
                                                      </font>
                                                </td>
                                          </tr>
                                    </xsl:for-each>
                              </table>
                        </section>
                  </body>
            </document>
      </xsl:template>
      <xsl:template match="para">
            <p>
                  <xsl:apply-templates/>
            </p>
      </xsl:template>
      <xsl:template match="emphasis">
            <em>
                  <xsl:apply-templates/>
            </em>
      </xsl:template>
      <xsl:template match="revision">
            <li>
                  <xsl:choose>
                        <xsl:when test="@revisionflag='added'">
                              <img align="absmiddle" alt="added" src="images/add.jpg"/>
                        </xsl:when>
                        <xsl:when test="@revisionflag='changed'">
                              <img align="absmiddle" alt="changed" src="images/update.jpg"/>
                        </xsl:when>
                        <xsl:when test="@revisionflag='deleted'">
                              <img align="absmiddle" alt="deleted" src="images/remove.jpg"/>
                        </xsl:when>
                        <xsl:when test="@revisionflag='off'">
                              <img align="absmiddle" alt="off" src="images/fix.jpg"/>
                        </xsl:when>
                        <xsl:otherwise>
                              <img align="absmiddle" alt="changed" src="images/update.jpg"/>
                        </xsl:otherwise>
                  </xsl:choose>
                  <xsl:value-of select="revremark"/>
                  <xsl:text> (</xsl:text>
                  <xsl:value-of select="authorinitials"/>
                  <xsl:text>)</xsl:text>
            </li>
      </xsl:template>
      <xsl:template match="revnumber|revremark|authorinitials|date"/>
      <xsl:template match="section">
            <section>
                  <xsl:apply-templates/>
            </section>
      </xsl:template>
      <xsl:template match="dedication">
            <table>
                  <tr>
                        <td>
                              <b>Dedication</b>
                        </td>
                  </tr>
                  <tr>
                        <td>
                              <br/>
                              <xsl:apply-templates/>
                        </td>
                  </tr>
            </table>
      </xsl:template>
      <xsl:template match="edition|pubdate|year|holder"/>
      <xsl:template match="copyright">
            <p>Copyright &#x00A9;<xsl:value-of select="year"/> by <xsl:value-of select="holder"/>.<br/>
                  <i>All rights reserved.</i>
            </p>
      </xsl:template>
      <xsl:template match="legalnotice">
            <table>
                  <tr>
                        <td>
                              <xsl:apply-templates/>
                        </td>
                  </tr>
            </table>
      </xsl:template>
      <xsl:template match="programlisting">
            <source>
                  <xsl:text disable-output-escaping="yes">&lt;![CDATA[</xsl:text>
                  <xsl:apply-templates/>
                  <xsl:text disable-output-escaping="yes">]]&gt;</xsl:text>
            </source>
      </xsl:template>
      <xsl:template match="screen">
            <source>
                  <xsl:text disable-output-escaping="yes">&lt;![CDATA[</xsl:text>
                  <xsl:apply-templates/>
                  <xsl:text disable-output-escaping="yes">]]&gt;</xsl:text>
            </source>
      </xsl:template>
      <xsl:template match="orderedlist">
            <ol>
                  <xsl:apply-templates/>
            </ol>
      </xsl:template>
      <xsl:template match="listitem">
            <li>
                  <xsl:apply-templates/>
            </li>
      </xsl:template>
      <xsl:template match="itemizedlist">
            <ul>
                  <xsl:apply-templates/>
            </ul>
      </xsl:template>
      <xsl:template match="command">
            <code>
                  <xsl:value-of select="."/>
            </code>
      </xsl:template>
      <xsl:template match="computeroutput">
            <code>
                  <xsl:value-of select="."/>
            </code>
      </xsl:template>
      <xsl:template match="varname">
            <code>
                  <xsl:value-of select="."/>
            </code>
      </xsl:template>
      <xsl:template match="filename">
            <code>
                  <xsl:value-of select="."/>
            </code>
      </xsl:template>
      <xsl:template match="classname|function|parameter">
            <code>
                  <xsl:apply-templates/>
                  <xsl:if test="name(.)='function'">
                        <xsl:text>()</xsl:text>
                  </xsl:if>
            </code>
      </xsl:template>
      <xsl:template match="blockquote">
            <table>
                  <xsl:if test="title">
                        <tr>
                              <td>
                                    <xsl:value-of select="title"/>
                              </td>
                        </tr>
                  </xsl:if>
                  <tr>
                        <td>
                              <xsl:apply-templates/>
                        </td>
                  </tr>
            </table>
      </xsl:template>
      <xsl:template match="warning">
            <warning>
                  <xsl:apply-templates/>
            </warning>
      </xsl:template>
      <xsl:template match="ulink">
            <xsl:element name="link">
                  <xsl:attribute name="href"><xsl:choose><xsl:when test="@uri"><xsl:value-of select="@uri"/></xsl:when><xsl:otherwise><xsl:value-of select="@url"/></xsl:otherwise></xsl:choose></xsl:attribute>
                  <xsl:apply-templates/>
            </xsl:element>
      </xsl:template>
      <xsl:template match="footnote">
            <sup>
                  <a href="#{generate-id(.)}">
                        <xsl:value-of select="generate-id(.)"/>
                  </a>
            </sup>
      </xsl:template>
      <xsl:template match="footnote" mode="base">
            <a name="{generate-id(.)}"/>
            <xsl:value-of select="generate-id(.)"/>
            <xsl:text>) </xsl:text>
            <i>
                  <xsl:value-of select="."/>
            </i>
      </xsl:template>
      <xsl:template match="figure">
            <table>
                  <tr>
                        <td>
                              <xsl:value-of select="title"/>
                        </td>
                  </tr>
                  <xsl:apply-templates/>
            </table>
      </xsl:template>
      <xsl:template match="graphic">
            <tr>
                  <td>
                        <img alt="{@srccredit}" src="{@fileref}"/>
                  </td>
            </tr>
            <xsl:if test="@srccredit">
                  <tr>
                        <td>
                              <ul>
                                    <li>
                                          <xsl:value-of select="@srccredit"/>
                                    </li>
                              </ul>
                        </td>
                  </tr>
            </xsl:if>
      </xsl:template>
      <xsl:template match="simplelist">
            <ul>
                  <xsl:apply-templates/>
            </ul>
      </xsl:template>
      <xsl:template match="member">
            <li>
                  <xsl:apply-templates/>
            </li>
      </xsl:template>
      <xsl:template match="table">
            <table>
                  <xsl:apply-templates/>
            </table>
      </xsl:template>
      <xsl:template match="tgroup">
            <xsl:apply-templates select="thead|tbody|tfoot"/>
      </xsl:template>
      <xsl:template match="thead">
            <xsl:apply-templates select="row" mode="head"/>
      </xsl:template>
      <xsl:template match="row" mode="head">
            <th>
                  <xsl:apply-templates/>
            </th>
      </xsl:template>
      <xsl:template match="row">
            <tr>
                  <xsl:apply-templates/>
            </tr>
      </xsl:template>
      <xsl:template match="tbody|tfoot">
            <xsl:apply-templates/>
      </xsl:template>
      <xsl:template match="entry">
            <td>
                  <xsl:apply-templates/>
            </td>
      </xsl:template>
      <xsl:template match="trademark">
            <xsl:apply-templates/>
            <sup>TM</sup>
      </xsl:template>
      <xsl:template match="node()|@*" priority="-1">
            <xsl:copy>
                  <xsl:apply-templates select="node()|@*"/>
            </xsl:copy>
      </xsl:template>
</xsl:stylesheet>
