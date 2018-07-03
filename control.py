import sys
import json
import socket

from pprint import pprint

if len(sys.argv) < 3:
    err = 'Usage: control.py ' + '<ip:control_port> <query> [key1=value1 key2=value2]'
    sys.exit(err)

d = {}
for a in sys.argv[3::]:
    k, v = a.split('=', 1)
    d[k] = v

if sys.argv[2] == 'createpool':
    msg = {'id': 1, 'method': 'control.' + 'create_pool', 'params': [ d['host'], d['port'], d['user'], d['pass'] ]}
elif sys.argv[2] == 'connectpool':
    msg = {'id': 1, 'method': 'control.' + 'connect_pool', 'params': [ int(d['pool']), d['miner'] ]}
elif sys.argv[2] == 'deletepool':
    msg = {'id': 1, 'method': 'control.' + 'delete_pool', 'params': [ int(d['pool']) ]}
elif sys.argv[2] == 'defaultpool':
    msg = {'id': 1, 'method': 'control.' + 'default_pool', 'params': []}
elif sys.argv[2] == 'listconnections':
    msg = {'id': 1, 'method': 'control.' + 'list_connections', 'params': []}
elif sys.argv[2] == 'listtables':
    msg = {'id': 1, 'method': 'control.' + 'list_tables', 'params': []}
elif sys.argv[2] == 'listsubscriptions':
    msg = {'id': 1, 'method': 'control.' + 'list_subscriptions', 'params': []}
elif sys.argv[2] == 'listminers':
    msg = {'id': 1, 'method': 'control.' + 'list_miners', 'params': []}
elif sys.argv[2] == 'addblacklist':
    msg = {'id': 1, 'method': 'control.' + 'add_blacklist', 'params': [ d['miner'] ]}
elif sys.argv[2] == 'deleteblacklist':
    msg = {'id': 1, 'method': 'control.' + 'delete_blacklist', 'params': [ d['miner'] ]}
else:
    err = 'Invalid message: ' + sys.argv[2]
    sys.exit(err)

serial = json.dumps(msg)

ip, port = sys.argv[1].split(':')

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

s.connect((ip, int(port)))

s.send(serial+'\n')

resp = ''
while True:
    resp = resp + s.recv(1024).decode('utf-8')
    if resp[len(resp)-2] == '}' : break

s.close

resp = json.loads(resp)

pprint(resp)
