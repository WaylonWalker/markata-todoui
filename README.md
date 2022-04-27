## markata-todui

### Install


```bash
pip install git+https://github.com/waylonwalker/markata-todoui
```

### Configuration

Create a `markata.toml` config file or copy the one in this repo

```bash
wget https://raw.githubusercontent.com/WaylonWalker/markata-todoui/main/markata.example.toml -o markata.toml
```

## Define Tasks

Create a directory `tasks` and create markdown files for each todo item...

```

tasks
├── task1.md
└── task2.md

```

```markdown

---
date: 2022-03-03
priority: 0
status: todo
tags:
- null
- null
- null
templateKey: task
title: Example task 
---

# Here's a header
Some description

## A subheading

Body of todo

```bash
echo "markata todoui is awesome!"
```


## To Run

run to todoui


```bash
markata todoui
```

## Usage

vim-like keybindings

* h/l for left/right navitation
* j/k for navigating tasks in a window
* H/L for moving a task left/right 
* J/K for moving tasks in a window
