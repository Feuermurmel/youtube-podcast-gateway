import sys
from lib import config, gateway


def main():
	settings = config.Configuration.from_arguments(sys.argv[1:])
	
	gateway.Gateway(settings).run()


main()
