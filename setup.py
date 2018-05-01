import setuptools


setuptools.setup(
    name='youtube-podcast-gateway',
    version='0.1',
    packages=['youtube_podcast_gateway', 'youtube_podcast_gateway.easy'],
    install_requires=[
        'google-api-python-client',
        'isodate',
        'pytz',
        'youtube_dl'],
    entry_points=dict(
        console_scripts=[
            'youtube-podcast-gateway=youtube_podcast_gateway:entry_point']))
