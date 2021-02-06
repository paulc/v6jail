ls v6jail/*py | entr rsync -av v6jail root@jail.pchak.net:v6jail/ --exclude __pycache__  --exclude \*.swp
