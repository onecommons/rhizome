<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf="http://rx4rdf.sf.net/ns/raccoon/xpath-ext#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:f="http://xmlns.4suite.org/ext" xmlns:x="http://www.w3.org/1999/XSL/Transform" exclude-result-prefixes="f wf a wiki rdf" version="1.0">
  <x:param name="_name"/>
  <x:param name="__resource" />
  <x:template match="/">
    <form action="site:///{$_name}" method="post">
      <input type="hidden" name="itemname" value="{$_name}"/>
      <input type="hidden" name="about" value="{$__resource}"/>
      <table>
        <tr>
          <td colspan="2">
            <b>Are you sure you want to delete this page? This can not be undone. </b>
          </td>
        </tr>
        <tr>
          <td>
            <button type="submit" name="action" value="delete">Yes</button>
          </td>
          <td>
            <button type="submit" name="action" value="view">No</button>
          </td>
        </tr>
      </table>
    </form>
  </x:template>
</x:stylesheet>

