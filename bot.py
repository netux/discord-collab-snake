import io
import random
from functools import partial
from typing import Union

import discord
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImagePalette, ImageFont

from utils import Dimension, Vector, NULL_VECTOR, looparound_vector
from config import channel_id, token, board_size, send_interval
from snake import SnakeGame, Snake, SnakeMove
from constants import *

board_size = Dimension(*board_size)
canvas_size = Dimension(*[s * 4 for s in board_size])
output_image_size = Dimension(*[s * 4 for s in canvas_size])

snake_facts = ['__no snake facts today, sorry :(__']
with open('snake_facts.json', 'rb') as f:
	import json

	snake_facts = json.loads(f.read().decode('utf-8'))

def to_canvas_coord(coords: Vector):
	return coords * 4 + (1, 1)

def format_time(date):
	parts = list(filter(lambda x: x is not None, [
		f'{date.hours} hour' + ('s' if date.hours == 1 else '') if date.hours != 0 else None,
		f'{date.minutes} minute' + ('s' if date.minutes == 1 else '') if date.minutes != 0 else None,
		f'{date.seconds} second' + ('s' if date.seconds == 1 else '') if date.seconds != 0 else None
	]))

	result = ''
	for i, s in enumerate(parts):
		result += s
		if i != len(parts) - 1:
			result += ' and ' if i == len(parts) - 1 else ', '

	return result


def create_checkerboard_bg_img() -> Image:
	img: Image = Image.new('P', canvas_size, color=0)
	img.putpalette([
		255, 255, 255, # full white
		205, 205, 205, # checkerboard border
			0, 	 0, 	0, # snake eyes
			2, 190, 	1, # snake body
		229, 	 0, 	0, # food
			0, 131, 199, # arrow emoji background
		136, 136, 136, # stats bar
	])
	draw = ImageDraw.Draw(img)

	draw.ink = 1
	for x in range(board_size.w):
		img_x = 3 + x * 4
		draw.line((img_x, 0, img_x, canvas_size.h))
	for y in range(board_size.h):
		img_y = 3 + y * 4
		draw.line((0, img_y, canvas_size.w, img_y))

	del draw
	return img
base_img = create_checkerboard_bg_img()

