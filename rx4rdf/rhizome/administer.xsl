<?xml version="1.0" encoding="UTF-8"?>
<x:stylesheet xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf="http://rx4rdf.sf.net/ns/racoon/xpath-ext#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:a="http://rx4rdf.sf.net/ns/archive#" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" xmlns:x="http://www.w3.org/1999/XSL/Transform" xmlns:f="http://xmlns.4suite.org/ext" xmlns:auth="http://rx4rdf.sf.net/ns/auth#" exclude-result-prefixes="f wf a wiki rdf rdfs auth" version="1.0">
  <x:param name="__resource"/>
  <x:template match="/">
    <Administration/>
    <hr>
      <table>
        <tr>
          <td>Users</td>
          <td>
            <a href="site:///search?search=%2Fwiki%3AUser&amp;searchType=RxPath&amp;view=html&amp;Search=search">List </a>
          </td>
          <td>
            <a href="site:///search?search=%2Fwiki%3AUser&amp;searchType=RxPath&amp;view=edit&amp;Search=search">Edit All </a>
          </td>
          <td>
            <a href="site:///users/guest?action=new">New </a>
          </td>
        </tr>
        <tr>
          <td>Roles</td>
          <td>
            <a href="site:///search?search=%2Fauth%3ARole&amp;searchType=RxPath&amp;view=html&amp;Search=search">List </a>
          </td>
          <td>
            <a href="site:///search?search=%2Fauth%3ARole&amp;searchType=RxPath&amp;view=edit&amp;Search=search">Edit All </a>
          </td>
          <td>
            <a href="site:///new-role-template">New </a>
          </td>
        </tr>
        <tr>
          <td>Access Tokens </td>
          <td>
            <a href="site:///search?search=%2Fauth%3AAccessToken&amp;searchType=RxPath&amp;view=html&amp;Search=search">List </a>
          </td>
          <td>
            <a href="site:///search?search=%2Fauth%3AAccessToken&amp;searchType=RxPath&amp;view=edit&amp;Search=search">Edit All </a>
          </td>
          <td>
            <a href="site:///new-accesstoken-template">New </a>
          </td>
        </tr>
        <tr>
          <td>Folders </td>
          <td>
            <a href="site:///search?search=%2Fwiki%3AFolder&amp;searchType=RxPath&amp;view=html&amp;Search=search">List </a>
          </td>
          <td>
            <a href="site:///search?search=%2Fwiki%3AFolder&amp;searchType=RxPath&amp;view=edit&amp;Search=search">Edit All </a>
          </td>
          <td>
            <a href="site:///new-folder-template">New </a>
          </td>
        </tr>
        <tr>
          <td>Labels </td>
          <td>
            <a href="site:///search?search=%2Fwiki%3ALabel&amp;searchType=RxPath&amp;view=html&amp;Search=search">List </a>
          </td>
          <td>
            <a href="site:///search?search=%2Fwiki%3ALabel&amp;searchType=RxPath&amp;view=edit&amp;Search=search">Edit All </a>
          </td>
          <td>
            <a href="site:///new-label-template">New </a>
          </td>
        </tr>
        <tr>
          <td>Dispositions</td>
          <td>
            <a href="site:///search?search=%2Fwiki%3AItemDisposition&amp;searchType=RxPath&amp;view=html&amp;Search=search">List </a>
          </td>
          <td>
            <a href="site:///search?search=%2Fwiki%3AItemDisposition&amp;searchType=RxPath&amp;view=edit&amp;Search=search">Edit All </a>
          </td>
          <td>
            <a href="site:///new-disposition-template">New </a>
          </td>
        </tr>
        <tr>
          <td>Doc Types</td>
          <td>
            <a href="site:///search?search=%2Fwiki%3ADocType&amp;searchType=RxPath&amp;view=html&amp;Search=search">List </a>
          </td>
          <td>
            <a href="site:///search?search=%2Fwiki%3ADocType&amp;searchType=RxPath&amp;view=edit&amp;Search=search">Edit All </a>
          </td>
          <td>
            <a href="site:///new-doctype-template">New </a>
          </td>
        </tr>
      </table>
    </hr>
  </x:template>
</x:stylesheet>

