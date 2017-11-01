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
     stp = None  # Reference to StratumProxy instance

     @classmethod
     def _set_stratum_proxy(cls, stp):
          cls.stp = stp

     @classmethod
     def _get_stratum_proxy(cls):
          return cls.stp

     '''
     def set_pool(self, host, port, user, passw):
          log.info("set pool.........%s %s %s %s" % (host, port, user, passw))
          stp = self._get_stratum_proxy()
          stp.reconnect(
               host=host,
               port=int(port),
               user=user,
               passw=passw)
          return True
     ''' 

     @pubsub.subscribe
     def subscribe_share(self):
          return ShareSubscription()

     @pubsub.unsubscribe
     def unsubscribe(self, subscription_key):
          return subscription_key
