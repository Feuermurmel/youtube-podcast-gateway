import urllib.request, datetime, socketserver, http.server, shutil, email, subprocess, socket, pytz, sys, isodate, threading
from . import env, util, youtube, config
import lib.easy.xml


_http_listen_address_key = config.Key('http_listen_address', str, '')
_http_listen_port_key = config.Key('http_listen_port', int, 8080)
_max_episode_count_key = config.Key('max_episode_count', int)


class Configuration:
	def __init__(self, max_episode_count, http_listen_address, http_listen_port):
		self.max_episode_count = max_episode_count
		self.http_listen_address = http_listen_address


class _File:
	def __init__(self, gateway, video_id, audio_only):
		self.gateway = gateway
		self.video_id = video_id
		self.audio_only = audio_only
		self._download_url = None
		self._download_url_time = None
	
	def __repr__(self, *args, **kwargs):
		return 'File(video_id = {}, audio_only = {})'.format(self.video_id, self.audio_only)
	
	def _get_download_url(self):
		# 248         webm      1080p       DASH webm 
		# 247         webm      720p        DASH webm 
		# 244         webm      480p        DASH webm 
		# 243         webm      360p        DASH webm 
		# 242         webm      240p        DASH webm 
		# 171         webm      audio only  DASH webm audio , audio@ 48k (worst)
		# 160         mp4       192p        DASH video 
		# 140         m4a       audio only  DASH audio , audio@128k
		# 137         mp4       1080p       DASH video 
		# 136         mp4       720p        DASH video 
		# 135         mp4       480p        DASH video 
		# 134         mp4       360p        DASH video 
		# 133         mp4       240p        DASH video 
		# 43          webm      640x360     
		# 36          3gp       320x240     
		# 22          mp4       1280x720    (best)
		# 18          mp4       640x360     
		# 17          3gp       176x144     
		# 5           flv       400x240     
		
		formats = [140, 171] if self.audio_only else [22, 18, 17]
		
		util.log('Getting URL for video {} ...', self.video_id)
		
		for i in formats:
			url = self._get_url_for_format(i)
			
			if url is not None:
				return url
		
		raise Exception('None of the requested formats are available.')
	
	def _get_url_for_format(self, format):
		process = subprocess.Popen(['youtube-dl', '-g', '-f', str(format), 'http://www.youtube.com/watch?v={}'.format(self.video_id)], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
		stdout, stderr = process.communicate()
		
		if process.returncode:
			message = stderr.decode().strip()
			
			if message.startswith('ERROR: requested format not available'):
				return None
			else:
				raise Exception(
					'Getting the download URL failed: {}'.format(message))
		else:
			return stdout.decode().strip()
	
	@property
	def download_url(self):
		now = datetime.datetime.now()
		
		if self._download_url is None or now - self._download_url_time > datetime.timedelta(minutes = 10):
			self._download_url = self._get_download_url()
			self._download_url_time = now
		
		return self._download_url


class _FileFactory:
	def __init__(self, gateway):
		self._gateway = gateway
		self._files_by_id = { } # map from url as string to File instance
	
	def get_file(self, video_id, audio_only):
		key = video_id, audio_only
		file = self._files_by_id.get(key)
		
		if file is None:
			file = _File(self._gateway, video_id, audio_only)
			
			self._files_by_id[key] = file
		
		return file


class _Video:
	def __init__(self, title, description, author, published, duration, file):
		self.title = title
		self.description = description
		self.author = author
		self.published = published
		self.duration = duration
		self.file = file
	
	def __repr__(self):
		return 'Video(title = {}, author = {})'.format(self.title, self.author)
	
	def make_podcast_entry_elem(self, base_url):
		if self.file.audio_only:
			type_fragment = 'audio'
			suffix = 'm4a'
			mime_type = 'audio/mp4'
		else:
			type_fragment = 'video'
			suffix = 'm4v'
			mime_type = 'video/mp4'
		
		n = lib.easy.xml.node
		encoded_page_url = '{}/{}/{}.{}'.format(base_url, type_fragment, self.file.video_id, suffix) # Extension is needed so that iTunes recognizes the enclosure as a media file (or something, it doesn't work otherwise).
		published = email.utils.formatdate((self.published - datetime.datetime(1970, 1, 1, tzinfo = pytz.utc)) / datetime.timedelta(seconds = 1))
		
		return n(
			'item',
			n('title', self.title),
			n('itunes__subtitle', self.description), # Shows in itunes description column
			n('itunes__summary', self.description), # Shows in iTunes information window
			n('description', self.description), # Shown on iPhone
			n('itunes__duration', str(self.duration)),
			n('pubDate', published),
			n('guid', self.file.video_id),
			n('enclosure', url = encoded_page_url, type = mime_type))


class _Feed:
	def __init__(self, title, description, videos, thumbnail_url):
		self.title = title
		self.description = description
		self.videos = videos
		self.thumbnail_url = thumbnail_url
	
	def __repr__(self):
		return 'Feed(videos = {})'.format(self.videos)
	
	def make_podcast_feed_elem(self, base_url):
		n = lib.easy.xml.node
		
		def channel_nodes():
			yield n('title', self.title)
			yield n('description', self.description)
			
			if self.thumbnail_url is not None:
				yield n('image', n('url', self.thumbnail_url))
			
			for i in self.videos:
				yield i.make_podcast_entry_elem(base_url)
		
		return n(
			'rss',
			n('channel', *list(channel_nodes())),
			xmlns__itunes = 'http://www.itunes.com/dtds/podcast-1.0.dtd',
			version = '2.0')


class Gateway:
	def __init__(self, settings : config.Configuration):
		self.max_episode_count = settings.get(_max_episode_count_key)
		self.service = youtube.YouTube.get_authenticated_instance()
		self.file_factory = _FileFactory(self)
		self._request_counter = 0
		self._request_counter_lock = threading.Lock()
		
		# noinspection PyMethodParameters
		class Handler(_RequestHandler):
			def __init__(handler_self, *args):
				super().__init__(self, *args)
		
		class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
			pass
		
		listen_address = settings.get(_http_listen_address_key)
		listen_port = settings.get(_http_listen_port_key)
		
		self.server = _Server((listen_address, listen_port), Handler)
	
	def get_next_request_id(self):
		with self._request_counter_lock:
			value = self._request_counter + 1
			self._request_counter = value
		
		return value
	
	def run(self):
		util.log('Starting server on port {} ...', self.server.server_port)
		
		self.server.serve_forever()


class _RequestHandler(http.server.SimpleHTTPRequestHandler):
	def __init__(self, gateway : Gateway, *args):
		self._gateway = gateway
		self._request_id = gateway.get_next_request_id()
		
		# WTF?! The handler method is called form inside __init__()!
		super().__init__(*args)
	
	def do_GET(self):
		self.log('Handling request for {} ...', self.path)
		
		try:
			path, args = self._parse_path(self.path)
			
			if path:
				type, *rest = path
				
				if type == 'audio':
					self._handle_media_request(self._gateway.file_factory.get_file(rest[0], True))
				elif type == 'video':
					self._handle_media_request(self._gateway.file_factory.get_file(rest[0], False))
				else:
					audio_only = args.get('audio') == 'true'
					
					self._handle_feed_request(type, rest[0], audio_only)
			else:
				self._send_headers(404)
		except socket.error as e:
			self.log('Connection was closed: {}', e)
		except Exception:
			sys.excepthook(*sys.exc_info())
	
	def log_message(self, format, *args):
		pass
	
	def log(self, message, *args):
		util.log('[{}]: {}', self._request_id, message.format(*args))
	
	def _send_headers(self, code, headers = { }):
		self.send_response(code)
		
		for k, v in headers.items():
			self.send_header(k, v)
		
		self.end_headers()
		
		self.log('Returned status {}.', code)
	
	def _get_base_url(self):
		host_header = self.headers['Host']
		
		if host_header:
			return 'http://{}'.format(host_header)
		else:
			return 'http://{}:{}'.format(env.local_address_best_guess(), self._gateway.server.server_port)
	
	def _handle_feed_request(self, type, id, audio_only):
		feeds_by_type = {
			'uploads': self._create_uploads_feed,
			'playlist': self._create_playlist_feed }
		
		feed_type = feeds_by_type.get(type)
		
		if feed_type is None:
			self._send_headers(404)
		else:
			base_url = self._get_base_url()
			feed = feed_type(id, audio_only)
			doc = feed.make_podcast_feed_elem(base_url)
			
			self._send_headers(200, { 'content-type': 'application/atom+xml; charset=utf-8' })
			
			self.wfile.write(str(doc).encode())
	
	def _handle_media_request(self, file : _File):
		range_header = self.headers.get('Range')
		
		if range_header is not None:
			self.log('Request for video {}.', file.video_id)
		else:
			self.log('Request for range {} of video {}.', range_header, file.video_id)
		
		request = urllib.request.Request(file.download_url)
		
		if range_header is not None:
			request.add_header('Range', range_header)
		
		with urllib.request.urlopen(request) as response:
			header_names = ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges']
			headers = { k: response.headers[k] for k in header_names }
			
			self._send_headers(200, headers)
			shutil.copyfileobj(response, self.wfile)
	
	def _create_uploads_feed(self, channel_id, audio_only):
		channel = self._gateway.service.get_channel_by_id_or_username(channel_id, 'snippet')
		title = 'Uploads by {}'.format(channel.snippet.title)
		description = channel.snippet.description
		thumbnail_url = self.find_best_thumbnail_url(channel.snippet.thumbnails)
		uploads = self._gateway.service.get_channel_videos(channel.id, 'id', max_results = self._gateway.max_episode_count)
		video_ids = [i.id.videoId for i in uploads]
		videos = self._gateway.service.get_videos(video_ids, ['contentDetails', 'snippet'])
		elements = [self._create_video(i, audio_only) for i in videos]
		
		return _Feed(title, description, elements, thumbnail_url)
	
	def _create_playlist_feed(self, playlist_id, audio_only):
		playlist = self._gateway.service.get_playlists(playlist_id, 'snippet')
		title = playlist.snippet.title
		description = playlist.snippet.description
		channel = self._gateway.service.get_channels(playlist.snippet.channelId, 'snippet')
		thumbnail_url = self.find_best_thumbnail_url(channel.snippet.thumbnails)
		playlist_items = self._gateway.service.get_playlist_items(playlist_id, 'snippet')
		playlist_items_by_video_id = { i.snippet.resourceId.videoId: i for i in playlist_items if i.snippet.resourceId.kind == 'youtube#video' }
		video_ids = list(playlist_items_by_video_id)
		
		# We need to truncate the list here because we have to get the full list of video IDs because we want to return the videos most recently added to the playlist.
		if self._gateway.max_episode_count is not None:
			del video_ids[:-self._gateway.max_episode_count]
		
		videos = self._gateway.service.get_videos(video_ids, ['contentDetails', 'snippet'])
		elements = [self._create_video(i, audio_only, isodate.parse_datetime(playlist_items_by_video_id[i.id].snippet.publishedAt)) for i in videos]
		
		return _Feed(title, description, elements, thumbnail_url)
	
	def _create_video(self, video, audio_only, date = None):
		if date is None:
			date = isodate.parse_datetime(video.snippet.publishedAt)
		
		title = video.snippet.title
		description = video.snippet.description
		author = video.snippet.channelTitle
		duration = isodate.parse_duration(video.contentDetails.duration)
		file = self._gateway.file_factory.get_file(video.id, audio_only)
		
		return _Video(title, description, author, date, duration, file)
	
	@classmethod
	def _parse_path(cls, path):
		path, *args = path.split('?', 1)
		path = [i for i in path.split('/') if i]
		path[-1] = path[-1].rsplit('.', 1)[0] # Allow flexibility in URLs by ignoring any file name extensions
		
		if args:
			args, = args
			args = dict(i.split('=', 1) for i in args.split('&'))
		else:
			args = { }
		
		return path, args
	
	@classmethod
	def find_best_thumbnail_url(cls, thumbnails):
		for i in 'standard', 'high', 'medium', 'default':
			thumbnail_item = getattr(thumbnails, i, None)
			
			if thumbnail_item is not None:
				return thumbnail_item.url
		
		return None
