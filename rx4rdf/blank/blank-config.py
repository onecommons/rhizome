#see rhizome/help/RaccoonConfig.txt for documentation on config file settings
SECURE_HASH_SEED = 'YOU SHOULD CHANGE THIS!'
ADMIN_PASSWORD = 'admin' #and change this too!

#If you don't set this then the hostname of this machine will be used
#this will cause big problem if you move the site to another machine!
#BASE_MODEL_URI='http://www.example.com/'

#make sure the path to rhizome-config.py is correct. If you installed rx4rdf 
#it will be in  <python share dir>/rx4rdf/rhizome (where <python share> is in  
#the Python install directory on Windows or on Unix-like systems one of the 
#standard "/usr/share", "usr/local/share", or "~/share")
__include__('../rhizome/rhizome-config.py') 

#you can speed up page display by setting these all to False:  
#externalLinkIndicator=False
#interWikiLinkIndicator=False
#undefinedPageIndicator=False
