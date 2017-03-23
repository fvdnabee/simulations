#!/usr/bin/python3
# Parse ns-3 lorawan nodes CSV output files
import csv
import argparse

parser = argparse.ArgumentParser(description='Process ns-3 lorawan nodes CSV output file.')
parser.add_argument('csvfiles', nargs='*', help='The CSV files to be parsed')
parser.add_argument('--output', default="parse-packet-trace.csv", help='The output CSV file')

args = parser.parse_args()
for csvfilename in args.csvfiles:
    print("Parsing nodes file {}".format(csvfilename))
    enddevices_per_datarateindex = {}
    with open(csvfilename, newline='') as csvfile:
        linereader = csv.reader(csvfile, delimiter=',', quotechar='|')
        # next(linereader) # skip the header line in the csv file
        for row in linereader:
            device_type = int(row[1])
            if device_type == 0:
                continue # skip gateway
            elif device_type == 1:
                distance = row[4]
                data_rate_index = int(row[5])
                enddevices_per_datarateindex[data_rate_index] = enddevices_per_datarateindex.get(data_rate_index, 0) + 1

    for k in sorted(enddevices_per_datarateindex):
        count = enddevices_per_datarateindex[k]
        print("DR={}\tSF={}\t {} end devices".format(k, 12-k, count))
    print ("------------------------------------------------------------------")
