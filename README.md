# bit-dhcp-server
lightweight dhcp tool utilizing macOS bootpd

There is no real manual for this tool as of yet, it is distributed merely as an experiment.

It is designed for use with the Bit Part bitbox, and will recognize a bitbox device when connected to a Mac.

this is tested with macOS 14

# useful related macOS commands
sudo log stream --process bootpd --info --debug
gathers bootpd data 
