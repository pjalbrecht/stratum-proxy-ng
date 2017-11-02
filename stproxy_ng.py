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
from mining_libs import stratum_listener
from mining_libs import client_service
from mining_libs import jobs
from mining_libs import control

import stratum.logger
log = stratum.logger.get_logger('proxy')  

class StratumServer():
    shutdown = False

    def __init__(self):
        stp = StratumProxy(
            settings.POOL_HOST,
            settings.POOL_PORT,
            settings.POOL_USER,
            settings.POOL_PASS)
        client_service.ClientMiningService._set_stratum_proxy(stp)
        # Setup stratum listener
        if settings.STRATUM_PORT > 0:
            stratum_listener.StratumProxyService._set_stratum_proxy(stp)
            self.f = SocketTransportFactory(
                debug=False,
                event_handler=ServiceEventHandler)
            reactor.addSystemEventTrigger(
                'before',
                'shutdown',
                self.on_shutdown,
                stp.f)
            log.info(
                "Proxy is listening on port %d (stratum)" %
                (settings.STRATUM_PORT))
        # Setup control listener
        if settings.CONTROL_PORT > 0:
            control.StratumControlService._set_stratum_proxy(stp)
            reactor.listenTCP(
                settings.CONTROL_PORT,
                SocketTransportFactory(
                    debug=True,
                    event_handler=ServiceEventHandler),
                interface=settings.CONTROL_HOST)

    def on_shutdown(self, f):
        self.shutdown = True
        '''Clean environment properly'''
        log.info("Shutting down proxy...")
        # Don't let stratum factory to reconnect again
        f.is_reconnecting = False

class StratumProxy():
    set_extranonce_pools = ['nicehash.com']

    def __init__(self, host, port, user, passw):
        self.difficulty = 1
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
        self.f = SocketTransportClientFactory(
            host,
            port,
            debug=True,
            event_handler=client_service.ClientMiningService)
        self.f.on_connect.addCallback(self.on_connect)
        self.f.on_disconnect.addCallback(self.on_disconnect)

    def _detect_set_extranonce(self):
        self.use_set_extranonce = False
        for pool in self.set_extranonce_pools:
            if self.host.find(pool) > 0:
                self.use_set_extranonce = True

    @defer.inlineCallbacks
    def on_connect(self, f):
        '''Callback when proxy get connected to the pool'''
        # Hook to on_connect again
        f.on_connect.addCallback(self.on_connect)

        # Subscribe proxy
        log.info("Subscribing for mining jobs")
        (_, extranonce1, extranonce2_size) = (yield self.f.rpc('mining.subscribe', [settings.USER_AGENT]))[:3]
        self.job_registry.set_extranonce(extranonce1, extranonce2_size)

        # Set extranonce
        if self.use_set_extranonce:
            log.info("Enable extranonce subscription method")
            f.rpc('mining.extranonce.subscribe', [])

        # Authorize proxy
        log.info( "Authorizing user %s, password %s" % self.auth)
        f.rpc('mining.authorize', [self.auth[0], self.auth[1]])

    def on_disconnect(self, f):
        '''Callback when proxy get disconnected from the pool'''
        f.on_disconnect.addCallback(self.on_disconnect)
        stratum_listener.MiningSubscription.reconnect_all()
