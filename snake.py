import random
from dataclasses import dataclass
from typing import List, NamedTuple

from utils import Dimension, Vector, NULL_VECTOR, looparound_vector
from constants import *

@dataclass
class SnakeMove:
	direction: str
	amount: int

class Snake:
	head_position: Vector
	movements: List[SnakeMove]
	size: int
	board_size: Dimension

	def __init__(self, position: Vector, board_size: Dimension):
		self.head_position = position
		self.size = 1
		self.movements = [SnakeMove(UP, self.size)]
		self.board_size = board_size

	def move(self, direction: str):
		if direction == UP:
			self.head_position += (0, -1)
		elif direction == DOWN:
			self.head_position += (0, 1)
		elif direction == RIGHT:
			self.head_position += (1, 0)
		elif direction == LEFT:
			self.head_position += (-1, 0)

		self.head_position = looparound_vector(self.board_size, self.head_position)

		if self.movements[-1].direction == direction:
			self.movements[-1].amount += 1
		else:
			self.movements.append(SnakeMove(direction, 1))

		movement_steps = sum(map(lambda move: move.amount, self.movements), 0)
		if movement_steps < self.size:
			self.movements[0].amount += 1
			movement_steps += 1
		else:
			while movement_steps > self.size:
				self.movements[0].amount -= 1
				movement_steps -= 1
				if self.movements[0].amount == 0:
					self.movements.pop(0)
	
	def occupies_body(self, position: Vector):
		last_movement_end = self.head_position
		for move in reversed(self.movements):
			sign = 0
			dir_vector = NULL_VECTOR

			if move.direction == UP or move.direction == DOWN:
				sign = 1 if move.direction == UP else -1
				dir_vector = Vector(0, sign)
			elif move.direction == RIGHT or move.direction == LEFT:
				sign = 1 if move.direction == RIGHT else -1
				dir_vector = Vector(sign, 0)

			for i in range(move.amount * sign):
				if looparound_vector(self.board_size, last_movement_end + dir_vector * (i+1)) == position:
					return True

			last_movement_end += dir_vector * move.amount

def randvect(board_size):
	return Vector(random.randrange(0, board_size.w), random.randrange(0, board_size.h))

class SnakeGame:
	snake: Snake
	food_position: Vector
	board_size: Dimension
	has_ended: bool

	def __init__(self, board_size):
		self.board_size = board_size
		# TODO(netux): subtract (0, self.snake.size) from board_size
		self.snake = Snake(randvect(self.board_size), self.board_size)
		self.food_position = randvect(self.board_size)
		self.has_ended = False

	def is_snake_eating(self):
		return self.snake.head_position == self.food_position

	def advance(self, direction) -> bool:
		if self.has_ended:
			return

		self.snake.move(direction)
		if self.snake.occupies_body(self.snake.head_position):
			self.has_ended = True
			return
		
		if self.is_snake_eating():
			self.snake.size += 1
			while self.is_snake_eating() or self.snake.occupies_body(self.food_position):
				self.food_position = randvect(self.board_size)
