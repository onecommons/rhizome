<x:stylesheet version="1.0" xmlns:x="http://www.w3.org/1999/XSL/Transform" 
     xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'
     xmlns:wf='http://rx4rdf.sf.net/ns/raccoon/xpath-ext#'
     xmlns:f = 'http://xmlns.4suite.org/ext' 
     xmlns:a="http://rx4rdf.sf.net/ns/archive#"
     xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#"
     xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
     xmlns:auth="http://rx4rdf.sf.net/ns/auth#"
     xmlns:foaf="http://xmlns.com/foaf/0.1/"
     xmlns:response-header = 'http://rx4rdf.sf.net/ns/raccoon/http-response-header#'
     exclude-result-prefixes = "f wf a wiki rdf rdfs auth foaf response-header" >
  <x:output method='xhtml' omit-xml-declaration="yes" encoding="UTF-8" indent='yes' />
  <x:param name="__resource" />
  <x:param name="__account" />
  <x:param name="action" />
  <x:param name="__passwordHashProperty" />
  
  <x:variable name='expires' select="wf:assign-metadata('response-header:expires', '-1')" />
  
  <x:template match='/'>
    <x:variable name='account' select='f:if($action!="new", $__resource)' />
    <x:variable name='user' select='/foaf:Person[foaf:holdsAccount = $account]' />
    <x:variable name='title' select="wf:assign-metadata('title', 
f:if($account, concat('Edit Profile of ', $account/foaf:accountName), 'Register new user'))" />

<style type="text/css">
#content-display-cell table, #content-display-cell td{
    border:none;
    }
.textfield {
	width:12.5em;
	}
.rolesListbox {
	width:13.6em;
	}
.ralign {
	text-align:right;
	}
.lalign {
	text-align:left;
	}
.narrow {
	width:7em;
	}
#roledetails {
	background-color:#ddd;
	height:5.6em;
	vertical-align:top;
	}
.bottom {
	vertical-align:bottom;
	}
.top	{
	vertical-align:top;
	}
.buttons {
	text-align:center;
	vertical-align:top;
	padding-top:2.5em;
	}
#usernameField {
	padding-left:3px;
	}
#passbutton {
	padding-left:7.5em;
	}
.demolink {
	float:right;
	margin-top:-20px;
	}
</style>

<script language="javascript" type="text/javascript">
<x:comment><![CDATA[
function doSubmit() {
  var assigned = document.getElementById('assigned');   
  for (var i=0; i < assigned.options.length; i++) {     
     var opt = assigned.options[i];
     opt.disabled = false; //might have been disabled
     opt.selected = true;
  }
  return true; // do submit
}

function exchangeVals (button) {
    var list1=(button=="assign")?"roles":"assigned";
    var list2=(button=="remove")?"roles":"assigned";
    var toMoveVal = new Array();
    var toMoveText = new Array();
    var toMoveNum = new Array();
    var toMoveTitle = new Array();
    
    for (var i=0;i<document.getElementById(list1).length;i++) {
    	if (document.getElementById(list1).options[i].selected==true) {
    		toMoveVal.push(document.getElementById(list1).options[i].value);
    		toMoveText.push(document.getElementById(list1).options[i].text);
    		toMoveTitle.push(document.getElementById(list1).options[i].title);
    		toMoveNum.push(i);
    	}
    }
    
    for (var i=0;i<toMoveVal.length;i++) {
    	var selectend=document.getElementById(list2).length;
    	var newOption= new Option(toMoveText[i], toMoveVal[i]);
    	newOption.title=toMoveTitle[i];
    	document.getElementById(list2).options[document.getElementById(list2).length]=newOption;
    	document.getElementById(list1).remove(toMoveNum[i]-i);
    }
    updateDetails();
}

function updateDetails(selectedList) {
    var defaultroledetails="Select a role to view further information."
    var selectedItem=(selectedList)?document.getElementById(selectedList).selectedIndex:null;
    var button=(selectedList=="roles")?"assign":"remove";
    var otherbutton=(selectedList=="roles")?"remove":"assign";
    var otherselect=(selectedList=="roles")?"assigned":"roles";
    
    if (selectedItem!=null){
        var selectedOption = document.getElementById(selectedList).options[selectedItem]
        var roleLink = '<a href="site:///?about=' + escape(selectedOption.value)+'" alt="View Role">' + selectedOption.text + '</a>';
    	document.getElementById("roledetails").innerHTML=roleLink + " <em>"+selectedOption.title+"</em>"; 
    	document.getElementById(button).disabled=false;
    	document.getElementById(otherbutton).disabled=true;
    	document.getElementById(otherselect).selectedIndex=-1;
    }
    else {  			//onload and after exchange
    
    //sorts and creates listboxes     
    	
        function createListBoxArray(selectName) {
            var selectList = new Array ();
            var selectElement = document.getElementById(selectName);
    		for (var i=0;i<selectElement.length; i++) {
    	        var val=selectElement.options[i].value;
    		    var txt=selectElement.options[i].text;		    
    		    var title=selectElement.options[i].title;		    
    		    selectList[i] = { 'txt': txt, 'val': val, 'title': title };
            }       
    		selectList.sort(sortAlph);		
    
    		for (var i=0;i<selectElement.length;i++){
    			selectElement.options[i].text=selectList[i].txt;	
    			selectElement.options[i].value=selectList[i].val;	
    			selectElement.options[i].title=selectList[i].title;	
    		}        
        }
    
        createListBoxArray('assigned');
        createListBoxArray('roles');
    //list sort seems to work perfectly but if you exchange values in IE many times, error in line 75 '(if (a<b)' "number expected", no specific reproducible steps
    
    	document.getElementById("roledetails").innerHTML=defaultroledetails;
    	document.getElementById(button).disabled=true;
    	document.getElementById(otherbutton).disabled=true;
    }
}

function sortAlph(aobj,bobj) {
    var a = aobj.txt.toLowerCase();
    var b = bobj.txt.toLowerCase();
    if (a<b){
        return -1;
    }
    else if (a>b) {
    	return 1;
    }
    else {
    	return 0;
    }
}
]]>//</x:comment>
</script>

    <form action="site:///accounts/?about={f:escape-url(f:if($account, $account, 'http://xmlns.com/foaf/0.1/OnlineAccount'))}" 
          onsubmit='return doSubmit()' accept-charset='UTF-8' method='post'>  
    <table>
 <tr><td class="narrow"></td><td></td></tr>
