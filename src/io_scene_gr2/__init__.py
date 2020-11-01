bl_info = {
    "name": "Divinity Collada Importer",
    "author": "VirtualBrain#8571",
    "blender": (2, 90, 0),
    "location": "File > Import-Export",
    "description": ("Import Collada/Granny files for Divinity: Original Sin 2 and Metin2."),
    "warning": "Metin2 is in beta.",
    "wiki_url": ("https://github.com/Virtual-Brain/dos2de_collada_importer"),
    "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Import-Export"}

import bpy


from bpy.path import display_name_from_filepath
from bpy.types import Operator, OperatorFileListElement, AddonPreferences, PropertyGroup, Panel
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, EnumProperty, PointerProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

import os
import subprocess
import re

class DivinityImporterAddonPreferences(AddonPreferences):
    bl_idname = "dos2de_collada_importer"
    divine_path : StringProperty(
        name="Divine Path",
        description="The path to divine.exe, used to convert from gr2 to dae",
        subtype="FILE_PATH"
    )

    extracted_assets_dir : StringProperty(
        name="Shared Assets",
        description="The path to extracted assets from Shared.pak. This should be Public/Shared/Assets.\nThis is used to automatically fetch conforming skeletons",
        subtype="DIR_PATH"
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.label(text="General:", icon="OUTLINER_DATA_META")
        row = box.row()
        row.prop(self, "divine_path")
        row = box.row()
        row.prop(self, "extracted_assets_dir")


base_skeleton_directories = ["Dwarves", "Elves", "Humans", "Lizards"]
base_skeleton_dict = {}

def get_base_skeletons(scene, context):
    assets_dir = ""
    if "dos2de_collada_importer" in context.preferences.addons:
        preferences = context.preferences.addons["dos2de_collada_importer"].preferences
        if preferences is not None:
            if "extracted_assets_dir" in preferences:
                assets_dir = preferences.extracted_assets_dir
    
    skeletons = [("DISABLED", "Disabled", "")]
    skeletons.append(("AUTO", "Auto", "Auto-select a base skeleton to conform to, based on the file name.\nThis happens when importing, to support multiple imports"))

    if assets_dir != "" and os.path.isdir(assets_dir):
        characters_dir = os.path.join(assets_dir, "Characters")
        if os.path.isdir(characters_dir):
            for race in base_skeleton_directories:
                race_dir = os.path.join(characters_dir, race)
                if os.path.isdir(race_dir):
                    base_skeleton_f = os.path.join(race_dir, race + "_Female_Base.gr2")
                    base_skeleton_m = os.path.join(race_dir, race + "_Male_Base.gr2")

                    global base_skeleton_dict

                    if os.path.isfile(base_skeleton_f):
                        key = race + "_Female"
                        display = race + " Female"
                        skeletons.append((key, display, base_skeleton_f))
                        base_skeleton_dict[key] = (base_skeleton_f, race, "Female")

                    if os.path.isfile(base_skeleton_m):
                        key = race + "_Male"
                        display = race + " Male"
                        skeletons.append((key, display, base_skeleton_m))
                        base_skeleton_dict[key] = (base_skeleton_m, race, "Male")

    return skeletons

rename_race_patterns = [
    ("Dwarves_Female", "DF"), 
    ("Dwarves_Male", "DM"),
    ("Elves_Female", "EF"),
    ("Elves_Male", "EM"),
    ("Humans_Female", "HF"),
    ("Humans_Male", "HM"),
    ("Lizards_Female", "LF"),
    ("Lizards_Male", "LM")
]

rename_patterns = [
    ("_MeshShape", "")
]

hero_pattern = re.compile(r'.*(Dwarves|Elves|Humans|Lizards)_(Male|Female)')

texture_pattern_basecolor = "{}.*?_(BM|BMA).dds"
texture_pattern_mskcloth = "{}.*?_(MSKcloth).dds"
texture_pattern_mskskin = "{}.*?_(MSKskin).dds"
texture_pattern_normalmap = "{}.*?_(NM).dds"
texture_pattern_physical = "{}.*?_(PM).dds"

class DOS2_Material_Textures():
    def __init__(self, bm=None, nm=None, pm=None):
        self.basecolor = bm
        self.normalmap = nm
        self.physicalmap = pm
        self.textures = [bm,nm,pm]

def get_textures(obj, filename, context, assets_dir):
    textures = None
    m = hero_pattern.match(filename)
    if m != None:
        race = m.group(1)
        gender = m.group(2)
        racegender = "{}_{}".format(race, gender)
        textures_dir = os.path.join(assets_dir, "Textures/Characters/{}/{}".format(race, racegender))
        if os.path.isdir(textures_dir):
            bm_pattern = re.compile(texture_pattern_basecolor.format(filename))
            nm_pattern = re.compile(texture_pattern_normalmap.format(filename))
            pm_pattern = re.compile(texture_pattern_physical.format(filename))
            files = list([f for f in os.listdir(textures_dir) if f.endswith(".dds")])
            basemap_texture = next(iter([f for f in files if bm_pattern.match(f)]), None)
            normalmap_texture = next(iter([f for f in files if nm_pattern.match(f)]), None)
            physicalmap_texture = next(iter([f for f in files if pm_pattern.match(f)]), None)
            if basemap_texture != None:
                basemap_texture = os.path.join(textures_dir, basemap_texture)
            if normalmap_texture != None:
                normalmap_texture = os.path.join(textures_dir, normalmap_texture)
            if physicalmap_texture != None:
                physicalmap_texture = os.path.join(textures_dir, physicalmap_texture)
            textures = DOS2_Material_Textures(
                bm=basemap_texture, 
                nm=normalmap_texture, 
                pm=physicalmap_texture
            )
    else:
        textures = DOS2_Material_Textures()
    return textures

def float_lerp(a, b, t):
    return (1.0 - t) * a + t * b

def sum_heights(nodes_array):
    result = 0
    for node in nodes_array:
        result = result + node.height
    return result

def sum_widths(depth_nodes):
    result = 0
    for depth in depth_nodes:
        max_width = 0
        for node in depth_nodes[depth]:
            if max_width < node.width:
                max_width = node.width
        result = result + max_width
    return result

def calc_priority_by_socket(node):
    if len(node.inputs) is 0:
        return -9999
    if len(node.outputs) is 0:
        return 9999

    result = 0
    for in_socket in node.inputs:
        if in_socket.is_linked:
            for link in in_socket.links:
                if link.is_valid:
                    if len(link.from_node.inputs) is 0:
                        result -= 1
                    else:
                        result += 2

    for out_socket in node.outputs:
        if out_socket.is_linked:
            for link in out_socket.links:
                if link.is_valid:
                    if len(link.to_node.outputs) is 0:
                        result += 10
                    else:
                        result -= 1

    return result

def arrange_nodes(node_array, calc_priority, horiz_padding=0.125, vert_padding=0.125):

    # Create a dictionary where the key is the
    # depth and the value is an array of nodes.
    depth_nodes = {}
    for node in node_array:

        depth = calc_priority(node)
        if depth in depth_nodes:

            # Add the node to the node array at that depth.
            depth_nodes[depth].append(node)
        else:

            # Begin a new array.
            depth_nodes[depth] = [node]

    # Add padding to half the width.
    extents_w = (0.5 + horiz_padding) * sum_widths(depth_nodes)
    t_w_max = 0.5
    sz0 = len(depth_nodes)
    if sz0 > 1:
        t_w_max = 1.0 / (sz0 - 1)

    # List of dictionary KVPs.
    depths = sorted(depth_nodes.items())
    depths_range = range(0, sz0, 1)
    for i in depths_range:
        nodes_array = depths[i][1]
        t_w = i * t_w_max
        x = float_lerp(-extents_w, extents_w, t_w)

        extents_h = (0.5 + vert_padding) * sum_heights(nodes_array)
        t_h_max = 0.5
        sz1 = len(nodes_array)
        if sz1 > 1:
            t_h_max = 1.0 / (sz1 - 1)

        nodes_range = range(0, sz1, 1)
        for j in nodes_range:
            node = nodes_array[j]
            t_h = j * t_h_max
            y = float_lerp(-extents_h, extents_h, t_h)
            half_w = 0.5 * node.width
            half_h = 0.5 * node.height
            node.location.xy = (x - half_w, y - half_h)

def get_image(file, context):
    if file != "" and file != None:
        for img in bpy.data.images:
            if img.filepath != "" and img.filepath != None:
                if img.filepath == file:
                    return img
                elif bpy.path.basename(img.filepath) == bpy.path.basename(file):
                    img.filepath = file
                    return img
        print("Loading image: " + file)
        img = bpy.data.images.load(file, check_existing=True)
        return img
    return None

def get_node_type(nodes, name):
    for x in nodes:
        print("{} ? {}".format(x.bl_idname, name))
        if name in x.bl_idname:
            return x
    return None

def offset_node_x(node, bynode, padding=50):
    node.location[0] = (bynode.location[0] + bynode.width) + padding
    node.location[1] = bynode.location[1]

def offset_node_y(node, bynode, padding=200):
    node.location[1] = (bynode.location[1] - bynode.height) - padding
    node.location[0] = bynode.location[0]

def create_dos2de_nodes(mat, context, textures=None):
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    diffuse = get_node_type(nodes, "ShaderNodeBsdfDiffuse")
    if diffuse is not None:
        #diffuse = nodes.new("ShaderNodeBsdfDiffuse")
        nodes.remove(diffuse)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    #diffuse.location = (50,0)

    bm_input = 0
    nm_input = 17
    metal_input = 4
    roughness_input = 7

    index = 0
    for inputnode in shader.inputs:
        if inputnode.name == "Normal":
            nm_input = index
        elif inputnode.name == "Roughness":
            roughness_input = index
        elif inputnode.name == "Metalness":
            metal_input = index
        elif inputnode.name == "Base Color":
            bm_input = index
        index = index + 1

    bm_node = nodes.new("ShaderNodeTexImage")
    bm_node.location = (10,0)
    bm_node.label = "BaseColor"
    if textures != None:
        bm_tex = get_image(textures.basecolor, context)
        bm_node.image = bm_tex
    links.new(bm_node.outputs[0], shader.inputs[bm_input])

    pm_node = nodes.new("ShaderNodeTexImage")
    offset_node_y(pm_node, bm_node)
    pm_node.label = "PhysicalMap"
    if textures != None:
        pm_tex = get_image(textures.physicalmap, context)
        pm_node.image = pm_tex
    pm_node.color_space = "NONE"
    pmsep_node = nodes.new("ShaderNodeSeparateXYZ")
    offset_node_x(pmsep_node, pm_node)
    links.new(pm_node.outputs[0], pmsep_node.inputs[0])
    links.new(pmsep_node.outputs[0], shader.inputs[metal_input])
    links.new(pmsep_node.outputs[1], shader.inputs[roughness_input])

    nm_node = nodes.new("ShaderNodeTexImage")
    offset_node_y(nm_node, pm_node)
    nm_node.label = "NormalMap"
    if textures != None:
        nm_tex = get_image(textures.normalmap, context)
        nm_node.image = nm_tex
    nm_node.color_space = "NONE"

    sep_node = nodes.new("ShaderNodeSeparateXYZ")
    offset_node_x(sep_node, nm_node)
    invert_node = nodes.new("ShaderNodeInvert")
    offset_node_x(invert_node, sep_node)
    combine_node = nodes.new("ShaderNodeCombineXYZ")
    offset_node_x(combine_node, invert_node)
    vector_node = nodes.new("ShaderNodeNormalMap")
    offset_node_x(vector_node, combine_node)
    links.new(nm_node.outputs[0], sep_node.inputs[0])
    links.new(nm_node.outputs[1], combine_node.inputs[0]) # Alpha to Red Channel
    links.new(sep_node.outputs[1], invert_node.inputs[1]) # Invert Green for OpenGL
    links.new(sep_node.outputs[2], combine_node.inputs[2]) # Blue to Blue Channel
    links.new(invert_node.outputs[0], combine_node.inputs[1]) # Inverted Green to Green Channel
    links.new(combine_node.outputs[0], vector_node.inputs[0]) # Combined XYZ to Normal Map
    links.new(vector_node.outputs[0], shader.inputs[nm_input])

    offset_node_x(shader, vector_node)
    shader.location[1] = bm_node.location[1]

    output = get_node_type(nodes, "ShaderNodeOutputMaterial")
    if output is None:
        output = nodes.new("ShaderNodeOutputMaterial")
    offset_node_x(output, shader)
    links.new(shader.outputs[0], output.inputs[0])

def create_material(mat_name, obj, file, context, assets_dir):
    textures = get_textures(obj, file, context, assets_dir)
    if textures != None:
        mat = bpy.data.materials.new(mat_name)
        obj.data.materials.append(mat)
        mat.use_nodes = True
        create_dos2de_nodes(mat, context, textures)

            #arrange_nodes(nodes, calc_priority_by_socket)
        return True
    #except Exception as e:
    #    print("[DOS2DE-Importer:create_material] Error creating material for '{}':\n    {}".format(obj.name, e))
    #    return False

class DOS2DE_IMPORTER_OT_nodes_create_material(Operator):
    """Insert a basic PBR node setup for DOS2DE textures"""
    bl_label = "Insert PBR Nodes"
    bl_idname = "dos2deimporter.nodes_createbasicmaterialoperator"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.active_material is not None

    def execute(self, context):
        mat = context.active_object.active_material
        create_dos2de_nodes(mat, context)
        return {'FINISHED'}

    def draw(self, context):
        pass

    def invoke(self, context, _event):
        return self.execute(context)

class NODE_PT_dos2de_material_helpers(Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_label = "DOS2DE Helpers"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.active_material is not None

    # def draw_header(self, context):
    #     node = context.active_node
    #     self.layout.prop(node, "use_custom_color", text="")

    def draw(self, context):
        layout = self.layout
        node = context.active_node
        row = layout.row()
        col = row.column(align=True)
        col.operator(DOS2DE_IMPORTER_OT_nodes_create_material.bl_idname)

class DOS2DEImporterSettings(PropertyGroup):
    bl_label = "Divinity Collada Importer"
    # LeaderHelpers Operator Settings
    toggled : BoolProperty(default=False, options={"HIDDEN"})

    # File Browser
    directory : StringProperty(
        name="Start Directory",
        description="The starting directory of the file browser",
        default=""
    )

    filter_search : StringProperty(
        name="Filter",
        description="File patterns to filter with in the file browser",
        default=""
    )

    recursion_level : EnumProperty(
        name="Search Depth",
        description="Number of directories to search within",
        items=(
            ("BLEND", "Blend File", "List .blend files’ content"),
            ("ALL_3", "Three Levels", "List all sub-directories’ content, three levels of recursion"),
            ("ALL_2", "Two Levels", "List all sub-directories’ content, two levels of recursion"),
            ("ALL_1", "One Level", "List all sub-directories’ content, one level of recursion"),
            ("NONE", "None", "Only list current directory’s content, with no recursion"),
        ),
        default="NONE"
    )

    # General Options
    apply_transformation : BoolProperty(
		name="Apply Transformations",
		description="Apply all object transformations on imported objects. Useful if the model is y-up, which comes with a X 90 rotation",
		default=True)
			
    delete_objects : EnumProperty(
		name="Delete",
		description="Delete imported objects of type",
		items=(
			("ALL", "All", "Typically for animations, delete all objects and preserve only actions"),
			("MESH", "Meshes", ""),
			("ARMATURE", "Armatures", ""),
			("DISABLED", "None", "")
		),
		default="DISABLED"
	)

    rename_armatures : EnumProperty(
		name="Armatures",
		description="Rename new armatures with the chosen pattern",
		items=(
			("SHORTHAND", "Race Shorthand", 
				"For Divinity models designed for a race/gender, turns the name into a shorthand, i.e. Humans_Female becomes HF"),
			("FILE", "Filename", "Use the name of the file, prefixed with the object type"),
			("FILE_SHORTHAND", "Filename & Shorthand", "Use the name of the file and replace race patterns"),
			("DISABLED", "Disabled", "")
		),
		default="FILE_SHORTHAND"
    )

    rename_meshes : EnumProperty(
		name="Meshes",
		description="Rename new meshes with the chosen pattern",
		items=(
			("SHORTHAND", "Race Shorthand", 
				"For Divinity models designed for a race/gender, turns the name into a shorthand, i.e. Humans_Female becomes HF"),
			("FILE", "Filename", "Use the name of the file, prefixed with the object type"),
            ("FILE_SHORTHAND", "Filename & Shorthand", "Use the name of the file and replace race patterns"),
			("DISABLED", "Disabled", "")
		),
		default="SHORTHAND"
    )

    use_rename_junk : BoolProperty(
		name="Replace Fluff",
		description="Rename fluff in imported object names, such as 'MeshShape' for meshes",
		default=True)

    use_build_material : BoolProperty(
		name="Create Materials",
		description="Automatically find associated textures and build materials. Only guaranteed to work if names match and the Shared assets directory is set",
		default=False)

    auto_connect : BoolProperty(
		name="Auto Connect",
		description="Set use_connect for parent bones which have exactly one child bone",
		default=False)

    find_chains : BoolProperty(
		name="Find Bone Chains",
		description="Find best matching Bone Chains and ensure bones in chain are connected",
		default=False)

    min_chain_length : IntProperty(
		name="Minimum Chain Length",
		description="When searching Bone Chains disregard chains of length below this value",
		default=0)

    fix_orientation : BoolProperty(
		name="Fix Leaf Bones",
		description="Fix Orientation of Leaf Bonese",
		default=False)

    import_units : BoolProperty(
		name="Import Units",
		description="If disabled match import to Blender’s current Unit settings, otherwise use the settings from the Imported scene",
		default=False)

    keep_bind_info : BoolProperty(
		name="Keep Bind Info",
		description="Store Bindpose information in custom bone properties for later use during Collada export",
		default=True)

    # Animation Options
    action_autorename : BoolProperty(
		name="Rename Imported Actions",
		description="Rename actions to the name of the file",
		default=True)

    action_set_fake_user : BoolProperty(
		name="Set Fake User",
		description="Set a fake user on newly imported actions",
		default=True)

    action_offset_zero : BoolProperty(
		name="Start at Frame 1",
		description="Offset animation start frames to begin at frame 1 (Blender's default)",
		default=True)

    action_clean_enabled : BoolProperty(
		name="Clean",
		description="Simplify F-Curves by removing closely spaced keyframes",
		default=False)

    action_clean_threshold : FloatProperty(
		name="Threshold",
		description="The threshold to use when cleaning",
        precision=4,
		default=0.001)

    action_clean_channels : BoolProperty(
		name="Channels",
		description="Clean channels along with keyframes",
		default=False)

    # GR2 Options
    gr2_delete_dae : BoolProperty(
		name="Delete DAE",
		description="When importing from gr2, delete the temporary .dae file that gets created",
		default=True)

    gr2_conform_enabled : BoolProperty(
		name="Conform",
		description="When importing from gr2, conform the file to a specific skeleton",
		default=False)

    gr2_set_skeleton : BoolProperty(
        name="Skeleton:",
        description="Set the skeleton to conform to",
		options={"HIDDEN"},
        default=False)

    gr2_base_skeleton : EnumProperty(
		name="Base Skeletons",
		description="Auto-detected skeletons that can be used when conforming.\nThis setting will override the conform path set",
		items=get_base_skeletons)

    gr2_conform_skeleton_path : StringProperty(
		name="Skeleton",
		description="Conform the imported armature to the target skeleton",
		default="")
	
    conform_path_changed : BoolProperty(
		options={"HIDDEN"},
		default=False)

    def as_keywords(self):
        keywords = {}
        keywords["filter_search"] = self.filter_search
        keywords["apply_transformation"] = self.apply_transformation
        keywords["delete_objects"] = self.delete_objects
        keywords["rename_armatures"] = self.rename_armatures
        keywords["rename_meshes"] = self.rename_meshes
        keywords["use_rename_junk"] = self.use_rename_junk
        keywords["use_build_material"] = self.use_build_material
        keywords["auto_connect"] = self.auto_connect
        keywords["find_chains"] = self.find_chains
        keywords["min_chain_length"] = self.min_chain_length
        keywords["fix_orientation"] = self.fix_orientation
        keywords["import_units"] = self.import_units
        keywords["keep_bind_info"] = self.keep_bind_info
        keywords["action_autorename"] = self.action_autorename
        keywords["action_set_fake_user"] = self.action_set_fake_user
        keywords["action_offset_zero"] = self.action_offset_zero
        keywords["gr2_delete_dae"] = self.gr2_delete_dae
        keywords["gr2_conform_enabled"] = self.gr2_conform_enabled
        keywords["gr2_set_skeleton"] = self.gr2_set_skeleton
        keywords["gr2_base_skeleton"] = self.gr2_base_skeleton
        keywords["gr2_conform_skeleton_path"] = self.gr2_conform_skeleton_path
        keywords["conform_path_changed"] = self.conform_path_changed
        keywords["action_clean_enabled"] = self.action_clean_enabled
        keywords["action_clean_threshold"] = self.action_clean_threshold
        keywords["action_clean_channels"] = self.action_clean_channels
        #keywords["conform_path_changed"] = "conform_path_changed" in self
        return keywords

    def draw(self, layout, context, filepath="", settings_panel=True):
        box = layout.box()
        row = box.row(align=False)
        row.label(text="Import Data Options:", icon="MESH_DATA")
        row = box.row()
        row.prop(self, "import_units")
        row = box.row()
        row.prop(self, "apply_transformation")
        row = box.row()
        row.prop(self, "delete_objects")
        row = box.row()
        row.prop(self, "use_build_material")

        box = layout.box()
        row = box.row(align=False)
        row.label(text="Rename Options:", icon="AUTOMERGE_ON")
        row = box.row()
        row.prop(self, "rename_armatures")
        row = box.row()
        row.prop(self, "rename_meshes")
        row = box.row()
        row.prop(self, "use_rename_junk")

        box = layout.box()
        row = box.row(align=False)
        row.label(text="GR2 Import Options:", icon="MESH_DATA")
        row = box.row()
        row.prop(self, "gr2_delete_dae")

        row = box.row()
        row.prop(self, "gr2_conform_enabled", text="Enable Conforming", toggle=True)
        if self.gr2_conform_enabled:
            row = box.row()
            box = row.box()
            row = box.row()
            row.label(text="Conform Options: ", icon="MOD_ARMATURE")
            row = box.row()
            row.prop(self, "gr2_set_skeleton", toggle=True)
            if self.gr2_set_skeleton:
                skeleton_box = box.row().box()
                row = skeleton_box.row()
                row.label(text="Use Skeleton: ")
                row = skeleton_box.row()
                row.prop(self, "gr2_base_skeleton", text="")
                row = skeleton_box.row()
                row.label(text="Manual Path: ")
                row = skeleton_box.row()
                row.prop(self, "gr2_conform_skeleton_path", text="")
                op = row.operator(DOS2DEImporter_GR2_AddConformPath.bl_idname, icon="IMPORT", text="")
                if filepath == "":
                    op.filepath = self.gr2_conform_skeleton_path
                else:
                    op.filepath = filepath

        row = box.row()
        box = layout.box()
        row = box.row(align=False)
        row.label(text="Animation Options:", icon="ANIM_DATA")
        row = box.row()
        row.prop(self, "action_autorename")
        row = box.row()
        row.prop(self, "action_offset_zero")
        row = box.row()
        row.prop(self, "action_set_fake_user")
        row = box.row()
        row.prop(self, "action_clean_enabled")
        if self.action_clean_enabled:
            row = box.row()
            row.prop(self, "action_clean_threshold")
            row = box.row()
            row.prop(self, "action_clean_channels")

        box = layout.box()
        row = box.row(align=False)
        row.label(text="Armature Options:", icon="MESH_DATA")
        row = box.row()
        row.prop(self, "fix_orientation")
        row = box.row()
        row.prop(self, "find_chains")
        row = box.row()
        row.prop(self, "auto_connect")
        row = box.row()
        row.prop(self, "min_chain_length")

        box = layout.box()
        row = box.row(align=False)
        row.prop(self, "keep_bind_info")

        if settings_panel == True:
            box = layout.box()
            row = box.row(align=False)
            row.label(text="Default File Search:", icon="FILE")
            row = box.row(align=False)
            row.prop(self, "filter_search")
            row = box.row(align=False)
            row.prop(self, "recursion_level")
            row = box.row(align=False)
            row.prop(self, "directory")


def transform_apply(self, context, obj, location=False, rotation=False, scale=False, children=False):
    last_active = getattr(bpy.context.scene.objects, "active", None)
    recurse_targets = []
    try:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action='DESELECT')
        bpy.context.scene.objects.active = obj
        obj.select = True
        bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)

        if children:
            for childobj in obj.children:
                childobj.select = True
                if childobj.children is not None:
                    recurse_targets.append(childobj)
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.transform_apply(location=location, rotation=rotation, scale=scale)
            bpy.ops.object.select_all(action='DESELECT')
        obj.select = False
    except:
        pass

    if last_active is not None:
        bpy.context.scene.objects.active = last_active
    if len(recurse_targets) > 0:
        for recobj in recurse_targets:
            transform_apply(self, context, recobj, location, rotation, scale, children)

