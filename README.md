# bit-dhcp-utility
A simple and lightweight dhcp tool utilizing macOS bootpd as the backend.

There is no real manual for this tool as of yet, it is distributed merely as an experiment.

It is designed for use with the Bit Part bitbox, and will recognize a bitbox device when connected to a Mac, though you can use any network device on your system.

This is only compatible with macOS 14 and up. There are some differences in bootpd implementation in earlier versions of macOS. If this is something that you require, please make any necessary changes and submit a pull request.

# usage
The first time you run the script, you will be presented with the option to create a new config. The script itself leaves a cookie trail in the /etc/bootpd.plist file to know that it was previously edited using this script. 

The second time you run the script, you will be presented with management options.

**Note: the script will enable bootpd to run at system startup**

# useful related macOS commands
sudo log stream --process bootpd --info --debug
streams bootpd data 

# known issues
**Must be run as superuser**

When configuring you may get an error such as:

```
New configuration written to /etc/bootpd.plist
Load failed: 5: Input/output error
Try running `launchctl bootstrap` as root for richer errors.
bootpd service started successfully.
```

If you run the application again, you will find that despite the error bootpd is running with the new configuration. It will be fixed in a future commit.

# support
This product is offered without support. We will be able to take suggestions via Discord or Git Hub.
