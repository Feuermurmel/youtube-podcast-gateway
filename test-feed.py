import urllib.request
from lib import easy
import lib.easy.xml


with urllib.request.urlopen('https://gdata.youtube.com/feeds/api/users/antvenom/uploads') as file:
	data = file.read()

dom = easy.xml.parse(data.decode())

for i in dom.walk(name = 'entry'):
	for j in i.walk(name = 'link', attrs = { 'rel': 'alternate', 'type': 'text/html' }):
		print(j.attributes['href'])
