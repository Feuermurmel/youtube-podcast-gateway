import os, json, weakref, appscript, time
from lib import util, easy
import lib.easy.xml


# Raised when interaction with the dombridge failed
class BridgeException(Exception): pass


class ClosingContextManager():
	def __enter__(self):
		return self

	#noinspection PyUnusedLocal
	def __exit__(self, exc_type, exc_val, exc_tb):
		self.close()
	
	def close(self):
		assert False


class Browser(ClosingContextManager):
	def __init__(self):
		self._app = appscript.app('Safari')
	#	self._app.close(self._app.windows) # Also launches the application
	
	def create_document(self, url):
		return Document(self._app, url)
	
	def close(self):
		pass
	#	self._app.quit()


class Document(ClosingContextManager):
	_timeout = 30
	
	def __init__(self, app, url):
		self._app = app
		self._tab = self._create_tab()
		self._handles_by_element = weakref.WeakKeyDictionary() # Map from easy.xml.ElementNode to handle
		
		self._load_page(url)
		self._dom = self._load_dom() # so reset() can reload the page using the DOM bridge
	
	def _create_tab(self):
		document = self._app.make(new = appscript.k.document)
		window, = [i for i in appscript.app('Safari').windows.get() if i.document.get() == document] # We need to get at the tab because the the document reference get's invalid as soon as a new page get's loaded.
		
		return window.tabs[0].get()
	
	def _load_page(self, url):
		def wait_for(fn):
			end_time = time.time() + self._timeout
		
			while time.time() < end_time:
				if fn():
					return
		
				time.sleep(.2)
			
			raise BridgeException('Timeout while waiting for the page to load.')

		self._tab.URL.set(url)
		
		# This should prevent safari from crashing
		self._app.windows.get()
		self._tab.index.get()
		self._tab.name.get()
		self._tab.text.get()
		self._tab.URL.get()
		self._tab.visible.get()
		
		wait_for(lambda: self._tab.source.get())
		
		for i in 'jquery-1.6.4.js', 'jquery.json-2.3.js', 'dombridge.js':
			self._run_javascript_raw(util.get_file(os.path.join('res/scripts', i)))
		
		wait_for(lambda: self._run_javascript('return $.dombridge.loaded'))
	
	def _load_dom(self):
		return self._to_xml(self._run_javascript('return $.dombridge.root'))
	
	def _to_xml(self, json):
		"""Convert a DOM serialized in a JSON document into an easyxml DOM"""
	
		if 'text' in json:
			return easy.xml.TextNode(json['text'])
		else:
			elem = easy.xml.ElementNode(json['name'], dict(json['attributes']), map(self._to_xml, json['children']))
	
			self._handles_by_element[elem] = json['handle']
	
			return elem
	
	def _run_javascript_raw(self, expr):
		return self._tab.do_JavaScript(expr)

	def _run_javascript(self, code, **kwargs):
		"""Run an expression within a function that receives the specified keyword arguments as arguments with that name."""
	
		params = ['$']
		args = ['jQuery']
	
		for k, v in kwargs.items():
			params.append(k)
	
			if isinstance(v, easy.xml.ElementNode):
				args.append('jQuery.dombridge.handles[%s]' % self._handles_by_element[v])
			else:
				args.append(json.dumps(v))
	
		res = self._run_javascript_raw('jQuery.toJSON((function (%s) { %s }) (%s))' % (', '.join(params), code, ', '.join(args)))
	
		if res is None:
			raise BridgeException('Error while executing JavaScript.')
		
		return json.loads(res)
	
#	def follow_link(self, elem):
#		"""Follow a link from a single a element within node, also works with links that have an onclick attribute."""
#		
#		elem, = elem.walk(name = 'a', attrs = { 'href': None }, root = True)
#		
#		href = elem.attributes.get('href')
#		onclick = elem.attributes.get('onclick')
#		
#		# TODO: Check whether we have to build the form in the right document
#		safari_json("""
#			var a = $(document.createElement('input')).attr('type', 'submit');
#			
#			if (onclick !== null)
#				a.attr('onclick', onclick);
#			
#			if (href !== null)
#				$('html').append($(document.createElement('form')).attr({ 'action': href, 'method': 'GET' }).append(a));
#			else
#				$('html').append(a);
#			
#			a.click();""", href = href, onclick = onclick)
#	
#	def click_element(self, node):
#		"""Click onto an element like a button."""
#		
#		safari_json("$(h).click()", h = node)

	def close(self):
		self._tab.close()
		self._tab = None
	
	@property
	def dom(self):
		assert self._dom is not None
		
		return self._dom