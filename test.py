import subprocess, appscript, urllib.request, time, sys, datetime
from lib import safari, easy
import lib.easy.xml


class NoMpegAvailableError(Exception):
	pass


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


browser = safari.Browser()


class Video:
	def __init__(self, title, description, author, updated, page_url):
		self.title = title
		self.description = description
		self.author = author
		self.updated = updated
		self.page_url = page_url
	
	def __repr__(self):
		return '<Video title = %r, author = %r>' % (self.title, self.author)
	
	def get_video_url(self):
		with browser.create_document(self.page_url) as doc:
			player_div = doc.dom.find(lambda x: x.attrs.get('class') in ['CTPmediaPlayer', 'CTPplaceholderContainer'], name = 'div')
			
			if player_div.attrs['class'] != 'CTPmediaPlayer':
				raise NoMpegAvailableError()

			return doc.dom.find(name = 'video').attrs['src']
	
	@classmethod
	def from_feed_entry(cls, node):
		assert node.name == 'entry'
		
		author, = node.find(name = 'author').find(name = 'name').text()
		updated, = node.find(name = 'updated').text()
		updated = datetime.datetime.strptime(updated, '%Y-%m-%dT%H:%M:%S.%fZ')
		
		group_node = node.find(name='media:group')
		page_url = group_node.find(name = 'media:content', attrs = { 'type': 'application/x-shockwave-flash' }).attrs['url']
		description, = group_node.find(name = 'media:description', attrs = { 'type': 'plain' }).text()
		title, = group_node.find(name = 'media:title', attrs = { 'type': 'plain' }).text()
		
		return cls(title, description, author, updated, page_url)		


class Feed:
	def __init__(self, videos):
		self.videos = videos
	
	def __repr__(self):
		return '<Feed videos = %s>' % self.videos
	
	@classmethod
	def from_feed_url(cls, feed_url):
		with urllib.request.urlopen(feed_url) as file:
			data = file.read()
		
		dom = easy.xml.parse(data.decode())
		
		return cls([Video.from_feed_entry(i) for i in dom.walk(name = 'entry')])




# https://developers.google.com/youtube/2.0/developers_guide_protocol_video_feeds#User_Uploaded_Videos

feed_url = 'https://gdata.youtube.com/feeds/api/users/antvenom/uploads'
feed = Feed.from_feed_url(feed_url)

print(feed)
print(feed.videos[0].get_video_url())


#safari.Browser().create_document('http://www.youtube.com/watch?v=AmN0YyaTD60&feature=g-all-u')