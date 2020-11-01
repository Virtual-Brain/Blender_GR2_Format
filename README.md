# GR2 Importer for Blender 2.90
  
An addon for Blender 2.90 that allows you to import gr2 files for the game Metin2.


## NOTICE

This fork is for the moment **only an adaptation to the new API of blender 2.90**, the [**original work**](https://github.com/LaughingLeader-DOS2-Mods/dos2de_collada_importer) is available in the credits, it is no longer maintained by its [**creator**](https://github.com/LaughingLeader-DOS2-Mods).

Like its original creation, this addon uses the [**lslib library**](https://github.com/Norbyte/lslib) from [**Norbyte**](https://github.com/Norbyte/), the hardest part of the work belongs to him by right. *Let's thank him* !


## DISCLAIMER

The final goal of this fork is to import/export .gr2 models from metin2.
The support of other convertible games by the lslib library will only be done after full support of Metin2.
Currently, the addon only allows to import .gr2 models from metin2, textures and animations are not supported.


## Features:

* Import from .gr2
* Auto-delete armatures/etc associated with animations when importing.
* Automatically rename imported animations to the name of the file.


## Installing


### Manual Method

* Copy the ***io_scene_gr2 folder*** from the *src folder* to the ***blender addons folder***.
	`Blender_GR2_Format/src/io_scene_gr2` -> `C:/Program Files/Blender Foundation/Blender 2.90/2.90/scripts/addons`


### Activating the Addon

* In Blender, navigate to File -> User Preferences -> Add-ons
* Either search for "GR2", or click Community, then Import-Export.
* Check the checkbox next to "GR2 Importer".
* In Preferences, add the path to the divine executable : `Blender Foundation/Blender 2.9x/2.9x/scripts/addons/io_scene_gr2/ExportTool-vx.x.x/divine.exe`


### Troubleshooting

* I don't see the addon inside Blender.

	*Make sure the folder with the scripts (io_scene_gr2/__init__.py, etc) is the folder inside scripts/addons.*
	*Blender won't read a nested folder. For example, if your folder is located like so: `scripts/addons/io_scene_gr2/io_scene_gr2`, Blender won't load the scripts or recognize the addon.*


## Credits
  
Special thanks to [Norbyte](https://github.com/Norbyte/) for developing and maintaining [lslib](https://github.com/Norbyte/lslib), which is the sole reason we can even convert models to DOS2's format in the first place.
And thanks to [LaughingLeader](https://github.com/LaughingLeader-DOS2-Mods) for for his initial work.