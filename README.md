# Hatta wiki exporter

Do you have several years of personal notes stuck in a [Hatta
wiki](http://hatta-wiki.org/) instance and want to migrate them elsewhere?
Probably not. But hey, if you do, you've come to the right place! The
`convert.py` script in this repo will take a Hatta configuration file, read all
pages (and other files) out of the corresponding repository, and copy them to a
specified output directory. For example, my Hatta config file is stored in
`/home/me/.hattarc`, and looks like this:

```ini
[hatta]
port = 8080
interface = localhost
pages_path = /home/me/notes/wiki_pages/
repo_path = /home/me/notes/
math_url = mathjax
```

If I run `./convert.py ~/.hattarc out/`, then the `./out/` directory will be
created & populated with HTML files corresponding to my wiki pages. For more
advanced usage, consult the Hatta-to-gitit example in `convert-to-gitit.sh`, or
try `./convert.py --help`.
