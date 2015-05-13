import sys
from lib import config, gateway


def main():
	configuration = config.Configuration.from_arguments(sys.argv[1:])
	
	gateway.Gateway(configuration).run()


main()
