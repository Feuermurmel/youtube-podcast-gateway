import appscript, urllib.request, time, sys, datetime, base64, socketserver, http.server, shutil, urllib.request, email
from lib import safari, easy, env
import lib.easy.xml


class NoMpegAvailableError(Exception):
	pass


class URLEncoder:
	_altchars = b'_-'
	
	@classmethod
	def encode(cls, data):
		return base64.b64encode(data.encode(), cls._altchars).decode()
	
	@classmethod
	def decode(cls, data):
		return base64.b64decode(data.encode(), cls._altchars, True).decode()


class Downloader:
	def __init__(self, browser, feed_url):
		self._browser = browser
		self._feed_url = feed_url
	
	def get_video_page_urls(self):
		def fn():
			with urllib.request.urlopen(self._feed_url) as file:
				data = file.read()
				
				dom = easy.xml.parse(data.decode())
				
				for i in dom.walk(name = 'entry'):
					for j in i.walk(name = 'link', attrs = { 'rel': 'alternate', 'type': 'text/html' }):
						yield j.attrs['href']
		
		return list(fn())
	
	def get_video_url(self, page_url):
		timeout = 0
		
		for i in range(10):
			try:
				with self._browser.create_document(page_url) as doc:
					player_div = doc.dom.find(lambda x: x.attrs.get('class') in ['CTPmediaPlayer', 'CTPplaceholderContainer'], name = 'div')
					
					if player_div.attrs['class'] != 'CTPmediaPlayer':
						raise NoMpegAvailableError()
					
					return doc.dom.find(name = 'video').attrs['src']
			except appscript.reference.CommandError:
				timeout += 2
				
				print('Safari crashed, retrying in %s seconds ...' % timeout, file = sys.stderr)
				
				time.sleep(timeout)
			except ( ):
				print('Page not loaded correctly, retrying ...', file = sys.stderr)
		else:
			raise RuntimeError('Too much fail!')


class Video:
	class File:
		def __init__(self, gateway, page_url):
			self.gateway = gateway
			self.page_url = page_url
			self._download_url = None
			self._download_url_time = None
		
		def _get_download_url(self):
			last_exception = None
			
			# Try five times if BridgeException is raised, if it still failse, re-raise the last exception.
			for i in range(5):
				try:
					with self.gateway.browser.create_document(self.page_url) as doc:
						player_div = doc.dom.find(lambda x: x.attrs.get('class') in ['CTPmediaPlayer', 'CTPplaceholderContainer'], name = 'div')
						
						if player_div.attrs['class'] != 'CTPmediaPlayer':
							raise NoMpegAvailableError()
						
						return doc.dom.find(name = 'video').attrs['src']
				except safari.BridgeException as e:
					last_exception = e
			
			raise last_exception
		
		@property
		def download_url(self):
			now = datetime.datetime.now()
			
			if self._download_url is None or now - self._download_url_time > datetime.timedelta(minutes = 10):
				self._download_url = self._get_download_url()
				self._download_url_time = now
			
			return self._download_url
	
	def __init__(self, title, description, author, published, file : File):
		self.title = title
		self.description = description
		self.author = author
		self.published = published
		self.file = file
	
	def __repr__(self):
		return '<Video title = %r, author = %r>' % (self.title, self.author)
	
	def make_podcast_entry_elem(self, gateway):
		n = lib.easy.xml.node
		encoded_page_url = '%s/video/%s.m4v' % (gateway.server_url, URLEncoder.encode(self.file.page_url)) # Extension is needed so that iTunes recognizes the enclosure as a media file (or something, it doesn't work otherwise).
		published = email.utils.formatdate((self.published - datetime.datetime(
			1970, 1, 1)) / datetime.timedelta(seconds=1))
		
		return n(
			'item',
			n('title', self.title),
			n('itunes__summary', self.description),
			n('pubDate', published),
			n('guid', self.file.page_url),
			n('enclosure', url = encoded_page_url))
	
	@classmethod
	def from_feed_entry(cls, file_factory, node):
		assert node.name == 'entry'
		
		author = node.find(name = 'author').find(name = 'name').text()
		published = node.find(name = 'published').text()
		published = datetime.datetime.strptime(published, '%Y-%m-%dT%H:%M:%S.%fZ')
		
		group_node = node.find(name='media:group')
		page_url = group_node.find(name = 'media:player').attrs['url']
		description = group_node.find(name = 'media:description', attrs = { 'type': 'plain' }).text()
		title = group_node.find(name = 'media:title', attrs = { 'type': 'plain' }).text()
		
		return cls(title, description, author, published, file_factory.get_file(page_url))


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
			
			print('Requesting %s ...' % request_url)
			
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
		
		print('GET', self.path)
		print(self.headers)
		
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
				file = self.file_factory.get_file(URLEncoder.decode(path[1]))
				download_url = file.download_url
				
				with urllib.request.urlopen(download_url) as request:
					self.send_response(200)
					self.send_header('content-type', request.headers.get('content-type'))
					self.send_header('content-length', request.headers.get('content-length'))
					self.end_headers()
					
					shutil.copyfileobj(request, self.wfile)
			else:
				self.send_response(404)
				self.end_headers()


class FileFactory:
	def __init__(self, gateway):
		self.gateway = gateway
		self._files_by_url = { } # map from url as string to File instance
	
	def get_file(self, page_url):
		file = self._files_by_url.get(page_url)
		
		if file is None:
			file = Video.File(self.gateway, page_url)
			
			self._files_by_url[page_url] = file
		
		return file


class Gateway(socketserver.ThreadingMixIn, http.server.HTTPServer):
	def __init__(self, port = 8080, server_address = None):
		if server_address is None:
			server_address = env.local_address_best_guess()
		
		self.host_port = '%s:%s' % (server_address, 8080)
		self.server_url = 'http://%s' % self.host_port
		self.browser = safari.Browser()
		
		class RequestHandler_(RequestHandler):
			file_factory = FileFactory(self)
		
		super().__init__(('', port), RequestHandler_)
	
	def serve_forever(self):
		print('Listening on {} ...'.format(self.host_port))
		
		super().serve_forever()
