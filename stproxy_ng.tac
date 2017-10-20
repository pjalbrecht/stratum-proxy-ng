from twisted.application import service, internet

from stratum import settings
from stproxy_ng import StratumServer

def getStratumService():
     return internet.TCPServer(settings.STRATUM_PORT, StratumServer().f)

application = service.Application("Stratum proxy application")

service = getStratumService()
service.setServiceParent(application)
