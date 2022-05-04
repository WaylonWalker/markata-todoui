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

__version__ = "0.0.1"


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
        # self.set_interval(1, self.action_refresh)

    async def on_load(self, event):
        self.m = Markata()
        self.config = self.m.get_plugin_config("todoui")

        user_defined_keys = self.config.get("keys", {})
        self.config["keys"] = {**user_defined_keys, **DEFAULT_KEYS}

        for key, command in self.config.get("keys", None).items():
            await self.bind(key, command)

    async def action_show_config(self) -> None:
        self.preview.text = "config\n" + str(self.config)
        self.preview.refresh()

    async def action_refresh(self, reload=True) -> None:
        self.todos.update()
        self.doing.update()
        self.done.update()
        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()
        self.refresh()

    async def action_next_post(self) -> None:
        self.current_stack.next_post()
        # await self.action_refresh(reload=False)
        # self.current_stack.update()
        # self.current_stack.refresh()
        # self.preview.text = self.current_stack.text() or ""
        # self.preview.refresh()

    async def action_move_next(self) -> None:
        current_post_uuid = self.current_stack.current_post.get("uuid", "")
        self.current_stack.move_next()
        self.m.glob()
        self.m.load()
        self.current_stack.select_post_by_id(current_post_uuid)
        await self.action_next_stack()

    async def action_move_previous(self) -> None:
        current_post_uuid = self.current_stack.current_post.get("uuid", "")
        self.current_stack.move_previous()
        self.m.glob()
        self.m.load()
        self.current_stack.select_post_by_id(current_post_uuid)
        await self.action_prev_stack()

    async def action_raise_priority(self) -> None:
        self.current_stack.raise_priority()
        self.m.glob()
        self.m.load()
        self.current_stack.update()
        # self.current_stack.refresh()
        # self.preview.text = self.current_stack.text() or ""
        # self.preview.refresh()

    async def action_lower_priority(self) -> None:
        self.current_stack.lower_priority()
        self.m.glob()
        self.m.load()
        self.current_stack.update()

        # self.current_stack.next_post()
        # self.current_stack.refresh()
        # self.preview.text = self.current_stack.text() or ""
        # self.preview.refresh()

    async def action_prev_post(self) -> None:
        self.current_stack.previous_post()
        # self.current_stack.update()
        # self.preview.text = self.current_stack.text() or ""
        # self.preview.refresh()

    async def action_next_stack(self) -> None:
        self.current_stack.is_selected = False
        # self.current_stack.update()
        self.current_stack = next(self.stacks)
        self.current_stack.is_selected = True
        # self.current_stack.update()
        # self.preview.text = self.current_stack.text() or ""
        # self.preview.refresh()
        await self.action_refresh(reload=False)

    async def action_prev_stack(self) -> None:
        self.current_stack.is_selected = False
        # self.current_stack.update()
        self.current_stack = next(self.stacks)
        self.current_stack = next(self.stacks)
        self.current_stack.is_selected = True
        # self.current_stack.update()
        # self.preview.text = self.current_stack.text() or ""
        # self.preview.refresh()
        await self.action_refresh(reload=False)

    async def action_open_post(self) -> None:
        self.current_stack.open_post()

    async def action_new_post(self) -> None:
        pop_dir = Path(__file__).parents[1]
        template = "plugins/todo-template"

        proc = subprocess.Popen(
            f'tmux popup -d "{pop_dir}" copier copy {template} tasks',
            shell=True,
        )
        proc.wait()


@hook_impl()
def load(markata):
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
def cli(app, markata):
    @app.command()
    def todoui(global_filter="True"):
        global GLOBAL_FILTER
        GLOBAL_FILTER = global_filter
        MarkataApp.run(log="textual.log")


if __name__ == "__main__":
    MarkataApp.run(log="textual.log")
