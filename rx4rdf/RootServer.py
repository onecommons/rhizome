'''
This kicks off Rhizome when being invoked from a Apache fastcgi script that starts a script that looks like:
#!/bin/tcsh
python2.2 /home/asouzis/asouzis.python-hosting.com/RootServer.py -s /home/asouzis/asouzis.python-hosting.com/RootServer.cfg >& /dev/null &

As you can see this is a bit of hack -- there are more levels of indirection than necessary.
for more infomation on using Rhizome's built-in http server with Apache and FastCGI see
http://www.cherrypy.org/static/html/howto/node3.html#SECTION003300000000000000000
'''
try:
    import os, sys
    os.chdir('site')    
    sys.path.append('..')
    import rx.racoon 
    rx.racoon.main(sys.argv[1:] + ['-l', '-a', 'site-config.py'])
except:
    import traceback
    f=open("bootstrap.log", "a")
    f.write(sys.version)
    traceback.print_exc(file=f)
    f.close()

