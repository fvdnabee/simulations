# Dispatch simulations to Celery work queue:
python3 dispatch_drcalcperlimit.py

# Start workers on machines:
celery -A simulation_tasks worker --loglevel=debug
