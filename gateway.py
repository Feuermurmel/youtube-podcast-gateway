import urllib.request, time, sys, datetime, socketserver, http.server, shutil, email, subprocess, socket
from lib import easy, env
import lib.easy.xml


def log(msg, *args):
	if args:
		msg = msg.format(*args)
	
	print(msg, file = sys.stderr)


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
	
	def __init__(self, title, description, author, published, duration, file : File):
		self.title = title
		self.description = description
		self.author = author
		self.published = published
		self.duration = duration
		self.file = file
	
	def __repr__(self):
		return '<Video title = %r, author = %r>' % (self.title, self.author)
	
	def make_podcast_entry_elem(self, gateway):
		n = lib.easy.xml.node
		encoded_page_url = '{}/video/{}.m4v'.format(gateway.server_url, self.file.video_id) # Extension is needed so that iTunes recognizes the enclosure as a media file (or something, it doesn't work otherwise).
		published = email.utils.formatdate((self.published - datetime.datetime(
			1970, 1, 1)) / datetime.timedelta(seconds=1))
		
		return n(
			'item',
			n('title', self.title),
			n('itunes__summary', self.description),
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
		description = group_node.find(name = 'media:description', attrs = { 'type': 'plain' }).text()
		title = group_node.find(name = 'media:title', attrs = { 'type': 'plain' }).text()
		
		return cls(title, description, author, published, file_factory.get_file(video_id))
		if duration:
			duration = duration[0].attrs['seconds']
		else:
			duration = ''
		return cls(title, description, author, published, duration, file_factory.get_file(video_id))


class Feed:
	def __init__(self, title, videos, feed_url):
		self.title = title
		self.videos = videos
		self.feed_url = feed_url
	
	def __repr__(self):
		return '<Feed videos = %s>' % self.videos
	
	def make_podcast_feed_elem(self, gateway):
		n = lib.easy.xml.node
		
		return n(
			'rss',
			n('channel',
				n('title', self.title),
				*[i.make_podcast_entry_elem(gateway) for i in self.videos]),
			xmlns__itunes = 'http://www.itunes.com/dtds/podcast-1.0.dtd',
			version = '2.0')
	
	@classmethod
	def from_feed_url(cls, file_factory, feed_url):
		videos = []
		title = None
		max_results = 50
		
		while len(videos) < 1000:
			request_url = '%s?v=%s&max-results=%s&start-index=%s' % (feed_url, 2, max_results, len(videos) + 1)
			
			log('Requesting {} ...', request_url)
			
			with urllib.request.urlopen(request_url) as file:
				data = file.read()
			
			dom = easy.xml.parse(data.decode())
			
			if title is None:
				title, = (i for i in dom.nodes if i.name == 'title')
				title = title.text()
			
			videos_add = [Video.from_feed_entry(file_factory, i) for i in dom.walk(name = 'entry')]
			
			if not videos_add:
				break
			
			videos.extend(videos_add)
		
		return cls(title, videos, feed_url)


class RequestHandler(http.server.SimpleHTTPRequestHandler):
	file_factory = None
	
	def do_GET(self):
		assert self.path[0] == '/'
		
		if self.headers['host'] != self.server.host_port:
			self.send_response(301)
			self.send_header('location', self.server.server_url + self.path)
			self.end_headers()
		else:
			path = self.path[1:].split('/')
			path[-1] = path[-1].rsplit('.', 1)[0] # Allow flexibility in URLs by ignoring any file name extensions
			
			feed_for_type = { 'uploads': 'users/%s/uploads', 'playlist': 'playlists/%s' }
			
			if path[0] in feed_for_type:
				feed_url = 'http://gdata.youtube.com/feeds/api/%s' % (feed_for_type[path[0]] % path[1])
				doc = Feed.from_feed_url(self.file_factory, feed_url).make_podcast_feed_elem(self.server)
				
				self.send_response(200)
				self.send_header('content-type', 'application/atom+xml; charset=utf-8')
				self.end_headers()
				
				self.wfile.write(str(doc).encode())
			elif path[0] == 'video':
				file = self.file_factory.get_file(path[1])
				download_url = file.download_url
				request = urllib.request.Request(download_url)
				
				if 'Range' in self.headers:
					log('Request for range {} of video with id {}.', self.headers['Range'], file.video_id)
				else:
					log('Request for video with id {}.', file.video_id)
				
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
	def __init__(self, port = 8080, server_address = None):
		if server_address is None:
			server_address = env.local_address_best_guess()
		
		self.host_port = '%s:%s' % (server_address, 8080)
		self.server_url = 'http://%s' % self.host_port
		
		class RequestHandler_(RequestHandler):
			file_factory = FileFactory(self)
		
		super().__init__(('', port), RequestHandler_)
	
	def serve_forever(self):
		log('Listening on {} ...', self.host_port)
		
		super().serve_forever()
