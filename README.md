# DOS2DE Collada Importer for Blender 2.90

An addon for Blender 2.90 that allows you to import dae/gr2 files for the game Divinity: Original Sin 2 and Metin2.


## DISCLAIMER

This fork is for the moment only an adaptation to the new API of blender 2.90, the [original work](https://github.com/LaughingLeader-DOS2-Mods/dos2de_collada_importer) is available in the sources, it is no longer maintained by its [creator](https://github.com/LaughingLeader-DOS2-Mods).
Like its original creation, this addon uses the [lslib library](https://github.com/Norbyte/lslib) from [Norbyte](https://github.com/Norbyte/), the hardest part of the work belongs to him by right. Let's thank him!



## Features:  
* Import from dae, or import from gr2 if the path to divine.exe is set.
* When importing from gr2, can conform to another file's skeleton.
* Auto-delete armatures/etc associated with animations when importing.
* Automatically rename imported animations to the name of the file.

## Installing

### Manual Method  
* Download this repository as a zip (using the green Clone or download button).
* Save the addon somewhere where you can find it again.
* Extract the zip.
* Copy the folder `dos2de_collada_importer`. Make sure this is the folder with the scripts under it (`dos2de_collada_importer\__init__.py` etc).
* Paste the `dos2de_collada_importer` folder into your addons folder. Default pathway:
```
%APPDATA%\Blender Foundation\Blender\2.79\scripts\addons
```
* (Optional) [You can set up a custom Scripts folder to use instead of your AppData folder via User Preferences -> File.](https://docs.blender.org/manual/en/latest/preferences/file.html#scripts-path)
* (Optional) Refer to Blender's guide for installing addons here: [Install from File](https://docs.blender.org/manual/en/latest/preferences/addons.html#header). It has a tip section for setting up a separate scripts/addons folder, outside of your appdata.

### Cloning  
* In Blender, navigate to File -> User Preferences -> File.
* The pathway for "Scripts" is where Blender will read new addon folders from. Add a pathway if it's blank.
* [Clone the repository](https://help.github.com/articles/cloning-a-repository/).
* Create a junction to the `dos2de_collada_importer` inside your scripts/addons folder.
  * You can create a junction with this command line command:
```
mklink /j "C:\Path1\dos2de_collada_importer" "C:\Path2\scripts\addons\dos2de_collada_importer"
```
| Rename | Description |
| --- | ----------- |
| Path1 | This should be the path where you cloned the repo. We want to junction the dos2de_collada_importer folder inside that contains all the py scripts.|
| Path2 | This is where your scripts/addons folder for Blender is. Either the AppData folder, or the custom scripts folder you set. We want to junction the dos2de_collada_importer folder with the py scripts to this folder. |
  * Alternatively, this program allows junction/symlink creation via right clicking files/folders in a file explorer: [Link Shell Extension](http://schinagl.priv.at/nt/hardlinkshellext/linkshellextension.html#download)
    * With this program installed, right click the dos2de_collada_importer folder and select "Pick Link Source", then go to scripts/addons, right click the background, and select Drop As... -> Junction.

### Activating the Addon  
* In Blender, navigate to File -> User Preferences -> Add-ons
* Either search for "Divinity", or click Community, then Import-Export.
* Check the checkbox next to "Divinity Collada Exporter".

### Troubleshooting
* I don't see the addon inside Blender.  
  Make sure the folder with the scripts (dos2de_collada_importer/__init__.py, etc) is the folder inside scripts/addons. Blender won't read a nested folder. For example, if your folder is located like so: `scripts/addons/dos2de_collada_importer/dos2de_collada_importer`, Blender won't load the scripts or recognize the addon.

## User Preferences Settings

### Divine Path  
This is the pathway to divine.exe, bundled with Norbyte's Export Tool. If set, the addon can import from the GR2 format, using divine.

## Credits
Special thanks to Norbyte for developing and maintaining [https://github.com/Norbyte/lslib](https://github.com/Norbyte/lslib), which is the sole reason we can even convert models to DOS2's format in the first place. 
