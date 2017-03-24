#!/usr/bin/python3
# Parse ns-3 lorawan PHY transmissions trace CSV output files
import csv
import argparse
import re
import os.path

parser = argparse.ArgumentParser(description='Process ns-3 lorawan PHY transmissions CSV output file.')
parser.add_argument('csvfiles', nargs='*', help='The CSV files to be parsed')
parser.add_argument('--output-simulation', dest='outputsimulation', default="parse_phytx_trace_per_simulation.csv", help='The output CSV file')
parser.add_argument('--output-enddevice', dest='outputenddevice', default="parse_phytx_trace_per_enddevice.csv", help='The output CSV file')
# parser.add_argument('--parseapppackets', type=bool, default=False, help='Parse app packets?')
feature_parser = parser.add_mutually_exclusive_group(required=False)
feature_parser.add_argument('--app-packets', dest='apppackets', action='store_true')
feature_parser.add_argument('--no-app-packets', dest='apppackets', action='store_false')
parser.set_defaults(feature=False)

args = parser.parse_args()
for csvfilename in args.csvfiles:
    print("Parsing phy tx csv file {}".format(csvfilename))
    nodes = {}
    app_packets = {}
    phy_transmissions = {}
    data_rate_stats = {0: (0,0), 1: (0,0), 2: (0,0), 3: (0,0), 4: (0,0), 5: (0,0)} # key=data rate index, value = (delivered,notdelivered)
    with open(csvfilename, newline='') as csvfile:
        linereader = csv.reader(csvfile, delimiter=',', quotechar='|')
        next(linereader) # skip the header line in the csv file

        # Process CSV file: populate phy_transmissions data structure
        for row in linereader:
            node_id = int(row[2])
            trace_source = row[5]
            # parse app layer packets:
            if args.apppackets:
                app_packets_key = row[7] # packet in hex
                if app_packets_key not in app_packets:
                    app_packets[app_packets_key] = {'PhyTxBegin': [], 'PhyRxBegin': [], 'PhyTxEnd': [], 'PhyRxEnd': [], 'PhyRxDrop': [], 'PhyTxDrop': []}
                app_packets[app_packets_key][trace_source].append(node_id)

            if node_id not in nodes:
                nodes[node_id] = {'DeviceType': int(row[1]), 'TransmissionsSent': 0, 'TransmissionsDelivered': 0, 'TransmissionsNotDelivered': 0, 'DropRxReason': []}

            # parse phy layer transmissions
            phy_key = row[6] # PhyTraceIdTag
            if phy_key not in phy_transmissions:
                phy_transmissions[phy_key] = {'PhyTxBegin': [], 'PhyTxBeginMisc': [], 'PhyRxBegin': [], 'PhyTxEnd': [], 'PhyRxEnd': [], 'PhyRxDrop': [], 'PhyRxDropMisc': [], 'PhyTxDrop': [], 'Delivered': False}

            phy_transmissions[phy_key][trace_source].append(node_id) # store this node under trace_source

            # Store any interesting misc fields depending on trace_source:
            if trace_source == 'PhyTxBegin':
                channel_index = int(row[9])
                data_rate_index = int(row[10])
                t = (node_id, channel_index, data_rate_index) # store node_id and channel_index and data_rate_index as a tuple
                phy_transmissions[phy_key]['PhyTxBeginMisc'].append(t)
            elif trace_source == 'PhyRxDrop':
                drop_reason = int(row[9])
                t = (node_id, drop_reason) # store node_id and drop_reason as a tuple
                phy_transmissions[phy_key]['PhyRxDropMisc'].append(t)

    # Process phy_transmissions data structure:
    # Was the transmission delivered and if so, was it received by a device of
    # the opposite device type (i.e. end device TX received by GW or visa versa)
    # When a transmission was not delivered, what was the reason?
    number_of_delivered_transmissions = 0
    number_of_undelivered_transmissions = 0
    sim_drop_reasons = [] # simple list of drop reasons, e.g. [0, 0, 0, 1]
    sim_drop_reasons_datarateindex = {} # dict of lists , e.g. {0: [0, 1], 1: [0,1]} dict keys are drop reasons, values are lists of data rate indexes of the phy transmission that was dropped for drop reason=key
    for key in list(phy_transmissions.keys()):
        tx = phy_transmissions[key]
        if len (tx['PhyTxBegin']) != 1:
            print("key={}: ERROR SKIPPING this transmissions as there is not exactly one node in PhyTxBegin list for tx = {}".format(key, tx))
            continue

        tx_node_id = tx['PhyTxBegin'][0] # a phy tx can only be started sending by one node
        nodes[tx_node_id]['TransmissionsSent'] += 1
        if len(tx['PhyTxEnd']) == 1 and tx['PhyTxEnd'][0] == tx_node_id:
            # check receivers
            tx_node_devicetype = nodes[tx_node_id]['DeviceType']
            expected_rx_devicetype = 0 # by default we expect the transmission was sent by an end device and will be received by a gateway
            if tx_node_devicetype == 0: # tx was gateway, so expect an end device to receive the transmission, TODO: check specific end device?
                expected_rx_devicetype = 1

            node_received = False # a node started receiving the tx
            found_expected_rx_device = False # a node that started receiving the tx has the correct device type
            receiver_in_phyrxend = False # a node that started receiving the tx and that is the correct device type also finished receiving the transmission
            receiver_not_in_phyrxdrop = False # a node that started receiving the tx, that is the correct device type and finished receiving the transmission also did not drop the packet
            for rx_node in tx['PhyRxBegin']:
                node_received = True
                # check if receiver is of opposite device type than transmitter
                if nodes[rx_node]['DeviceType'] == expected_rx_devicetype:
                    found_expected_rx_device = True
                    # Check whether this receiver reached PhyRxEnd for this transmission
                    if rx_node in tx['PhyRxEnd']:
                        receiver_in_phyrxend = True
                        # Check whether this receiver did not drop the packet after ending reception
                        if rx_node not in tx['PhyRxDrop']:
                            # PHY Transmission delivered!
                            receiver_not_in_phyrxdrop = True
                            number_of_delivered_transmissions += 1
                            phy_transmissions[key]['Delivered'] = True
                            nodes[tx_node_id]['TransmissionsDelivered'] += 1
                            # Update global delivered/undelivered stats:
                            data_rate_index = int(tx['PhyTxBeginMisc'][0][2]) # always index 0 here as there is only one node that starts sending a transmission
                            data_rate_stats[data_rate_index] = (data_rate_stats[data_rate_index][0] + 1, data_rate_stats[data_rate_index][1])
                            break

            transmission_not_delivered = not node_received or not found_expected_rx_device or not receiver_in_phyrxend or not receiver_not_in_phyrxdrop
            if transmission_not_delivered:
                number_of_undelivered_transmissions += 1
                nodes[tx_node_id]['TransmissionsNotDelivered'] += 1

                # store DropRxReason:
                for drop_tuple in tx['PhyRxDropMisc']:
                    drop_node_id = drop_tuple [0]
                    # check if we are actually interested in the drop event (i.e. was the end device transmission dropped by a gateway phy?)
                    if nodes[drop_node_id]['DeviceType'] == expected_rx_devicetype:
                        # Update global delivered/undelivered stats:
                        data_rate_stats[data_rate_index] = (data_rate_stats[data_rate_index][0], data_rate_stats[data_rate_index][1] + 1)
                        drop_reason = int(drop_tuple [1])
                        # store drop reason per node:
                        nodes[tx_node_id]['DropRxReason'].append(drop_reason)
                        # store drop reason over all nodes:
                        sim_drop_reasons.append(drop_reason)
                        # store data rate index for drop_reason
                        data_rate_index = int(tx['PhyTxBeginMisc'][0][2]) # always index 0 here as there is only one node that starts sending a transmission
                        if drop_reason not in sim_drop_reasons_datarateindex:
                            sim_drop_reasons_datarateindex[drop_reason] = list()
                        sim_drop_reasons_datarateindex[drop_reason].append(data_rate_index)

                # print reason:
                if not node_received:
                    # print ("key = {}: Transmission not delivered because no node started receiving it".format(key))
                    pass
                else:
                    if not found_expected_rx_device:
                        # print ("key = {}: Transmission not delivered because there wasn't a suitable receiver, tx_node_devicetype = {} tx = {}".format(key, tx_node_devicetype, tx))
                        pass
                    else:
                        if not receiver_in_phyrxend:
                            print ("key = {}: Transmission not delivered because the receiver did not enter the PhyRxEnd state, tx = {}".format(key, tx))
                        else:
                            if not receiver_not_in_phyrxdrop:
                                #print ("key = {}: Transmission not delivered because the receiver dropped the packet after reception, tx = {}".format(key, tx))
                                pass
        else:
            if tx_node_id in tx['PhyTxDrop']:
                print("key = {}: case where transmission is aborted is not implemented. tx = {}".format(tx)) # TODO: count number of aborted transmissions
                exit(1)
            else:
                # print ("key = {}: WARNING transmission not delivered because sending node not found in PhyTxEnd nor in PhyTxDrop. Skipping this Transmission tx = {}".format(key, tx))
                del phy_transmissions[key]


    # Generate output:
    n_delivered = number_of_delivered_transmissions
    n_undelivered = number_of_undelivered_transmissions
    n_tx = len(phy_transmissions)
    pdr = n_delivered/n_tx
    print ("\nSimulation PHY delivery ratio: {}/{} = {}% ({} undelivered).".format(n_delivered, n_tx, 100*pdr, n_undelivered))

    print ("\nDelivery/drop numbers per data rate index:")
    print("{:<5}{:>15}{:>15}{:>15}".format("DR", "Delivered","Undelivered","%"))
    for data_rate_index in data_rate_stats:
        fraction = 100*data_rate_stats[data_rate_index][0] / ( data_rate_stats[data_rate_index][0] + data_rate_stats[data_rate_index][1])
        print("{:<5}{:>15}{:>15}{:>15.2f}".format(data_rate_index, data_rate_stats[data_rate_index][0], data_rate_stats[data_rate_index][1], fraction))

    # For every drop reason, print the amount of times a transmission with a
    # specific data rate index was dropped for that drop reason
    print("\nNumber of dropped PHY transmissions at a specific data rate index for every drop reason:")
    print("{:<25}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}{:>10}".format("Drop reason | DR:", 0, 1, 2, 3, 4, 5, "Sum")) #\t\t0\t1\t2\t3\t4\t5\tSum")
    drop_reason_text = ["PHY_BUSY_RX", "SINR_TOO_LOW", "NOT_IN_RX_STATE", "PACKET_DESTROYED", "ABORTED", "PACKET_ABORTED"]
    for drop_reason in sorted(sim_drop_reasons_datarateindex):
        drop_reason_output = "{}({})".format(drop_reason_text[drop_reason], drop_reason)
        s = "{:<25}".format(drop_reason_output)
        for data_rate_index in range(6):
            count = sim_drop_reasons_datarateindex[drop_reason].count(data_rate_index)
            s = s + "{:>10}".format(count)
        s = s + "{:>10}".format(sim_drop_reasons.count(drop_reason))
        print(s)

    # parse sim settings file:
    sim_settings_file_name = csvfilename.replace("trace-phy-tx.csv", "sim-settings.txt")

    sim_settings = {"nGateways": -1, "nEndDevices": -1, "totalTime": -1, "usDataPeriod": -1, "seed": -1, "drCalcMethod": -1, "drCalcMethodMisc": -1  }
    with open(sim_settings_file_name) as sim_settings_file:
        sim_settings_file_contents = sim_settings_file.read()

        p_ngateways = re.compile('nGateways = ([0-9]+)')
        p_nenddevices = re.compile('nEndDevices = ([0-9]+)')
        p_totaltime = re.compile('totalTime = ([0-9]+)')
        p_data_period = re.compile('usDataPeriod = ([0-9]+)')
        p_seed = re.compile('seed = ([0-9]+)')
        p_drcalcmethod = re.compile('Data rate assignment method index: ([0-9]+)')

        sim_settings['nGateways'] = int(p_ngateways.search (sim_settings_file_contents).groups()[0])
        sim_settings['nEndDevices'] = int(p_nenddevices.search (sim_settings_file_contents).groups()[0])
        sim_settings['totalTime'] =  int(p_totaltime.search (sim_settings_file_contents).groups()[0])
        sim_settings['usDataPeriod'] = int(p_data_period.search (sim_settings_file_contents).groups()[0])
        sim_settings['seed'] = int(p_seed.search (sim_settings_file_contents).groups()[0])

        sim_settings['drCalcMethod'] = int(p_drcalcmethod.search (sim_settings_file_contents).groups()[0])
        if sim_settings['drCalcMethod'] == 0:
            p_drcalcperlimit = re.compile('PER limit = (\d+\.\d+)')
            sim_settings['drCalcMethodMisc'] = float(p_drcalcperlimit.search (sim_settings_file_contents).groups()[0])
        if sim_settings['drCalcMethod'] == 1:
            p_drcalcfixeddr = re.compile('Fixed Data Rate Index = ([0-9]+)')
            sim_settings['drCalcMethodMisc'] = int(p_drcalcfixeddr.search (sim_settings_file_contents).groups()[0])

    # Generate output per simulation
    print ("\nAppending output per simulation to {}".format(args.outputsimulation))
    write_header = False
    if not os.path.exists(args.outputsimulation):
        write_header = True
    with open(args.outputsimulation, 'a') as output_file: # append to output file
        outputFormat = "<nGateways>,<nEndDevices>,<totalTime>,<drCalcMethod>,<drCalcMethodMisc>,<seed>,<usDataPeriod>,<delivered>,<sent>,<PDR>"\
                       "<deliveredDR0>,<sentDR0>,<PDRDR0>,<deliveredDR1>,<sentDR1>,<PDRDR1>,<deliveredDR2>,<sentDR2>,<PDRDR2>,"\
                       "<deliveredDR3>,<sentDR3>,<PDRDR3>,<deliveredDR4>,<sentDR4>,<PDRDR4>,<deliveredDR5>,<sentDR5>,<PDRDR5>\n"
        if write_header:
            output_file.write(outputFormat)

        output_line_dr_pdrs = ""
        for data_rate_index in data_rate_stats:
            dr_delivered = data_rate_stats[data_rate_index][0]
            dr_undelivered = data_rate_stats[data_rate_index][1]
            dr_tx = dr_delivered + dr_undelivered
            dr_pdr = dr_delivered/dr_tx
            output_line_dr_pdrs = output_line_dr_pdrs + "{},{},{:1.4f},".format(dr_delivered, dr_tx, dr_pdr)
        output_line_dr_pdrs = output_line_dr_pdrs[:-1] # remove trailing comma

        output_line = "{},{},{},{},{},{},{},{},{},{:1.4f},{}\n".format(sim_settings['nGateways'], sim_settings['nEndDevices'], sim_settings['totalTime'],
                                                                  sim_settings['drCalcMethod'], sim_settings['drCalcMethodMisc'], sim_settings['seed'], sim_settings['usDataPeriod'],
                                                                  n_delivered, n_tx, pdr, output_line_dr_pdrs)
        output_file.write(output_line)

    # Generate output per node
    print ("Appending output per end device to {}".format(args.outputenddevice))
    write_header = False
    if not os.path.exists(args.outputenddevice):
        write_header = True
    with open(args.outputenddevice, 'a') as output_file: # append to output file
        outputFormat = "<nGateways>,<nEndDevices>,<totalTime>,<drCalcMethod>,<drCalcMethodMisc>,<seed>,<usDataPeriod>,<nodeId>,<tranmissionsDeliveredForNode>,<tranmissionsSentForNode>,<PDRForNode>\n"
        if write_header:
            output_file.write(outputFormat)

        for node_id in sorted(nodes):
            if nodes[node_id]['TransmissionsSent'] > 0:
                output_line = "{},{},{},{},{},{},{},{},{},{},{}\n".format(sim_settings['nGateways'], sim_settings['nEndDevices'], sim_settings['totalTime'],
                                                                          sim_settings['drCalcMethod'], sim_settings['drCalcMethodMisc'], sim_settings['seed'], sim_settings['usDataPeriod'],
                                                                          node_id, nodes[node_id]['TransmissionsDelivered'], nodes[node_id]['TransmissionsSent'], nodes[node_id]['TransmissionsDelivered']/nodes[node_id]['TransmissionsSent'])
                output_file.write(output_line)
            else:
                # print ("{},{},{},{}".format(k, 0, 0, 1))
                pass
    print ("------------------------------------------------------------------")