<!--    <tr> 
      <td colspan="2"><strong>Account Info</strong>
      <hr/></td>
    </tr>    
--> <x:choose>
  <x:when test='not($account)'>    
    <tr>       
    <td colspan="2">&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;Login name:    
    <input type="text" name="loginname" id="username" class="textfield" /> *
    </td></tr>
  </x:when>            
  <x:otherwise>
    <input type='hidden' name='loginname' value="{$account/foaf:accountName}" />
  </x:otherwise>
 </x:choose>
 
<x:if test='not($account)'>
    <tr>
      <td>
        </td>
      <td>
      <input type="checkbox" name="loginnow" value="1">
      <x:if test="$__account/foaf:accountName = 'guest'"><x:attribute name='checked'>checked</x:attribute></x:if>
      </input>           
      Login as user after account creation</td>
    </tr>
</x:if> 

 <!--
    <div id="passtable2">
    <table><tr> 
      <td class="ralign narrow">
        Old Password:</td>
      <td>        
        <input type="text" name="oldpassword" class="textfield"/>
      </td>
    </tr>
    <tr> 
      <td class="ralign">
        New Password:</td>
      <td>        <input type="text" name="newpassword" class="textfield"/>&#xA0;(6-20 characters)</td>
    </tr><tr> 
      <td class="ralign narrow">
        Confirm New:</td>
      <td>        
        <input type="text" name="confirmnewpassword" class="textfield"/>
      </td>
    </tr>
    </table>
    </div>
    <div id="passbutton"><input type="button" value="Change Password" id="changepass" onclick="changePass()"/></div>
 -->
   
     
    <tr>
      <td colspan="2"><br/><strong>User Information </strong>
      <hr/></td>
    </tr>
    <tr>
      <td class="ralign">&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;Email:</td>
      <td>
        <input type="text" name="email" id="email" value="{substring-after($user/foaf:mbox,'mailto:')}"  class="textfield"/>
      </td>
    </tr>
 <!--
    <tr> 
      <td class="ralign">
        Website&#xA0;Address: </td>
      <td>        <input type="text" name="website" id="website" class="textfield"/>        </td>
    </tr>
    <tr>
      <td class="ralign"> 
        Website Name: </td>
      <td>
        <input type="text" name="websitename" id="websitename" class="textfield"/> 
       </td>
    </tr>
  -->
    <tr>
      <td class="ralign">Full Name:</td>
      <td class="lalign"><input type='text' name='fullname' value="{$user/foaf:name}" class="textfield"/></td>
    </tr>
 <!--
    <tr class="top">
      <td class="ralign">
        About Me: </td>
      <td class="narrow">
        <textarea name="aboutme" id="aboutme" cols="50" rows="6"></textarea> </td>
    </tr>
 -->   
 <x:if test='$account'>
    <tr id="changepass">
      <td></td><td><input type="button" onclick="document.getElementById('passtable1').style.display='block';
                           document.getElementById('changepass').style.display='none'" value="Change Password"/></td>
    </tr>
 </x:if>    
    <tr>
      <td colspan="2">
      <div id="passtable1" style="display:{f:if($account,'none','block')}">      
    <table><tr> 
      <td class="ralign">
        Password:</td>
      <td>        
        <input type="password" name="password" class="textfield" value="{$account/*[uri(.)=$__passwordHashProperty]}" />
        <x:value-of select='f:if($account,"", "&#xA0;*")' /></td>
    </tr>
    <tr> 
      <td class="ralign">
        Confirm&#xA0;Password:</td>
      <td>
      <input type="password" name="confirm-password" class="textfield" value="{$account/*[uri(.)=$__passwordHashProperty]}"/>
      <x:value-of select='f:if($account,"", "&#xA0;*")' /></td>
    </tr>
    </table></div></td>
    </tr>   
 <x:variable name='availableRoles' select='$__account/auth:can-assign-role/* | $__account/auth:has-role/*/auth:can-assign-role/*' />
 <x:if test='$availableRoles'>
   <!-- if there are roles that the current user can assign -->
    <input type='hidden' name='setroles' value="1" />
    <tr>
      <td colspan="2"><strong>Roles</strong>
        <hr/></td>
    </tr>
    <tr>
      <td>&#xA0;</td>
      <td><table class="narrow">
        <tr class="bottom">
          <td>&#xA0;<em>Available Roles</em></td>
          <td>&#xA0;</td>
          <td>&#xA0;<em>Assigned Roles</em></td>
        </tr>
        <tr>          
          <td><select name="roles" id="roles" size="10" class="rolesListbox" onchange="updateDetails(this.name)" multiple='multiple' >
             <x:for-each select='$availableRoles[not(. = $account/auth:has-role/*)]'>
              <option value="{.}" title="{./rdfs:comment}">
                <x:value-of select='f:if(./rdfs:label,./rdfs:label, name-from-uri(.))'/>
              </option>
             </x:for-each>
          </select></td>
          <td class="buttons">
              <input type="button" name="assign" id="assign" onclick="exchangeVals(this.name)" value="Assign >"/><br/><br/>
               <input type="button" name="remove" id="remove" onclick="exchangeVals(this.name)" value="Remove&lt;"/>
                </td>
          <td>
            <select name="assigned" id="assigned" size="10" class="rolesListbox" onchange="updateDetails(this.name)" multiple='multiple'>
             <x:for-each select='$account/auth:has-role/*'>
                <option value="{.}" title="{f:if(./rdfs:comment, ./rdfs:comment, f:if(./rdfs:label,./rdfs:label, name-from-uri(.)))}">
                <x:if test="not(. = $availableRoles)">
                    <x:attribute name='disabled'>disabled</x:attribute>
               </x:if>
                <x:value-of select='f:if(./rdfs:label,./rdfs:label, name-from-uri(.))'/>
               </option>
             </x:for-each>
             </select>
          
            </td>
        </tr>
        <tr>
          <td colspan="3" id="roledetails">
                    </td>
          </tr>
      </table></td>
    </tr>
    <tr>
      <td colspan="2"><hr/></td>
    </tr>
    </x:if>
   

 <x:if test='not($account)'>
    <tr class="top">
      <td colspan="2" id="mandatory" class="lalign">&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;&#xA0;*&#xA0;Required&#xA0;fields</td>
    </tr>
 </x:if>
    <tr> 
      <td colspan="2">&#xA0;
                <!-- workaround IE bug: value doesn't work with button -->
               <input type="hidden" name="action" value="{f:if($account,'save','creation')}" />
               <button type='submit'><x:value-of select='f:if($account,"Save Changes", "Create New Account")' /></button>
      </td></tr>
  </table>
</form>

   </x:template>
   </x:stylesheet>