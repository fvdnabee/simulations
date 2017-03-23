#!/usr/bin/python3
# Simulations for determining PER limit in DR Calculation
from utils import dispatch_simulation_tasks

# Simulation settings:
randomSeedBase = 12345
nGateways = 1
discRadius = 6100.0
nRuns = 1
drCalcMethodIndex = 0 # PER calc method
# drCalcPerLimit = 0.01
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
    drCalcPerLimitValues = [0.1, 0.05, 0.025, 0.01, 0.0075, 0.005, 0.0025, 0.001]
    for drCalcPerLimit in drCalcPerLimitValues:
        for k in [1, 5, 10]:
            nEndDevices = 1000*k # Run nRuns for 1000*k end devices
            randomSeed = randomSeedBase + (k-1)*nRuns
            outputFileNamePrefix = "simulations/output/drcalcper/LoRaWAN-drcalcper-{}-{}".format (drCalcPerLimit, nEndDevices) # note: relative to ns-3 root folder

            cli_command = "./waf --run=lorawan-example-tracing --command-template=\"%s --randomSeed={} --nEndDevices={} --nGateways={} --discRadius={} --totalTime={} --nRuns={} --drCalcMethodIndex={} --drCalcPerLimit={} "\
                "--usPacketSize={} --usDataPeriod={} --usConfirmedData={} --dsDataGenerate={} --verbose={} --stdcout={} --tracePhyTransmissions={} --tracePhyStates={} --traceMacPackets={} --traceMacStates={} --outputFileNamePrefix={}\""\
                .format(randomSeed, nEndDevices, nGateways, discRadius, totalTime, nRuns, drCalcMethodIndex, drCalcPerLimit,
                        usPacketSize, usDataPeriod, usConfirmedData, dsDataGenerate, verbose, stdcout, tracePhyTransmissions, tracePhyStates, traceMacPackets, traceMacStates, outputFileNamePrefix)
            cli_commands.append(cli_command)

    # Dispatch celery tasks:
    dispatch_simulation_tasks(cli_commands)
