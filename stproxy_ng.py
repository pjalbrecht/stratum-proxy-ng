'''
    Stratum mining proxy new generation
    Copyright (C) 2012 Marek Palatinus <slush@satoshilabs.com>
    Copyright (C) 2014 Pau Escrich <p4u@dabax.netm>

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU Affero General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.
	
	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU Affero General Public License for more details.
	
	You should have received a copy of the GNU Affero General Public License
	along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from twisted.internet import reactor, defer
from stratum.socket_transport import SocketTransportFactory, SocketTransportClientFactory

from stratum import settings
from stratum.services import ServiceEventHandler
from stratum.protocol import ClientProtocol
from mining_libs import stratum_listener
from mining_libs import client_service
from mining_libs import jobs
from mining_libs import control

import stratum.logger
log = stratum.logger.get_logger('proxy')  

class StratumServer():
    pool2proxy = {}
    miner2proxy = {}
    stp = None

    def __init__(self):
        StratumServer.stp = StratumProxy(
            settings.POOL_HOST,
            settings.POOL_PORT,
            settings.POOL_USER,
            settings.POOL_PASS)

        self.f = SocketTransportFactory(
            debug=False,
            event_handler=ServiceEventHandler)

        reactor.addSystemEventTrigger(
            'before',
            'shutdown',
            self.on_shutdown)

        log.info(
            "Proxy is listening on port %d (stratum)" %
            (settings.STRATUM_PORT))

    def on_shutdown(self):
        '''Clean environment properly'''
        log.info("Shutting down proxy...")
        # Don't let stratum factory to reconnect again
        for proxy in self.pool2proxy.itervalues(): 
            proxy.f.is_reconnecting = False

class StratumControl():
    def __init__(self):
        self.f = SocketTransportFactory(
                     debug=True,
                     event_handler=ServiceEventHandler)

        log.info(
            "Proxy is listening on port %d (control)" %
            (settings.CONTROL_PORT))

class StratumProxy():
    set_extranonce_pools = ['nicehash.com']

    def __init__(self, host, port, user, passw):
        self.last_broadcast = None 
        self.use_set_extranonce = False
        log.info(
            "Connecting to Stratum pool at %s:%d" %
            (host, port))
        self.host = host
        self.port = int(port)
        self._detect_set_extranonce()
        self.job_registry = jobs.JobRegistry()
        self.auth = (user, passw)
        self.connected = defer.Deferred()
        self.authorized = False
        self.f = SocketTransportClientFactory(
            host,
            port,
            debug=True,
            event_handler=client_service.ClientMiningService)
        self.f.on_connect.addCallbacks(self.on_connect, self.on_timeout)
        self.f.on_disconnect.addCallback(self.on_disconnect)

    def _detect_set_extranonce(self):
        self.use_set_extranonce = False
        for pool in self.set_extranonce_pools:
            if self.host.find(pool) > 0:
                self.use_set_extranonce = True

    def on_timeout(self, e):
        log.info('on timeout..................... %s' % (self))
        self.f.on_connect.addCallbacks(self.on_connect, self.on_timeout)

    @defer.inlineCallbacks
    def on_connect(self, f):
        log.info('on connect..................... %s' % (self))

        # Callback when proxy get connected to the pool
        f.on_connect.addCallbacks(self.on_connect, self.on_timeout)

        # Set the pool proxy into table
        StratumServer.pool2proxy[id(f)] = self

        # Broadcast connect event
        control.PoolConnectSubscription.emit(id(f))

        # Subscribe proxy
        log.info("Subscribing for mining jobs %s" % (self))
        try:
            (_, extranonce1, extranonce2_size) = (yield self.f.rpc('mining.subscribe', [settings.USER_AGENT]))[:3]
            self.job_registry.set_extranonce(extranonce1, extranonce2_size)
        except Exception as e:
            log.info('on connect subscription failed..................%s %s' % (e, self))
            return

        # Set extranonce
        if self.use_set_extranonce:
            log.info("Enable extranonce subscription method %s" % (self))
            try:
                f.rpc('mining.extranonce.subscribe', [])
            except Exception as e:
                log.info('extranonce subscription failed..............%s %s' % (e, self))
                return

        # Authorize proxy
        log.info( "Authorizing user %s, password %s, proxy %s" % (self.auth[0], self.auth[1], self))
        try:
            self.authorized = (yield f.rpc('mining.authorize', [self.auth[0], self.auth[1]]))
        except Exception as e:
            log.info('on connect authorization failed.................%s %s' % (e, self))

        if not self.authorized:
            log.info('on connect authorization failed...................%s' % (self))

        log.info('.....................on connect %s' % (self))

        # Proxy connected
        self.connected.callback(self)

    def on_disconnect(self, f):
        log.info('on disconnect................. %s' % (self))

        # Callback when proxy get disconnected from the pool
        f.on_disconnect.addCallback(self.on_disconnect)

        # Broadcast disconnect event
        control.PoolDisconnectSubscription.emit(id(f))

        # Reset connected deferred
        if self.connected.called:
            self.connected = defer.Deferred()

        # Connect miners
        stratum_listener.MiningSubscription.reconnect_all(self)

        log.info('..................on disconnect %s' % (self))
