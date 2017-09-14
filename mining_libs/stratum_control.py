from twisted.internet import defer
from stratum.services import GenericService
import stratum.pubsub as pubsub
import stratum.logger
log = stratum.logger.get_logger('proxy')

rm_shares = {}

class ShareSubscription(pubsub.Subscription):
    event = 'control.share'

class StratumControlService(GenericService):
     service_type = 'control'
     service_vendor = 'mining_proxy'
     is_default = True

     @classmethod
     def _set_stratum_proxy(cls, stp):
          cls.stp = stp

     @classmethod
     def _get_stratum_proxy(cls):
          return cls.stp

     def set_pool(self, host, port, user, passw):
          log.info("set pool.........%s %s %s %s" % (host, port, user, passw))
          stp = self._get_stratum_proxy()
          stp.reconnect(
               host=host,
               port=int(port),
               user=user,
               passw=passw)
          return True

     def set_backup(self, host, port):
          log.info("set backup.......%s %s" % (host, port))
          stp = self._get_stratum_proxy()
          stp.backup = [host, int(port)]
          return True

     def get_shares(self):
          log.info("get shares.......")
          stp = self._get_stratum_proxy()
          shares = {}
          for sh in stp.sharestats.shares.keys():
              acc, rej = stp.sharestats.shares[sh]
              log.info("shares sent......sh = %s acc = %s rej = %s" % (sh, acc, rej))
              if acc + rej > 0:
                  shares[sh] = {'accepted': acc, 'rejected': rej}
          log.info('Shares sent: %s' % shares)
          for sh in shares.keys():
              if sh in rm_shares:
                   rm_shares[sh]['accepted'] += shares[sh]['accepted']
                   rm_shares[sh]['rejected'] += shares[sh]['rejected']
              else:
                   rm_shares[sh] = shares[sh]
          return True

     def clean_shares(self):
          log.info("clean shares....")
          stp = self._get_stratum_proxy()
          return True

     @pubsub.subscribe
     def subscribe_share(self):
          return ShareSubscription()

     @pubsub.unsubscribe
     def unsubscribe(self, subscription_key):
          return subscription_key
