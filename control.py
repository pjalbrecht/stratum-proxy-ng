import sys
import json
import socket

def niceprint(data):
    return json.dumps(
        data,
        sort_keys=True,
        indent=4,
        separators=(
            ',',
            ': ')).__str__()

if len(sys.argv) < 3:
    print(
        "Usage: %s <ip:control_port> <query> [key1=value1 key2=value2]" %
        sys.argv[0])
    sys.exit(1)

d = {}

for a in sys.argv[3::]:
    k, v = a.split('=', 1)
    d[k] = v

if sys.argv[2] == 'createpool':
    l = [ d['host'], d['port'], d['user'], d['pass'] ]
    msg = {'id': 1234, 'method': 'control.' + 'create_pool', 'params': l}
    print msg
elif sys.argv[2] == 'connectpool':
    l = [ int(d['pool']), d['miner'] ]
    msg = {'id': 1234, 'method': 'control.' + 'connect_pool', 'params': l}
    print msg
elif sys.argv[2] == 'deletepool':
    l = [ int(d['pool']) ]
    msg = {'id': 1234, 'method': 'control.' + 'delete_pool', 'params': l}
    print msg
elif sys.argv[2] == 'defaultpool':
    l = []
    msg = {'id': 1234, 'method': 'control.' + 'default_pool', 'params': l}
    print msg
elif sys.argv[2] == 'listconnections':
    l = []
    msg = {'id': 1234, 'method': 'control.' + 'list_connections', 'params': l}
    print msg
elif sys.argv[2] == 'listtables':
    l = []
    msg = {'id': 1234, 'method': 'control.' + 'list_tables', 'params': l}
    print msg
elif sys.argv[2] == 'listsubscriptions':
    l = []
    msg = {'id': 1234, 'method': 'control.' + 'list_subscriptions', 'params': l}
    print msg
else:
    msg = {}
    pass

print niceprint(msg)
serial = json.dumps(msg)
print serial

ip, port = sys.argv[1].split(':')
print ip,port

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((ip, int(port)))
s.send(serial+'\n')
resp = s.recv(8192)
s.close

print resp
