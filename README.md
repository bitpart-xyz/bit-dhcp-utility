# bit-dhcp-utility
A simple and lightweight dhcp tool utilizing macOS bootpd as the backend.

There is no real manual for this tool as of yet, it is distributed merely as an experiment.

It is designed for use with the Bit Part bitbox, and will recognize a bitbox device when connected to a Mac, though you can use any network device on your system.

This is only compatible with macOS 14 and up. There are some differences in bootpd implementation in earlier versions of macOS. If this is something that you require, please fork the project and create your own version.

# useful related macOS commands
sudo log stream --process bootpd --info --debug
streams bootpd data 

# support
This product is offered without support. We will be able to take suggestions via Discord or Git Hub.
