__include__('site-config.py')

#have Raccoon also check if the underlying files have changed
LIVE_ENVIRONMENT=1

#disable Python content authorization
authorizeContentProcessors['http://rx4rdf.sf.net/ns/wiki#item-format-python'] = lambda *args: 1
