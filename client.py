from subprocess import PIPE, Popen, call
import datetime
import time

import threading
import socket

from statistics import mean

server_ip = '127.0.0.1'
server_port = 9994

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((server_ip, server_port))


def send_msg(msg):
    msg_to_send = msg.encode()
    try:
        client.send(msg_to_send)
    except:
        print("Connection problem with " + client + ". Could not send message")


# connect to the router using ssh and copy the output to a local file
def connectToRouter1():
    cmd = 'iwinfo wlan0 assoclist > test.txt'
    stream = Popen(['ssh', 'root@192.168.1.1', cmd],
                   stdin=PIPE, stdout=PIPE)
    rsp = stream.stdout.read().decode('utf-8')
    cmd = "scp root@192.168.1.1:test.txt results.txt"
    call(cmd.split(" "))


def connectToRouter2():
    cmd = 'iwinfo wlan0 assoclist > test.txt'
    stream = Popen(['ssh', 'root@192.168.1.2', cmd],
                   stdin=PIPE, stdout=PIPE)
    rsp = stream.stdout.read().decode('utf-8')
    cmd = "scp root@192.168.1.2:test.txt results2.txt"
    call(cmd.split(" "))


def getParameters():
    send_msg("Parameters")
    recv = client.recv(4096).decode()
    if len(recv) != 0:
        return recv

    else:
        print("Please insert valid parameters")


rssis = {}
alerts = {}
queue = {}
clients = 0
clients2 = 0
waitTimes = list()


def readFile(max_rssi, min_rssi, rssi_samples):
    global clients
    global clients2
    global time
    repeated = 0
    repeatedMacs = list()
    string_time = "0"
    cycle = 0
    f = open("results.txt")
    lines = f.read().split("\n")
    f.close()
    desired_lines = lines[0:len(lines):5]
    clients = 0
    clients2 = 0
    f2 = open("results2.txt")
    lines2 = f2.read().split("\n")
    f2.close()
    desired_lines2 = lines2[0:len(lines2):5]
    i = 0
    j = 0

    # if the device performing the acess to the routers is connected by WiFi,it needs to be ignored
    if "B0:35:9F:1F:72:A0" == desired_lines[0].split(" ")[0]:
        i = 1
        if "B0:35:9F:1F:72:A0" == desired_lines2[0].split(" ")[0]:
            j = 1
    else:
        j = 1

    # if there are no stations in this router,there are no need to perform the cycle
    if desired_lines[0].split(" ")[0] == "No":
        i = len(desired_lines) - 1

    if desired_lines2[0].split(" ")[0] == "No":
        j = len(desired_lines2) - 1

    x = i
    y = j
    # check if there are macs in both routers assoclist and count them as well as appending to a list
    while x < len(desired_lines) - 1:
        while y < len(desired_lines2) - 1:
            if desired_lines[x].split(" ")[0] == desired_lines2[y].split(" ")[0]:
                repeated = repeated + 1
                repeatedMacs.append(desired_lines[x].split(" ")[0])
            y = y + 1
        x = x + 1

    # iterate over the lines of the output returned by the ssh and scp calls to the APs
    while i < len(desired_lines) - 1:
        rssi = desired_lines[i].split(" ")[2]
        mac = desired_lines[i].split(" ")[0]

        # update the rssi value if the device was already connected
        if mac in rssis.keys():
            rssis[mac] = rssi
            # the alert for the repeateMacs is given only after knowing the value from the second Ap
            if (int(rssi) < min_rssi) and mac not in repeatedMacs:
                send_msg("Send alert to " + mac)

        # create an entry in the rssis dictionary for a device that just arrived in the queue
        else:
            if int(rssi) > min_rssi:

                rssis[mac] = rssi
                # the macs that are in both Aps are added later
                if mac not in repeatedMacs:
                    clients = clients + 1

        if mac in alerts.keys():

            # if the client is still in the queue
            if queue[mac] == "True":

                if mac not in repeatedMacs:
                    clients = clients + 1

                # if the rssi is higher that the service period threshold,
                # we can calculate the waitTime and take him out of the queue
                if int(rssi) > max_rssi:
                    aux = datetime.datetime.now() - alerts[mac]
                    waitTimes.append(aux.total_seconds())
                    queue[mac] = "False"
                    alerts[mac] = datetime.datetime.now()
                    if mac not in repeatedMacs:
                        clients = clients - 1


        else:
            # start the timer for a client that enters in the queue
            alerts[mac] = datetime.datetime.now()
            queue[mac] = "True"

        i = i + 1

    while j < len(desired_lines2) - 1:
        rssi = desired_lines2[j].split(" ")[2]
        mac = desired_lines2[j].split(" ")[0]

        if mac in rssis.keys():
            # replace the rssi if the one acquired from the second Ap is better
            if int(rssi) > int(rssis[mac]):
                rssis[mac] = rssi
            if (int(rssi) < min_rssi):
                send_msg("Send alert to " + mac)
        else:
            if int(rssi) > min_rssi:
                if mac not in repeatedMacs:
                    clients2 = clients2 + 1

                rssis[mac] = rssi

        if mac in alerts.keys():

            if queue[mac] == "True":
                if mac not in repeatedMacs:
                    clients2 = clients2 + 1
                if int(rssi) > max_rssi:
                    aux = datetime.datetime.now() - alerts[mac]
                    waitTimes.append(aux.total_seconds())
                    queue[mac] = "False"
                    alerts[mac] = datetime.datetime.now()
                    if mac not in repeatedMacs:
                        clients2 = clients2 - 1


        else:
            alerts[mac] = datetime.datetime.now()
            queue[mac] = "True"

        j = j + 1

    total_clients = clients + clients2

    # add the device that is connected to both routers to the client total
    while cycle < len(repeatedMacs):
        if queue[repeatedMacs[cycle]] == "True":
            total_clients = total_clients + 1
        cycle = cycle + 1

    # create the string that has the client number and the average wait time in the queue
    if total_clients >= rssi_samples:
        msg_to_send = str(total_clients)
        size = len(waitTimes)
        if (size != 0):
            averageWaitTime = sum(waitTimes) / len(waitTimes)
            ty_res = time.gmtime(averageWaitTime)
            string_time = time.strftime("%H:%M:%S", ty_res)

        msg_to_send = msg_to_send + " " + string_time
        print(msg_to_send)
        send_msg(msg_to_send)

    clients = 0
    clients2 = 0


def main():
    """
    cycle to get the parameters defined by the monitor, this values are hardcoded just for test purposes
    while True:
        recv = getParameters()
        if len(recv) != 0:
            parameters=recv.split(" ")
            max_rssi=parameters[0]
            min_rssi=parameters[1]
            rssi_samples=parameters[2]
            max_threshold=parameters[3]
            min_threshold=parameters[4]
            alert=parameters[5]
            break

    """

    max_rssi = -30
    min_rssi = -60
    rssi_samples = 0
    # repeat the code above every 5 seconds
    threading.Timer(5.0, main).start()
    connectToRouter1()
    connectToRouter2()
    readFile(max_rssi, min_rssi, rssi_samples)
    print(rssis)
    


main()



