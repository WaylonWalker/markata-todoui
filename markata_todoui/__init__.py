import itertools
import subprocess
from enum import Enum, auto
from pathlib import Path
from typing import Optional

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


def keys_on_file(post):
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
        self.title = title
        self.name = title
        self.filter = filter
        self.is_selected = False
        self.row_selected = 0

    def text(self) -> Optional[str]:
        for i, post in enumerate(self.m.filter(self.filter)):
            if i == self.row_selected and self.is_selected:
                return post.content
        return None

    def render(self) -> Panel:
        grid = Table.grid(expand=True)

        for i, post in enumerate(
            sorted(
                self.m.filter(self.filter), key=lambda x: x["priority"], reverse=True
            )
        ):
            if i == self.row_selected and self.is_selected:
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

    def get_current_post(self):
        for i, post in enumerate(
            sorted(
                self.m.filter(self.filter), key=lambda x: x["priority"], reverse=True
            )
        ):
            if i == self.row_selected and self.is_selected:
                return post
        return None

    def move_next(self):

        post = self.get_current_post()
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["status"] = Status(Status._member_map_[post["status"]]).next().name
        path.write_text(frontmatter.dumps(post))

    def raise_priority(self):
        post = self.get_current_post()
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["priority"] = post["priority"] + 1
        path.write_text(frontmatter.dumps(post))

    def lower_priority(self):
        post = self.get_current_post()
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["priority"] = post["priority"] - 1
        path.write_text(frontmatter.dumps(post))

    def open_post(self):

        post = self.get_current_post()
        proc = subprocess.Popen(
            f'nvr --remote "{post["path"]}"',
            shell=True,
        )
        proc.wait()

    def move_previous(self):

        post = self.get_current_post()
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["status"] = Status(Status._member_map_[post["status"]]).previous().name
        path.write_text(frontmatter.dumps(post))

    def update_markata(self, markata):
        self.m = markata

    # def render(self):
    #     return self.__rich__()

    # async def update(self, renderable: RenderableType) -> None:
    #     self.refresh()


class MarkataWidget(Widget):
    def __init__(self, markata: Markata, widget: str = "server"):
        super().__init__(widget)
        self.m = markata
        self.widget = widget
        self.renderable = getattr(self.m, self.widget)

    def render(self):
        return self.renderable

    # async def update(self, renderable: RenderableType) -> None:
    #     self.renderable = renderable
    #     self.refresh()


class MarkataApp(App):
    async def on_mount(self) -> None:
        self.m = Markata()
        self.m.console.quiet = True
        self.preview = Preview(text="init")
        self.todos = Posts(self.m, "todo", 'status=="todo"')
        self.doing = Posts(self.m, "doing", 'status=="doing"')
        self.done = Posts(self.m, "done", 'status=="done"')
        self.stacks = itertools.cycle([self.todos, self.doing, self.done])
        self.current = self.todos
        self.todos.is_selected = True
        await self.view.dock(
            self.preview, self.todos, self.doing, self.done, edge="left", name="todos"
        )
        self.set_interval(1, self.action_refresh)

    async def on_load(self, event):
        await self.bind("q", "quit", "quit")
        await self.bind("l", "next_stack", "next_stack")
        await self.bind("L", "move_next", "move_next")
        await self.bind("H", "move_previous", "move_previous")
        await self.bind("J", "lower_priority", "lower_priority")
        await self.bind("K", "raise_priority", "raise_priority")
        await self.bind("h", "prev_stack", "prev_stack")
        await self.bind("r", "refresh", "refresh")
        await self.bind("j", "next_post", "next_post")
        await self.bind("k", "prev_post", "prev_post")
        await self.bind("enter", "open_post", "open_post")
        await self.bind("n", "new_post", "new_post")

    async def action_refresh(self) -> None:
        # self.refresh()
        # self.m = Markata()
        self.m.glob()
        self.m.load()
        self.todos.refresh()
        self.doing.refresh()
        self.done.refresh()
        self.preview.text = self.current.text() or ""
        self.preview.refresh()

    async def action_next_post(self) -> None:
        self.current.row_selected += 1
        self.current.refresh()
        self.preview.text = self.current.text() or ""
        self.preview.refresh()

    async def action_move_next(self) -> None:
        self.current.move_next()
        self.m.glob()
        self.m.load()
        self.current.is_selected = False
        self.current = next(self.stacks)
        self.current.is_selected = True
        self.preview.text = self.current.text() or ""
        # self.action_refresh()

    async def action_move_previous(self) -> None:
        self.current.move_previous()
        self.m.glob()
        self.m.load()
        self.current.is_selected = False
        self.current = next(self.stacks)
        self.current = next(self.stacks)
        self.current.is_selected = True
        self.preview.text = self.current.text() or ""
        # self.action_refresh()

        self.todos.refresh()
        self.doing.refresh()
        self.done.refresh()
        self.preview.refresh()

    async def action_raise_priority(self) -> None:
        self.current.raise_priority()
        self.m.glob()
        self.m.load()

        self.current.row_selected -= 1
        self.current.refresh()
        self.preview.text = self.current.text() or ""
        self.preview.refresh()
        # self.action_refresh()

    async def action_lower_priority(self) -> None:
        self.current.lower_priority()
        self.m.glob()
        self.m.load()

        self.current.row_selected += 1
        self.current.refresh()
        self.preview.text = self.current.text() or ""
        self.preview.refresh()
        # self.action_refresh()

    async def action_prev_post(self) -> None:
        self.current.row_selected -= 1
        self.current.refresh()
        self.preview.text = self.current.text() or ""
        self.preview.refresh()

    async def action_next_stack(self) -> None:
        self.current.is_selected = False
        self.current.refresh()
        self.current = next(self.stacks)
        self.current.is_selected = True
        self.current.refresh()
        self.preview.text = self.current.text() or ""
        self.preview.refresh()

    async def action_prev_stack(self) -> None:
        self.current.is_selected = False
        self.current.refresh()
        self.current = next(self.stacks)
        self.current = next(self.stacks)
        self.current.is_selected = True
        self.current.refresh()
        self.preview.text = self.current.text() or ""
        self.preview.refresh()

    async def action_open_post(self) -> None:
        self.current.open_post()

    async def action_new_post(self) -> None:
        pop_dir = Path(__file__).parents[1]
        template = "plugins/todo-template"

        proc = subprocess.Popen(
            f'tmux popup -d "{pop_dir}" copier copy {template} tasks',
            shell=True,
        )
        proc.wait()


@hook_impl()
def cli(app, markata):
    @app.command()
    def todoui():
        MarkataApp.run(log="textual.log")


if __name__ == "__main__":
    MarkataApp.run(log="textual.log")
