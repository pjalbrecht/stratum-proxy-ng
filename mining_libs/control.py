from twisted.internet import defer
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
            MinerConnectSubscription.emit(miner_id, id(proxy.f))
            log.info(miner_id)

        log.info('...................after miner connect subscribe')

        return result

class StratumControlService(GenericService):
    service_type = 'control'
    service_vendor = 'mining_proxy'
    is_default = True

    def default_pool(self):
        log.info('default pool...........%s' % (id(stproxy_ng.StratumServer.stp.f)))

        return id(stproxy_ng.StratumServer.stp.f)

    def create_pool(self, host, port, user, passw):
        log.info('create pool..........%s %s %s %s' % (host, port, user, passw))

        stp = stproxy_ng.StratumProxy(host, int(port), user, passw)
        log.info('create pool..........pool id: %s' % (id(stp.f)))

        return id(stp.f)

    def delete_pool(self, pool_id):
        log.info('delete pool..................%s' % pool_id)

        if pool_id == id(stproxy_ng.StratumServer.stp.f):
            return False

        try:
            stp = stproxy_ng.StratumServer.pool2proxy.pop(pool_id)
        except KeyError: 
            log.info('delete pool........invalid pool id: %s' % pool_id)
            return False

        for miner_id, proxy in stproxy_ng.StratumServer.miner2proxy.items():
            if stp is proxy:
                stproxy_ng.StratumServer.miner2proxy[miner_id] = stproxy_ng.StratumServer.stp 

        stratum_listener.MiningSubscription.reconnect_all(stp)

        stp.f.is_reconnecting = False
        stp.f.client.transport.loseConnection()

        return True

    def connect_pool(self, pool_id, miner_id):
        log.info('connect pool...............%s %s' % (pool_id, miner_id))

        try:
            stp = stproxy_ng.StratumServer._get_pool_proxy(pool_id)
        except KeyError:
            log.info('connect pool.......invalid pool id: %s' % (pool_id))
            raise ConnectPoolException('Connect pool--Invalid pool!')

        if miner_id not in stproxy_ng.StratumServer.miner2proxy:
            log.info('connect pool.......invalid miner id: %s' % (miner_id))
            raise ConnectPoolException('Connect pool--Invalid miner!')

        stproxy_ng.StratumServer._set_miner_proxy(miner_id, stp)

        for ref in stratum.connection_registry.ConnectionRegistry.iterate():
             conn = ref()

             if conn is None or conn.transport is None:
                 continue

             if conn._get_ip() == miner_id:
                 conn.transport.loseConnection() 
                 break

        return True

    def list_connections(self):
        log.info("list connections.........")

        l = []
        for ref in stratum.connection_registry.ConnectionRegistry.iterate():
            conn = ref()
            l.append([str(conn), str(conn.get_ident())])
            log.info('connection -> %s ident -> %s' % (conn, conn.get_ident()))

        log.info(".........list connections")

        return l

    def list_tables(self):
        log.info('list tables..........................')

        c = len(stproxy_ng.StratumServer.pool2proxy)
        log.info('pool2proxy: %s' % (c))

        l1 = [c]
        for pool_id,proxy in stproxy_ng.StratumServer.pool2proxy.iteritems():
            l1.append([str(pool_id), str(proxy)])
            log.info('%s %s' % (pool_id, proxy))

        c = len(stproxy_ng.StratumServer.miner2proxy)
        log.info('miner2proxy: %s' % (c))

        l2 = [c]
        for miner_id,proxy in stproxy_ng.StratumServer.miner2proxy.iteritems():
            l2.append([str(miner_id), str(proxy)])
            log.info('%s %s' % (miner_id, proxy))

        log.info('..........................list tables')

        return [l1, l2]

    def list_subscriptions(self):
        log.info("list subscriptions.........")

        c = pubsub.Pubsub.get_subscription_count('mining.set_difficulty')
        log.info(c)

        l1 = [c]
        for subs in pubsub.Pubsub.iterate_subscribers('mining.set_difficulty'):
            s = pubsub.Pubsub.get_subscription(
                subs.connection_ref(),
                'mining.set_difficulty',
                key=None)
            l1.append([str(s), str(s.stp), str(s.connection_ref())])
            log.info('%s %s %s' % (s, s.stp, s.connection_ref()))

        c = pubsub.Pubsub.get_subscription_count('mining.notify')
        log.info(c)

        l2 = [c]
        for subs in pubsub.Pubsub.iterate_subscribers('mining.notify'):
            s = pubsub.Pubsub.get_subscription(
                subs.connection_ref(),
                'mining.notify',
                key=None)
            l2.append([str(s), str(s.stp), str(s.connection_ref())])
            log.info('%s %s %s' % (s, s.stp, s.connection_ref()))

        c = pubsub.Pubsub.get_subscription_count('control.share')
        log.info(c)

        l3 = [c]
        for subs in pubsub.Pubsub.iterate_subscribers('control.share'):
            s = pubsub.Pubsub.get_subscription(
                subs.connection_ref(),
                'control.share',
                key=None)
            l3.append([str(s), str(s.connection_ref())])
            log.info('%s %s' % (s, s.connection_ref()))

        log.info(".........list subscriptions")

        return [l1, l2, l3]

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

    @pubsub.unsubscribe
    def unsubscribe(self, subscription_key):
        return subscription_key
