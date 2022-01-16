# YT-DLP Utils
#### Mr. George L. Malone; 2021-2022


## Overview


This repository contains a "module-like" collection of scripts and class
definitions used for wrapping the [yt-dlp utility][ytdlp].  The current state
permits batch handling of video downloads, either serially or concurrently, or
playlist downloads.  Serial batch downloads are handled using the Python API
directly; concurrent and playlist downloads are currently handled using the
`subprocess` module to call the yt-dlp CLI.


## Current state


Currently, the wrapper provides more interesting messages (as well as less text
overall) such as individual video download progress and stage, and handles
circumstances such as a "speed sink" or other failure.  This permits automated
restarting of the download should it be jammed at a low speed (sub-1.0MiB/s) or
should permission be denied by request frequency.

Some important scenarios are as yet unhandled.  Please open a ticket if you
would like to request a possible change, or fork this repo and make a pull
request if you would like to make a direct contribution.  Furthermore, I'm not
an expert developer and this is a bit of a pet project, so there will be wonky
bits, rough edges, and a somewhat slow dev cycle.  I am also exclusively
developing this on a Ubuntu system so there may be cross-platform
incompatibilities.  For example, there is a known bug (of currently unknown
cause or source) running subprocess calls on the WSL, which doesn't stop the
video successfully downloading, but breaks console output.


## Changes


**Future changes may include:**

- Renaming of components
- Restructuring to permit usage of the yt-dlp Python API


_This project is written as a wrapper for the yt-dlp utility [(project
page)][ytdlp]._


[ytdlp]:https://github.com/yt-dlp/yt-dlp
