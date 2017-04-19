#!/usr/bin/python3
# Parse ns-3 lorawan NS DS packets trace CSV output files
import csv
import argparse
import re
import os.path
from collections import Counter

parser = argparse.ArgumentParser(description='Process ns-3 lorawan NS DS packets CSV output file.')
parser.add_argument('csvfiles', nargs='+', help='The CSV files to be parsed')
parser.add_argument('--output-file-simulation', dest='outputfilesimulation', default="parse_macpackets_trace_per_simulation.csv", help='The output CSV file')
parser.add_argument('--output-file-enddevices', dest='outputfileenddevice', default="parse_macpackets_trace_per_enddevice.csv", help='The output CSV file')
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
    mac_packets = {}
    data_rate_stats = {0: (0,0), 1: (0,0), 2: (0,0), 3: (0,0), 4: (0,0), 5: (0,0)} # key=data rate index, value = (delivered,notdelivered)
    nsds_messages = {}
    with open(csvfilename, newline='') as csvfile:
        linereader = csv.reader(csvfile, delimiter=',', quotechar='|')
        next(linereader) # skip the header line in the csv file

        # Process CSV file: populate mac_packets data structure
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
                nsds_messages[msg_key] = {'DSMsgTx': [], 'DSMsgAckd': [], 'DSMsgDrop': []} #'MacTx': [], 'MacTxOk': [], 'MacTxDrop': [], 'MacRx': [], 'MacRxDrop': [], 'MacSentPkt': [], 'MacSentPktMisc': []}
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

    nr_dsmsgtx = 0
    nr_dsmsgtx_unique = 0
    nr_dsmsgackd = 0
    nr_dsmsgdrop = 0
    for k in nsds_messages:
        # print ("{}: {}".format(k, nsds_messages[k]))
        len_dsmsgtx = len(nsds_messages[k]['DSMsgTx'])
        len_dsmsgackd = len(nsds_messages[k]['DSMsgAckd'])
        len_dsmsgdrop = len(nsds_messages[k]['DSMsgDrop'])
        assert len_dsmsgtx > 0 # assume packet was sent at least once

        # check for sent packets without an Ack that were not dropped
        # if this occured near the end of the simulation then, don't process these packets
        if len_dsmsgackd == 0 and len_dsmsgdrop == 0:
            packet_timestamp = nsds_messages[k]['DSMsgTx'][0][0]
            fraction = packet_timestamp/last_timestamp
            if fraction < 0.99: # only print if we are not near the end of the trace
                 print("key={}: Unexpected case, skipping this packet. {}/{}. nsds_message = {}".format(k, packet_timestamp, last_timestamp, nsds_messages[k]))
            continue

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


        nr_dsmsgtx += len(nsds_messages[k]['DSMsgTx'])
        nr_dsmsgackd += len(nsds_messages[k]['DSMsgAckd'])
        nr_dsmsgdrop += len(nsds_messages[k]['DSMsgDrop'])

    print("Total/unique number of sent DS messages by NS: {}/{}".format(nr_dsmsgtx, nr_dsmsgtx_unique))
    print("Number of sent DS messages in RW1/RW2: {}/{}".format(nr_sent_rw1, nr_sent_rw2))
    print("Number of Ackd DS messages by NS: {}".format(nr_dsmsgackd))
    print("Number of dropped DS messages by NS: {}".format(nr_dsmsgdrop))
    print("PDR: {:.4f} {:.4f}".format(nr_dsmsgackd/nr_dsmsgtx_unique, (nr_dsmsgtx_unique-nr_dsmsgdrop)/nr_dsmsgtx_unique))
    print("Average nr of sent DS message per unique DS message: {:.4f}".format(nr_dsmsgtx/nr_dsmsgtx_unique))
    print("Average nr of sent DS message per Ackd DS message: {:.4f}".format(nr_dsmsgtx/nr_dsmsgackd))

    print("\nNumber of remaining TX for Ackd DS message: {}".format(nr_ackd_tx_remaining))
    print("{:<25}{:>10}{:>10}{:>10}{:>10}".format("Remaining TX", 0, 1, 2, 3))
    print("{:<25}{:>10}{:>10}{:>10}{:>10}".format("Number of ackd packets", nr_ackd_tx_remaining[0], nr_ackd_tx_remaining[1], nr_ackd_tx_remaining[2], nr_ackd_tx_remaining[3]))

    print ("------------------------------------------------------------------")
