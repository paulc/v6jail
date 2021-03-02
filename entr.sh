
/bin/ls -d v6jail bin/v6 v6jail/*.py | entr -c make upload-shiv

# ls v6jail/*py | entr rsync -av v6jail ${UPLOAD?} --exclude __pycache__  --exclude \*.swp
