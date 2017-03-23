#!/usr/bin/python3
# Dispatch a number of simulation tasks to a celery task queue
import time
from simulation_tasks import run_simulation_task

def dispatch_simulation_tasks(cli_commands):
    print("Dispatching following cli commands to celery workers:")
    results = list()
    for i in range(len(cli_commands)):
        cli_command = cli_commands[i]
        print(cli_command)
        task_id = "{}".format(i) # apparently integers don't work

        r = run_simulation_task.apply_async((cli_command,), task_id=task_id) # set task id to command
        results.append(r)

    print("\nWaiting for all tasks to complete:")
    stop = False
    num_tasks = len(results)
    while not stop:
        for i in range(len(results)):
            r = results[i]
            if r.ready():
                task_id = r.id
                list_index = int(task_id)
                print ("Task #{}/{} has completed: {}".format(task_id, num_tasks, cli_commands[list_index]))
                results.pop(i) # task finished, so remove it from results
                break

        if len(results) == 0:
            print("All tasks have completed. Stopping")
            stop = True
        time.sleep(0.100)
