import pickle, datetime


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


@memorized
def get_file(path):
	with open(path, 'rt') as file:
		return file.read()


def pickle(data, path):
	with open(path, 'wb') as file:
		return pickle.dump(data, file)


def unpickle(path):
	with open(path, 'rb') as file:
		return pickle.load(file)


def epoch(dt):
	return (dt - datetime.datetime(1970, 1, 1)) / datetime.timedelta(seconds = 1)

