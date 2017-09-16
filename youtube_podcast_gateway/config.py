class Key:
    def __init__(self, name, type, default_value=None):
        self.name = name
        self.type = type
        self.default_value = default_value


class Configuration:
    def __init__(self, values: dict):
        self._values = values

    def get(self, key: Key):
        value_str = self._values.get(key.name)

        # Use the default value of no value has been set for the key or the
        # value is empty.
        if value_str:
            try:
                return key.type(value_str)
            except ValueError:
                raise Exception('Error parsing value "{}" as type {} for configuration key {}.'.format(value_str, key.type.__name__, key.name))
        else:
            return key.default_value

    @classmethod
    def from_arguments(cls, argv):
        return cls(dict(i.split('=', 1) for i in argv))
