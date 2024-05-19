To find serial name

`
ls /dev/tty.* -ls
`

To Write flash
`
esptool.py --chip esp32 --port /dev/tty.usbserial-0001 --baud 460800 write_flash -z 0x1000 ~/Downloads/ESP32_GENERIC-20240222-v1.22.2.bin
`

Control commands:
  - CTRL-A        -- on a blank line, enter raw REPL mode
  - CTRL-B        -- on a blank line, enter normal REPL mode
  - CTRL-C        -- interrupt a running program
  - CTRL-D        -- on a blank line, do a soft reset of the board
  - CTRL-E        -- on a blank line, enter paste mode