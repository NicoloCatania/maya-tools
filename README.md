# Maya Tools

A small collection of standalone Maya tools I use in my own rigging and
animation workflow. Each tool lives in its own folder with its own README, so
they can be dropped into a shelf or Maya's `scripts` folder independently of
one another.

Bigger, standalone projects (like [RigDiff](https://github.com/NicoloCatania/RigDiff))
get their own repository — this one is for smaller, single-file utilities
that don't need that much ceremony.

## Tools

| Tool | Description |
| --- | --- |
| [Animation Recorder](animation_recorder/) | Small PySide6 UI for keyframe recording, cleanup, and transferring animation between objects. |

## Requirements

- Autodesk Maya 2025+ (PySide6 / shiboken6)
- Python 3 (bundled with Maya)

## Installation

Clone or download this repository, then copy the tool folder you want (e.g.
`animation_recorder/`) into your Maya `scripts` directory:

```
C:/Users/<you>/Documents/maya/<version>/scripts/
```

Each tool's own README has the exact `import` / launch command.

## License

MIT — see [LICENSE](LICENSE).
