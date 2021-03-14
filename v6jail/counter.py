#!/usr/bin/env python3

import fcntl,sys,os
from contextlib import contextmanager

@contextmanager
def locked_fd(filename):
    fd = os.open(filename,os.O_RDWR|os.O_CREAT)
    fcntl.lockf(fd,fcntl.LOCK_EX)
    try:
        yield fd
    finally:
        os.fsync(fd)
        fcntl.lockf(fd,fcntl.LOCK_UN)
        os.close(fd)

def counter(filename,n=1):
    with locked_fd(filename) as fd:
        c = os.read(fd,40)
        new = (int(c) if c else 0) + n
        new_b = f'{new}\n'.encode('ascii')
        os.lseek(fd,0,os.SEEK_SET)
        os.write(fd,new_b)
        os.ftruncate(fd,len(new_b))
    return new

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='counter')
    parser.add_argument('filename',help='Counter filename')
    parser.add_argument('increment',type=int,nargs='?',default=1,help='Increment')
    args = parser.parse_args()
    print(counter(args.filename,args.increment))
