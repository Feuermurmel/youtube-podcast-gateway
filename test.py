import appscript, urllib.request, time, sys, datetime, base64, http.server
from lib import safari, easy
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


server_address = ('localhost', 8081)
server_url = 'http://%s:%s' % server_address


browser = safari.Browser()


class Video:
	def __init__(self, title, description, author, published, page_url):
		self.title = title
		self.description = description
		self.author = author
		self.published = published
		self.page_url = page_url
	
	def __repr__(self):
		return '<Video title = %r, author = %r>' % (self.title, self.author)
	
	def get_video_url(self):
		with browser.create_document(self.page_url) as doc:
			player_div = doc.dom.find(lambda x: x.attrs.get('class') in ['CTPmediaPlayer', 'CTPplaceholderContainer'], name = 'div')
			
			if player_div.attrs['class'] != 'CTPmediaPlayer':
				raise NoMpegAvailableError()
			
			return doc.dom.find(name = 'video').attrs['src']
	
	def make_podcast_entry_elem(self):
		n = lib.easy.xml.node
		encoded_page_url = '%s/video/%s.m4v' % (server_url, URLEncoder.encode(self.page_url)) # Extension is needed so that iTunes recognizes the enclosure a media file (or something, it doesn't work otherwise).
		
		return n(
			'entry',
			n('title', self.title),
			n('link', rel = 'enclosure', href = encoded_page_url),
			n('id', encoded_page_url),
			n('published', self.published.isoformat() + 'Z'),
			n('content', self.description))
	
	@classmethod
	def from_feed_entry(cls, node):
		assert node.name == 'entry'
		
		author, = node.find(name = 'author').find(name = 'name').text()
		published, = node.find(name = 'published').text()
		published = datetime.datetime.strptime(published, '%Y-%m-%dT%H:%M:%S.%fZ')
		
		group_node = node.find(name='media:group')
		page_url = group_node.find(name = 'media:player').attrs['url']
		description, = group_node.find(name = 'media:description', attrs = { 'type': 'plain' }).text()
		title, = group_node.find(name = 'media:title', attrs = { 'type': 'plain' }).text()
		
		return cls(title, description, author, published, page_url)		


class Feed:
	def __init__(self, title, videos, feed_url):
		self.title = title
		self.videos = videos
		self.feed_url = feed_url
	
	def __repr__(self):
		return '<Feed videos = %s>' % self.videos
	
	def make_podcast_feed_elem(self):
		n = lib.easy.xml.node
		encoded_feed_url = '%s/%s' % (server_url, URLEncoder.encode(self.feed_url))
		
		return n(
			'feed',
			n('id', encoded_feed_url),
			n('title', self.title),
			*[i.make_podcast_entry_elem() for i in self.videos],
			xmlns = 'http://www.w3.org/2005/Atom')
	
	@classmethod
	def from_feed_url(cls, feed_url):
		with urllib.request.urlopen(feed_url) as file:
			data = file.read()
		
		dom = easy.xml.parse(data.decode())
		title, = (i for i in dom.nodes if i.name == 'title')
		title, = title.text()
		
		return cls(title, [Video.from_feed_entry(i) for i in dom.walk(name = 'entry')], feed_url)


# https://developers.google.com/youtube/2.0/developers_guide_protocol_video_feeds#User_Uploaded_Videos

#feed_url = 'https://gdata.youtube.com/feeds/api/users/antvenom/uploads'
#feed = Feed.from_feed_url(feed_url)
#
##print(feed)
##print(feed.videos[0].page_url)
#print(feed.make_podcast_feed_elem())

#print(feed.videos[0].get_video_url())


#safari.Browser().create_document('http://www.youtube.com/watch?v=AmN0YyaTD60&feature=g-all-u')

class RequestHandler(http.server.SimpleHTTPRequestHandler):
	def do_GET(self):
		assert self.path[0] == '/'
		
		path = self.path[1:].split('/')
		path[-1], _ = path[-1].rsplit('.', 1) # Allow flexibility in URLs by ignoring any file name extensions
		
		if path[0] == 'uploads':
			feed_url = 'http://gdata.youtube.com/feeds/api/users/%s/uploads' % path[1]

			doc = Feed.from_feed_url(feed_url).make_podcast_feed_elem()

			self.send_response(200)
			self.send_header('content-type', 'application/atom+xml; charset=utf-8')
			self.end_headers()
	
			self.wfile.write(str(doc).encode())
		elif path[0] == 'video':
			video_page_url = URLEncoder.decode(path[1])
			
			print(video_page_url)
			
			self.send_response(200)
			self.send_header('content-type', 'video/mp4')
			self.end_headers()
			
			with open('rss/Badday.m4v', 'rb') as file:
				self.wfile.write(file.read())
		else:
			self.send_response(404)


http.server.HTTPServer(('', server_address[1]), RequestHandler).serve_forever()

