<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" 
xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" 
xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" 
xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" 
xmlns:x="http://www.w3.org/1999/XSL/Transform" xmlns:f="http://xmlns.4suite.org/ext" 
xmlns:auth="http://rx4rdf.sf.net/ns/auth#" 
exclude-result-prefixes="f wf a wiki rdf rdfs auth" version="1.0">
  <x:param name="__resource"/>
  
  <x:template name="rows">
     <x:param name='search'/>
     <x:param name='shownew'/>
<x:for-each select="$search">
    <x:variable name='resName' select="f:if(./wiki:name, ./wiki:name, f:if(./rdfs:label,./rdfs:label, name-from-uri(.) ))" />
        <tr>
          <td><x:value-of select='$resName' /></td>
          <td>
             <!-- /*[is-instance-of(.,'uri')] -->
            <a href="site:///search?search=%2F*%5Bis-instance-of%28.%2C%27{f:escape-url(string(.))}%27%29%5D&amp;searchType=RxPath&amp;view=list">List </a>
          </td>
          <td>
            <a href="site:///search?search=%2F*%5Bis-instance-of%28.%2C%27{f:escape-url(string(.))}%27%29%5D&amp;searchType=RxPath&amp;view=edit">Edit All </a>
          </td>
          <x:if test='$shownew'>
          <td>
            <a href="site:///.?about={f:escape-url(string(.))}&amp;action=new">New </a>
          </td>
          </x:if>
        </tr>  
</x:for-each>  
  </x:template>
  
  <x:template match="/">    
    <x:variable name='_robots' select="wf:assign-metadata('_robots', 'nofollow,noindex')" />
    <p>
    The tables below give you access that all the resources of this site. <br/>    
    To create new resources of any type, click <a href='site:///generic-new-template'>here</a>.<br/> 
    To delete resources, choose the appropriate "Edit All" link and delete the offending resources from the results.
    </p>
    <p>To execute arbitrary scripts or stylesheets, use the <a href='site:///Sandbox'>Sandbox</a>.<br/>
       To evaluate an arbitrary RxPath expression, use the search bar at the footer of this page.
    </p>   
       
      <b>Manageable Resources by Type</b>
      <table>   
      <!--       
      select all the classes that are handled in one way or the other      
      -->                    
      <x:call-template name='rows'>
        <x:with-param name='search' select="id(/*/wiki:action-for-type/*)[. != uri('rdfs:Resource')]" />
        <x:with-param name='shownew' select="true()" />
      </x:call-template>
      </table>  
      <b>Internal Resources by Type</b>
      <table>         
      <x:call-template name='rows'>
        <x:with-param name='search' select="id(/*/rdf:type/*)[not(. = /*/wiki:action-for-type)]"/>
      </x:call-template> 
      </table>  
      <b>List all <a href='site:///search?search=%2F*%5Bnot%28rdf%3Atype%29%5D&amp;searchType=RxPath&amp;view=list'>un-typed resources</a></b>
  </x:template>
</x:stylesheet>