def can_delete(objtype, delete_objects):
    return (delete_objects == "ALL" or (delete_objects == "ARMATURE" and objtype == "ARMATURE") 
                or (delete_objects == "MESH" and objtype == "MESH"))

lastNum = re.compile(r'(?:[^\d]*(\d+)[^\d]*)+')

def increment_string(s):
    m = lastNum.search(s)
    if m:
        next = str(int(m.group(1))+1)
        start, end = m.span(1)
        s = s[:max(end-len(next), start)] + next + s[end:]
    else:
        s = s + "_1"
    return s

def safe_rename(obj, context, next_name):
    if obj.type == "ARMATURE":
        for check in bpy.data.armatures:
            if check != obj.data and check.name == next_name:
                next_name = increment_string(next_name)
    elif obj.type == "MESH":
        for check in bpy.data.meshes:
            if check != obj.data and check.name == next_name:
                next_name = increment_string(next_name)
    obj.name = next_name
    obj.data.name = next_name

def import_collada(operator, context, load_filepath, rename_temp=False, **args):
    rename_actions = args["action_autorename"]
    use_build_material = args["use_build_material"]

    action_set_fake_user = args["action_set_fake_user"]
    action_offset_zero = args["action_offset_zero"]
    action_clean_enabled = args["action_clean_enabled"]
    action_clean_threshold = args["action_clean_threshold"]
    action_clean_channels = args["action_clean_channels"]

    gr2_conform_enabled = args["gr2_conform_enabled"]
    delete_objects_options = args["delete_objects"]
    rename_armatures = args["rename_armatures"]
    rename_meshes = args["rename_meshes"]
    use_rename_junk = args["use_rename_junk"]

    fix_orientation = args["fix_orientation"]
    auto_connect = args["auto_connect"]
    find_chains = args["find_chains"]
    min_chain_length = args["min_chain_length"]
    import_units = args["import_units"]
    apply_transformation = args["apply_transformation"]
    keep_bind_info = args["keep_bind_info"]

    #ignored_objects = list(filter(lambda obj: obj.type == "ARMATURE", context.scene.objects.values()))
    ignored_objects = context.scene.objects.values()

    print("[DOS2DE-Importer] Importing collada file: '{}'".format(load_filepath))

    bpy.ops.wm.collada_import(filepath=load_filepath, fix_orientation=fix_orientation, import_units=import_units, 
        find_chains=find_chains, auto_connect=auto_connect, min_chain_length=min_chain_length, keep_bind_info=keep_bind_info)

    parse_actions = action_offset_zero or rename_actions or action_set_fake_user
    if parse_actions:
        new_armatures = list(filter(lambda obj: obj.type == "ARMATURE" and obj.animation_data != None and not obj in ignored_objects, context.scene.objects.values()))
        if len(new_armatures) > 0:
            print("[DOS2DE-Importer] New Armature Objects: ({}). Parsing actions".format(len(new_armatures)))
            for ob in new_armatures:
                action = (ob.animation_data.action
                    if ob.animation_data is not None and
                    ob.animation_data.action is not None
                    else None)

                if action is not None:
                    action_name = action.name

                    if rename_actions:
                        new_name = bpy.path.display_name_from_filepath(load_filepath)
                        if rename_temp:
                            new_name = str.replace(new_name, "-temp", "")
                        operator.report({'INFO'}, "[DOS2DE-Importer] Renamed action '{}' to '{}'.".format(action_name, new_name))
                        ob.animation_data.action.name = new_name
                        action_name = new_name

                    if action_set_fake_user:
                        action.use_fake_user = True
                        print("[DOS2DE-Importer] Enabled fake user for action '{}'.".format(action_name))

                    if action_offset_zero:
                        fcurves = ob.animation_data.action.fcurves
                        for fc in fcurves:
                            for keyframe in fc.keyframe_points:
                                keyframe.co.x += 1

                    # if action_clean_enabled:
                    #     print("[DOS2DE-Importer] Cleaning action. Threshold '{}' Channels '{}'.".format(action_clean_threshold, action_clean_channels))
                    #     bpy.ops.object.select_all(action='DESELECT')
                    #     last = bpy.context.scene.objects.active
                    #     bpy.context.scene.objects.active = ob
                    #     ob.select = True
                    #     bpy.ops.object.mode_set(mode="POSE")
                    #     bpy.ops.action.clean(threshold=action_clean_threshold, channels=action_clean_channels)
                    #     #bpy.ops.action.clean(0.001, True)
                    #     bpy.ops.object.mode_set(mode="OBJECT")
                    #     ob.select = False
                    #     bpy.context.scene.objects.active = last

        else:
            #operator.report({'INFO'}, "[DOS2DE-Importer] No new actions to rename.")
            pass

    if apply_transformation:
        new_armatures = list(filter(lambda obj: not obj in ignored_objects, context.scene.objects.values()))
        for obj in new_armatures:
            print("[DOS2DE-Importer] Applying transformation for object '{}:{}' and children.".format(obj.name, obj.type))
            transform_apply(operator, context, obj, location=True, rotation=True, scale=True, children=True)

    if delete_objects_options != "DISABLED":
        delete_objects = list(filter(lambda obj: not obj in ignored_objects and can_delete(obj.type, delete_objects_options), context.scene.objects.values()))
        print("[DOS2DE-Importer] Deleting '{}' new objects after import.".format(len(delete_objects)))
        for obj in delete_objects:
            index = bpy.data.objects.find(obj.name)
            if index > -1:
                obj_data = bpy.data.objects[index]
                print("[DOS2DE-Importer] Deleting object '{}:{}'.".format(obj.name, obj.type))
                bpy.data.objects.remove(obj_data)
    
    rename_objects = (rename_armatures != "DISABLED" or rename_meshes != "DISABLED")

    if rename_objects == True:
        new_objects = list(filter(lambda obj: not obj in ignored_objects, context.scene.objects.values()))
        filename = os.path.basename(load_filepath).replace("-temp", "")
        index_of_dot = filename.index('.')
        if index_of_dot >= 0:
            filename = filename[:index_of_dot]

        for obj in new_objects:
            name_prefix = ""
            next_name = ""
            rename_option = "DISABLED"
            if obj.type == "ARMATURE":
                rename_option = rename_armatures
            if obj.type == "MESH":
                rename_option = rename_meshes

            if rename_option != "DISABLED":
                if obj.type == "ARMATURE":
                    name_prefix = "Arm_"
                elif obj.type == "MESH":
                    pass
                if rename_option == "FILE" or rename_option == "FILE_SHORTHAND":
                    next_name = "{}{}".format(name_prefix, filename)
                elif rename_option == "SHORTHAND":
                    next_name = "{}{}".format(name_prefix, obj.name)
                if rename_option == "SHORTHAND" or rename_option == "FILE_SHORTHAND":
                    for pattern in rename_race_patterns:
                        next_name = next_name.replace(pattern[0], pattern[1])
                if next_name != "":
                    if use_rename_junk:
                        for pattern in rename_patterns:
                            next_name = next_name.replace(pattern[0], pattern[1])
                    print("[DOS2DE-Importer] Renaming object '{} => {}'.".format(obj.name, next_name))
                    safe_rename(obj, context, next_name)

    if use_build_material:
        assets_dir = ""
        if "dos2de_collada_importer" in context.preferences.addons:
            preferences = context.preferences.addons["dos2de_collada_importer"].preferences
            if preferences is not None:
                if "extracted_assets_dir" in preferences:
                    assets_dir = preferences.extracted_assets_dir
        if assets_dir != "":
            check_findname = os.path.basename(load_filepath).replace("-temp.dae", "")
            new_meshes = list(filter(lambda obj: not obj in ignored_objects and obj.type == "MESH", context.scene.objects.values()))
            for mesh in new_meshes:
                mat_name="{}_DOS2DE_PBR".format(obj.name)
                mat = bpy.data.materials.get(mat_name)
                if mat is None:
                    if create_material(mat_name, mesh, check_findname, context, assets_dir):
                        print("[DOS2DE-Importer] Created material for '{}'".format(mesh.name))
                else:
                    mesh.data.materials.append(mat)
    return True

