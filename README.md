# YT-DLP Utils
#### Mr. George L. Malone; 2021-2022


## Overview


This repository contains a "module-like" collection of scripts and class
definitions used for wrapping the [yt-dlp utility][ytdlp].  The current state
permits batch handling of video downloads, either serially or concurrently, and
playlist downloads.  Channel data can also be checked according to a channel
data file, which defaults to concurrent data retrieval.


## Current state


Currently, the wrapper provides more interesting messages (as well as less text
overall) such as individual video download progress and stage, and handles
retry messages and retry failures.

Some important scenarios are as yet unhandled.  Please open a ticket if you
would like to request a possible change, or fork this repo and make a pull
request if you would like to make a direct contribution.  Furthermore, I'm not
an expert developer and this is a bit of a pet project, so there will be wonky
bits, rough edges, and a somewhat slow dev cycle.  I am also exclusively
developing this on Linux systems (previously Ubuntu, now Fedora) so there may
be cross-platform incompatibilities.  For example, there is a known bug (of
currently unknown cause or source) running subprocess calls on the Ubuntu WSL,
which doesn't stop the video successfully downloading, but breaks console
output.


## Changes


**Future changes may include:**

* Renaming of components
* Additional exception or failure handling


## Contributors


* Me (@glm729)
* @TheSpectacledOne:
  * WSL testing and general ideas
* @tecosaur:
  * _Overwriteable_ definition; ported from his example in Julia


_This project is written as a wrapper for the yt-dlp utility [(project
page)][ytdlp]._


[ytdlp]: https://github.com/yt-dlp/yt-dlp
