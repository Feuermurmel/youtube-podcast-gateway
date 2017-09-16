import os
import socket

from youtube_podcast_gateway import util


@util.memorized
def local_address_for_sending_to(host):
    """
    Return an address of a local network socket that can be used to send data
    to the specified host an on which the remote host can send data to the
    local host.
    """

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        # Uses Discard Protocol port, but doesn't actually send any data
        s.connect((host, 9))

        return s.getsockname()[0]


def local_address_best_guess():
    """
    Return the local address of a random network interface (usually the first
    one) or, if configured, the network.local-address key in the default
    configuration.
    """

    return local_address_for_sending_to('1.0.0.0')


def get_script_dir():
    import __main__

    return os.path.dirname(__main__.__file__)
