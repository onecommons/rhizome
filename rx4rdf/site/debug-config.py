__include__('site-config.py')

LIVE_ENVIRONMENT=1
authorizeContentProcessors['http://rx4rdf.sf.net/ns/wiki#item-format-python'] = lambda *args: 1