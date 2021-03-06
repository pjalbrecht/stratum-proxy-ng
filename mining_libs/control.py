from twisted.internet import defer
from stratum import settings
from stratum.services import GenericService
import stratum.pubsub as pubsub
import stratum.connection_registry
import stratum.protocol
from stratum.custom_exceptions import ServiceException

import stproxy_ng
import stratum_listener

import stratum.logger
log = stratum.logger.get_logger('proxy')

class ConnectPoolException(ServiceException):
    code = -2

class ReconnectMinerException(ServiceException):
    code = -2

class ShareSubscription(pubsub.Subscription):
    event = 'control.share'

class PoolConnectSubscription(pubsub.Subscription):
    event = 'control.pool_connect'

    def after_subscribe(self, result):
        log.info('after pool connect subscribe....................')

        for proxy in stproxy_ng.StratumServer.pool2proxy.values():
            PoolConnectSubscription.emit(id(proxy.f))
            log.info(id(proxy.f))

        log.info('....................after pool connect subscribe')

        return result

class PoolDisconnectSubscription(pubsub.Subscription):
    event = 'control.pool_disconnect'

class MinerConnectSubscription(pubsub.Subscription):
    event = 'control.miner_connect'

    def after_subscribe(self, result):
        log.info('after miner connect subscribe...................')

        for miner_id,proxy in stproxy_ng.StratumServer.miner2proxy.iteritems():
            pool_id = id(proxy.f) if proxy is not None else 0

            MinerConnectSubscription.emit(miner_id, pool_id)

            log.info(miner_id)

        log.info('...................after miner connect subscribe')

        return result

class MinerDisconnectSubscription(pubsub.Subscription):
    event = 'control.miner_disconnect'

