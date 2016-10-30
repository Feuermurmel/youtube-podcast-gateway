import threading, httplib2, apiclient.discovery, oauth2client.client, oauth2client.file, oauth2client.tools, googleapiclient.http
from lib import util


_api_name = 'youtube'
_api_version = 'v3'
_auth_scope = 'https://www.googleapis.com/auth/youtube.readonly'

_client_secrets_path = "client_secrets.json"
_oauth2_token_path = 'oauth2_token.json'


def _get_authenticated_service(api_name, api_version, auth_scope):
	flow = oauth2client.client.flow_from_clientsecrets(_client_secrets_path, scope = auth_scope)
	
	storage = oauth2client.file.Storage(_oauth2_token_path)
	credentials = storage.get()
	
	if credentials is None or credentials.invalid:
		credentials = oauth2client.tools.run_flow(flow, storage, oauth2client.tools.argparser.parse_args(['--noauth_local_webserver']))
	
	return apiclient.discovery.build(api_name, api_version,
		http = credentials.authorize(httplib2.Http()))


class _Item:
	def __init__(self, items):
		self._items = items
	
	def __getattr__(self, name):
		item = self._items.get(name)
		
		if item is None:
			raise AttributeError('No item named {}.'.format(name))
		
		return item
	
	@classmethod
	def wrap_json(cls, value):
		if isinstance(value, dict):
			return cls({ k: cls.wrap_json(v) for k, v in value.items() })
		else:
			return value


class YouTube:
	_max_results_per_request = 50
	
	def __init__(self, service):
		self._service = service
		self._service_lock = threading.Lock()
	
	def get_channel_by_id_or_username(self, channel_id_or_username, part):
		channel = self.get_channels(channel_id_or_username, part)
		
		if channel is None:
			items = self._get(self._service.channels(), part = part, forUsername = channel_id_or_username)
			
			if items:
				item, *rest = items
				
				if rest:
					raise ValueError('Multiple channels found with username {}.', channel_id_or_username)
				
				return item
			else:
				return None
		else:
			return channel
	
	def get_channels(self, channel_id, part):
		return self._get(self._service.channels(), part, id = channel_id)
	
	def get_playlists(self, playlist_id, part):
		return self._get(self._service.playlists(), part, id = playlist_id)
	
	def get_playlist_items(self, playlist_id, part):
		return self._get(self._service.playlistItems(), part, playlistId = playlist_id)
	
	def get_channel_videos(self, channelId, part, order = 'date', max_results = None):
		return self._get(self._service.search(), part, channelId = channelId, order = order, type = 'video', max_results = max_results)
	
	def get_videos(self, video_id, part):
		return self._get(self._service.videos(), part, id = video_id)
	
	@classmethod
	def get_authenticated_instance(cls):
		return cls(_get_authenticated_service(_api_name, _api_version, _auth_scope))
	
	def _get(self, resource, part, *, id = None, max_results = None, **kwargs):
		assert id is None or max_results is None
		
		if isinstance(part, list):
			part = ','.join(part)
		
		with self._service_lock:
			if id is None:
				items = self._get_raw(resource, part, max_results, **kwargs)
			else:
				if isinstance(id, list):
					items = [j for i in range(0, len(id), self._max_results_per_request) for j in self._get_raw(resource, part, id = ','.join(id[i:i + self._max_results_per_request]), **kwargs)]
				else:
					items = self._get_raw(resource, part, id = id, **kwargs)
		
		if isinstance(id, list) or id is None:
			return items
		else:
			if items:
				item, *rest = items
				
				if rest:
					raise ValueError('Multiple items were returned.')
				
				return item
			else:
				return None
	
	@classmethod
	def _get_raw(cls, resource, part, max_results = None, **kwargs):
		if max_results is not None and max_results < cls._max_results_per_request:
			max_results_per_request = max_results
		else:
			max_results_per_request = cls._max_results_per_request
		
		results = []
		request = resource.list(part = part, maxResults = max_results_per_request, **kwargs)
		
		while request and (max_results is None or len(results) < max_results):
			util.log('Requesting {} ...', request.uri)
			
			try:
				response = request.execute()
			except googleapiclient.http.HttpError as e:
				# The HttpError class is currently broken and does not decode the received data before parsing it. 
				if isinstance(e.content, bytes):
					e.content = e.content.decode()
				
				raise
			
			results.extend(map(_Item.wrap_json, response.get('items', [])))
			
			request = resource.list_next(request, response)
		
		return results[:max_results]
