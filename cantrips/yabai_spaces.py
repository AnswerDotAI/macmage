"""Use yabai to navigate spaces and move windows between them.

Requires yabai at `/opt/homebrew/bin/yabai`. To use it, copy this file next to
your `config.py` and add `import yabai_spaces` there. Option-number focuses that
space; adding Shift moves the current window there and follows it. Ctrl-left and
Ctrl-right focus the previous and next spaces.
"""
import asyncio, subprocess

from macmage import mage


class Yabai:
    def __getattr__(self, command):
        async def run(**opts):
            cmd = ['/opt/homebrew/bin/yabai', '-m', command.replace('_', '-')]
            for k,v in opts.items():
                cmd.append(f'--{k.replace("_", "-")}')
                if v is not True: cmd.append(str(v))
            p = await asyncio.create_subprocess_exec(*cmd)
            if await p.wait(): raise subprocess.CalledProcessError(p.returncode, cmd)
        return run


yabai = Yabai()


@mage(keys='ctrl-left')
async def previous_space(): await yabai.space(focus='prev')


@mage(keys='ctrl-right')
async def next_space(): await yabai.space(focus='next')


def bind_space(i):
    async def focus(): await yabai.space(focus=i)
    async def move(): await yabai.window(space=i, focus=True)
    mage(focus, keys=f'ctrl-{i}')
    mage(move, keys=f'ctrl-shift-{i}')


for i in range(1, 10): bind_space(i)
