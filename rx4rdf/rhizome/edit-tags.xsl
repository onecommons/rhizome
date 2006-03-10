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

<xsl:variable name='expires' select="wf:assign-metadata('response-header:expires', '-1')" />	

<xsl:template name="write-keywords">
<xsl:param name="topics" />
<xsl:param name="width" select='40' />
<xsl:param name="field-name" select='"keywords"' />
<xsl:param name="add-script" select='true()' />

<xsl:if test='$add-script'>
    <script language="JavaScript">
    <xsl:comment><![CDATA[    
        function domouseout(e, fromElement){  
          var toElement = (e && e.relatedTarget) || window.event.toElement;
          var currElement = toElement;
          while (currElement != fromElement)
          {
             currElement = currElement.parentNode;
             if (!currElement) {
                //reached the top, must be outside the div so hide it after a tiny delay
                var closure = function() { divSetVisible(fromElement, false);};
                setTimeout(closure, 500);  
                return true;    
            }        
          }  
        }
        
        function updateEditField(e, inputID) {
          var elem = (e && e.currentTarget ) || window.event.srcElement;
          var remove = !elem.checked;
          if (remove) {
            document.getElementById(inputID).value = document.getElementById(inputID).value.replace(elem.value, '');
          }
          else {
            document.getElementById(inputID).value = document.getElementById(inputID).value + elem.value + ' ';
          }
        }

       function getAbsX(elt) { return (elt.x) ? elt.x : getAbsPos(elt,"Left"); }
       function getAbsY(elt) { return (elt.y) ? elt.y : getAbsPos(elt,"Top"); }
       function getAbsPos(elt,which) {
        	iPos = 0;
        	while (elt != null) {
        	    iPos += elt["offset" + which];
        	    elt = elt.offsetParent;
        	}
        	return iPos;
      }
       
      function showOrHide(textId, divId) {
       var selDiv = document.getElementById(divId);
       if (selDiv.style.display=='none') 
       {    
          var selTxt = document.getElementById(textId);         
          selDiv.style.top = (getAbsY(selTxt)+selTxt.offsetHeight+1) + 'px';
          selDiv.style.left = getAbsX(selTxt) +'px';
          selDiv.style.width = selTxt.offsetWidth + 'px';
          
          //selDiv.style.display='block';
          divSetVisible(selDiv, true);
       }
       else {
          //selDiv.style.display='none'; 
          divSetVisible(selDiv, false);
       }
     }

    function divSetVisible(DivRef, state)
    {
        var IfrRef = document.all ? document.getElementById('DivShim') : null;
        if(state) {
          DivRef.style.display = "block";
          if (IfrRef) {//IE hack
            IfrRef.style.width = DivRef.offsetWidth;
            IfrRef.style.height = DivRef.offsetHeight;
            IfrRef.style.top = DivRef.style.top;
            IfrRef.style.left = DivRef.style.left;
            IfrRef.style.zIndex = DivRef.style.zIndex - 1;
            IfrRef.style.display = "block";            
          }
        }
        else {
           DivRef.style.display = "none";
           if (IfrRef)
              IfrRef.style.display = "none";
        }
    }      
    ]]> 
    //</xsl:comment>
    </script>    
</xsl:if>

    <xsl:variable name='keywords'>
         <xsl:for-each select='$topics'>          
           <xsl:value-of select='f:if(namespace-uri-from-uri(.)=concat($BASE_MODEL_URI,"kw#"),local-name-from-uri(.), name-from-uri(.))'/>
           <xsl:text> </xsl:text>
         </xsl:for-each>
    </xsl:variable>    

	<input TYPE="text" NAME="{$field-name}" VALUE="{$keywords}" SIZE="{$width}" MAXLENGTH="200" id='{$field-name}Txt' />	 
	<img src="site:///arrow_up.gif" onmousedown="this.src='site:///arrow_down.gif'" style='vertical-align: bottom'
	    onload="this.height=document.getElementById('{$field-name}Txt').offsetHeight"
	    onmouseup="this.src='site:///arrow_up.gif'" onmouseout="this.src='site:///arrow_up.gif'"
	    onclick="showOrHide('{$field-name}Txt', '{$field-name}Div');" />

     <div style='border: solid gray 1px; background-color: #ffffdd; display: none; z-index: 2; position: absolute' 
       id='{$field-name}Div' onmouseout="domouseout(event, this)" >    
       
        <xsl:for-each select='/wiki:Keyword | id(/*/wiki:about/*)' >
          <xsl:variable name='kwValue' select='f:if(namespace-uri-from-uri(.)=concat($BASE_MODEL_URI,"kw#"),
                                                        local-name-from-uri(.), name-from-uri(.))' />   
                                                                                                                       
          <input type="checkbox" value="{$kwValue}" onclick="updateEditField(event, '{$field-name}Txt')">
            <xsl:if test="contains($keywords,$kwValue)">
               <xsl:attribute name='checked'>checked</xsl:attribute>
            </xsl:if>
          </input>
          <a href="site:///keywords/{local-name-from-uri(.)}?about={f:escape-url(.)}" title='{rdfs:comment}' >
            <xsl:value-of select='$kwValue' />
          </a>
          <br/>
        </xsl:for-each>
    </div> 
   <xsl:comment>hack for IE</xsl:comment> 
   <iframe id="DivShim" src="javascript:false;" scrolling="no" frameborder="0"
           style="position:absolute; top:0px; left:0px; display:none;">
   </iframe>       
</xsl:template>

</xsl:stylesheet>