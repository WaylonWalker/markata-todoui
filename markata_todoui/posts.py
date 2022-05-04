import itertools
import subprocess
from copy import deepcopy
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Optional

import frontmatter
from rich.panel import Panel
from rich.table import Table
from textual.widget import Widget


class DummyPost(frontmatter.Post):
    uuid = ""


def keys_on_file(post: frontmatter.Post) -> Dict[str, str]:
    return {key: post[key] for key in frontmatter.load(post.get("path")).keys()}


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


class Posts(Widget):
    def __init__(self, markata: "Markata", title: str, filter: str):
        super().__init__(title)
        self.m = markata
        self.config = self.m.get_plugin_config(__file__) or {}

        self.title = title
        self.name = title
        self.filter = filter
        self.is_selected = True
        self.current_post = DummyPost("")
        self.messages = ""
        self.update()
        self.next_post()

    def update(self, reload=False) -> None:
        current_uuid = self.current_post.get("uuid", None)
        # if reload:
        #     self.m.glob()
        #     self.m.load()

        self.post_list = sorted(
            self.m.filter(self.filter), key=lambda x: x["priority"], reverse=True
        )
        self.post_cycle = itertools.cycle(self.post_list)
        if current_uuid is not None:
            self.select_post_by_id(current_uuid)
        self.messages = self.messages + f"{self.current_post.get('uuid')}\n"
        self.refresh()

    def text(self) -> Optional[str]:
        return self.messages
        # return self.current_post.get("uuid", "") + self.current_post.content

    def render(self) -> Panel:
        grid = Table.grid(expand=True)

        for post in self.post_list:
            if (
                post.get("uuid", "") == self.current_post.get("uuid", "")
                and self.is_selected
            ):
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

    def previous_post(self) -> None:
        if len(self.post_list):
            for _ in range(len(self.post_list) - 1):
                self.current_post = next(self.post_cycle)
        self.refresh()

    def __next__(self) -> frontmatter.Post:
        return self.next_post()

    def next_post(self) -> frontmatter.Post:
        try:
            self.current_post = next(self.post_cycle)
        except StopIteration:
            ...
        self.refresh()
        # else:
        #     self.current_post.content = "No More Posts"
        # return self.current_post

    def select_post_by_id(self, uuid: str) -> frontmatter.Post:
        first_uuid = self.current_post["uuid"]
        self.messages = "getting post by id\n"
        self.messages = self.messages + f"first_uuid: {first_uuid}\n"
        self.messages = self.messages + f"looking for uuid: {uuid}\n"
        while uuid != self.current_post["uuid"]:

            self.current_post = next(self.post_cycle)
            self.messages = self.messages + f'this uuid: {self.current_post["uuid"]}\n'
            if self.current_post["uuid"] == first_uuid:
                raise RecursionError(f"could not find post uuid: {uuid}")

    def move_next(self) -> None:

        post = deepcopy(self.current_post)
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["status"] = Status(Status._member_map_[post["status"]]).next().name
        path.write_text(frontmatter.dumps(post))
        self.update()

    def raise_priority(self) -> None:
        post = deepcopy(self.current_post)
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["priority"] = post["priority"] + 1
        path.write_text(frontmatter.dumps(post))
        self.update()

    def lower_priority(self) -> None:
        post = deepcopy(self.current_post)
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

        post = deepcopy(self.current_post)
        path = Path(post["path"])
        post.metadata = keys_on_file(post)
        post["status"] = Status(Status._member_map_[post["status"]]).previous().name
        path.write_text(frontmatter.dumps(post))
        self.update()
