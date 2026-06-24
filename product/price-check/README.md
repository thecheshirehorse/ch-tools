# Price Checker

A barcode-scanning PWA for in-store use. Point a phone or tablet camera at a product barcode and it jumps straight to that product's live page on cheshirehorse.com, so staff (or customers) can see the current price, stock status, and description without looking anything up manually.

Part of the [ch-tools](https://github.com/caitlinsc/ch-tools) monorepo.

## How it works

1. Open the tool — the camera starts automatically (tap **Start Scan** if autoplay is blocked, which is common on iOS).
2. Point the camera at a barcode.
3. On a successful scan, the page redirects to `https://www.cheshirehorse.com/p/<scanned code>`.

There's no manual entry field — if the camera can't read the barcode, the only path is rescanning.

## Installing as an app

This is a real PWA (`manifest.json` + a service worker), so it can be added to a phone's home screen via the browser's "Add to Home Screen" / "Install" option. Once installed it opens full-screen without browser chrome, which makes repeated scanning at a register or sales floor faster.

The service worker is currently a simple passthrough (it doesn't cache pages for offline use) — it exists mainly to satisfy PWA install criteria.

## Requirements

- Camera permission in the browser.
- HTTPS (required for camera access) — works fine when served from GitHub Pages.

## Built with

[html5-qrcode](https://github.com/mebjas/html5-qrcode) for barcode/QR scanning via the device camera.
