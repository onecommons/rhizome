try:
    includedir=__argv__[__argv__.index("--includedir")+1]
except (IndexError, ValueError):
    includedir='.'
__include__(includedir + '/test-config.py')

#save all content into the model (no external files)
MAX_MODEL_LITERAL = -1