<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf="http://rx4rdf.sf.net/ns/racoon/xpath-ext#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:f="http://xmlns.4suite.org/ext" xmlns:x="http://www.w3.org/1999/XSL/Transform" exclude-result-prefixes="f wf a wiki rdf" version="1.0">
  <x:param name="_name"/>
  <x:template match="/">
    <form action="{$_name}" method="post">
      <input type="hidden" name="itemname" value="{$_name}"/>
      <table>
        <tr>
          <td colspan="2">
            <b>Are you sure you want to delete this page? This can not be undone. </b>
          </td>
        </tr>
        <tr>
          <td>
            <input type="submit" name="action" value="delete">Yes</input>
          </td>
          <td>
            <input type="submit" name="action" value="view">No</input>
          </td>
        </tr>
      </table>
    </form>
  </x:template>
</x:stylesheet>

