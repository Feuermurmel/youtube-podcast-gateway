import urllib.request, datetime, socketserver, http.server, shutil, email, subprocess, socket, functools
from . import easy, env, util
import lib.easy.xml


def request_xml(request_url):
	util.log('Requesting {} ...', request_url)
	
	with urllib.request.urlopen(request_url) as file:
		data = file.read()
	
	return easy.xml.parse(data.decode())


class Video:
	class File:
		def __init__(self, gateway, video_id, audio_only):
			self.gateway = gateway
			self.video_id = video_id
			self.audio_only = audio_only
			self._download_url = None
			self._download_url_time = None
		
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
			
			for i in formats:
				proc = subprocess.Popen(['youtube-dl', '-g', '-f', str(i), 'http://www.youtube.com/watch?v={}'.format(self.video_id)], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
				stdout, stderr = proc.communicate()
				
				if proc.returncode:
					message = stderr.decode().strip()
					
					if message.startswith('ERROR: requested format not available'):
						continue
					else:
						raise Exception('Getting the download URL failed: {}'.format(message))
				
				return stdout.decode().strip()
			
			raise Exception('None of the requested formats are available.')
		
		@property
		def download_url(self):
			now = datetime.datetime.now()
			
			if self._download_url is None or now - self._download_url_time > datetime.timedelta(minutes = 10):
				self._download_url = self._get_download_url()
				self._download_url_time = now
			
			return self._download_url
	
	def __init__(self, title, description, author, published, duration, file):
		self.title = title
		self.description = description
		self.author = author
		self.published = published
		self.duration = duration
		self.file = file
	
	def __repr__(self):
		return '<Video title = {}, author = {}>'.format(self.title, self.author)
	
	def make_podcast_entry_elem(self, base_url):
		if self.file.audio_only:
			type = 'audio'
			suffix = 'm4a'
		else:
			type = 'video'
			suffix = 'm4v'
		
		n = lib.easy.xml.node
		encoded_page_url = '{}/{}/{}.{}'.format(base_url, type, self.file.video_id, suffix) # Extension is needed so that iTunes recognizes the enclosure as a media file (or something, it doesn't work otherwise).
		published = email.utils.formatdate((self.published - datetime.datetime(
			1970, 1, 1)) / datetime.timedelta(seconds=1))
		
		return n(
			'item',
			n('title', self.title),
			n('itunes__subtitle', self.description), # Shows in itunes description column
			n('itunes__summary', self.description), # Shows in iTunes information window
			n('description', self.description), # Shown on iPhone
			n('itunes__duration', self.duration),
			n('pubDate', published),
			n('guid', self.file.video_id),
			n('enclosure', url = encoded_page_url))
	
	@classmethod
	def from_feed_entry(cls, file_factory, node):
		assert node.name == 'entry'
		
		author = node.find(name = 'author').find(name = 'name').text()
		published = node.find(name = 'published').text()
		published = datetime.datetime.strptime(published, '%Y-%m-%dT%H:%M:%S.%fZ')
		
		group_node = node.find(name='media:group')
		video_id = group_node.find(name = 'yt:videoid').text()
		
		duration = list(group_node.walk(name = 'yt:duration'))
		
		if duration:
			duration = duration[0].attrs['seconds']
		else:
			duration = ''
		
		def get_metadata(name):
			res = list(group_node.walk(name = name, attrs = { 'type': 'plain' }))
			
			if res:
				return res[0].text()
			else:
				return ''
		
		description = get_metadata('media:description')
		title = get_metadata('media:title')
		
		return cls(title, description, author, published, duration, file_factory(video_id))


class Feed:
	def __init__(self, title, videos, feed_url, thumbnail_url):
		self.title = title
		self.videos = videos
		self.feed_url = feed_url
		self.thumbnail_url = thumbnail_url
	
	def __repr__(self):
		return '<Feed videos = {}>'.format(self.videos)
	
	def make_podcast_feed_elem(self, base_url):
		n = lib.easy.xml.node
		
		def channel_nodes():
			yield n('title', self.title)
			
			if self.thumbnail_url is not None:
				yield n('itunes__image', href = self.thumbnail_url)
			
			for i in self.videos:
				yield i.make_podcast_entry_elem(base_url)
		
		return n(
			'rss',
			n('channel', *channel_nodes()),
			xmlns__itunes = 'http://www.itunes.com/dtds/podcast-1.0.dtd',
			version = '2.0')
	
	@classmethod
	def get_avatar_url(cls, user_url):
		dom = request_xml(user_url)
		nodes = list(dom.walk(name = 'media:thumbnail'))
		
		if nodes:
			node, = nodes
			return node.attrs['url']
		else:
			return None
	
	@classmethod
	def from_feed_url(cls, file_factory, feed_url):
		videos = []
		title = None
		max_results = 50
		avatar_url = ...
		
		while len(videos) < 1000:
			dom = request_xml('{}?v={}&max-results={}&start-index={}'.format(feed_url, 2, max_results, len(videos) + 1))
			
			if title is None:
				title, = (i for i in dom.nodes if i.name == 'title')
				title = title.text()
			
			videos_add = [Video.from_feed_entry(file_factory, i) for i in dom.walk(name = 'entry')]
			
			if not videos_add:
				break
			
			videos.extend(videos_add)
			
			if avatar_url is ...:
				user_url = list(dom.walk(name = 'author'))[0].find(name = 'uri').text()
				
				avatar_url = cls.get_avatar_url(user_url)
		
		return cls(title, videos, feed_url, avatar_url)
	
	@classmethod
	def user_uploads(cls, file_factory, username):
		feed_url = 'http://gdata.youtube.com/feeds/api/users/{}/uploads'.format(username)
		
		return cls.from_feed_url(file_factory, feed_url)
	
	@classmethod
	def playlist(cls, file_factory, playlist_id):
		feed_url = 'http://gdata.youtube.com/feeds/api/playlists/{}'.format(playlist_id)
		
		return cls.from_feed_url(file_factory, feed_url)


class RequestHandler(http.server.SimpleHTTPRequestHandler):
	file_factory = None

	def do_GET(self):
		path, args = self.parse_path(self.path)
		base_url = self.get_base_url()
		
		feed_for_type = { 'uploads': Feed.user_uploads, 'playlist': Feed.playlist }
		
		if path[0] in feed_for_type:
			audio_only = args.get('audio', 'false') == 'true'
			file_factory = functools.partial(self.file_factory.get_file, audio_only = audio_only)
			feed = feed_for_type[path[0]](file_factory, path[1])
			doc = feed.make_podcast_feed_elem(base_url)
			
			self.send_response(200)
			self.send_header('content-type', 'application/atom+xml; charset=utf-8')
			self.end_headers()
			
			self.wfile.write(str(doc).encode())
		elif path[0] == 'audio':
			self.handle_media_request(self.file_factory.get_file(path[1], True))
		elif path[0] == 'video':
			self.handle_media_request(self.file_factory.get_file(path[1], False))
		else:
			self.send_response(404)
			self.end_headers()

	def get_base_url(self):
		host_header = self.headers['Host']
		
		if host_header:
			return 'http://{}'.format(host_header)
		else:
			return 'http://{}:{}'.format(env.local_address_best_guess(), self.server.port)
	
	def handle_media_request(self, file):
		request = urllib.request.Request(file.download_url)
		
		if 'Range' in self.headers:
			util.log('Request for range {} of video with id {}.', self.headers['Range'], file.video_id)
		else:
			util.log('Request for video with id {}.', file.video_id)
		
		for i in ['Range']:
			if i in self.headers:
				request.add_header(i, self.headers[i])
		
		with urllib.request.urlopen(request) as response:
			self.send_response(200)
			
			for i in ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges']:
				if i in response.headers:
					self.send_header(i, response.headers[i])
			
			self.end_headers()
			
			try:
				shutil.copyfileobj(response, self.wfile)
			except socket.error:
				pass # Ignore errors like a closed connection.
	
	@classmethod
	def parse_path(cls, path):
		path, *args = path.split('?', 1)
		path = [i for i in path.split('/') if i]
		path[-1] = path[-1].rsplit('.', 1)[0] # Allow flexibility in URLs by ignoring any file name extensions
		
		if args:
			args, = args
			
			args = dict(i.split('=', 1) for i in args.split('&'))
		
		return path, args


class FileFactory:
	def __init__(self, gateway):
		self.gateway = gateway
		self._files_by_id = { } # map from url as string to File instance
	
	def get_file(self, video_id, audio_only):
		key = video_id, audio_only
		file = self._files_by_id.get(key)
		
		if file is None:
			file = Video.File(self.gateway, video_id, audio_only)
			
			self._files_by_id[key] = file
		
		return file


class Gateway(socketserver.ThreadingMixIn, http.server.HTTPServer):
	def __init__(self, port = 8080):
		self.port = port
		
		class Handler(RequestHandler):
			file_factory = FileFactory(self)
		
		super().__init__(('', port), Handler)
	
	def serve_forever(self):
		util.log('Listening on port {} ...', self.port)
		
		super().serve_forever()
