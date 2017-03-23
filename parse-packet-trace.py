#!/usr/bin/python3
# Parse ns-3 lorawan packet trace CSV output files
import csv
import argparse
import re
import json

parser = argparse.ArgumentParser(description='Process ns-3 lorawan packet trace CSV output file.')
parser.add_argument('csvfiles', nargs='*', help='The CSV files to be parsed')
parser.add_argument('--output', default="parse-packet-trace.csv", help='The output CSV file')

args = parser.parse_args()
for csvfilename in args.csvfiles:
    print("\nParsing file {}".format(csvfilename))
    nodes = {}
    app_packets = {}
    phy_transmissions = {}
    with open(csvfilename, newline='') as csvfile:
        linereader = csv.reader(csvfile, delimiter=',', quotechar='|')
        next(linereader) # skip the header line in the csv file

        # Process CSV file: populate phy_transmissions data structure
        for row in linereader:
            # parse app layer packets:
            key = row[7] # packet in hex
            if key not in app_packets:
                app_packets[key] = {'PhyTxBegin': [], 'PhyRxBegin': [], 'PhyTxEnd': [], 'PhyRxEnd': [], 'PhyRxDrop': [], 'PhyTxDrop': []}

            node_id = row[2]
            trace_source = row[5]
            app_packets[key][trace_source].append(node_id)
            if node_id not in nodes:
                nodes[node_id] = {'DeviceType': int(row[1]), 'TransmissionsSent': 0, 'TransmissionsDelivered': 0, 'TransmissionsNotDelivered': 0, 'DropRxReason': []}

            # parse phy layer transmissions
            key = row[6] # PhyTraceIdTag
            if key not in phy_transmissions:
                phy_transmissions[key] = {'PhyTxBegin': [], 'PhyRxBegin': [], 'PhyTxEnd': [], 'PhyRxEnd': [], 'PhyRxDrop': [], 'PhyTxDrop': [], 'Delivered': False}
            if trace_source == 'PhyTxBegin':
                channel_index = row[9]
                data_rate_index = row[10]
                phy_transmissions[key][trace_source].append((node_id, channel_index, data_rate_index)) # store node_id and channel_index and data_rate_index as a tuple
            elif trace_source == 'PhyRxDrop':
                drop_reason = row[9]
                phy_transmissions[key][trace_source].append((node_id, drop_reason)) # store node_id and drop_reason as a tuple
            else:
                phy_transmissions[key][trace_source].append(node_id)

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

        tx_node_id = tx['PhyTxBegin'][0][0]
        nodes[tx_node_id]['TransmissionsSent'] += 1
        if len(tx['PhyTxEnd']) == 1 and tx['PhyTxEnd'][0] == tx_node_id:
            # check receivers
            tx_node_devicetype = nodes[tx_node_id]['DeviceType']
            expected_rx_devicetype = 0 # by default we expect the transmission was sent by an end device and will be received by a gateway
            if tx_node_devicetype == 0: # tx was gateway
                expected_rx_devicetype = 1

            node_received = False
            found_expected_rx_device = False
            receiver_in_phyrxend = False
            for rx_node in tx['PhyRxBegin']:
                node_received = True
                # check if receiver is of opposite device type than transmitter
                if nodes[rx_node]['DeviceType'] == expected_rx_devicetype:
                    found_expected_rx_device = True
                    # Check whether this receiver reached PhyRxEnd for this transmission
                    if rx_node in tx['PhyRxEnd']:
                        phy_transmissions[key]['Delivered'] = True
                        receiver_in_phyrxend = True
                        number_of_delivered_transmissions += 1
                        nodes[tx_node_id]['TransmissionsDelivered'] += 1
                        break

            transmission_not_delivered = not node_received or not found_expected_rx_device or not receiver_in_phyrxend
            if transmission_not_delivered:
                number_of_undelivered_transmissions += 1
                nodes[tx_node_id]['TransmissionsNotDelivered'] += 1

                # store DropRxReason:
                for drop_tuple in tx['PhyRxDrop']:
                    drop_node_id = drop_tuple [0]
                    # check if we are actually interested in the drop event (i.e. was the end device transmission dropped by a gateway phy?)
                    if nodes[drop_node_id]['DeviceType'] == expected_rx_devicetype:
                        drop_reason = int(drop_tuple [1])
                        # store drop reason per node:
                        nodes[tx_node_id]['DropRxReason'].append(drop_reason)
                        # store drop reason over all nodes:
                        sim_drop_reasons.append(drop_reason)
                        # store data rate index for drop_reason
                        data_rate_index = int(tx['PhyTxBegin'][0][2])
                        if drop_reason not in sim_drop_reasons_datarateindex:
                            sim_drop_reasons_datarateindex[drop_reason] = list()
                        sim_drop_reasons_datarateindex[drop_reason].append(data_rate_index)

                # print reason:
                if not node_received:
                    pass
                    # print ("key = {}: Transmission not delivered because no node started receiving it".format(key))
                else:
                    if not found_expected_rx_device:
                        pass
                        # print ("key = {}: Transmission not delivered because there wasn't a suitable receiver, tx_node_devicetype = {} tx = {}".format(key, tx_node_devicetype, tx))
                    else:
                        if not receiver_in_phyrxend:
                            print ("key = {}: Transmission not delivered because the receiver did not enter the PhyRxEnd state, tx = {}".format(key, tx))
        else:
            if tx_node_id in tx['PhyTxDrop']:
                print("key = {}: case where transmission is aborted is not implemented. tx = {}".format(tx)) # TODO: count number of aborted transmissions
                exit(1)
            else:
                print ("key = {}: WARNING transmission not delivered because sending node not found in PhyTxEnd nor in PhyTxDrop. Skipping this Transmission tx = {}".format(key, tx))
                del phy_transmissions[key]


    # Generate output:
    sim_settings_file_name = csvfilename.replace("trace-phy-tx.csv", "sim-settings.txt")
    # parse sim settings file:
    sim_settings = {"usDataPeriod": -1, "nGateways": -1, "nEndDevices": -1, "seed": -1}
    with open(sim_settings_file_name) as sim_settings_file:
        sim_settings_file_contents = sim_settings_file.read()

        p_data_period = re.compile('usDataPeriod = ([0-9]+)')
        p_ngateways = re.compile('nGateways = ([0-9]+)')
        p_nenddevices = re.compile('nEndDevices = ([0-9]+)')
        p_seed = re.compile('seed = ([0-9]+)')

        sim_settings['usDataPeriod'] = int(p_data_period.search (sim_settings_file_contents).groups()[0])
        sim_settings['nGateways'] = int(p_ngateways.search (sim_settings_file_contents).groups()[0])
        sim_settings['nEndDevices'] = int(p_nenddevices.search (sim_settings_file_contents).groups()[0])
        sim_settings['seed'] = int(p_seed.search (sim_settings_file_contents).groups()[0])

    # <usDataPeriod>,<nGateways>,<nEndDevices>,<seed>,<nodeId>,<tranmissionsDelivered>,<tranmissionsSent>,<PDR>
    print ("\nSimulation PHY delivery ratio: {}/{} = {}%. PHY Undelivered = {}.".format(number_of_delivered_transmissions, len(phy_transmissions), number_of_delivered_transmissions/len(phy_transmissions)*100, number_of_undelivered_transmissions))

    print ("\nSimulation PHY drop reasons: {} transmissions dropped. Reasons:".format(len(sim_drop_reasons)))
    print ("0x00 (LORAWAN_RX_DROP_PHY_BUSY_RX) = {}".format(sim_drop_reasons.count(0)))
    print ("0x01 (LORAWAN_RX_DROP_SINR_TOO_LOW) = {}".format(sim_drop_reasons.count(1)))
    print ("0x02 (LORAWAN_RX_DROP_NOT_IN_RX_STATE) = {}".format(sim_drop_reasons.count(2)))
    print ("0x03 (LORAWAN_RX_DROP_PACKET_DESTOYED) = {}".format(sim_drop_reasons.count(3)))
    print ("0x04 (LORAWAN_RX_DROP_ABORTED) = {}".format(sim_drop_reasons.count(4)))
    print ("0x05 (LORAWAN_RX_DROP_PACKET_ABORTED) = {}".format(sim_drop_reasons.count(5)))

    # For every drop reason, print the amount of times a transmission with a
    # specific data rate index was dropped for that drop reason
    print("\nNumber of dropped PHY transmissions at a specific data rate index for every drop reason:")
    print("Drop reason\tDR:drop_count")
    for drop_reason in sim_drop_reasons_datarateindex:
        s = "0x0{} ".format(drop_reason)
        for data_rate_index in range(6):
            count = sim_drop_reasons_datarateindex[drop_reason].count(data_rate_index)
            s = s + "\t{}:{}".format(data_rate_index, count)
        print(s)

    print ("Writing/appending output to {}".format(args.output))
    with open(args.output, 'a') as output_file: # append to output file
        for k in nodes:
            if nodes[k]['TransmissionsSent'] > 0:
                output_line = "{},{},{},{},{},{},{},{}\n".format(sim_settings['usDataPeriod'], sim_settings['nGateways'], sim_settings['nEndDevices'], sim_settings['seed'], k, nodes[k]['TransmissionsDelivered'], nodes[k]['TransmissionsSent'], nodes[k]['TransmissionsDelivered']/nodes[k]['TransmissionsSent'])
                output_file.write(output_line)
            else:
                # print ("{},{},{},{}".format(k, 0, 0, 1))
                pass
    print ("------------------------------------------------------------------")
