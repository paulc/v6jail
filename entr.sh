ls v6jail/*py | entr  rsync -av v6jail root@shell.pchak.net:.local/lib/python3.7/site-packages/ --exclude __pycache__  --exclude \*.swp