def import_granny(operator, context, load_filepath, divine_path, **args):
    gr2_conform_enabled = args["gr2_conform_enabled"]
    if gr2_conform_enabled == True:
        conform_skeleton_path = args["gr2_conform_skeleton_path"]

        base_skeleton = args["gr2_base_skeleton"]
        autoselect = base_skeleton != None and base_skeleton == "AUTO"

        if base_skeleton is not None and base_skeleton != "DISABLED":
            if autoselect == True:
                filename = os.path.basename(load_filepath)
                print("  [DOS2DE-Importer] Auto-select base skeleton set. Looking for match in name {}".format(load_filepath))

                auto_skeleton = None
                for key,entry in base_skeleton_dict.items():
                    base_file = entry[0]
                    if filename.count(key) > 0:
                        auto_skeleton = base_file
                        break
                    else:
                        race = entry[1]
                        gender = entry[2]
                        if filename.count(race + "_Hero_"+gender) > 0:
                            auto_skeleton = base_file
                            break

                if auto_skeleton is not None and os.path.isfile(auto_skeleton):
                    conform_skeleton_path = auto_skeleton
                    print("    [DOS2DE-Importer] Auto-selected skeleton {}".format(auto_skeleton))
                else:
                    print("    [DOS2DE-Importer] No auto base skeleton found.")

            else:
                print("[DOS2DE-Importer] Looking for '{}'.".format(base_skeleton))
                if base_skeleton in base_skeleton_dict.keys():
                    check_path = base_skeleton_dict[base_skeleton][0]
                    if os.path.isfile(check_path):
                        conform_skeleton_path = check_path
                        print("[DOS2DE-Importer] Using base skeleton '{}'.".format(conform_skeleton_path))
        else:
            print("[DOS2DE-Importer] No base skeleton set. Using conform path.")
    else:
        conform_skeleton_path = ""
    delete_dae = args["gr2_delete_dae"]

    divine_exe = '"{}"'.format(divine_path)
    
    from pathlib import Path
    path_start = Path(load_filepath)
    dae_temp_path = str(Path(str(path_start.with_suffix("")) + "-temp.dae"))

    if gr2_conform_enabled and conform_skeleton_path is not None and os.path.isfile(conform_skeleton_path):
        gr2_options_str = "-e conform -e conform-copy --conform-path \"{}\"".format(conform_skeleton_path)
    else:
        gr2_options_str = ""

    proccess_args = "{} --loglevel all -g dos2de -s \"{}\" -d \"{}\" -i gr2 -o dae -a convert-model {}".format(
        divine_exe, load_filepath, dae_temp_path, gr2_options_str)

    print("Starting GR2->DAE conversion using divine.exe.")
    print("Sending command: {}".format(proccess_args))

    process = subprocess.run(proccess_args, 
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    print(process.stdout)

    if process.returncode != 0:
        #raise Exception("Error converting DAE to GR2: \"{}\"{}".format(process.stderr, process.stdout))
        error_message = "[DOS2DE-Importer] [ERROR:{}] Error converting GR2 to DAE. {}".format(process.returncode, '\n'.join(process.stdout.splitlines()[-1:]))
        operator.report({"ERROR"}, error_message)
        print(error_message)
    else:
        #Deleta .dae
        print("[DOS2DE-Importer] Importing temp dae file: '{}'.".format(dae_temp_path))
        if import_collada(operator, context, load_filepath=dae_temp_path, rename_temp=True, **args):
            if delete_dae:
                print("[DOS2DE-Importer] Deleting temp file: '{}'.".format(dae_temp_path))
                if os.path.isfile(dae_temp_path):
                    os.remove(dae_temp_path)
            return True
        else:
            print("Failed?")
    return False

def import_start(operator, context, load_filepath, divine_path, **args):
    name = os.path.split(load_filepath)[-1].split(".")[0]
    parts = os.path.splitext(load_filepath)
    ext = parts[1].lower()

    print("[DOS2DE-Importer] Importing file: '{}'.".format(load_filepath))

    # Ignore current armatures when renaming actions
    ignored_objects = list(filter(lambda obj: obj.type == "ARMATURE", context.scene.objects.values()))
    #print("[DOS2DE-Importer] Ignored Objects {}".format(len(ignored_objects)))
    if ext == ".dae":
        return import_collada(operator, context, load_filepath, **args)
    elif ext == ".gr2":

        if divine_path != "" and os.path.isfile(divine_path):
            return import_granny(operator, context, load_filepath, divine_path, **args)
        else:
            operator.report({"ERROR"}, "[DOS2DE-Importer] Failed to find divine.exe at path: '{}'. Canceling GR2 import.".format(divine_path))
    else:
        raise RuntimeError("[DOS2DE-Importer] Unknown extension: %s" % ext)
        return False
    return True

class DOS2DEImporter_FileSelectorOperator(bpy.types.Operator):
    bl_idname = "dos2deimporter.op_fileselector"
    bl_label = "Select File"

    filename_ext = ".gr2"

    filepath : bpy.props.StringProperty(subtype="FILE_PATH") 

    def execute(self, context):
        display = "filepath= "+self.filepath  
        return {'FINISHED'}

    def invoke(self, context, event): 
        context.window_manager.invoke_popup(self) 
        return {'RUNNING_MODAL'} 

class DOS2DEImporter_GR2_AddConformPath(Operator):
    """Use the selected file as the skeleton to conform to"""
    bl_idname = "dos2deimporter.op_gr2_addconformpath"
    bl_label = ""

    filepath : StringProperty(default="", subtype="FILE_PATH")
    updated : BoolProperty(default=False, options={'HIDDEN'})
    file_ext = ".gr2"

    def execute(self, context):
        if self.filepath != "":
            settings = getattr(context.scene, "dos2de_importer_settings", None)
            if settings != None:
                settings.gr2_conform_skeleton_path = self.filepath
                settings.conform_path_changed = True
                print("[DOS2DE-Importer] Set pathway to '{}.'".format(self.filepath))
                updated = True

        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)

