#!/usr/bin/python3
# Task for running a simulation
import subprocess
import shlex
import os
from celery import Celery

broker_uri = "pyamqp://guest@localhost//"
app = Celery('run-simulations-celery', backend='rpc://', broker=broker_uri)

cwd = os.path.dirname(os.path.realpath(__file__))
ns3_root_dir = cwd + "/.."

@app.task
def run_simulation_task(command):
    print (command)
    p = subprocess.Popen(shlex.split(command) , stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ns3_root_dir)
    stdout,error = p.communicate()
    return {"result":stdout.decode('utf-8'), "error":error.decode('utf-8')}
