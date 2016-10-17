# YouTube Podcast Gateway

Transforms a YouTube playlist or a user's uploads into a Podcast.


## Description

This Python application can be used to subscribe to a YouTube channel or a playlist using a podcast client.


## Requirements

You will need the following, if you want to use this application:

- Python >= 3.2
- A Google account
- A podcast client


## Setup

After checking out the `master` branch of this repository, the application can be run directly. There is no installation necessary [0]. Instead, all dependencies are installed into a Python virtualenv and the application is run using the virtualenv's `python` binary.

[0]: Installation using a `setup.py` script could probably be added easily.


### Setting up the virtualenv

To set up the virtualenv, run `./setup-venv.sh`:

```
$ ./setup-venv.sh 
Running virtualenv with interpreter /opt/local/bin/python3.4
Using base prefix '/opt/local/Library/Frameworks/Python.framework/Versions/3.4'
New python executable in venv/bin/python3.4
Also creating executable in venv/bin/python
Installing setuptools, pip...done.
[...]
Successfully installed google-api-python-client isodate pytz youtube-dl httplib2 oauth2client six uritemplate pyasn1 pyasn1-modules rsa simplejson
Cleaning up...
```

There are normally some warnings of the form `warning: no files found matching`, you can safely ignore them. If the last two lines look like the example above, the setup was successful.


### Creating a YouTube API key and access token.

Next, you will need to create a `client_secrets.json` file containing your API key, which is used to access the YouTube API. You will need a Google account for this.

Go to the (Google Developer Console)[https://console.developers.google.com] and create a new project. Under **APIs & Auth** > **APIs**, enable the **YouTube Data API v3** for the new project. Then, under **APIs & Auth** > **Consent screen**, choose an **Email address** [1] and set a **Product name** [2].

Then, go to **APIs & Auth** > **Credentials** and create an OAuth 2.0 Client ID. For the **Application type**, choose **Installed application** and for **Installed application type**, choose **Other**. After creating the key, click **Download JSON**. This will download a JSON file. Rename the file to `client_secrets.json` and put it in the root directory of the application.

Now you can run the application for the first time using `./run.sh`. It should ask you to visit an web site.

```
$ ./run.sh 
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

`<channel-id>` is either the use name of the cannel's owner or the channel ID. YouTube currently uses both to refer to channels, depending on context. For example:

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

Here, `PLbQ-gSLYQEc4Ah-5yF3IH29er13oJs_Xy` is the ID of a playlist. `WL` is the ID of *your* watch later playlist, if you want to subscribe to it.


## Configuration

Some settings can be configured by creating a file `settings.sh` in the root directory of the application. This is an example configuration file showing the settings that can be adjusted:

```sh
# Host name or IP address to listen on. Defaults to listening all interfaces.
http_listen_address=0.0.0.0

# Local port to listen on. Defaults to 8080.
http_listen_port=8080

# Maximum number of episodes to fetch for a single feed. Defaults to no limit.
max_episode_count=20
```

The settings file is actually just a shell script sourced from a `bash` session. The variables can be set in any way supported by bash and the values can e.g. computed dynamically.
