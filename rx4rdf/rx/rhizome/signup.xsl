<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf="http://rx4rdf.sf.net/ns/racoon/xpath-ext#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:f="http://xmlns.4suite.org/ext" xmlns:x="http://www.w3.org/1999/XSL/Transform" exclude-result-prefixes="f wf a wiki rdf" version="1.0">
  <x:param name="_resource"/>
  <x:param name="action"/>
  <x:template match="/">
    <x:variable name="user" select='f:if($action!="new", $_resource)'/>
    <x:variable name="title" select="wf:assign-metadata('title',  f:if($user, concat('Edit Profile of ', $user/wiki:login-name), 'Register new user'))"/>
    <x:value-of select="$title"/>
    <hr/>
    <form action="{concat('users-',$_resource/wiki:login-name)}" method="post">
      <table>
        <x:choose>
          <x:when test="not($user)">
            <tr>
              <td>*Login name: </td>
              <td>
                <input type="text" name="loginname"/>
              </td>
            </tr>
          </x:when>
          <x:otherwise/>
        </x:choose>
        <tr>
          <td>Password: </td>
          <td>
            <input type="password" name="password" value="{$user/wiki:sha1-password}"/>
          </td>
        </tr>
        <tr>
          <td>Confirm Password: </td>
          <td>
            <input type="password" name="confirm-password" value="{$user/wiki:sha1-password}"/>
          </td>
        </tr>
        <tr>
          <td>email: </td>
          <td>
            <input type="text" name="email" value="{$user/wiki:email}"/>
          </td>
        </tr>
        <tr>
          <td>Full Name: </td>
          <td>
            <input type="text" name="fullname" value="{$user/wiki:fullname}"/>
          </td>
        </tr>
        <tr>
          <td>
            <input type="submit" name="action" value="{f:if($user,'save','creation')}">Signup</input>
          </td>
        </tr>
      </table>
    </form>
  </x:template>
</x:stylesheet>

