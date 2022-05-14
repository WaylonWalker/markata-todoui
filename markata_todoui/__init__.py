import itertools
import subprocess
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional

import frontmatter
from markata import Markata
from markata.hookspec import hook_impl
from rich.console import RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from textual.app import App
from textual.widget import Widget
from textual.widgets import Footer

from markata_todoui.posts import Posts

__version__ = "0.0.4"


DEFAULT_KEYS = {
    "q": "quit",
    "l": "next_stack",
    "L": "move_next",
    "H": "move_previous",
    "J": "lower_priority",
    "K": "raise_priority",
    "h": "prev_stack",
    "r": "refresh",
    "j": "next_post",
    "k": "prev_post",
    "enter": "open_post",
    "n": "new_post",
    "ctrl+@": "show_config",
    "c": "show_config",
    "g": "first_post",
    "G": "last_post",
    "D": "delete_post",
    "r": "refresh",
}

GLOBAL_FILTER = "True"


class Preview(Widget):
    def __init__(self, text):
        super().__init__("preview")
        self.text = text

    def render(self):
        return Panel(Markdown(self.text))


class MarkataApp(App):
    async def on_mount(self) -> None:
        self.m.console.quiet = True
        self.preview = Preview(text="init")
        self.todos = Posts(self.m, "todo", f'{GLOBAL_FILTER} and status=="todo"')
        self.doing = Posts(self.m, "doing", f'{GLOBAL_FILTER} and status=="doing"')
        self.done = Posts(self.m, "done", f'{GLOBAL_FILTER} and status=="done"')
        self.stacks = itertools.cycle([self.todos, self.doing, self.done])
        self.current_stack = next(self.stacks)
        self.todos.is_selected = True
        self.doing.is_selected = False
        self.done.is_selected = False
        await self.view.dock(
            self.preview, self.todos, self.doing, self.done, edge="left", name="todos"
        )

    async def on_load(self, event):
        self.m = Markata()
        self.config = self.m.get_plugin_config("todoui")
        self.config["global_filter"] = GLOBAL_FILTER

        user_defined_keys = self.config.get("keys", {})
        self.config["keys"] = {**user_defined_keys, **DEFAULT_KEYS}

        for key, command in self.config.get("keys", None).items():

            await self.bind(key, command)

    async def action_show_config(self) -> None:
        self.preview.text = "config\n" + str(self.config) + self.current_stack.text()
        self.preview.refresh()

    async def action_refresh(self, update=True, reload=True) -> None:
        if reload:
            self.m.glob()
            self.m.load()
            self.todos.update(reload=False)
            self.doing.update(reload=False)
            self.done.update(reload=False)

        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()
        self.refresh()

    async def action_next_post(self) -> None:
        self.current_stack.next_post()
        await self.action_refresh(reload=False)

    async def action_move_next(self) -> None:
        current_post_uuid = self.current_stack.current_post.get("uuid", "")
        self.current_stack.move_next()
        self.m.glob()
        self.m.load()
        await self.action_next_stack()
        self.current_stack.select_post_by_id(current_post_uuid)

    async def action_move_previous(self) -> None:
        current_post_uuid = self.current_stack.current_post.get("uuid", "")
        self.current_stack.move_previous()
        self.m.glob()
        self.m.load()
        await self.action_prev_stack()
        self.current_stack.select_post_by_id(current_post_uuid)

    async def action_raise_priority(self) -> None:
        self.current_stack.raise_priority()
        self.m.glob()
        self.m.load()
        self.current_stack.update()

    async def action_lower_priority(self) -> None:
        self.current_stack.lower_priority()
        self.m.glob()
        self.m.load()
        self.current_stack.update()

    async def action_prev_post(self) -> None:
        self.current_stack.previous_post()
        await self.action_refresh(reload=False)

    async def action_next_stack(self) -> None:
        self.current_stack.is_selected = False
        self.current_stack = next(self.stacks)
        self.current_stack.is_selected = True
        await self.action_refresh(reload=True)

    async def action_prev_stack(self) -> None:
        self.current_stack.is_selected = False
        self.current_stack = next(self.stacks)
        self.current_stack = next(self.stacks)
        self.current_stack.is_selected = True
        await self.action_refresh(reload=True)

    async def action_open_post(self) -> None:
        self.current_stack.open_post()

    async def action_first_post(self) -> None:
        self.current_stack.select_post_by_index(0)

    async def action_last_post(self) -> None:
        self.current_stack.select_post_by_index(-1)

    async def action_new_post(self) -> None:
        cmd = self.config.get("new_post")

        proc = subprocess.Popen(
            cmd,
            shell=True,
        )
        proc.wait()
        await self.action_refresh(reload=True)

    async def action_delete_post(self) -> None:
        self.current_stack.delete_current()


@hook_impl()
def load(markata: Markata) -> None:
    for article in markata.articles:

        if "uuid" not in article.keys():
            article["uuid"] = str(uuid.uuid4())
            og_keys = frontmatter.loads(Path(article["path"]).read_text()).keys()
            save_article = deepcopy(article)
            for key in set(article.keys()) - set(og_keys):
                if key != "uuid":
                    print("deleting" + key)
                    del save_article[key]
            Path(article["path"]).write_text(frontmatter.dumps(save_article))


@hook_impl()
def cli(app, markata: Markata) -> None:
    @app.command()
    def todoui(global_filter="True") -> None:
        global GLOBAL_FILTER
        GLOBAL_FILTER = global_filter
        MarkataApp.run(log="textual.log")


if __name__ == "__main__":
    MarkataApp.run(log="textual.log")
