from twisted.internet import defer
from stratum.services import GenericService
import stratum.pubsub as pubsub
import stratum.connection_registry
import stratum.protocol

import stratum.logger
log = stratum.logger.get_logger('proxy')

class ShareSubscription(pubsub.Subscription):
    event = 'control.share'

class StratumControlService(GenericService):
     service_type = 'control'
     service_vendor = 'mining_proxy'
     is_default = True

     def create_pool(self, host, port, user, passw):
          log.info('create pool..........%s %s %s %s' % (host, port, user, passw))
          return True

     def destroy_pool(self, pool_id):
          log.info('destroy pool..................%s' % pool_id)
          return True

     def connect_pool(self, pool_id, miner_id):
          log.info('connect pool...............%s %s' % (pool_id, miner_id))
          return True

     def list_connections(self):
          log.info("list connections.........")

          for x in stratum.connection_registry.ConnectionRegistry.iterate():
              c = x()
              log.info('connection -> %s ident -> %s id -> %x' % (c, c.get_ident(), id(c)))

          log.info(".........list connections")

          return True

     def list_subscriptions(self):
          log.info("list subscriptions.........")

          c = pubsub.Pubsub.get_subscription_count('control.share')
          log.info(c)

          for subs in pubsub.Pubsub.iterate_subscribers('control.share'):
              s = pubsub.Pubsub.get_subscription(
                  subs.connection_ref(),
                  'control.share',
                  key=None)
              log.info(s)

          c = pubsub.Pubsub.get_subscription_count('mining.set_difficulty')
          log.info(c)

          for subs in pubsub.Pubsub.iterate_subscribers('mining.set_difficulty'):
              s = pubsub.Pubsub.get_subscription(
                  subs.connection_ref(),
                  'mining.set_difficulty',
                  key=None)
              log.info(s)

          c = pubsub.Pubsub.get_subscription_count('mining.notify')
          log.info(c)

          for subs in pubsub.Pubsub.iterate_subscribers('mining.notify'):
              s = pubsub.Pubsub.get_subscription(
                  subs.connection_ref(),
                  'mining.notify',
                  key=None)
              log.info(s)

          log.info(".........list subscriptions")

          return True

     @pubsub.subscribe
     def subscribe_share(self):
          return ShareSubscription()

     @pubsub.unsubscribe
     def unsubscribe(self, subscription_key):
          return subscription_key
