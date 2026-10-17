# What it's for

Scrutiny monitors hard drive health through S.M.A.R.T. data and shows trends in a web UI.

[Check out the project](https://github.com/AnalogJ/scrutiny)

# Why it's needed

It warns about failing drives based on real-world failure rates, before a drive dies and puts the pool at risk.

# Notes

1. Drives are passed through one by one (`/dev/sda` to `/dev/sdk`). When drives are added or replaced, the list needs updating. Device names can also shift between boots.

2. The `nightly-omnibus` image tracks the latest development build, which may occasionally be unstable.