class CollabSnake(commands.Bot):
	game: SnakeGame
	channel: discord.TextChannel
	last_msg: discord.Message
	tie_detected: bool
	has_ended: bool

	def __init__(self):
		super().__init__('cs!')

		self.game = SnakeGame(board_size)
		self.last_msg = None
		self.tie_detected = False
		self.has_ended = False

	def draw_gamestate(self, draw: ImageDraw.Draw):
		# food (cross)
		food_tile_center = to_canvas_coord(self.game.food_position)
		draw.ink = 4
		draw.point(food_tile_center + (-1, 0))
		draw.point(food_tile_center + (0, -1))
		draw.point(food_tile_center)
		draw.point(food_tile_center + (1, 0))
		draw.point(food_tile_center + (0, 1))

		# snake body
		draw.ink = 3
		draw.fill = 3
		snake_head_tile_center = to_canvas_coord(self.game.snake.head_position)
		tile_center = snake_head_tile_center
		is_first = True

		labs = partial(looparound_vector, board_size)
		tile_position = self.game.snake.head_position
		for move in reversed(self.game.snake.movements):
			start_offset = NULL_VECTOR
			end_offset = NULL_VECTOR

			if move.direction == UP:
				dir_vector = Vector(0, 1)
				start_offset = Vector(0, -1)
			elif move.direction == DOWN:
				dir_vector = Vector(0, -1)
				end_offset = Vector(0, 1)
			elif move.direction == LEFT:
				dir_vector = Vector(1, 0)
				start_offset = Vector(-1, 0)
			elif move.direction == RIGHT:
				dir_vector = Vector(-1, 0)
				end_offset = Vector(1, 0)

			for i in range(move.amount):
				tile_position = labs(tile_position + dir_vector)
				tile_center = to_canvas_coord(tile_position)
				if move.direction == UP and tile_position.y == board_size.h - 1:
					end_offset += (0, 1)
				elif move.direction == LEFT and tile_position.x == board_size.w - 1:
					end_offset += (1, 0)

				draw.rectangle([
					tile_center + (-1, -1) + start_offset,
					tile_center + (1, 1) + end_offset
				])

			if is_first:
				# snake head
				end_offset = NULL_VECTOR
				if move.direction == UP and self.game.snake.head_position.y == board_size.h - 1:
					end_offset += (0, 1)
				elif move.direction == LEFT and self.game.snake.head_position.x == board_size.w - 1:
					end_offset += (1, 0)

				draw.rectangle([
					snake_head_tile_center + (-1, -1),
					snake_head_tile_center + (1, 1) + end_offset
				])

			is_first = False

		# snake eyes
		last_movement_dir = self.game.snake.movements[-1].direction
		if last_movement_dir == UP or last_movement_dir == DOWN:
			draw.point(snake_head_tile_center + (-1, 0), 2)
			draw.point(snake_head_tile_center + (1, 0), 2)
		else:
			draw.point(snake_head_tile_center + (0, -1), 2)
			draw.point(snake_head_tile_center + (0, 1), 2)

	def draw_gameover(self, draw: ImageDraw.Draw):
		text = 'GAME OVER'
		text_width, text_height = draw.textsize(text)
		draw.text(
			(Vector(*canvas_size) - (text_width, text_height)) / 2,
			text,
			fill=(255, 255, 255, 255)
		)

	def create_image(self):
		img = base_img.copy()

		draw = ImageDraw.Draw(img)
		self.draw_gamestate(draw)
		del draw

		if self.game.has_ended:
			img = img.convert('RGBA')
			fg_img = Image.new('RGBA', canvas_size, color=(0, 0, 0, 204))

			fg_draw = ImageDraw.Draw(fg_img)
			self.draw_gameover(fg_draw)
			del fg_draw

			img.alpha_composite(fg_img)

		return img.resize(output_image_size)

	def get_winning_move(self):
		valid_reactions = list(filter(lambda r: r.emoji in (UP, DOWN, LEFT, RIGHT), self.last_msg.reactions))
		winner = None
		tie = False

		if len(valid_reactions) > 0:
			best = valid_reactions[0]
			for reaction in valid_reactions[1:]:
				if reaction.count == best.count:
					tie = True
				elif reaction.count > best.count:
					best = reaction
					tie = False

			winner = best.emoji

		return winner if not tie else None


	async def send_new_state(self, img: Image):
		img_bytes = io.BytesIO()
		img.convert('RGBA').save(img_bytes, format='PNG')
		img_bytes.seek(0)

		content = (
			f'🐍 Did you know? {random.choice(snake_facts)}\n'
			'React to choose what move comes next 🎮'
		)

		if self.game.has_ended:
			content = (
				'Oh no! We\'ve lost!\n'
				f'Starting new game in {format_time(self.advance_task)}'
			)

		self.last_msg = await self.channel.send(
			content=content,
			file=discord.File(img_bytes, filename='collab_snake.png')
		)

		if not self.game.has_ended:
			snake_last_move_dir = self.game.snake.movements[-1].direction
			if snake_last_move_dir != DOWN:
				await self.last_msg.add_reaction(UP)
			if snake_last_move_dir != RIGHT:
				await self.last_msg.add_reaction(LEFT)
			if snake_last_move_dir != UP:
				await self.last_msg.add_reaction(DOWN)
			if snake_last_move_dir != LEFT:
				await self.last_msg.add_reaction(RIGHT)

	async def advance(self):
		if self.game.has_ended:
			self.last_msg = None
			self.game = SnakeGame(board_size)
			self.game.has_ended = False
			return

		if self.last_msg:
			# update last_msg with the one in cache (https://github.com/Rapptz/discord.py/issues/861)
			self.last_msg = discord.utils.get(self.cached_messages, id=self.last_msg.id)

			direction = None
			tie_message_appended = False
			prev_last_message = None
			while direction is None:
				direction = self.get_winning_move()
				if not direction:
					if not tie_message_appended:
						prev_last_message = self.last_msg.content
						await self.last_msg.edit(content='**❗ Tie detected**\n' + prev_last_message)
						tie_message_appended = True
					def check(reaction: discord.Reaction, user: discord.User):
						return user.id != self.user.id and reaction.message.id == self.last_msg.id
					await self.wait_for('reaction_add', check=check)
			if tie_message_appended:
				await self.last_msg.edit(content=prev_last_message)

			self.game.advance(direction)

		img = self.create_image()
		await self.send_new_state(img)

		if self.game.has_ended:
			self.has_ended = True

	@tasks.loop(**send_interval)
	async def advance_task(self):
		try:
			await self.advance()
		except Exception as e:
			# TODO(netux): use after_advance_task()
			from sys import stdout
			from traceback import print_exc

			print(e)
			print_exc(file=stdout)

	@advance_task.after_loop
	async def after_advance_task(self):
		if self.advance_task.failed():
			# TODO(netux): find out why execution stops after this
 			print(self.advance_task.exception())

	async def on_ready(self):
		print(f'Ready to work')

		self.channel = self.get_channel(channel_id)
		self.advance_task.start()

bot = CollabSnake()
bot.run(token)
