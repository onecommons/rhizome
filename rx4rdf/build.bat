del docs\*.
cd site
python ..\rx\raccoon.py -x -a site-config.py -export ../docs -static
cd ..
python setup.py sdist --force-manifest --formats=gztar,zip