class StratumControlService(GenericService):
    service_type = 'control'
    service_vendor = 'mining_proxy'
    is_default = True

    def default_pool(self):
        log.info('default pool...........%s', id(stproxy_ng.StratumServer.stp.f))

        return id(stproxy_ng.StratumServer.stp.f)

    def create_pool(self, host, port, user, passw):
        log.info('create pool..........%s %s %s %s', host, port, user, passw)

        stp = stproxy_ng.StratumProxy(host, int(port), user, passw)
        log.info('create pool..........pool id: %s', id(stp.f))

        return id(stp.f)

    def delete_pool(self, pool_id):
        log.info('delete pool..................%s', pool_id)

        if pool_id == id(stproxy_ng.StratumServer.stp.f):
            return False

        try:
            stp = stproxy_ng.StratumServer.pool2proxy.pop(pool_id)
        except KeyError: 
            log.info('delete pool........invalid pool id: %s', pool_id)
            return False

        for miner_id, proxy in stproxy_ng.StratumServer.miner2proxy.items():
            if stp is proxy:
                stproxy_ng.StratumServer.miner2proxy[miner_id] = stproxy_ng.StratumServer.stp 

        stratum_listener.MiningSubscription.reconnect_all(stp)

        stp.f.is_reconnecting = False
        stp.f.client.transport.loseConnection()

        return True

    def connect_pool(self, pool_id, miner_id):
        log.info('connect pool...............%s %s', pool_id, miner_id)

        try:
            stp = stproxy_ng.StratumServer.pool2proxy[pool_id]
        except KeyError:
            log.info('connect pool.......invalid pool id: %s', pool_id)
            raise ConnectPoolException('Connect pool--Invalid pool!')

        if miner_id not in stproxy_ng.StratumServer.miner2proxy:
            log.info('connect pool.......invalid miner id: %s', miner_id)
            raise ConnectPoolException('Connect pool--Invalid miner!')

        stproxy_ng.StratumServer.miner2proxy[miner_id] = stp

        for ref in stratum.connection_registry.ConnectionRegistry.iterate():
             conn = ref()

             if conn is None or conn.transport is None:
                 continue

             if conn._get_ip() == miner_id:
                 conn.transport.loseConnection()

        return True

    def reconnect_miner(self, miner_id, immediate):
        log.info('reconnect miner.............%s %s', miner_id, immediate)

        if miner_id not in stproxy_ng.StratumServer.miner2proxy:
            log.info('reconnect miner.......invalid miner id: %s', miner_id)
            raise ReconnectMinerException('Reconnect miner--Invalid miner!')

        for ref in stratum.connection_registry.ConnectionRegistry.iterate():
             conn = ref()

             if conn is None or conn.transport is None:
                 continue

             if conn._get_ip() == miner_id:
                 if not immediate:
                     conn.transport.loseConnection()
                 else:
                     conn.transport.abortConnection()

        return True

    def list_connections(self):
        log.info("list connections.........")

        l1 = []
        l2 = []
        l3 = []
        for ref in stratum.connection_registry.ConnectionRegistry.iterate():
            conn = ref()
            log.info('connection -> %s peer -> %s', conn, conn._get_ip())

            if isinstance(conn, stratum.protocol.ClientProtocol): 
                l1.append([str(conn), id(conn.factory)])
            elif settings.STRATUM_PORT == conn.transport.getHost().port:
                l2.append([str(conn), conn._get_ip()])
            else:
                l3.append([str(conn), conn._get_ip()])

        log.info(".........list connections")

        return [[len(l1), l1], [len(l2), l2], [len(l3), l3]]

    def list_tables(self):
        log.info('list tables..........................')

        c1 = len(stproxy_ng.StratumServer.pool2proxy)
        log.info('pool2proxy: %s', c1)

        l1 = []
        for pool_id,proxy in stproxy_ng.StratumServer.pool2proxy.iteritems():
            l1.append([str(pool_id), str(proxy)])
            log.info('%s %s', pool_id, proxy)

        c2 = len(stproxy_ng.StratumServer.miner2proxy)
        log.info('miner2proxy: %s', c2)

        l2 = []
        for miner_id,proxy in stproxy_ng.StratumServer.miner2proxy.iteritems():
            l2.append([str(miner_id), str(proxy)])
            log.info('%s %s', miner_id, proxy)

        log.info('..........................list tables')

        return [[c1,l1], [c2,l2]]

    def list_subscriptions(self):
        log.info("list subscriptions.........")

        c = pubsub.Pubsub.get_subscription_count('control.share')
        log.info(c)

        l = []
        for subs in pubsub.Pubsub.iterate_subscribers('control.share'):
            s = pubsub.Pubsub.get_subscription(
                subs.connection_ref(),
                'control.share',
                key=None)
            l.append([str(s), str(s.connection_ref())])
            log.info('%s %s', s, s.connection_ref())

        log.info(".........list subscriptions")

        return [c, l]

    def list_miners(self):
        log.info("list miners................")

        l = []
        for ref in stratum.connection_registry.ConnectionRegistry.iterate():
            conn = ref()
            if (conn is None or
                conn.transport is None or
                settings.STRATUM_PORT != conn.transport.getHost().port):
                continue
            miner_id = conn._get_ip()
            session = conn.get_session()
            last = session.get('last_share', 0)
            start = session.get('subscribed', 0)
            shares = session.get('shares_sent', 0)
            proxy = session.get('proxy')
            pool_id = id(proxy.f) if proxy is not None else 0
            difficulty = proxy.job_registry.difficulty if proxy is not None else 0
            l.append([str(miner_id),
                      pool_id,
                      difficulty,
                      start,
                      last,
                      shares])
            log.info('%s %s %s %s %s %s', miner_id, pool_id, difficulty, start, last, shares)

        log.info("................list miners")

        return [len(l), l]

    def list_pools(self):
        log.info("list pools.................")

        l = []
        for ref in stratum.connection_registry.ConnectionRegistry.iterate():
            conn = ref()
            if (conn is None or
                conn.transport is None or
                not isinstance(conn, stratum.protocol.ClientProtocol)):
                continue
            pool_id = id(conn.factory)
            stp = stproxy_ng.StratumServer.pool2proxy[pool_id]
            ntime = stp.last_broadcast[7] if stp.last_broadcast is not None else 0
            l.append([pool_id,
                      conn.transport.getHost().port,
                      conn.transport.getPeer().host,
                      conn.transport.getPeer().port,
                      stp.subscribed,
                      stp.job_registry.difficulty,
                      int(ntime, 16)])
            log.info('%s', pool_id)

        log.info(".................list pools")

        return [len(l), l]

    def add_blacklist(self, miner_id):
        log.info('add black list %s.............................', miner_id)

        if miner_id not in stproxy_ng.StratumServer.miner2proxy:
            return False

        stproxy_ng.StratumServer.miner2proxy[miner_id] = None

        for ref in stratum.connection_registry.ConnectionRegistry.iterate():
             conn = ref()

             if conn is None or conn.transport is None:
                 continue

             if conn._get_ip() == miner_id:
                 conn.transport.loseConnection()

        log.info('.............................add black list')
        return True

    def delete_blacklist(self, miner_id):
        log.info('delete black list %s..........................', miner_id)

        if miner_id not in stproxy_ng.StratumServer.miner2proxy:
            return False

        if stproxy_ng.StratumServer.miner2proxy[miner_id] is not None:
            return False

        del stproxy_ng.StratumServer.miner2proxy[miner_id]

        log.info('..........................delete black list')
        return True

    @pubsub.subscribe
    def subscribe_share(self):
        return ShareSubscription()

    @pubsub.subscribe
    def subscribe_poolconnect(self):
        return PoolConnectSubscription()

    @pubsub.subscribe
    def subscribe_pooldisconnect(self):
        return PoolDisconnectSubscription()

    @pubsub.subscribe
    def subscribe_minerconnect(self):
        return MinerConnectSubscription()

    @pubsub.subscribe
    def subscribe_minerdisconnect(self):
        return MinerDisconnectSubscription()

    @pubsub.unsubscribe
    def unsubscribe(self, subscription_key):
        return subscription_key