class ImportDivinityCollada(bpy.types.Operator, ImportHelper):
    """Load a Divinity .dae file"""
    bl_idname = "import_scene.divinitycollada"
    bl_label = "Import"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".dae"
    filter_glob : StringProperty(
            default="*.dae;*.gr2",
            options={'HIDDEN'})

    files : CollectionProperty(
            name='File Path',
            type=OperatorFileListElement
            )

    directory : StringProperty(
            subtype='DIR_PATH'
            )

    settings = None
    
    debug_mode : BoolProperty(default=False, options={'HIDDEN'})

    def invoke(self, context, event):
        settings = getattr(context.scene, "dos2de_importer_settings", None)
        if settings is not None:
            if settings.directory != "":
                self.directory = settings.directory
            self.filter_search = settings.filter_search
            self.recursion_level = settings.recursion_level

        self.settings = settings
        if ((settings.gr2_conform_skeleton_path != "" and 
                os.path.isfile(settings.gr2_conform_skeleton_path)) or settings.gr2_base_skeleton != "DISABLED"):
            pass
        else:
            settings.gr2_conform_enabled = False

        if "laughingleader_blender_helpers" in context.preferences.addons:
            helper_preferences = context.preferences.addons["laughingleader_blender_helpers"].preferences
            if helper_preferences is not None:
                self.debug_mode = getattr(helper_preferences, "debug_mode", False)

        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        settings = self.settings
        if settings is not None:
            if settings.conform_path_changed:
                self.gr2_conform_skeleton_path = settings.gr2_conform_skeleton_path
                settings.conform_path_changed = False
            print("[DOS2DE-Importer] Saved importer settings to scene.")

            keywords = settings.as_keywords()

            selection = bpy.context.selected_objects
            last_active = getattr(bpy.context.scene.objects, "active", None)

            directory = self.directory
            settings.directory = directory

            divine_path = ""

            print(context.preferences.addons)
            if "dos2de_collada_importer" in context.preferences.addons:
                preferences = context.preferences.addons["dos2de_collada_importer"].preferences

                if preferences is not None and "divine_path" in preferences:

                    divine_path = preferences.divine_path

            for file_elem in self.files:
                filepath = os.path.join(directory, file_elem.name)
                #print("Selected file: {}".format(filepath))
                import_start(self, context, filepath, divine_path, **keywords)

            if(len(selection) > 0):
                for obj in selection:
                    obj.select_set(True)

            if last_active is not None:
                bpy.context.scene.objects.active = last_active

        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        #settings = getattr(context.scene, "settings", None)
        if self.settings is not None:
            self.settings.draw(layout, context, self.filepath, settings_panel=False)
        else:
            print("[DOS2DE-Importer] settings is None.")

import traceback

def menu_func_import(self, context):
    self.layout.operator(ImportDivinityCollada.bl_idname, text="Divinity Collada (.dae, .gr2)")


classes = (
    DOS2DEImporterSettings,
    DivinityImporterAddonPreferences,
    DOS2DE_IMPORTER_OT_nodes_create_material,
    NODE_PT_dos2de_material_helpers,
    DOS2DEImporter_FileSelectorOperator,
    DOS2DEImporter_GR2_AddConformPath,
    ImportDivinityCollada,
)


def register():
    try: 
        for cls in classes:
            bpy.utils.register_class(cls)

        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
        bpy.types.Scene.dos2de_importer_settings = PointerProperty(type=DOS2DEImporterSettings, 
            name="DOS2DE Import Settings",
            description="Persistent settings saved between imports for this specific scene"
        )

    except: traceback.print_exc()

def unregister():
    try: 
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

        for cls in classes:
            bpy.utils.unregister_class(cls)

    except: traceback.print_exc()