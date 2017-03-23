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
totalTime = 10 * usDataPeriod # send 10 packets on average per node

if __name__ == "__main__":
    # Create a list of cli commands that have to be run
    cli_commands = list()
    drCalcPerLimitValues = [0.9, 0.5, 0.2, 0.1, 0.01, 0.001]
    for drCalcPerLimit in drCalcPerLimitValues:
        # Run nRuns for 1000*k end devices
        for k in reversed(range (1, 10 + 1)):
            nEndDevices = 1000*k
            randomSeed = randomSeedBase + (k-1)*nRuns
            outputFileNamePrefix = "output/drcalcper/LoRaWAN-drcalcper-{}-{}".format (drCalcPerLimit, nEndDevices) # note: relative to ns-3 root folder

            cli_command = "./waf --run=lorawan-example-tracing --command-template=\"%s --randomSeed={} --nEndDevices={} --nGateways={} --discRadius={} --totalTime={} --nRuns={} --drCalcMethodIndex={} --drCalcPerLimit={} "\
                "--usPacketSize={} --usDataPeriod={} --usConfirmedData={} --dsDataGenerate={} --verbose={} --stdcout={} --tracePhyTransmissions={} --tracePhyStates={} --traceMacPackets={} --traceMacStates={} --outputFileNamePrefix={}\""\
                .format(randomSeed, nEndDevices, nGateways, discRadius, totalTime, nRuns, drCalcMethodIndex, drCalcPerLimit,
                        usPacketSize, usDataPeriod, usConfirmedData, dsDataGenerate, verbose, stdcout, tracePhyTransmissions, tracePhyStates, traceMacPackets, traceMacStates, outputFileNamePrefix)
            cli_commands.append(cli_command)

    # Dispatch celery tasks:
    dispatch_simulation_tasks(cli_commands)
