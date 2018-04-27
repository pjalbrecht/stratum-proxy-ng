from twisted.application import service, internet

from stratum import settings
from stproxy_ng import StratumServer, StratumControl

stratumService = service.MultiService()

internet.TCPServer(settings.STRATUM_PORT, StratumServer().f, interface=settings.STRATUM_HOST).setServiceParent(stratumService)
internet.TCPServer(settings.CONTROL_PORT, StratumControl().f, interface=settings.CONTROL_HOST).setServiceParent(stratumService)

application = service.Application("Stratum proxy application")

stratumService.setServiceParent(application)
