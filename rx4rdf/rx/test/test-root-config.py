try:
    rhizomedir=__argv__[__argv__.index("--rhizomedir")+1]
except (IndexError, ValueError):
    rhizomedir='../rhizome'
__include__(rhizomedir + '/root-config.py')

APPLICATION_MODEL = rxml.zml2nt(nsMap = nsMap, contents='''
 {http://www.foo.com/}:
   config:hostname: "foo.com"
   config:hostname: "foo.org"
   config:hostname: "foo.bar.org"
   config:config-path: "test-links.py"
   config:path: "."

 {http://bar.org/bar/}:
   config:appBase: "/bar"
   config:appName: "bar"
   config:config-path: "test-links.py"
   config:path: "."
''')