<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" xmlns:x="http://www.w3.org/1999/XSL/Transform" xmlns:f="http://xmlns.4suite.org/ext" xmlns:auth="http://rx4rdf.sf.net/ns/auth#" exclude-result-prefixes="f wf a wiki rdf rdfs auth" version="1.0">
  <x:param name="__resource"/>
  <x:param name="action"/>
  <x:param name="__passwordHashProperty"/>
  <x:template match="/">
    <x:variable name="user" select='f:if($action!="new", $__resource)'/>
    <x:variable name="title" select="wf:assign-metadata('title',  f:if($user, concat('Edit Profile of ', $user/wiki:login-name), 'Register new user'))"/>
    <x:value-of select="$title"/>
    <hr/>
    <form action="{concat('site:///users/',$__resource/wiki:login-name)}" method="post">
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
          <x:otherwise>
            <input type="hidden" name="loginname" value="{$__resource/wiki:login-name}"/>
          </x:otherwise>
        </x:choose>
        <tr>
          <td>Password: </td>
          <td>
            <input type="password" name="password" value="{$user/*[uri(.)=$__passwordHashProperty]}"/>
          </td>
        </tr>
        <tr>
          <td>Confirm Password: </td>
          <td>
            <input type="password" name="confirm-password" value="{$user/*[uri(.)=$__passwordHashProperty]}"/>
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
            <button type="submit" name="action" value="{f:if($user,'save','creation')}">Signup</button>
          </td>
        </tr>
      </table>
    </form>
  </x:template>
</x:stylesheet>

