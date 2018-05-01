import argparse

from youtube_podcast_gateway import config, gateway


def option_type(value_str):
    key, value = value_str.split('=', 1)

    return key, value


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o',
        '--option',
        dest='options',
        action='append',
        type=option_type,
        help='Modify default settings. See readme.md for a list of available '
             'settings.')

    return parser.parse_args()


def main(options):
    gateway.Gateway(config.Configuration(dict(options))).run()


def entry_point():
    main(**vars(parse_args()))
