#!/usr/bin/python3
# Simulations for PDR calculation for upstream and downstream traffic (using
# optimal PER based SF calculation):
# * 1, 2 or 4 gateways
# * different number of end devices: 100,500,1 000, 5 000, 10 000
# * fixed US traffic period of 6 000s
# * confirmed US data
# * confirmed DS data
# * different DS data generation means (dsDataExpMean): 10 and 100 times us period
from utils import dispatch_simulation_tasks

# Simulation settings:
randomSeedBase = 12345
nGateways = 1
discRadius = 6100.0
nRuns = 1
drCalcMethodIndex = 0
drCalcPerLimit = 0.01
drCalcFixedDRIndex = 0
usPacketSize = 21
usDataPeriod = 6000
usConfirmedData = 1
dsDataGenerate = 1
dsConfirmedData = 1
dsPacketSize = 21
dsDataExpMean = 60000
verbose = 0
stdcout = 0
tracePhyTransmissions = 0
tracePhyStates = 0
traceMacPackets = 1
traceMacStates = 0
traceMisc = 1
totalTime = 100 * usDataPeriod # send 100 packets on average per node

if __name__ == "__main__":
    # Create a list of cli commands that have to be run
    cli_commands = list()

    for nGateways in [1, 2, 4]:
        dsDataExpMeanList = [usDataPeriod*10, usDataPeriod*100]
        for dsDataExpMean in dsDataExpMeanList:
            for k in [1, 5, 10, 50, 100]:
                totalTime = 100 * usDataPeriod # send 100 packets on average per node
                nEndDevices = 100*k # Run nRuns for 100*k end devices
                randomSeed = randomSeedBase + (k-1)*nRuns
                outputFileNamePrefix = "simulations/output/downstream/LoRaWAN-downstream-{}-{}-{}-{}".format (nGateways, usDataPeriod, dsDataExpMean, nEndDevices) # note: relative to ns-3 root folder

                cli_command = "./waf --run=lorawan-example-tracing --command-template=\"%s --randomSeed={} --nEndDevices={} --nGateways={} --discRadius={} --totalTime={} --nRuns={} --drCalcMethodIndex={} --drCalcPerLimit={} "\
                    "--usPacketSize={} --usDataPeriod={} --usConfirmedData={} --dsDataGenerate={} --dsConfirmedData={} --dsPacketSize={} --dsDataExpMean={} --verbose={} --stdcout={} --tracePhyTransmissions={} --tracePhyStates={} --traceMacPackets={} --traceMacStates={} --traceMisc={} --outputFileNamePrefix={}\""\
                    .format(randomSeed, nEndDevices, nGateways, discRadius, totalTime, nRuns, drCalcMethodIndex, drCalcPerLimit,
                            usPacketSize, usDataPeriod, usConfirmedData, dsDataGenerate, dsConfirmedData, dsPacketSize, dsDataExpMean, verbose, stdcout, tracePhyTransmissions, tracePhyStates, traceMacPackets, traceMacStates, traceMisc, outputFileNamePrefix)
                cli_commands.append(cli_command)

    # Dispatch celery tasks:
    dispatch_simulation_tasks(cli_commands)
