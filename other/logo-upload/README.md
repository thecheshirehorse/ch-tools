# Logo Upload

**Status: idea / not yet built.** This folder is a placeholder — there is no tool here yet, just the concept.

Part of the [ch-tools](https://github.com/caitlinsc/ch-tools) monorepo.

## The idea

A simple graphical interface to upload logo files into a shared folder — likely [`assets/`](../../assets) at the root of this monorepo, which currently holds `logo-green.svg` and `logo-white.svg` and is referenced by the brand header in every tool (`<img src="../../assets/logo-white.svg">`). Right now adding or swapping a logo means manually committing a file to that folder; this tool would make that a drag-and-drop or file-picker action instead.

## What's needed before this can be built

- Confirm the target: is this strictly about `assets/` (the shared brand logo used across tool headers), or a broader logo library for other purposes (vendor logos, category images, etc.)?
- Decide on file handling: since GitHub Pages is static hosting with no backend, an in-browser tool can't write directly to the repo. Likely options are (a) generate a downloadable file plus instructions to commit it manually, or (b) use the GitHub API with a personal access token to commit directly from the browser.
- Naming/sizing conventions for anything added, so tools that reference these assets don't break.
