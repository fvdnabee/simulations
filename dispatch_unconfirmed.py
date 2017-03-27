#!/usr/bin/python3
# Simulations for PDR calculation for optimal PER based SF calculation for
# different number of end devices and different US traffic periods
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
usDataPeriod = 600
usConfirmedData = 0
dsDataGenerate = 0
verbose = 0
stdcout = 0
tracePhyTransmissions = 1
tracePhyStates = 0
traceMacPackets = 0
traceMacStates = 0
totalTime = 100 * usDataPeriod # send 100 packets on average per node

if __name__ == "__main__":
    # Create a list of cli commands that have to be run
    cli_commands = list()

    usDataPeriodValues = [600, 6000, 60000] # 10 minutes, 1.6h and 16h
    for usDataPeriod in usDataPeriodValues:
        for k in [1, 5, 10, 50, 100]:
            totalTime = 100 * usDataPeriod # send 100 packets on average per node
            nEndDevices = 100*k # Run nRuns for 100*k end devices
            randomSeed = randomSeedBase + (k-1)*nRuns
            outputFileNamePrefix = "simulations/output/unconfirmed/LoRaWAN-unconfirmed-{}-{}".format (usDataPeriod, nEndDevices) # note: relative to ns-3 root folder

            cli_command = "./waf --run=lorawan-example-tracing --command-template=\"%s --randomSeed={} --nEndDevices={} --nGateways={} --discRadius={} --totalTime={} --nRuns={} --drCalcMethodIndex={} --drCalcPerLimit={} "\
                "--usPacketSize={} --usDataPeriod={} --usConfirmedData={} --dsDataGenerate={} --verbose={} --stdcout={} --tracePhyTransmissions={} --tracePhyStates={} --traceMacPackets={} --traceMacStates={} --outputFileNamePrefix={}\""\
                .format(randomSeed, nEndDevices, nGateways, discRadius, totalTime, nRuns, drCalcMethodIndex, drCalcPerLimit,
                        usPacketSize, usDataPeriod, usConfirmedData, dsDataGenerate, verbose, stdcout, tracePhyTransmissions, tracePhyStates, traceMacPackets, traceMacStates, outputFileNamePrefix)
            cli_commands.append(cli_command)

    # Dispatch celery tasks:
    dispatch_simulation_tasks(cli_commands)
