from twisted.application import service, internet

import sys
#print 'sys.path is ...........', sys.path
sys.path.insert(0, '/home/paul/github/stratum')
sys.path.insert(0, '/home/paul/github/stratum-proxy-ng')
#print 'sys.path is ...........', sys.path

print 'sys.version is ......... ', sys.version

from stratum import settings
from stproxy_ng import StratumServer, StratumControl

stratumService = service.MultiService()

internet.TCPServer(settings.STRATUM_PORT, StratumServer().f, interface=settings.STRATUM_HOST).setServiceParent(stratumService)
internet.TCPServer(settings.CONTROL_PORT, StratumControl().f, interface=settings.CONTROL_HOST).setServiceParent(stratumService)

application = service.Application("Stratum proxy application")

stratumService.setServiceParent(application)
