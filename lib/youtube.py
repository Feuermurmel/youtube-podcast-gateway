import httplib2, apiclient.discovery, oauth2client.client, oauth2client.file, oauth2client.tools
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
	_max_results = 50
	
	def __init__(self, service):
		self._service = service
	
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
		return self._get(self._service.playlists(), part = part, id = playlist_id)
	
	def get_playlist_items(self, playlist_id, part):
		return self._get(self._service.playlistItems(), part = part, playlistId = playlist_id)
	
	def get_videos(self, video_id, part):
		return self._get(self._service.videos(), part = part, id = video_id)
	
	@classmethod
	def get_authenticated_instance(cls):
		return cls(_get_authenticated_service(_api_name, _api_version, _auth_scope))
	
	@classmethod
	def _get(cls, resource, part, *, id = None, **kwargs):
		if isinstance(part, list):
			part = ','.join(part)
		
		if id is None:
			items = cls._get_raw(resource, part, **kwargs)
		else:
			if isinstance(id, list):
				items = [j for i in range(0, len(id), cls._max_results) for j in cls._get_raw(resource, part, id = ','.join(id[i:i + cls._max_results]), **kwargs)]
			else:
				items = cls._get_raw(resource, part, id = id, **kwargs)
		
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
	def _get_raw(cls, resource, part, **kwargs):
		def iter_items():
			request = resource.list(part = part, maxResults = cls._max_results, **kwargs)
			
			while request:
				util.log('Requesting {} ...', request.uri)
				
				response = request.execute()
				
				yield from response.get("items", [])
				
				request = resource.list_next(request, response)
		
		return [_Item.wrap_json(i) for i in iter_items()]
