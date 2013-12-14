import sys


def freeze(obj):
	if isinstance(obj, dict):
		return frozenset(map(freeze, obj.items()))
	if isinstance(obj, (list, tuple)):
		return tuple(map(freeze, obj))
	if isinstance(obj, set):
		return frozenset(obj)
	else:
		return obj


def memorized(func):
	map = { }
	
	def fn(*args, **kwargs):
		key = freeze(args), freeze(kwargs)
		
		try:
			return map[key]
		except KeyError:
			value = func(*args, **kwargs)
			map[key] = value
			
			return value
	
	return fn


def log(msg, *args):
	if args:
		msg = msg.format(*args)
	
	print(msg, file = sys.stderr)
