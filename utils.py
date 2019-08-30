from typing import NamedTuple

Dimension = NamedTuple('Dimension', [('w', int), ('h', int)])

class Vector(NamedTuple('Vector', [('x', int), ('y', int)])):
	def __add__(self, other):
		if isinstance(other, tuple):
			if isinstance(other, Vector):
				other_x = other.x
				other_y = other.y
			else:
				other_x, other_y = other
			return Vector(self.x + other_x, self.y + other_y)
		else:
			return NotImplemented

	def __neg__(self):
		return self.__mul__(-1)

	def __sub__(self, other):
		if isinstance(other, tuple) and not isinstance(other, Vector):
			other = Vector(*other)
		return self + (-other)

	def __mul__(self, other):
		if isinstance(other, tuple):
			if isinstance(other, Vector):
				other_x = other.x
				other_y = other.y
			else:
				other_x, other_y = other
			return Vector(self.x * other_x, self.y * other_y)
		else:
			return Vector(self.x * other, self.y * other)

	def __rmul__(self, other):
		return self.__mul__(other)

	def __truediv__(self, other):
		if isinstance(other, tuple):
			if isinstance(other, Vector):
				other_x = other.x
				other_y = other.y
			else:
				other_x, other_y = other
		else:
			other_x = other
			other_y = other
		return self.__mul__((1 / other_x, 1 / other_y))

NULL_VECTOR = Vector(0, 0)

def looparound_vector(dimensions: Dimension, vec: Vector):
	x, y = vec
	w, h = dimensions
	return Vector(
		w + x if x < 0 else x - w if x >= w else x,
		h + y if y < 0 else y - h if y >= h else y
	)
