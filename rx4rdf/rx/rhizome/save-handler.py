def _req_default_save(self, **kw):
    '''This is the form handler for the built-in default_edit page'''
    #print 'saving...'
    wikiname = kw['itemname'] 
    contents = kw['file'] or kw['contents']
    title = kw['title']
    label = ''#kw['label']
    authtoken = kw['authtoken']
    #sha = utils.shaDigestString(contents)
    itemURI = generateBnode()
    nameURI = self.BASE_MODEL_URI + filter(lambda c: c.isalnum() or c in '_-./', wikiname) #note filter: URI fragment might not match wikiname
    patchRefURI = itemURI #if we create a patch, its base should be this content
    listURI = generateBnode()
    
    #update algorithm:
    #    if currentcontent:
    #       patch = diff currentcontent newcontent
    #       replace current content with patch
    #    append new revision with newcontent
    #todo: don't patch binary content (where line feeds are signficant)    
    #todo: only do a diff with inline content -- so we don't have to worry about the file changing out from underneath us:
    patch = ''
    patchTransformURI = ''
    if not kw.get('minor_edit'):
        #given a tree like: item/contents/dynamic-transform/contents/static-transform1/contents/static-transform2/contents/text()
        #1. start with the latest revision:
        currentItemXpath = '/*[wiki:name/text()="%s"]/wiki:revisions/*[last()]' % wikiname
    ##    #2. descendent-or-self subject with a contents predicate that not pointing dynamic transform
    ##    #  (because we don't support subclasses yet we need the starts-with() hackery
    ##    nonDynamicContentXPath = './/*[a:contents[not( starts-with(*/a:transformed-by/*/@rdf:about, "http://rx4rdf.sf.net/ns/wiki#item-format-"))]]'
    ##    #3 get the first (shallowest - (nodeset)[1]) node in the nodeset 
        # above is too complicated: instead skip all transformations by just get the last (deepest - (nodeset)[last()] ) resource element with a 'contents' predicate    
        nonDynamicContentXPath = '//*[a:contents]'
        oldcontentXPath = '(' + currentItemXpath + nonDynamicContentXPath + ')[last()]'
        oldContentResource = self.evalXPath(oldcontentXPath, kw)
        if oldContentResource:
            oldContents = self.doActions([self.rhizome.findContentAction, self.rhizome.processContentAction], kw.copy(), oldContentResource[0])         
            if oldContents:
                patchTupleList = utils.diff(contents, oldContents) #compare  
                if patchTupleList is not None:
                    patch = pickle.dumps(patchTupleList)
                    patchTransformURI = generateBnode()
    kw['patch'] = patch
    #note: we just compared the raw content, so any encoding has to happen after diff-ing

    format = kw['format']
    if not format: 
        format = 'http://rx4rdf.sf.net/ns/wiki#item-format-binary'  #unnecessary, but for now always have a format
    formatTransformURI = generateBnode()        
    patchRefURI = formatTransformURI #patch base should be innermost content
    
    encodedURI = ''    
    if kw['file']:
        try:
            contents.encode('ascii') #test to see if is just ascii (all <128)
        except UnicodeError:
            encodedURI = generateBnode()
            patchRefURI = encodedURI#we want our patch to reference the raw content (thus the innermost content resource)
            contents = base64.encodestring(contents)

    contentLength = len(contents)            
    if self.MAX_MODEL_LITERAL > -1 and contentLength > self.MAX_MODEL_LITERAL:  #save as file
        import os.path                    
        filepath = self.SAVE_DIR + wikiname
        if wikiname.find('.') == -1 and self.rhizome.exts.get(format):
            filepath += '.' + self.rhizome.exts[format]
        try: 
           os.makedirs(self.SAVE_DIR)
        except OSError: pass #dir might already exist
        f = file(filepath, 'wb')
        f.write(contents)
        f.close()
        #we assume SAVE_DIR is a relative path rooted in one of the directories on the RHIZOME_PATH
        contentRef = "<rdf:Description rdf:about='path:" + filepath+"' />"
        contentResource = "<a:ContentLocation rdf:about='path:" + filepath+"' />"
    else:
        contentRef = "<xu:value-of select='$contents'/>"
        contentResource = ""

    kw['contents'] = contents
        
    disposition = kw['disposition']    

    curtime = time.time()
    
    xupdate=\
    '''<xu:modifications version="1.0" xmlns:xu="http://www.xmldb.org/xupdate"
		    xmlns="http://rx4rdf.sf.net/ns/archive#" xmlns:a="http://rx4rdf.sf.net/ns/archive#"
			xmlns:wiki="http://rx4rdf.sf.net/ns/wiki#" xmlns:wf='http://rx4rdf.sf.net/ns/racoon/xpath-ext#'
			xmlns:auth="http://rx4rdf.sf.net/ns/auth#"
			xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#' >

    <xu:if test='number($startTime) &lt; /*[wiki:name/text()="%(wikiname)s"]/a:last-modified/text()'>
        <xu:message text="Conflict: Item has been modified after you started editing this item!" terminate="yes" />
    </xu:if>
    <xu:if test='$patch and /*[wiki:name/text()="%(wikiname)s"]/wiki:revisions/*'>  
        <xu:update select='(/*[wiki:name/text()="%(wikiname)s"]/wiki:revisions/*[last()]//a:contents)[last()]'>
            <rdf:Description rdf:about='%(patchTransformURI)s' />
        </xu:update>
        <xu:append select='/'>
            <a:ContentTransform rdf:about='%(patchTransformURI)s'>
                <a:transformed-by><rdf:Description rdf:about='http://rx4rdf.sf.net/ns/content#pydiff-patch-transform'/></a:transformed-by>
                <a:contents><xu:value-of select='$patch'/></a:contents>
                <a:pydiff-patch-base><rdf:Description rdf:about='%(patchRefURI)s' /></a:pydiff-patch-base>
            </a:ContentTransform>
        </xu:append>
    </xu:if>

    <!-- if the wikiname does not exist, add it now -->    
    <xu:if test='not(/*[wiki:name/text()="%(wikiname)s"])'>
        <xu:append select='/'>
			<NamedContent rdf:about='%(nameURI)s'>
			<wiki:name>%(wikiname)s</wiki:name>
			<a:last-modified>%(curtime).3f</a:last-modified>
			<wiki:revisions listID='%(listURI)s' />
			</NamedContent>
        </xu:append>
    </xu:if>
    <xu:if test='/*[wiki:name/text()="%(wikiname)s"]/a:last-modified'>
        <xu:update select='/*[wiki:name/text()="%(wikiname)s"]/a:last-modified'>%(curtime).3f</xu:update>
    </xu:if>
    
    <!-- don't bother saving the last revision if this was just a minor edit
    todo: this doesn't delete the actual content if stored in an external file
    -->    
    <xu:if test='wf:get-metadata("minor_edit") and /*[wiki:name/text()="%(wikiname)s"]/wiki:revisions/*'>
    <xu:remove select='/*[wiki:name/text()="%(wikiname)s"]/wiki:revisions/*[last()]'/>
    </xu:if>

    <!-- set access control: remove previous, add selected, if any -->
    <xu:remove select='/*[wiki:name="%(wikiname)s"]/auth:needs-token'/>
    <xu:if test="$authtoken"> 
       <xu:append select='/*[wiki:name="%(wikiname)s"]'>    
         <auth:needs-token><xu:attribute name="rdf:resource"><xu:value-of select="$authtoken"/></xu:attribute></auth:needs-token>
       </xu:append>
    </xu:if>
    
    <!-- add a new revision -->
    <xu:append select='/'>
        <xu:if test="string('%(encodedURI)s')"> 
            <a:ContentTransform rdf:about='%(encodedURI)s'>
            <a:transformed-by><rdf:Description rdf:about='http://www.w3.org/2000/09/xmldsig#base64'/></a:transformed-by>
            <a:contents>%(contentRef)s</a:contents>
            </a:ContentTransform>        
        </xu:if>

        <a:ContentTransform rdf:about='%(formatTransformURI)s'>
        <a:transformed-by><rdf:Description rdf:about='%(format)s'/></a:transformed-by>
        <a:contents>
            <xu:if test="string('%(encodedURI)s')"><rdf:Description rdf:about='%(encodedURI)s' /></xu:if>
            <xu:if test='not(string("%(encodedURI)s"))'>%(contentRef)s</xu:if>
        </a:contents>
        </a:ContentTransform>
        %(contentResource)s
    
        <wiki:Item rdf:about='%(itemURI)s'>
            <a:contents><rdf:Description rdf:about='%(formatTransformURI)s' /></a:contents>
            <wiki:item-disposition><rdf:Description rdf:about='%(disposition)s' /></wiki:item-disposition>
            <xu:if test='wf:get-metadata("doctype")'>
                <wiki:doctype><xu:attribute name="rdf:resource"><xu:value-of select="$doctype"/></xu:attribute></wiki:doctype>
            </xu:if>
            <xu:if test='$title'>
                <wiki:title>%(title)s</wiki:title>
            </xu:if>
            <!--<xu:if test='$label'>
                <wiki:has-label>%(label)s</wiki:has-label>
            </xu:if> -->
            <a:created-on>%(curtime).3f</a:created-on>
            <wiki:created-by><xu:attribute name="rdf:resource"><xu:value-of select="$_user"/></xu:attribute></wiki:created-by>
        </wiki:Item>        	    
        <xu:if test="wf:assign-metadata('revision-added', '%(itemURI)s')" /> <!-- do nothing - just for the side-effect -->
        <xu:if test="wf:assign-metadata('_update-trigger', 'revision-added')" /> <!-- do nothing - just for the side-effect -->
    </xu:append>
    
    <xu:append select='/*[wiki:name/text()="%(wikiname)s"]/wiki:revisions'>
        <wiki:Item rdf:about='%(itemURI)s' />
    </xu:append>
        
	</xu:modifications>
	''' % locals()
    #sys.stderr.write(xupdate)
    #sys.stderr.flush()
    self.xupdate(str(xupdate), kw)
    #return self.handleRequest(wikiname, **kw)

_req_default_save(__requestor__.server, **locals())