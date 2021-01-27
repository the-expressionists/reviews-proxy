#!/usr/bin/python3

import re
import os
import subprocess
import sys
import asyncio
import inspect
import contextlib
import signal
import argparse
from collections import namedtuple 
from functools import partial

@contextlib.contextmanager
def pushd(dir):
    prev_dir = os.getcwd()
    os.chdir(dir)
    try:
        yield
    finally:
        os.chdir(prev_dir)

def find_git_modules():
    path_reg = r"^\s*path\s*=\s*(?P<path>[\w\-]+)$"
    with open('.gitmodules', 'r') as fp:
        s = fp.read()
        return re.findall(path_reg, s, re.MULTILINE|re.ASCII)

def npm_install(path):
    with pushd(path):
        print(f"Installing npm modules for {path}!")
        os.system("npm install")

def parse_args(argv):
    args = [ ('install', 'Install dependencies for services')
           , ('clone', 'Clone down submodules')
           , ('build', 'Build bundles for all services')
           , ('run', 'Run all services')
           ]
    parser = argparse.ArgumentParser(description="Helper script for the JTWENL proxy server")
    actions = parser.add_mutually_exclusive_group(required=True)
    for arg, help in args:
        actions.add_argument('--'+arg, f"-{arg[0]}", help=help, action='store_true')

    return parser.parse_args(argv)

async def lift(f, *args):
    if inspect.iscoroutinefunction(f):
        print('yep')
        return await(f(*args))
    return f(args)

async def pushd_each(paths, f):
    for p in paths:
        with pushd(p):
            await lift(f, p)
    return None

async def buildall(paths):
    return await pushd_each(paths, lambda _: os.system("npm run build"))

async def clone_modules():
    os.system("git submodule update --init --recursive --remote")

async def run_services(paths):
    procs = []
    async def run_service(p):
        try:
            proc = subprocess.Popen(["npm", "start"])
            print(f"Service running in the background: {p}, new pid is {proc.pid}")
            procs.append(proc)
        except OSError as e:
            print(e)
            pretty_kill(procs)
            sys.exit(1)
    await pushd_each(paths, run_service)
    return procs

def run_installs(paths):
    for p in paths:
        npm_install(p)
    return

async def bg_loop():
    while True:
        # just a dummy loop to keep it from exiting
        await asyncio.sleep(300)

def pretty_kill(procs):
    print("") # create newline after ^C
    for i in procs:
        print(f"killed pid {i.pid}")
        i.terminate()
    return 

def signal_handler(procs):
    def cleanup(signum, frame):
        pretty_kill(procs)
        sys.exit(0)
    return cleanup

async def main():
    args = parse_args(sys.argv[1:])
    
    def run_exit(f, args=None):
        f(args)
        sys.exit(0)
    
    async def service(paths):
        procs = await run_services(paths)
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, signal_handler(procs))
        return await bg_loop()

    paths = find_git_modules()

    actions = {
        'clone': partial(run_exit, clone_modules),
        'install': partial(run_exit, run_installs, paths),
        'run': partial(service, paths),
        'build': partial(buildall, paths)
    }

    for v, b in vars(args).items():
        if b:
            await actions[v]()
            break
    
if __name__ == '__main__':
    asyncio.run(main())
