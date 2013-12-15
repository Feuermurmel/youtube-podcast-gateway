import urllib.request, datetime, socketserver, http.server, shutil, email, subprocess, socket
from . import easy, env, util
import lib.easy.xml


def request_xml(request_url):
	util.log('Requesting {} ...', request_url)
	
	with urllib.request.urlopen(request_url) as file:
		data = file.read()
	
	return easy.xml.parse(data.decode())


class Video:
	class File:
		def __init__(self, gateway, video_id):
			self.gateway = gateway
			self.video_id = video_id
			self._download_url = None
			self._download_url_time = None
		
		def _get_download_url(self):
			formats = [
			#	37, #	:	mp4	[1080x1920]
			#	46, #	:	webm	[1080x1920]
				22, #	:	mp4	[720x1280]
			#	45, #	:	webm	[720x1280]
			#	35, #	:	flv	[480x854]
			#	44, #	:	webm	[480x854]
			#	34, #	:	flv	[360x640]
				18, #	:	mp4	[360x640]
			#	43, #	:	webm	[360x640]
			#	5 , #	:	flv	[240x400]
				17, #	:	mp4	[144x176]
			]
			
			
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
		n = lib.easy.xml.node
		encoded_page_url = '{}/video/{}.m4v'.format(base_url, self.file.video_id) # Extension is needed so that iTunes recognizes the enclosure as a media file (or something, it doesn't work otherwise).
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
		
		return cls(title, description, author, published, duration, file_factory.get_file(video_id))


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
		path = [i for i in self.path.split('/') if i]
		path[-1] = path[-1].rsplit('.', 1)[0] # Allow flexibility in URLs by ignoring any file name extensions
		base_url = self.get_base_url()
		
		feed_for_type = { 'uploads': Feed.user_uploads, 'playlist': Feed.playlist }
		
		if path[0] in feed_for_type:
			doc = feed_for_type[path[0]](self.file_factory, path[1]).make_podcast_feed_elem(base_url)
			
			self.send_response(200)
			self.send_header('content-type', 'application/atom+xml; charset=utf-8')
			self.end_headers()
			
			self.wfile.write(str(doc).encode())
		elif path[0] == 'video':
			file = self.file_factory.get_file(path[1])
			download_url = file.download_url
			request = urllib.request.Request(download_url)
			
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
		else:
			self.send_response(404)
			self.end_headers()

	def get_base_url(self):
		host_header = self.headers['Host']
		
		if host_header:
			return 'http://{}'.format(host_header)
		else:
			return 'http://{}:{}'.format(env.local_address_best_guess(), self.server.port)


class FileFactory:
	def __init__(self, gateway):
		self.gateway = gateway
		self._files_by_id = { } # map from url as string to File instance
	
	def get_file(self, video_id):
		file = self._files_by_id.get(video_id)
		
		if file is None:
			file = Video.File(self.gateway, video_id)
			
			self._files_by_id[video_id] = file
		
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
