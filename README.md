# Introduction
This repository contains various pthon scripts for running lorawan ns-3
simulations on a set of computers via a distributed task queue. Celery and amqp
are used to implement the DTQ.  This readme also contains instructions on how to
configure machines to run ns-3 experiments from the DQT. The idea is that
simulations tasks are completed by a set of machines, which write their output
to the file system. Afterwards, this output can be parsed by simple python
scripts.

# Setup celery broker machine
sudo apt-get -y install rabbitmq-server python3-pip
sudo pip3 install celery
## Allow guest access to rabbitmq-server:
Add the following to `/etc/rabbitmq/rabbitmq.config`
[{rabbit, [{loopback_users, []}]}].

# Clone and compile ns-3 on network storage (only has to be done once)
cd /groups/wall2-ilabt-iminds-be/lorawan/
git config --global http.proxy http://proxy.atlantis.ugent.be:8080/
git config --global https.proxy https://proxy.atlantis.ugent.be:8080/
git clone https://github.com/imec-idlab/ns-3-dev-git
cd ns-3-dev-git
git checkout lorawan
sudo apt-get update
sudo apt-get -y install libgsl-dev libxml2 libxml2-dev
./waf configure --build-profile=optimized --disable-tests --disable-python --disable-nsclick --disable-gtk
./waf
cp src/lorawan/examples/lorawan-example-tracing.cc scratch
cd /groups/wall2-ilabt-iminds-be/lorawan/ns-3-dev-git
./waf --run=lorawan-example-tracing --command-template="%s --randomSeed=12354 --nEndDevices=100 --nGateways=1 --discRadius=6100.0 --totalTime=6000 --nRuns=1 --usPacketSize=21 --usDataPeriod=600 --usConfirmedData=0 --dsDataGenerate=0 --verbose=0 --stdcout=0 --tracePhyTransmissions=0 --tracePhyStates=0 --traceMacPackets=0 --traceMacStates=0 --outputFileNamePrefix=simulations/output/test"

# Clone python scripts (i.e. this repository)
cd /groups/wall2-ilabt-iminds-be/lorawan/ns-3-dev-git
git clone https://github.com/fvdnabee/simulations.git
Make sure broker_uri is set to the broker machine in simulation_tasks.py, e.g. 
broker_uri = "pyamqp://guest@node0.nbrep.wall2-ilabt-iminds-be.wall2.ilabt.iminds.be//

# Setup worker machines
sudo apt-get update
sudo apt-get -y install libgsl-dev libxml2 libxml2-dev
sudo apt-get -y install python3-pip
sudo pip3 install celery

# Start workers on machines:
cd /groups/wall2-ilabt-iminds-be/lorawan/ns-3-dev-git/simulations
tmux
celery -A simulation_tasks worker --loglevel=debug

# Dispatch simulations to Celery work queue:
python3 dispatch_drcalcperlimit.py
Note that there exist a number of different dispatch scripts, one for each
scenario that was tested in the original paper.

# Output
Now you should wait for all the simulations to complete succesfully. It is
important that you verify that this is actually the case by double checking the
output files. In case of problems, this will only be apparerent from the
contents of the output files (e.g. output stopped before the simulation
completed).

Once you have collected the output (e.g. PHY packets/state, MAC
messages/states, end device + NS messages and misc stats), you can parse
these output files using the parse_macpackets_trace.py, parse_nodes.py,
parse_nsdsmsgs_trace.py, parse_phytx_trace.py scripts. Each of these scripts
parses one type of output file and generates a CSV file with some of the
condensed statistics per scenario.
