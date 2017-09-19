#!/usr/bin/python3
# Parse ns-3 lorawan NS DS packets trace CSV output files
import csv
import argparse
import re
import os.path
from collections import Counter

parser = argparse.ArgumentParser(description='Process ns-3 lorawan NS DS packets CSV output file.')
parser.add_argument('csvfiles', nargs='+', help='The CSV files to be parsed')
parser.add_argument('--output-file-simulation', dest='outputfile', default="parse_nsdsmsgs_trace.csv", help='The output CSV file')
# parser.add_argument('--parseapppackets', type=bool, default=False, help='Parse app packets?')
#feature_parser = parser.add_mutually_exclusive_group(required=False)
#feature_parser.add_argument('--app-packets', dest='apppackets', action='store_true')
#feature_parser.add_argument('--no-app-packets', dest='apppackets', action='store_false')
#parser.set_defaults(feature=False)

args = parser.parse_args()
for csvfilename in args.csvfiles:
    print("Parsing NS DS packets csv file {}".format(csvfilename))
    last_timestamp = -1
    nodes = {}
    data_rate_stats = {0: (0,0), 1: (0,0), 2: (0,0), 3: (0,0), 4: (0,0), 5: (0,0)} # key=data rate index, value = (delivered,notdelivered)
    nsds_messages = {}
    with open(csvfilename, newline='') as csvfile:
        linereader = csv.reader(csvfile, delimiter=',', quotechar='|')
        next(linereader) # skip the header line in the csv file

        # Process CSV file: populate nsds_messages data structure
        for row in linereader:
            packet_length = int(row[6])
            if packet_length == 0:
                # Skipping DS message with empty payload (probably Ack)
                msg_type = int(row[3])
                assert msg_type == 3 # acks should be sent as unconfirmed data down messages
                continue

            packet_hex = row[5]
            msg_key = packet_hex # assume packet_hex is unique for every generated DS msg
            packet_timestamp = float(row[0])
            trace_source = row[1]
            node_id = int(row[2])
            msg_type = int(row[3])
            tx_remaining = int(row[4])
            packet_hex = row[5]
            if msg_key not in nsds_messages:
                nsds_messages[msg_key] = {'DSMsgGenerated': [], 'DSMsgTx': [], 'DSMsgAckd': [], 'DSMsgDrop': []} #'MacTx': [], 'MacTxOk': [], 'MacTxDrop': [], 'MacRx': [], 'MacRxDrop': [], 'MacSentPkt': [], 'MacSentPktMisc': []}
                last_timestamp = packet_timestamp
            else:
                # sanity checks:
                # nsds_messages[msg_key]
                pass

            t = (packet_timestamp, node_id, tx_remaining)
            if trace_source == 'DSMsgTx':
                receive_window = int(row[7])
                t += (receive_window,)

            nsds_messages[msg_key][trace_source].append(t)

    nr_sent_rw1 = 0
    nr_sent_rw2 = 0
    nr_ackd_tx_remaining = [0, 0, 0, 0, 0]

    nr_dsmsggenerated = 0
    nr_dsmsgtx = 0
    nr_dsmsgtx_unique = 0
    nr_dsmsgackd = 0
    nr_dsmsgdrop = 0
    nr_dsmsgackdwithouttx = 0
    for k in nsds_messages:
        # print ("{}: {}".format(k, nsds_messages[k]))
        len_dsmsgtx = len(nsds_messages[k]['DSMsgTx'])
        len_dsmsgackd = len(nsds_messages[k]['DSMsgAckd'])
        len_dsmsgdrop = len(nsds_messages[k]['DSMsgDrop'])
        # assert len_dsmsgtx > 0 # assume packet was sent at least once
        # if len_dsmsgtx == 0:
        #     print("PACKET NEVER SENT, SKIPPING: {}".format(nsds_messages[k]))
        #     continue

        # check for sent packets without an Ack that were not dropped
        # if this occured near the end of the simulation then, don't process these packets
        if len_dsmsgackd == 0 and len_dsmsgdrop == 0:
            packet_timestamp = nsds_messages[k]['DSMsgGenerated'][0][0]
            fraction = packet_timestamp/last_timestamp
            if fraction >= 0.99:
                continue

        if len_dsmsgackd > 0 and len_dsmsgtx == 0:
        #     print("Packet ackd but it was never sent: {}".format(nsds_messages[k]))
            nr_dsmsgackdwithouttx  += 1
            continue

        assert len(nsds_messages[k]['DSMsgGenerated']) == 1
        nr_dsmsggenerated += 1

        if len_dsmsgtx > 0:
            nr_dsmsgtx_unique += 1

        for t in nsds_messages[k]['DSMsgTx']:
            receive_window = t[3]
            if receive_window == 1:
                nr_sent_rw1 += 1
            elif receive_window == 2:
                nr_sent_rw2 += 1
            else:
                assert False

        if len_dsmsgackd > 0:
            assert len(nsds_messages[k]['DSMsgAckd']) == 1 # sanity check
            tx_remaining = nsds_messages[k]['DSMsgAckd'][0][2]
            nr_ackd_tx_remaining[tx_remaining] += 1

        if len_dsmsgdrop > 0:
            assert len(nsds_messages[k]['DSMsgDrop']) == 1 # sanity check

        # if len_dsmsgackd == 0 and len_dsmsgdrop == 0:
        #     print("DS MSG neither in ackd or drop: {}".format(nsds_messages[k]))



        nr_dsmsgtx += len(nsds_messages[k]['DSMsgTx'])
        nr_dsmsgackd += len(nsds_messages[k]['DSMsgAckd'])
        nr_dsmsgdrop += len(nsds_messages[k]['DSMsgDrop'])

    # parse trace misc csv file so they can added to the output file:
    trace_misc_file_name = csvfilename.replace("trace-ns-dsmsgs.csv", "trace-misc.csv")
    trace_misc = {"nrRW1Sent": -1, "nrRW2Sent": -1, "nrRW1Missed": -1,"nrRW2Missed": -1}
    with open(trace_misc_file_name, newline='') as csvfile:
        linereader = csv.reader(csvfile, delimiter=',', quotechar='|')
        next(linereader) # skip the header line in the csv file
        row = next(linereader)
        trace_misc['nrRW1Sent'] = int(row[0])
        trace_misc['nrRW2Sent'] = int(row[1])
        trace_misc['nrRW1Missed'] = int(row[2])
        trace_misc['nrRW2Missed'] = int(row[3])

    # Generate output:
    print("Total number of generated packets by NS: {}".format(nr_dsmsggenerated))
    print("Total/unique number of sent DS messages by NS: {}/{}".format(nr_dsmsgtx, nr_dsmsgtx_unique))
    print("Number of Ackd packets without being transmitted by NS: {}".format(nr_dsmsgackdwithouttx))
    print("Number of sent DS messages in RW1/RW2: {}/{}".format(nr_sent_rw1, nr_sent_rw2))
    print("Number of Ackd DS messages by NS: {}".format(nr_dsmsgackd))
    print("Number of dropped DS messages by NS: {}".format(nr_dsmsgdrop))
    print("Number of missed RW1/RW2 (misc): {}/{}".format(trace_misc['nrRW1Missed'], trace_misc['nrRW2Missed']))
    print("PDR: {:.4f} ({:.4f} {:.4f})".format(nr_dsmsgackd/nr_dsmsggenerated, nr_dsmsgackd/nr_dsmsgtx_unique, (nr_dsmsgtx_unique-nr_dsmsgdrop)/nr_dsmsgtx_unique))

    if nr_dsmsgtx_unique > 0:
        print("Average nr of sent DS message per unique DS message: {:.4f}".format(nr_dsmsgtx/nr_dsmsgtx_unique))
    if nr_dsmsgackd > 0:
        print("Average nr of sent DS message per Ackd DS message: {:.4f}".format(nr_dsmsgtx/nr_dsmsgackd))

    print("\nNumber of remaining TX for Ackd DS message: {}".format(nr_ackd_tx_remaining))
    print("{:<25}{:>10}{:>10}{:>10}{:>10}".format("Remaining TX", 0, 1, 2, 3))
    print("{:<25}{:>10}{:>10}{:>10}{:>10}".format("Number of ackd packets", nr_ackd_tx_remaining[0], nr_ackd_tx_remaining[1], nr_ackd_tx_remaining[2], nr_ackd_tx_remaining[3]))

    # parse sim settings file so they can be added to the output file:
    sim_settings_file_name = csvfilename.replace("trace-ns-dsmsgs.csv", "sim-settings.txt")
    sim_settings = {"nGateways": -1, "nEndDevices": -1, "totalTime": -1, "usConfirmedData": -1, "usDataPeriod": -1, "seed": -1, "drCalcMethod": -1, "drCalcMethodMisc": -1, "dsDataGenerate": -1, "dsDataExpMean": -1, "dsConfirmedData": -1}

    with open(sim_settings_file_name) as sim_settings_file:
        sim_settings_file_contents = sim_settings_file.read()

        p_ngateways = re.compile('nGateways = ([0-9]+)')
        p_nenddevices = re.compile('nEndDevices = ([0-9]+)')
        p_totaltime = re.compile('totalTime = ([0-9]+)')
        p_confirmed_data = re.compile('usConfirmedData = ([0-1])')
        p_data_period = re.compile('usDataPeriod = ([0-9]+)')
        p_seed = re.compile('seed = ([0-9]+)')
        p_drcalcmethod = re.compile('Data rate assignment method index: ([0-9]+)')
        p_dsdatagenerate = re.compile('dsDataGenerate = ([0-1])')
        p_dsdataexpmean = re.compile('dsDataExpMean = ([0-9]+)')
        p_dsconfirmeddata = re.compile('dsConfirmedData = ([0-1])')

        sim_settings['nGateways'] = int(p_ngateways.search (sim_settings_file_contents).groups()[0])
        sim_settings['nEndDevices'] = int(p_nenddevices.search (sim_settings_file_contents).groups()[0])
        sim_settings['totalTime'] =  int(p_totaltime.search (sim_settings_file_contents).groups()[0])
        sim_settings['usConfirmedData'] = int(p_confirmed_data.search (sim_settings_file_contents).groups()[0])
        sim_settings['usDataPeriod'] = int(p_data_period.search (sim_settings_file_contents).groups()[0])
        sim_settings['seed'] = int(p_seed.search (sim_settings_file_contents).groups()[0])
        sim_settings['dsDataGenerate'] = int(p_dsdatagenerate.search (sim_settings_file_contents).groups()[0])
        sim_settings['dsDataExpMean'] = int(p_dsdataexpmean.search (sim_settings_file_contents).groups()[0])
        sim_settings['dsConfirmedData'] = int(p_dsconfirmeddata.search (sim_settings_file_contents).groups()[0])

        sim_settings['drCalcMethod'] = int(p_drcalcmethod.search (sim_settings_file_contents).groups()[0])
        if sim_settings['drCalcMethod'] == 0:
            p_drcalcperlimit = re.compile('PER limit = (\d+\.\d+)')
            sim_settings['drCalcMethodMisc'] = float(p_drcalcperlimit.search (sim_settings_file_contents).groups()[0])
        if sim_settings['drCalcMethod'] == 2:
            p_drcalcfixeddr = re.compile('Fixed Data Rate Index = ([0-9]+)')
            sim_settings['drCalcMethodMisc'] = int(p_drcalcfixeddr.search (sim_settings_file_contents).groups()[0])

    # Generate output file:
    print ("\nAppending output to {}".format(args.outputfile))
    write_header = False
    if not os.path.exists(args.outputfile):
        write_header = True
    with open(args.outputfile, 'a') as output_file: # append to output file
        outputFormat = "<nGateways>,<nEndDevices>,<totalTime>,<drCalcMethod>,<drCalcMethodMisc>,<seed>,"\
                       "<usConfirmedData>,<usDataPeriod>,<dsDataGenerate>,<dsConfirmedData>,<dsDataExpMean>,"\
                       "<dsGenerated>,<dsSentRW1>,<dsSentRW2>,<dsSent>,<dsSentUnique>,<dsAckd>,<dsDrop>,<dsPDR>,<dsPDRUniqueAckd>,<dsPDRUniqueDrop>,"\
                       "<dsSentRW1Misc>,<dsSentRW2Misc>,<dsMissedRW1Misc>,<dsMissedRW2Misc>,"\
                       "<dsRemainingTx0>,<dsRemainingTx1>,<dsRemainingTx2>,<dsRemainingTx3>\n"

        if write_header:
            output_file.write(outputFormat)

        # sim settings + us stats + ds stats
        output_line = "{},{},{},{},{},{},"\
                      "{},{},{},{},{},"\
                      "{},{},{},{},{},{},{},{:1.4f},{:1.4f},{:1.4f},"\
                      "{},{},{},{},"\
                      "{},{},{},{}\n".format(sim_settings['nGateways'], sim_settings['nEndDevices'], sim_settings['totalTime'], sim_settings['drCalcMethod'], sim_settings['drCalcMethodMisc'], sim_settings['seed'],
                                               sim_settings['usConfirmedData'], sim_settings['usDataPeriod'], sim_settings['dsDataGenerate'],  sim_settings['dsConfirmedData'],  sim_settings['dsDataExpMean'], 
                                               nr_dsmsggenerated, nr_sent_rw1, nr_sent_rw2, nr_dsmsgtx, nr_dsmsgtx_unique, nr_dsmsgackd, nr_dsmsgdrop, nr_dsmsgackd/nr_dsmsggenerated, nr_dsmsgackd/nr_dsmsgtx_unique, (nr_dsmsgtx_unique-nr_dsmsgdrop)/nr_dsmsgtx_unique,
                                               trace_misc['nrRW1Sent'], trace_misc['nrRW2Sent'], trace_misc['nrRW1Missed'],  trace_misc['nrRW2Missed'],
                                               nr_ackd_tx_remaining[0], nr_ackd_tx_remaining[1], nr_ackd_tx_remaining[2], nr_ackd_tx_remaining[3])
        print(output_line)
        output_file.write(output_line)

    print ("------------------------------------------------------------------")
