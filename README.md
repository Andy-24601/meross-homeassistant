[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)

# Meross Home Assistant component

This repository is a personal patched copy of Alberto Geniola's Meross Home Assistant custom integration.

Full credit for the original project, architecture, reverse engineering, and the vast majority of the code belongs to Alberto Geniola and the upstream contributors.

Upstream project:
- [albertogeniola/meross-homeassistant](https://github.com/albertogeniola/meross-homeassistant)

Underlying library:
- [albertogeniola/MerossIot](https://github.com/albertogeniola/MerossIot)

## What this repo is

This repo exists so I can keep a small set of local fixes on top of upstream `v1.3.12` for my own Home Assistant setup, while still being able to install and update it through HACS.

It is not presented as an original project or a replacement for the upstream integration.

## Why keep a separate copy

I am using this repository to track device-specific changes that work better in my environment, without taking any credit away from the original author.

At the time of writing, the local changes include:
- `MSL120D` light color temperature mapping fixes
- light automation fixes so brightness and color temperature can be applied together
- reduced switch refresh churn to avoid some state/timeout issues
- runtime support patching for `MS200` hub sensor events

## Installation

If you want the original project, please use Alberto's repository:
- [albertogeniola/meross-homeassistant](https://github.com/albertogeniola/meross-homeassistant)

If you specifically want these personal patches, add this repository to HACS as a custom repository and install it as an `Integration`.

## Support and credit

Please direct original-project credit, stars, and upstream issue context to Alberto Geniola's work:
- [Original Meross Home Assistant integration](https://github.com/albertogeniola/meross-homeassistant)
- [MerossIot library](https://github.com/albertogeniola/MerossIot)
- [Meross local broker addon](https://github.com/albertogeniola/ha-meross-local-broker)

If you use this patched copy, remember that the hard part was already done upstream.
