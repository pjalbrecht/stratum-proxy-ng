#!/usr/bin/env python
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

import time

from twisted.internet import reactor, defer, task
from stratum.socket_transport import SocketTransportFactory, SocketTransportClientFactory

from stratum import settings
from stratum.services import ServiceEventHandler
from mining_libs import stratum_listener
from mining_libs import client_service
from mining_libs import jobs
from mining_libs import version
from mining_libs import utils
from mining_libs import stratum_control
import stratum.logger


class StratumServer():
    shutdown = False
    log = None
    backup = None

    def __init__(self, st_listen, st_control):
        self.log = stratum.logger.get_logger('proxy%s' % settings.STRATUM_PORT)
        st_listen.log = stratum.logger.get_logger(
            'proxy%s' %
            settings.STRATUM_PORT)
        stp = StratumProxy(st_listen)
        stp.set_pool(
            settings.POOL_HOST,
            settings.POOL_PORT,
            settings.POOL_USER,
            settings.POOL_PASS,
            timeout=settings.POOL_TIMEOUT)
        stp.connect()
        w = task.LoopingCall(self.watcher, stp, st_listen)
        w.start(10.0)
        # Setup stratum listener
        if settings.STRATUM_PORT > 0:
            st_listen.StratumProxyService._set_stratum_proxy(stp)
            self.stf = SocketTransportFactory(
                debug=False,
                event_handler=ServiceEventHandler)
            reactor.addSystemEventTrigger(
                'before',
                'shutdown',
                self.on_shutdown,
                stp.f)
            self.log.warning(
                "PROXY IS LISTENING ON ALL IPs ON PORT %d (stratum)" %
                (settings.STRATUM_PORT))
        if settings.CONTROL_PORT > 0:
            st_control.StratumControlService._set_stratum_proxy(stp)
            reactor_control = reactor.listenTCP(
                settings.CONTROL_PORT,
                SocketTransportFactory(
                    debug=True,
                    event_handler=ServiceEventHandler),
                interface=settings.CONTROL_HOST)

    def on_shutdown(self, f):
        self.shutdown = True
        '''Clean environment properly'''
        self.log.info("Shutting down proxy...")
        # Don't let stratum factory to reconnect again
        f.is_reconnecting = False

    def watcher(self, stp, stl):
        # counter for number of watcher iterations with clients connected
        it_with_clients = 0
        conn = stl.MiningSubscription.get_num_connections()
        last_job_secs = int(time.time() - stp.last_job_time)
        notify_time = stp.cservice.get_last_notify_secs()
        total_jobs = stp.rejected_jobs + \
            stp.accepted_jobs
        if total_jobs == 0:
            total_jobs = 1
        rejected_ratio = float(
            (stp.rejected_jobs * 100) / total_jobs)
        accepted_ratio = float(
            (stp.accepted_jobs * 100) / total_jobs)
        self.log.info(
            'Last Job/Notify: %ss/%ss | Accepted:%s%% Rejected:%s%% | Clients: %s | Pool: %s (diff:%s backup:%s)' %
            (last_job_secs,
             notify_time,
             accepted_ratio,
             rejected_ratio,
             conn,
             stp.host,
             stp.jobreg.difficulty,
             stp.using_backup))
        if notify_time > stp.pool_timeout or (
                it_with_clients > 6 and last_job_secs > 360):
            if stp.backup:
                self.log.error(
                    'Detected problem with current pool, configuring backup')
                '''
                stp.reconnect(
                    host=stp.backup[0],
                    port=int(
                        stp.backup[1]))
                stp.using_backup = True
                '''
            else:
                self.log.error(
                    'Detected problem with current pool, reconnecting')
                #stp.reconnect()
            notify_time = 0
            last_job_secs = 0
            it_with_clients = 0

        if conn > 0:
            it_with_clients += 1
            if it_with_clients > 65536:
                it_with_clients = 7
        else:
            it_with_clients = 0

