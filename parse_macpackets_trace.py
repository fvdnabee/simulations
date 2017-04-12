#!/usr/bin/python3
# Parse ns-3 lorawan MAC packets trace CSV output files
import csv
import argparse
import re
import os.path

parser = argparse.ArgumentParser(description='Process ns-3 lorawan MAC packets CSV output file.')
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
    print("Parsing mac packets csv file {}".format(csvfilename))
    last_timestamp = -1
    nodes = {}
    mac_packets = {}
    data_rate_stats = {0: (0,0), 1: (0,0), 2: (0,0), 3: (0,0), 4: (0,0), 5: (0,0)} # key=data rate index, value = (delivered,notdelivered)
    with open(csvfilename, newline='') as csvfile:
        linereader = csv.reader(csvfile, delimiter=',', quotechar='|')
        next(linereader) # skip the header line in the csv file

        # Process CSV file: populate mac_packets data structure
        for row in linereader:
            node_id = int(row[2])
            trace_source = row[5]
            mac_packets_key = row[6] # packet in hex
            if mac_packets_key not in mac_packets:
                packet_timestamp = float(row[0])
                last_timestamp = packet_timestamp
                mac_packets[mac_packets_key] = {'Timestamp': packet_timestamp, 'MacTx': [], 'MacTxOk': [], 'MacTxDrop': [], 'MacRx': [], 'MacRxDrop': [], 'MacSentPkt': [], 'MacSentPktMisc': []}
            mac_packets[mac_packets_key][trace_source].append(node_id)

            if node_id not in nodes:
                nodes[node_id] = {'DeviceType': int(row[1]), 'PacketsSent': 0, 'PacketsReceived': 0, 'PacketsDropped': 0, 'PacketsGenerated': 0, 'PacketsDelivered': 0, 'PacketsNotDelivered': 0}

            # Store any interesting misc fields depending on trace_source:
            if trace_source == 'MacSentPkt':
                n_transmissions = int(row[8])
                t = (node_id, n_transmissions) # store node_id and n_transmissions as a tuple
                mac_packets[mac_packets_key]['MacSentPktMisc'].append(t)

    # Process mac_packets data structure:
    # * Was a packet delivered?
    #   -> MacSentPkt trace and how many transmissions did it take?
    # * How many times was a packet received by a gateway without an Ack ever reaching the end device?
    #   -> Look at MacRx
    upstream_stats = {'nrPackets': 0, 'nrSent': 0, 'nrReceived': 0, 'nrDelivered': 0, 'nrUndelivered': 0, 'nrMacSentPktTries': 0}
    upstream_stats_sent = [0, 0, 0, 0, 0]
    upstream_stats_received = [0] * 20
    upstream_stats_senttries = [0, 0, 0, 0, 0]
    downstream_stats = {'nrPackets': 0, 'nrSent': 0, 'nrReceived': 0, 'nrDelivered': 0, 'nrUndelivered': 0, 'nrMacSentPktTries': 0}
    downstream_stats_sent = [0, 0, 0, 0, 0]
    downstream_stats_received = [0, 0, 0, 0, 0]
    downstream_stats_senttries = [0, 0, 0, 0, 0]
    us_packets_sent_vs_received = [[0],[0,0],[0,0,0],[0,0,0,0],[0,0,0,0,0]] # e.g. first index is number of times sent, second index is number of times received
    ds_packets_sent_vs_received = [[0],[0,0],[0,0,0],[0,0,0,0],[0,0,0,0,0]]
    number_of_us_sent_packets_that_were_not_received = 0  # when a packet has been sent 3 times but was never received, increment this counter by 3
    number_of_ds_sent_packets_that_were_not_received = 0
    for key in list(mac_packets.keys()):
        packet = mac_packets[key]
        nr_of_transmitters = len(set(packet['MacTx']))
        if nr_of_transmitters != 1:
             print("key={}: ERROR SKIPPING this MAC packet as there is more than one transmitter in MacTx for packet = {}".format(key, packet))
             continue
        nr_of_receivers = len(set(packet['MacRx']))
        if nr_of_receivers < 0 or nr_of_receivers > 4:
             print("key={}: ERROR SKIPPING this MAC packet as the number of receivers in MacRx is not equal to 0, 1, 2 or 4 for packet = {}".format(key, packet))
             continue

        nr_sent = len(packet['MacTx'])
        nr_received = len(packet['MacRx'])
        nr_received_dropped = len(packet['MacRxDrop'])

        # Either packet is in MacTxOk or in MacTxDrop
        delivered = False
        nr_sent_tries = 0
        if len(packet['MacTxOk']) == 1:
            delivered = True
            if len(packet['MacSentPktMisc']) > 0:
                nr_sent_tries = packet['MacSentPktMisc'][0][1]
                if nr_sent != nr_sent_tries:
                    print("nr_sent == {} and nr_sent_tries = {}, packet = {}".format(nr_sent, nr_sent_tries, packet))
                assert nr_sent == nr_sent_tries
            else:
                print ("WARNING skipping packet because packet['MacSentPktMisc'] is empty for packet = {}".format(packet))
                continue
        elif len(packet['MacTxDrop']) == 1:
            delivered = False
        else:
            # This should only happen at the end of trace:
            fraction = packet['Timestamp']/last_timestamp
            if fraction < 0.99: # only print if we are not near the end of the mac packet trace
                print("key={}: Unexpected case, skipping this packet. {}/{}. packet = {}".format(key, packet['Timestamp'], last_timestamp, packet))
            continue

        # update stats dictionaries
        tx_node_id = packet['MacTx'][0]
        tx_node_devicetype = nodes[tx_node_id]['DeviceType']
        if nodes[tx_node_id]['DeviceType'] == 1: # upstream packet
            upstream_stats['nrPackets'] += 1
            upstream_stats['nrSent'] += nr_sent
            upstream_stats['nrReceived'] += nr_received
            if delivered:
                upstream_stats['nrDelivered'] += 1
            else:
                upstream_stats['nrUndelivered'] += 1
            upstream_stats['nrMacSentPktTries'] += nr_sent_tries

            upstream_stats_sent[nr_sent] += 1
            upstream_stats_received[nr_received] += 1
            if delivered:
                upstream_stats_senttries[nr_sent_tries] += 1

            # us_packets_sent_vs_received[nr_sent][nr_received] += 1
            # say a packet was sent 4 times, but only received 2 times. this means two sent packets were lost
            if nr_sent != nr_received:
                number_of_us_sent_packets_that_were_not_received += nr_sent-nr_received
        elif nodes[tx_node_devicetype]['DeviceType'] == 0: # downstream packet
            downstream_stats['nrPackets'] += 1
            downstream_stats['nrSent'] += nr_sent
            downstream_stats['nrReceived'] += nr_received
            if delivered:
                downstream_stats['nrDelivered'] += 1
            else:
                downstream_stats['nrUndelivered'] += 1
            downstream_stats['nrMacSentPktTries'] += nr_sent_tries

            downstream_stats_sent[nr_sent] += 1
            downstream_stats_received[nr_received] += 1
            if delivered:
                downstream_stats_senttries[nr_sent_tries] += 1

            if nr_sent != nr_received:
                number_of_ds_sent_packets_that_were_not_received += nr_sent-nr_received
        else:
            print("Fatal error unknown device type")
            exit()

        # update nodes dictionary:
        nodes[tx_node_id]['PacketsSent'] += nr_sent
        nodes[tx_node_id]['PacketsReceived'] += nr_received
        nodes[tx_node_id]['PacketsDropped'] += nr_received_dropped
        nodes[tx_node_id]['PacketsGenerated'] += 1
        if delivered:
            nodes[tx_node_id]['PacketsDelivered'] += 1
        else:
            nodes[tx_node_id]['PacketsNotDelivered'] += 1


    # Generate output:
    print("\nUpstream stats: {}".format(upstream_stats))
    print("Number of times a MAC event occured per US packet:")
    print("{:<26}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("Traffic | Number of times:", 0, 1, 2, 3, 4, "Sum", "W sum"))
    print("{:<26}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("US sent", upstream_stats_sent[0], upstream_stats_sent[1], upstream_stats_sent[2], upstream_stats_sent[3], upstream_stats_sent[4],
        upstream_stats_sent[0] + upstream_stats_sent[1] + upstream_stats_sent[2] + upstream_stats_sent[3] + upstream_stats_sent[4],
        0*upstream_stats_sent[0] + 1*upstream_stats_sent[1] + 2*upstream_stats_sent[2] + 3*upstream_stats_sent[3] + 4*upstream_stats_sent[4]))
    print("{:<26}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("US received", upstream_stats_received[0], upstream_stats_received[1], upstream_stats_received[2], upstream_stats_received[3], upstream_stats_received[4],
        upstream_stats_received[0] + upstream_stats_received[1] + upstream_stats_received[2] + upstream_stats_received[3] + upstream_stats_received[4],
        0*upstream_stats_received[0] + 1*upstream_stats_received[1] + 2*upstream_stats_received[2] + 3*upstream_stats_received[3] + 4*upstream_stats_received[4]))
    print("{:<26}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("US senttries", upstream_stats_senttries[0], upstream_stats_senttries[1], upstream_stats_senttries[2], upstream_stats_senttries[3], upstream_stats_senttries[4],
        upstream_stats_senttries[0] + upstream_stats_senttries[1] + upstream_stats_senttries[2] + upstream_stats_senttries[3] + upstream_stats_senttries[4],
        0*upstream_stats_senttries[0] + 1*upstream_stats_senttries[1] + 2*upstream_stats_senttries[2] + 3*upstream_stats_senttries[3] + 4*upstream_stats_senttries[4]))

    print("Number of times a US packet was received vs number of times it was sent:")
    print("{:<20}{:>10}{:>10}{:>10}{:>10}{:>10}{:>20}".format("#sent | #received", 0, 1, 2, 3, 4, "Total not received"))
    print("{:<20}{:>10}{:>10}{:>10}{:>10}{:>10}{:>20}".format("1",us_packets_sent_vs_received[1][0], us_packets_sent_vs_received[1][1],"","","",
        1*us_packets_sent_vs_received[1][0]))
    print("{:<20}{:>10}{:>10}{:>10}{:>10}{:>10}{:>20}".format("2",us_packets_sent_vs_received[2][0], us_packets_sent_vs_received[2][1], us_packets_sent_vs_received[2][2],"","",
        2*us_packets_sent_vs_received[2][0] + 1*us_packets_sent_vs_received[2][1]))
    print("{:<20}{:>10}{:>10}{:>10}{:>10}{:>10}{:>20}".format("3",us_packets_sent_vs_received[3][0], us_packets_sent_vs_received[3][1], us_packets_sent_vs_received[3][2], us_packets_sent_vs_received[3][3],"",
        3*us_packets_sent_vs_received[3][0] + 2*us_packets_sent_vs_received[3][1] + 1*us_packets_sent_vs_received[3][2]))
    print("{:<20}{:>10}{:>10}{:>10}{:>10}{:>10}{:>20}".format("4",us_packets_sent_vs_received[4][0], us_packets_sent_vs_received[4][1], us_packets_sent_vs_received[4][2], us_packets_sent_vs_received[4][3], us_packets_sent_vs_received[4][4],
        4*us_packets_sent_vs_received[4][0] + 3*us_packets_sent_vs_received[4][1] + 2*us_packets_sent_vs_received[4][2] + 1*us_packets_sent_vs_received[4][3]))
    print("number_of_us_sent_packets_that_were_not_received = {}".format(number_of_us_sent_packets_that_were_not_received))

    print("\nDS stats: {}".format(downstream_stats))
    print("{:<25}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("Traffic | number of times:", 0, 1, 2, 3, 4, "Sum", "W sum"))
    print("{:<26}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("DS sent", downstream_stats_sent[0], downstream_stats_sent[1], downstream_stats_sent[2], downstream_stats_sent[3], downstream_stats_sent[4],
        downstream_stats_sent[0] + downstream_stats_sent[1] + downstream_stats_sent[2] + downstream_stats_sent[3] + downstream_stats_sent[4],
        0*downstream_stats_sent[0] + 1*downstream_stats_sent[1] + 2*downstream_stats_sent[2] + 3*downstream_stats_sent[3] + 4*downstream_stats_sent[4]))
    print("{:<26}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("DS received", downstream_stats_received[0], downstream_stats_received[1], downstream_stats_received[2], downstream_stats_received[3], downstream_stats_received[4],
        downstream_stats_received[0] + downstream_stats_received[1] + downstream_stats_received[2] + downstream_stats_received[3] + downstream_stats_received[4],
        0*downstream_stats_received[0] + 1*downstream_stats_received[1] + 2*downstream_stats_received[2] + 3*downstream_stats_received[3] + 4*downstream_stats_received[4]))
    print("{:<26}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("DS senttries", downstream_stats_senttries[0], downstream_stats_senttries[1], downstream_stats_senttries[2], downstream_stats_senttries[3], downstream_stats_senttries[4],
        downstream_stats_senttries[0] + downstream_stats_senttries[1] + downstream_stats_senttries[2] + downstream_stats_senttries[3] + downstream_stats_senttries[4],
        0*downstream_stats_senttries[0] + 1*downstream_stats_senttries[1] + 2*downstream_stats_senttries[2] + 3*downstream_stats_senttries[3] + 4*downstream_stats_senttries[4]))
    print("number_of_ds_sent_packets_that_were_not_received = {}".format(number_of_ds_sent_packets_that_were_not_received))

    # parse sim settings file:
    sim_settings_file_name = csvfilename.replace("trace-mac-packets.csv", "sim-settings.txt")

    sim_settings = {"nGateways": -1, "nEndDevices": -1, "totalTime": -1, "usConfirmedData": -1, "usDataPeriod": -1, "seed": -1, "drCalcMethod": -1, "drCalcMethodMisc": -1  }
    with open(sim_settings_file_name) as sim_settings_file:
        sim_settings_file_contents = sim_settings_file.read()

        p_ngateways = re.compile('nGateways = ([0-9]+)')
        p_nenddevices = re.compile('nEndDevices = ([0-9]+)')
        p_totaltime = re.compile('totalTime = ([0-9]+)')
        p_confirmed_data = re.compile('usConfirmedData = ([0-1])')
        p_data_period = re.compile('usDataPeriod = ([0-9]+)')
        p_seed = re.compile('seed = ([0-9]+)')
        p_drcalcmethod = re.compile('Data rate assignment method index: ([0-9]+)')

        sim_settings['nGateways'] = int(p_ngateways.search (sim_settings_file_contents).groups()[0])
        sim_settings['nEndDevices'] = int(p_nenddevices.search (sim_settings_file_contents).groups()[0])
        sim_settings['totalTime'] =  int(p_totaltime.search (sim_settings_file_contents).groups()[0])
        sim_settings['usConfirmedData'] = int(p_confirmed_data.search (sim_settings_file_contents).groups()[0])
        sim_settings['usDataPeriod'] = int(p_data_period.search (sim_settings_file_contents).groups()[0])
        sim_settings['seed'] = int(p_seed.search (sim_settings_file_contents).groups()[0])

        sim_settings['drCalcMethod'] = int(p_drcalcmethod.search (sim_settings_file_contents).groups()[0])
        if sim_settings['drCalcMethod'] == 0:
            p_drcalcperlimit = re.compile('PER limit = (\d+\.\d+)')
            sim_settings['drCalcMethodMisc'] = float(p_drcalcperlimit.search (sim_settings_file_contents).groups()[0])
        if sim_settings['drCalcMethod'] == 2:
            p_drcalcfixeddr = re.compile('Fixed Data Rate Index = ([0-9]+)')
            sim_settings['drCalcMethodMisc'] = int(p_drcalcfixeddr.search (sim_settings_file_contents).groups()[0])

    # # Generate output per simulation
    print ("\nAppending output per simulation to {}".format(args.outputfilesimulation))
    write_header = False
    if not os.path.exists(args.outputfilesimulation):
        write_header = True
    with open(args.outputfilesimulation, 'a') as output_file: # append to output file
        outputFormat = "<nGateways>,<nEndDevices>,<totalTime>,<drCalcMethod>,<drCalcMethodMisc>,<seed>,"\
                       "<usConfirmedData>,<usDataPeriod>,<usDelivered>,<usPackets>,<PDR>,<usSent>,<usReceived>,"\
                       "<usSent0>,<usSent1>,<usSent2>,<usSent3>,<usSent4>,"\
                       "<usReceived0>,<usReceived1>,<usReceived2>,<usReceived3>,<usReceived4>,"\
                       "<usSentTries0>,<usSentTries1>,<usSentTries2>,<usSentTries3>,<usSentTries4>,"\
                       "<usSent1Received0>,<usSent1Received1>,"\
                       "<usSent2Received0>,<usSent2Received1>,<usSent2Received2>,"\
                       "<usSent3Received0>,<usSent3Received1>,<usSent3Received2>,<usSent3Received3>,"\
                       "<usSent4Received0>,<usSent4Received1>,<usSent4Received2>,<usSent4Received3>,<usSent4Received4>,"\
                       "<dsSent0>,<dsSent1>,<dsSent2>,<dsSent3>,<dsSent4>,"\
                       "<dsReceived0>,<dsReceived1>,<dsReceived2>,<dsReceived3>,<dsReceived4>,"\
                       "<dsSentTries0>,<dsSentTries1>,<dsSentTries2>,<dsSentTries3>,<dsSentTries4>\n"
        if write_header:
            output_file.write(outputFormat)

        output_line_dr_pdrs = ""
        for data_rate_index in data_rate_stats:
            dr_delivered = data_rate_stats[data_rate_index][0]
            dr_undelivered = data_rate_stats[data_rate_index][1]
            dr_tx = dr_delivered + dr_undelivered
            dr_pdr = dr_delivered/dr_tx if dr_tx > 0 else 0
            output_line_dr_pdrs = output_line_dr_pdrs + "{},{},{:1.4f},".format(dr_delivered, dr_tx, dr_pdr)
        output_line_dr_pdrs = output_line_dr_pdrs[:-1] # remove trailing comma

        output_line = "{},{},{},{},{},{},"\
                      "{},{},{},{},{:1.4f},{},{},"\
                      "{},{},{},{},{},"\
                      "{},{},{},{},{},"\
                      "{},{},{},{},{},"\
                      "{},{},"\
                      "{},{},{},"\
                      "{},{},{},{},"\
                      "{},{},{},{},{},"\
                      "{},{},{},{},{},"\
                      "{},{},{},{},{},"\
                      "{},{},{},{},{}\n".format(sim_settings['nGateways'], sim_settings['nEndDevices'], sim_settings['totalTime'], sim_settings['drCalcMethod'], sim_settings['drCalcMethodMisc'], sim_settings['seed'],
                                                sim_settings['usConfirmedData'], sim_settings['usDataPeriod'], upstream_stats['nrDelivered'], upstream_stats['nrPackets'], upstream_stats['nrDelivered']/upstream_stats['nrPackets'], upstream_stats['nrSent'], upstream_stats['nrReceived'],
                                                upstream_stats_sent[0],upstream_stats_sent[1],upstream_stats_sent[2],upstream_stats_sent[3],upstream_stats_sent[4],
                                                upstream_stats_received[0],upstream_stats_received[1],upstream_stats_received[2],upstream_stats_received[3],upstream_stats_received[4],
                                                upstream_stats_senttries[0],upstream_stats_senttries[1],upstream_stats_senttries[2],upstream_stats_senttries[3],upstream_stats_senttries[4],
                                                us_packets_sent_vs_received[1][0], us_packets_sent_vs_received[1][1],
                                                us_packets_sent_vs_received[2][0], us_packets_sent_vs_received[2][1], us_packets_sent_vs_received[2][2],
                                                us_packets_sent_vs_received[3][0], us_packets_sent_vs_received[3][1], us_packets_sent_vs_received[3][2], us_packets_sent_vs_received[3][3],
                                                us_packets_sent_vs_received[4][0], us_packets_sent_vs_received[4][1], us_packets_sent_vs_received[4][2], us_packets_sent_vs_received[4][3], us_packets_sent_vs_received[4][4],
                                                downstream_stats_sent[0],downstream_stats_sent[1],downstream_stats_sent[2],downstream_stats_sent[3],downstream_stats_sent[4],
                                                downstream_stats_received[0],downstream_stats_received[1],downstream_stats_received[2],downstream_stats_received[3],downstream_stats_received[4],
                                                downstream_stats_senttries[0],downstream_stats_senttries[1],downstream_stats_senttries[2],downstream_stats_senttries[3],downstream_stats_senttries[4])
        output_file.write(output_line)

    # # Generate output per node
    print ("Appending output per end device to {}".format(args.outputfileenddevice))
    write_header = False
    if not os.path.exists(args.outputfileenddevice):
        write_header = True
    with open(args.outputfileenddevice, 'a') as output_file: # append to output file
        outputFormat = "<nGateways>,<nEndDevices>,<totalTime>,<drCalcMethod>,<drCalcMethodMisc>,<seed>,<usDataConfirmed>,<usDataPeriod>,<nodeId>,<packetsDelivered>,<packetsGenerated>,<PDR>,<packetsSent>,<packetsReceived>,\n"
        if write_header:
            output_file.write(outputFormat)

        for node_id in sorted(nodes):
            if nodes[node_id]['PacketsGenerated'] > 0:
                output_line = "{},{},{},{},{},{},{},{},{},{},{},{:1.4f},{},{}\n".format(sim_settings['nGateways'], sim_settings['nEndDevices'], sim_settings['totalTime'],
                                                                          sim_settings['drCalcMethod'], sim_settings['drCalcMethodMisc'], sim_settings['seed'], sim_settings['usConfirmedData'], sim_settings['usDataPeriod'],
                                                                          node_id, nodes[node_id]['PacketsDelivered'], nodes[node_id]['PacketsGenerated'], nodes[node_id]['PacketsDelivered']/nodes[node_id]['PacketsGenerated'], nodes[node_id]['PacketsSent'], nodes[node_id]['PacketsReceived'])
                output_file.write(output_line)
            else:
                # print ("{},{},{},{}".format(k, 0, 0, 1))
                pass
    print ("------------------------------------------------------------------")
