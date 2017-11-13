from twisted.internet import defer
from stratum.services import GenericService
import stratum.pubsub as pubsub
import stratum.connection_registry
import stratum.protocol
from stratum.custom_exceptions import ServiceException

import stproxy_ng

import stratum.logger
log = stratum.logger.get_logger('proxy')

class ConnectPoolException(ServiceException):
    code = -2

class ShareSubscription(pubsub.Subscription):
    event = 'control.share'

class PoolSubscription(pubsub.Subscription):
    event = 'control.pool'

    def after_subscribe(self, result):
        log.info('after pool subscribe....................')
        for k in stproxy_ng.StratumServer.pool2proxy:
            PoolSubscription.emit(k)
            log.info(k)
        log.info('....................after pool subscribe')
        return result

class MinerSubscription(pubsub.Subscription):
    event = 'control.miner'

    def after_subscribe(self, result):
        log.info('after miner subscribe...................')
        for k in stproxy_ng.StratumServer.miner2proxy:
            MinerSubscription.emit(k)
            log.info(k)
        log.info('...................after miner subscribe')
        return result

class StratumControlService(GenericService):
     service_type = 'control'
     service_vendor = 'mining_proxy'
     is_default = True

     def create_pool(self, host, port, user, passw):
          log.info('create pool..........%s %s %s %s' % (host, port, user, passw))
          stproxy_ng.StratumProxy(host, int(port), user, passw)
          return True

     def destroy_pool(self, pool_id):
          log.info('destroy pool..................%s' % pool_id)
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
          conn = stproxy_ng.StratumServer._get_miner_conn(miner_id)

          conn.transport.loseConnection() 

          return True

     def list_tables(self):
          log.info('list tables..........................')

          l1 = []
          log.info('pool2proxy: %s' % (len(stproxy_ng.StratumServer.pool2proxy)))
          for k,v in stproxy_ng.StratumServer.pool2proxy.iteritems():
              l1.append([str(k), str(v)])
              log.info('%s %s' % (k, v))

          l2 = []
          log.info('miner2proxy: %s' % (len(stproxy_ng.StratumServer.miner2proxy)))
          for k,v in stproxy_ng.StratumServer.miner2proxy.iteritems():
              l2.append([str(k), str(v)])
              log.info('%s %s' % (k, v))

          l3 = []
          log.info('miner2conn: %s' % (len(stproxy_ng.StratumServer.miner2conn)))
          for k,v in stproxy_ng.StratumServer.miner2conn.iteritems():
              l2.append([str(k), str(v)])
              log.info('%s %s' % (k, v))

          log.info('..........................list tables')

          return [l1, l2, l3]

     def list_connections(self):
          log.info("list connections.........")

          l = []
          for x in stratum.connection_registry.ConnectionRegistry.iterate():
              c = x()
              l.append([str(c), str(c.get_ident())])
              log.info('connection -> %s ident -> %s' % (c, c.get_ident()))

          log.info(".........list connections")

          return l

     def list_subscriptions(self):
          log.info("list subscriptions.........")

          c = pubsub.Pubsub.get_subscription_count('control.share')
          log.info(c)

          l1 = []
          for subs in pubsub.Pubsub.iterate_subscribers('control.share'):
              s = pubsub.Pubsub.get_subscription(
                  subs.connection_ref(),
                  'control.share',
                  key=None)
              l1.append(str(s))
              log.info(s)

          c = pubsub.Pubsub.get_subscription_count('mining.set_difficulty')
          log.info(c)

          l2 = []
          for subs in pubsub.Pubsub.iterate_subscribers('mining.set_difficulty'):
              s = pubsub.Pubsub.get_subscription(
                  subs.connection_ref(),
                  'mining.set_difficulty',
                  key=None)
              l2.append(str(s))
              log.info(s)

          c = pubsub.Pubsub.get_subscription_count('mining.notify')
          log.info(c)

          l3 = []
          for subs in pubsub.Pubsub.iterate_subscribers('mining.notify'):
              s = pubsub.Pubsub.get_subscription(
                  subs.connection_ref(),
                  'mining.notify',
                  key=None)
              l3.append(str(s))
              log.info(s)

          log.info(".........list subscriptions")

          return [l1, l2, l3]

     @pubsub.subscribe
     def subscribe_share(self):
          return ShareSubscription()

     @pubsub.subscribe
     def subscribe_pool(self):
          return PoolSubscription()

     @pubsub.subscribe
     def subscribe_miner(self):
          return MinerSubscription()

     @pubsub.unsubscribe
     def unsubscribe(self, subscription_key):
          return subscription_key
