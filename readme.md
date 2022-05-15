# YouTube Podcast Gateway

| :exclamation: This project is not maintained anymore. I haven't been using it myself since 2018 and thus can't test issues or fixes myself. If you want to take over the project, I'll gladly transfer it to you. Hit me up by email! |
|-|

Transforms a YouTube playlist or a user's uploads into a Podcast.


## Description

This Python application can be used to subscribe to a YouTube channel or a playlist using a podcast client.


## Requirements

You will need the following, if you want to use this application:

- Python >= 3.2
- A Google account
- A podcast client


## Setup

To use the application, you will have to install it using `pip` either into a virtualenv or globally. The instructions below are for installing into a virtualenv.


### Setting up the virtualenv

To set up a virtualenv with the necessary requirements, run th following commands:

    $ python3 -m venv venv
    $ . venv/bin/activate
    $ pip install git+https://github.com/Feuermurmel/youtube-podcast-gateway.git
    [...]
    Successfully installed google-api-python-client-1.6.4 httplib2-0.10.3 isodate-0.5.4 oauth2client-4.1.2 pyasn1-0.3.6 pyasn1-modules-0.1.4 pytz-2017.2 rsa-3.4.2 six-1.11.0 uritemplate-3.0.0 youtube-dl-2017.9.24 youtube-podcast-gateway-0.1

If the last two lines look like the example above, the setup was successful.


### Creating a YouTube API key and access token.

Next, you will need to create a `client_secrets.json` file containing your API key, which is used to access the YouTube API. You will need a Google account for this.

Go to the (Google Developer Console)[https://console.developers.google.com] and create a new project. Under **APIs & Auth** > **APIs**, enable the **YouTube Data API v3** for the new project. Then, under **APIs & Auth** > **Consent screen**, choose an **Email address** [1] and set a **Product name** [2].

Then, go to **APIs & Auth** > **Credentials** and create an OAuth 2.0 Client ID. For the **Application type**, choose **Installed application** and for **Installed application type**, choose **Other**. After creating the key, click **Download JSON**. This will download a JSON file. Rename the file to `client_secrets.json` and put it in the root directory of the application.

Now you can run the application for the first time using `youtube-podcast-gateway`. It should ask you to visit an web site.

```
$ youtube-podcast-gateway
Go to the following link in your browser:

    https://accounts.google.com/[...]

Enter verification code: 
```

Navigate to the displayed URL. It should give you the option to log in and ask you whether you want to allow the application read access to your youtube account. You will need allow this [3]. You can of course use the same Google account for logging into the Developer Console as well as YouTube.

After accepting, the page will give you the verification code as string, which you can paste back into the console where the URL was displayed. Then it should say that authentication was successful and the the HTTP server is started:

```
Enter verification code: [...]
Authentication successful.
Starting server on port 8080 ...
```

From now on, the application will use the saved access token when it is started.

[1]: God knows why …

[2]: The name of the project as well as the product name are not important, you will only see the product name when authorizing the application to access your account.

[3]: The main benefit is that this way, you can subscribe to private playlists you created [4].

[4]: Or e.g. the "Watch Later" playlist, which also private.


## Subscribing to Channels and playlists

To subscribe to a YouTube channel or playlist, URLs of the following form have to be assembled:

- `http://localhost:8080/uploads/<channel-id>`
- `http://localhost:8080/playlist/<playlist-id>`

In both cases, the assembled URI (possibly with `localhost` replaced by the host name of your server) can be used in a podcast client to subscribe to the channel or playlist [5].

[5]: I've successfully tested **iTunes**, Apple's **Podcasts** app for iOS and **Downcast** for iOS. Please open an issue if you have trouble with your podcast client.


### Subscribing to a channel

`<channel-id>` is either the use name of the channel's owner or the channel ID. YouTube currently uses both to refer to channels, depending on context. For example:

```
https://www.youtube.com/channel/UCOGeU-1Fig3rrDjhm9Zs_wg
https://www.youtube.com/user/CGPGrey
```

Here, `UCOGeU-1Fig3rrDjhm9Zs_wg` is the channel ID of a channel and `CGPGrey` is the username of another channel. Either can be used in place of `<channel-id>`


### Subscribing to a playlist

<playlist-id> is the ID of the playlist to subscribe to. For example:

```
https://www.youtube.com/playlist?list=PLbQ-gSLYQEc4Ah-5yF3IH29er13oJs_Xy
```

Here, `PLbQ-gSLYQEc4Ah-5yF3IH29er13oJs_Xy` is the ID of a playlist.


## Configuration

Some settings can be configured using the `-o` command line option. For example:

```
$ youtube-podcast-gateway -o max_episode_count=100
```

This is a list of available settings:

__http_listen_address__: Host name or IP address to listen on. Defaults to listening all interfaces. Defaults to `0.0.0.0`.

__http_listen_port__: Local port to listen on. Defaults to `8080`.

__max_episode_count__: Maximum number of episodes to fetch for a single feed. Defaults to no limit.

__client_secrets_path__: Path to the `client_secrets.json` file downloaded from the Google Developer Console. Defaults to `client_secrets.json`.

__oauth2_token_path__: Path to the `oauth2_token.json` file which stores the OAuth 2 authorization tokes. Defaults to `oauth2_token.json`. 

__canonical_base_url__: Base URL of the application which is used to generate URLs to the media files embedded in the feeds. This URL should point to the `/` path of the HTTP server run by the application. By default the base URI is guessed from the `Host:` header sent by a client and the port the HTTP server is listening on.
