def getContents(rev, __kw__, __server__, sep='\n'):    
    #todo: check that content isn't binary and (less important) that revision exists
    from Ft.Xml import InputSource
    contents = InputSource.DefaultFactory.fromUri('site:///'+ __kw__['name']+
        '?action=view-source&_disposition=http%3A//rx4rdf.sf.net/ns/wiki%23item-disposition-complete'
        '&_noErrorHandling=1&revision='+ str(rev)).read() #_noErrorHandling cuz we want errors to be raised
    #print >> sys.stderr, type(contents), contents
    lines = contents.split(sep)
    return lines

def makeDiff(fromlines, tolines,label1, label2, context, fullpage):
    from rx.htmldiff import HtmlDiff
            
    if fromlines != tolines:
        HtmlDiff._default_prefix = 0
        htmlDiff = HtmlDiff(wrapcolumn=60)                
        if fullpage:
            return htmlDiff.make_file(fromlines,tolines, label1, label2, 
                            context=context,numlines=context)
        else:
            return htmlDiff.make_table(fromlines,tolines, label1, label2, 
                    context=context,numlines=context) + htmlDiff._legend
    else:
        return "<b>%s and %s are identical</b>" % (label1, label2)

def run(__kw__, __server__, getContents, makeDiff):                   
  revisions = __kw__.get('rev')
  if  __kw__.get('diff') == 'Context':
     context = int(__kw__.get('context', 5))
  else:
     context = 0
  __kw__['_nextFormat'] = 'http://rx4rdf.sf.net/ns/wiki#item-format-xml' 
  #todo: error if item format is binary 
  if not isinstance(revisions, (type([]), type(()))) or len(revisions) != 2:
     print "<b>Error: you must select two revisions to diff.</b>"     
  else:
    revisions = [int(i) for i in revisions]
    revisions.sort()
    if revisions[0] == revisions[1]:        
       return "<b>%s and %s are identical</b>" % (label1, label2)
    fromlines = getContents(revisions[0], __kw__, __server__)
    if fromlines is None:
        return 
    tolines = getContents(revisions[1], __kw__, __server__)
    if tolines is None:
       return 
    label1 = 'Revision '+str(revisions[0])
    label2 = 'Revision '+str(revisions[1])       
    print makeDiff(fromlines, tolines, label1, label2,context, 
        __kw__.get('_disposition') == 'http://rx4rdf.sf.net/ns/wiki#item-disposition-complete')    

#this script isn't a real module so we must pass the variables defined here to run()
run(__kw__, __server__, getContents, makeDiff)