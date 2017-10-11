from twisted.application import service, internet

from stratum import settings
from stproxy_ng import StratumServer
from mining_libs import stratum_listener
from mining_libs import stratum_control

def getStratumService():
     ss = StratumServer(stratum_listener, stratum_control) 
     return internet.TCPServer(settings.STRATUM_PORT, ss.stf)

application = service.Application("Stratum proxy application")

service = getStratumService()
service.setServiceParent(application)
