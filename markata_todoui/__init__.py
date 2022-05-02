import itertools
import subprocess
import uuid
from copy import deepcopy
from enum import Enum, auto
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
from textual.widgets import Footer, Placeholder

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


class DummyPost(frontmatter.Post):
    uuid = ""


class Status(Enum):
    todo = auto()
    doing = auto()
    done = auto()

    def next(self):
        if self.value == len(self._member_names_):
            return Status(1)
        else:
            return Status(self.value + 1)

    def previous(self):
        if self.value == 1:
            return Status(len(self._member_names_))
        else:
            return Status(self.value - 1)


def nth(iterable, n, default=None):
    "Returns the nth item or a default value"
    return next(islice(iterable, n, None), default)


def keys_on_file(post: frontmatter.Post) -> Dict[str, str]:
    return {key: post[key] for key in frontmatter.load(post.get("path")).keys()}


class Preview(Widget):
    def __init__(self, text):
        super().__init__("preview")
        self.text = text

    def render(self):
        return Panel(Markdown(self.text))


class Posts(Widget):
    def __init__(self, markata: "Markata", title: str, filter: str):
        super().__init__(title)
        self.m = markata
        self.config = self.m.get_plugin_config(__file__)
        self.config["keys"] = {**self.config.get("keys", {}), **DEFAULT_KEYS}

        self.title = title
        self.name = title
        self.filter = filter
        self.is_selected = False
        self.update()

    def update(self):
        self.post_list = sorted(
            self.m.filter(self.filter), key=lambda x: x["priority"], reverse=True
        )
        self.post_cycle = itertools.cycle(self.post_list)
        self.current_post = DummyPost("")
        self.next_post()

    def text(self) -> Optional[str]:
        return self.current_post.content

    def render(self) -> Panel:
        grid = Table.grid(expand=True)

        for post in self.post_list:
            if post["uuid"] == self.current_post["uuid"] and self.is_selected:
                grid.add_row(
                    f"[red]{post.get('title')}",
                    f"[bright_black]({post.get('priority')})[/]",
                    f"[bright_black]{post.get('date')}[/]",
                )
            else:
                grid.add_row(
                    f"[purple]{post.get('title')}",
                    f"[bright_black]({post.get('priority')})[/]",
                    f"[bright_black]{post.get('date')}[/]",
                )
        if self.is_selected:
            self.border_style = "#e8bde3"
        else:
            self.border_style = "#c122ac"
        return Panel(
            grid,
            title=f"[#e1af66]{self.title} ({len(self.m.filter(self.filter))})",
            border_style=self.border_style,
        )

    def prev_post(self) -> frontmatter.Post:
        if len(self.post_list):
            for _ in range(len(self.post_list) - 1):
                self.current_post = next(self.post_cycle)

    def next_post(self) -> frontmatter.Post:
        if len(self.post_list):
            self.current_post = next(self.post_cycle)

    def move_next(self) -> None:

        post = self.current_post
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["status"] = Status(Status._member_map_[post["status"]]).next().name
        path.write_text(frontmatter.dumps(post))
        self.update()

    def raise_priority(self) -> None:
        post = self.current_post
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["priority"] = post["priority"] + 1
        path.write_text(frontmatter.dumps(post))
        self.update()

    def lower_priority(self) -> None:
        post = self.current_post
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["priority"] = post["priority"] - 1
        path.write_text(frontmatter.dumps(post))
        self.update()

    def open_post(self) -> None:

        post = self.current_post
        proc = subprocess.Popen(
            f'nvr --remote "{post["path"]}"',
            shell=True,
        )
        proc.wait()

    def move_previous(self) -> None:

        post = self.current_post
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["status"] = Status(Status._member_map_[post["status"]]).previous().name
        path.write_text(frontmatter.dumps(post))
        self.update()


class MarkataWidget(Widget):
    def __init__(self, markata: Markata, widget: str = "server"):
        super().__init__(widget)
        self.m = markata
        self.widget = widget
        self.renderable = getattr(self.m, self.widget)

    def render(self):
        return self.renderable


class MarkataApp(App):
    async def on_mount(self) -> None:
        self.m.console.quiet = True
        self.preview = Preview(text="init")
        self.todos = Posts(self.m, "todo", 'status=="todo"')
        self.doing = Posts(self.m, "doing", 'status=="doing"')
        self.done = Posts(self.m, "done", 'status=="done"')
        self.stacks = itertools.cycle([self.todos, self.doing, self.done])
        self.current_stack = self.todos
        self.todos.is_selected = True
        await self.view.dock(
            self.preview, self.todos, self.doing, self.done, edge="left", name="todos"
        )
        self.set_interval(1, self.action_refresh)

    async def on_load(self, event):
        self.m = Markata()
        self.config = self.m.get_plugin_config("todoui")
        for key, command in self.config.get("keys", None).items():
            await self.bind(key, command)

    async def action_show_config(self) -> None:
        self.preview.text = "config\n" + str(self.config)
        self.preview.refresh()

    async def action_refresh(self) -> None:
        self.m.glob()
        self.m.load()
        self.todos.refresh()
        self.doing.refresh()
        self.done.refresh()
        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()

    async def action_next_post(self) -> None:
        self.current_stack.next_post()
        self.current_stack.refresh()
        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()

    async def action_move_next(self) -> None:
        self.current_stack.move_next()
        self.m.glob()
        self.m.load()
        await self.action_next_stack()

    async def action_move_previous(self) -> None:
        self.current_stack.move_previous()
        self.m.glob()
        self.m.load()
        await self.action_prev_stack()

    async def action_raise_priority(self) -> None:
        self.current_stack.raise_priority()
        self.m.glob()
        self.m.load()
        self.current_stack.refresh()
        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()

    async def action_lower_priority(self) -> None:
        self.current_stack.lower_priority()
        self.m.glob()
        self.m.load()

        self.current_stack.next_post()
        self.current_stack.refresh()
        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()

    async def action_prev_post(self) -> None:
        self.current_stack.prev_post()
        self.current_stack.refresh()
        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()

    async def action_next_stack(self) -> None:
        self.current_stack.is_selected = False
        self.current_stack.refresh()
        self.current_stack.update()
        self.current_stack = next(self.stacks)
        self.current_stack.is_selected = True
        self.current_stack.refresh()
        self.current_stack.update()
        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()

    async def action_prev_stack(self) -> None:
        self.current_stack.is_selected = False
        self.current_stack.refresh()
        self.current_stack.update()
        self.current_stack = next(self.stacks)
        self.current_stack = next(self.stacks)
        self.current_stack.is_selected = True
        self.current_stack.refresh()
        self.current_stack.update()
        self.preview.text = self.current_stack.text() or ""
        self.preview.refresh()

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
    def todoui():
        MarkataApp.run(log="textual.log")


if __name__ == "__main__":
    MarkataApp.run(log="textual.log")
