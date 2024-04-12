To Find Serial Name

`
ls /dev/tty.* -ls
`

*To Deploy and Run

`
ampy --port /[serialname] run main.py
`


Control commands:
  CTRL-A        -- on a blank line, enter raw REPL mode
  CTRL-B        -- on a blank line, enter normal REPL mode
  CTRL-C        -- interrupt a running program
  CTRL-D        -- on a blank line, do a soft reset of the board
  CTRL-E        -- on a blank line, enter paste mode