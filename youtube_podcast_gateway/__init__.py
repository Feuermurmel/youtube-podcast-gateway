import sys

from youtube_podcast_gateway import config, gateway


def entry_point():
    settings = config.Configuration.from_arguments(sys.argv[1:])

    gateway.Gateway(settings).run()
