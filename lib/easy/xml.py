import itertools


_xml_entities = { 'lt': '<', 'gt': '>', 'amp': '&', 'apos': "'", 'quot': '"' }
_xml_entities_encode_map = { ord(v): '&%s;' % k for k, v in _xml_entities.items() }


class Node:
	"""Abstract base class for text and element nodes."""
	
	def walk(self, fn = None, *, name = None, attrs = None, prune = True, root = False):
		"""Iterate over all the elements inside this node which mach the given specification.
		
		name: If specified. Only return element with the given name.
		attrs: A map of attribute names to values. Only return elements which have all the specified attributes with the given values. Or which have the specified attributes with any value, if the value is given as None.
		prune: Do not return any child elements of elements that are also returned.
		root: Allow this element to be considered a match. If set to False, only child elements will be considered."""
		
		def find(elem):
			if isinstance(elem, ElementNode):
				if (elem != self or root) and (name is None or elem.name == name):
					for k, v in ({ } if attrs is None else attrs).items():
						if not (k in elem.attrs and (v is None or elem.attrs[k] == v)):
							break
					else:
						if ((lambda _: True) if fn is None else fn)(elem):
							yield elem
							
							if prune:
								return
				
				for i in elem.nodes:
					for j in find(i):
						yield j
		
		return find(self)
	
	def find(self, *args, **kwargs):
		"""Same as walk(), but returns exactly one element. Throws an exception if no or multiple elements match the specification."""
		
		res, = self.walk(*args, **kwargs)
		
		return res
	
	def contains(self, *args, **kwargs):
		"""Tests whether any element would be returned by walk()."""
		
		try:
			next(self.walk(*args, **kwargs))
		except StopIteration:
			return False
		
		return True
	
	def text(self):
		"""Concatenation of the string contents of all TextNodes inside this element."""
		
		return ''.join(i.value for i in self._all() if isinstance(i, TextNode))
	
	# Iterate over all the nodes in this subtree in pre-order.
	def _all(self):
		assert False


class TextNode(Node):
	"""Represens a text element between two XML tags."""
	
	def __init__(self, value):
		super().__init__()
		
		self.value = value
	
	def __str__(self):
		return self.value.translate(_xml_entities_encode_map)
	
	def _all(self):
		return [self]


class ElementNode(Node):
	"""Represents a Node of an XML document, with attributes and children."""
	
	def __init__(self, name, attrs = { }, nodes = []):
		super().__init__()
		
		self.name = name
		self.attrs = dict(attrs)
		self.nodes = list(nodes)
	
	def __str__(self):
		attrs = ''.join(' %s="%s"' % (k, v.translate(_xml_entities_encode_map)) for k, v in self.attrs.items())
		children = ''.join(map(str, self.nodes))
		
		if children:
			return '<%s%s>%s</%s>' % (self.name, attrs, children, self.name)
		else:
			return '<%s%s/>' % (self.name, attrs)
	
	def _all(self):
		return itertools.chain([self], *(i._all() for i in self.nodes))


class ParseHandler:
	"""Internal class used by parse() to consume all parsed elements and build an XML tree."""
	
	def __init__(self):
		self._element_stack = []
		self.result = None
	
	def tag(self, name, attrs):
		self.tag_start(name, attrs)
		self.tag_end(name)
	
	def tag_start(self, tag, attrs):
		self._element_stack.append(ElementNode(tag, dict(attrs)))
	
	def tag_end(self, tag):
		node = self._element_stack.pop()
		
		assert tag == node.name, '%s != %s' % (tag, node.name)
		
		if self._element_stack:
			self._element_stack[-1].nodes.append(node)
		else:
			assert self.result is None
			
			self.result = node
	
	def data(self, data):
		# Discard data outside of the main html element
		if self._element_stack:
			self._element_stack[-1].nodes.append(TextNode(data))
	
	def handle_charref(self, name):
		assert False, 'charref: %s' % name
	
	def handle_entityref(self, name):
		assert False, 'entityref: %s' % name


def node(name, *nodes, **attrs):
	nodes = [i if isinstance(i, Node) else TextNode(i) for i in nodes]
	attrs = { k.replace('__', ':'): v for k, v in attrs.items() }
	
	return ElementNode(name, attrs, nodes)


def parse(str):
	"""Parse a string into an XML document."""
	from lib.easy.regex import grp, rep, opt, alt, matchone, matchall
	
	id = '[A-Za-z_][A-Za-z0-9_:-]*'
	string = alt('"[^"]*"', "'[^']*'")
	
	ws = r'[\n\r\t ]*'
	wsr = r'[\n\r\t ]+'
	
	attr = grp(id, 'name') + ws + '=' + ws + grp(string, 'value')
	attr_anon = id + ws + '=' + ws + string
	tag = '<' + ws + grp(id, 'name') + alt(ws, wsr + grp(rep(attr_anon + ws, '+'), 'attrs')) + opt(grp('/', 'end')) + ws + '>'
	tag_anon = '<' + ws + id + alt(ws, wsr + rep(attr_anon + ws, '+')) + opt('/') + ws + '>'
	tagend = '<' + ws + '/' + ws + grp(id, 'name') + ws + '>'
	tagend_anon = '<' + ws + '/' + ws + id + ws + '>'
	declaration = '<[?!][^<>]+>'
	
	data_elem = alt(grp('[^<&]+', 'char'), '&' + grp(rep('[a-z]', '+'), 'name') + ';')
	data_elem_anon = alt('[^<&]+', '&' + rep('[a-z]', '+') + ';')
	data = rep(data_elem_anon, '+')
	
	handler = ParseHandler()
	
	def parse_data(data):
		def fn(match):
			if 'char' in match:
				return match['char']
			else:
				return _xml_entities[match['name']]
		
		return ''.join(map(fn, matchall(data_elem, data)))
	
	for i in matchall(alt(grp(tag_anon, 'tag'), grp(tagend_anon, 'tagend'), grp(data, 'data'), declaration), str):
		# XML entities and declarations are ignored
		if 'tag' in i:
			match = matchone(tag, i['tag'])
			attrs = { }
			
			if 'attrs' in match:
				for j in matchall(attr + ws, match['attrs']):
					attrs[j['name']] = parse_data(j['value'][1:-1])
			
			if 'end' in match:
				handler.tag(match['name'], attrs)
			else:
				handler.tag_start(match['name'], attrs)
		elif 'tagend' in i:
			handler.tag_end(matchone(tagend, i['tagend'])['name'])
		elif 'data' in i:
			handler.data(parse_data(i['data']))
	
	return handler.result