class StratumProxy():
    f = None
    jobreg = None
    cservice = None
    accepted_jobs = 0
    rejected_jobs = 0
    last_job_time = time.time()
    use_set_extranonce = False
    set_extranonce_pools = ['nicehash.com']
    disconnect_counter = 0
    pool_timeout = 0
    backup = []
    using_backup = False
    origin_pool = []
    connecting = False

    def __init__(self, stl):
        self.log = stratum.logger.get_logger('proxy')
        self.stl = stl

    def _detect_set_extranonce(self):
        self.use_set_extranonce = False
        for pool in self.set_extranonce_pools:
            if self.host.find(pool) > 0:
                self.use_set_extranonce = True

    def set_pool(self, host, port, user, passw, timeout=120):
        self.log.warning(
            "Trying to connect to Stratum pool at %s:%d" %
            (host, port))
        self.host = host
        self.port = int(port)
        self._detect_set_extranonce()
        self.cservice = client_service.ClientMiningService
        self.f = SocketTransportClientFactory(
            host,
            port,
            debug=True,
            event_handler=self.cservice)
        self.jobreg = jobs.JobRegistry(self.f, scrypt_target=True)
        self.cservice.job_registry = self.jobreg
        self.cservice.use_dirty_ping = False
        self.pool_timeout = timeout
        self.cservice.reset_timeout()
        self.cservice.auth = (user, passw)
        self.cservice.f = self.f
        self.f.on_connect.addCallback(self.on_connect)
        self.f.on_disconnect.addCallback(self.on_disconnect)

    def reconnect(self, host=None, port=None, user=None, passw=None):
        if host:
            self.host = host
        if port:
            self.port = int(port)
        self._detect_set_extranonce()
        cuser, cpassw = self.cservice.auth
        if not user:
            user = cuser
        if not passw:
            passw = cpassw
        self.cservice.auth = (user, passw)
        self.cservice.controlled_disconnect = True
        self.log.info("Trying reconnection with pool")
        if not self.f.client:
            self.log.info("Client was not connected before!")
            self.f.on_connect.addCallback(self.on_connect)
            self.f.on_disconnect.addCallback(self.on_disconnect)
            self.f.new_host = (self.host, self.port)
            self.f.connect()
        else:
            self.f.reconnect(host, port, None)

    def connect(self):
        self.connecting = True
        yield self.f.on_connect
        self.connecting = False

    @defer.inlineCallbacks
    def on_connect(self, f):
        '''Callback when proxy get connected to the pool'''
        # Hook to on_connect again
        f.on_connect.addCallback(self.on_connect)

        # Subscribe for receiving jobs
        self.log.info("Subscribing for mining jobs")
        (_, extranonce1, extranonce2_size) = (yield self.f.rpc('mining.subscribe', []))[:3]
        self.jobreg.set_extranonce(extranonce1, extranonce2_size)

        if self.use_set_extranonce:
            self.log.info("Enable extranonce subscription method")
            f.rpc('mining.extranonce.subscribe', [])

        self.log.warning(
            "Authorizing user %s, password %s" %
            self.cservice.auth)
        self.cservice.authorize(self.cservice.auth[0], self.cservice.auth[1])

        # Set controlled disconnect to False
        self.cservice.controlled_disconnect = False
        self.disconnect_counter = 0
        defer.returnValue(f)

    def on_disconnect(self, f):
        '''Callback when proxy get disconnected from the pool'''
        f.on_disconnect.addCallback(self.on_disconnect)
        if not self.cservice.controlled_disconnect:
            self.log.error(
                "Uncontroled disconnect detected for pool %s:%d" %
                self.f.main_host)
            if self.backup and self.disconnect_counter > 1:
                self.log.error(
                    "Two or more connection lost, switching to backup pool: %s" %
                    self.backup)
                f.new_host = (self.backup[0], self.backup[1])
                self.origin_pool = [self.host, self.port]
                self.host = self.backup[0]
                self.port = self.backup[1]
                self.using_backup = True
        else:
            self.log.info("Controlled disconnect detected")
            self.cservice.controlled_disconnect = False
        self.stl.MiningSubscription.reconnect_all()
        self.disconnect_counter += 1
        return f
