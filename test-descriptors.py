class D:
	class I:
		def __init__(self):
			self._counter = 0
		
		def __get__(self, instance, owner):
			self._counter += 1
			
			return self._counter
	
	def __get__(self, instance, owner):
		if instance is None:
			return self
		else:
			name, = [k for k, v in vars(owner).items() if v == self]
			
			setattr(instance, name, self.I())
			
			return getattr(instance, name)


class A():
	d1 = D()
	d2 = D()


a1 = A()
a2 = A()

print(a1.d1)
print(a1.d2)
print(a2.d1)
print(a2.d2)

print(a1.d1)
print(a1.d2)
print(a2.d1)
print(a2.d2)