# ##### BEGIN GPL LICENSE BLOCK #####
#
# SPRIG Tools-Specify transformations relative to geometry in your scene.
# Copyright (C) 2015 Eric Gentry
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####
#
# <pep8-80 compliant>


# Blender requires addons to provide this information.
bl_info = {
    "name": "SPRIG Tools Alpha",
    "description": (
        "Precisely align, arrange and transform objects "
        "and mesh parts using real or imaginary geometry "
        "from your scene."
    ),
    "author": "Eric Gentry",
    "version": "0, 1",
    "blender": (2, 75, 0),
    "location": "Properties -> Scene -> MCT Tools",
    "warning": "Alpha release, there may be bugs.",
    "category": "Mesh"
}  # Todo/Fix, add more information here


import bpy
import bmesh
import math
import mathutils
import collections


# This is the basic data structure for the addon. The item can be a point,
# line, plane, calc, or transf (only one at a time), chosen by the user
# (defaults to point). A SPRIGPrimitive always has data slots for each of
# these types, regardless of which 'kind' the item is currently
class SPRIGPrimitive(bpy.types.PropertyGroup):
    name = bpy.props.StringProperty(
        name="Item name",
        description="The name of this item",
        default="Name"
    )
    kind = bpy.props.EnumProperty(
        items=[
            ('POINT', 'Point', 'Point Primitive'),
            ('LINE', 'Line', 'Line Primitive'),
            ('PLANE', 'Plane', 'Plane Primitive'),
            ('CALCULATION', 'Calculation', 'Calculation Primitive'),
            ('TRANSFORMATION', 'Transformation', 'Transformation Primitive')
        ],
        name="Item Type",
        default='POINT',
        description="The type of this item"
    )

    # Point primitive data/settings
    point = bpy.props.FloatVectorProperty(
        description="Point primitive coordinates",
        precision=6
    )
    pt_make_unit_vec = bpy.props.BoolProperty(
        description="Treat the point like a vector of length 1"
    )
    pt_flip_direction = bpy.props.BoolProperty(
        description=(
            "Treat the point like a vector pointing in"
            " the opposite direction"
        )
    )
    pt_multiplier = bpy.props.FloatProperty(
        description=(
            "Treat the point like a vector and multiply"
            " its length by this value"
        ),
        default=1.0,
        precision=6
    )

    # Line primitive data/settings
    line_start = bpy.props.FloatVectorProperty(
        description="Line primitive, starting point coordinates",
        precision=6
    )
    line_end = bpy.props.FloatVectorProperty(
        description="Line primitive, ending point coordinates",
        precision=6
    )
    ln_make_unit_vec = bpy.props.BoolProperty(
        description="Make the line's length 1"
    )
    ln_flip_direction = bpy.props.BoolProperty(
        description="Point the line in the opposite direction"
    )
    ln_multiplier = bpy.props.FloatProperty(
        description="Multiply the line's length by this amount",
        default=1.0,
        precision=6
    )

    # Plane primitive data
    plane_pt_a = bpy.props.FloatVectorProperty(
        description="Plane primitive, point A coordinates",
        precision=6
    )
    plane_pt_b = bpy.props.FloatVectorProperty(
        description="Plane primitive, point B coordinates",
        precision=6
    )
    plane_pt_c = bpy.props.FloatVectorProperty(
        description="Plane primitive, point C coordinates",
        precision=6
    )

    # Calculation primitive data/settings, FIX this placeholder value and
    # insert real props later (todo)
    calc = bpy.props.StringProperty(default='placeholder_fix')

    # Transformation primitive data/settings (several blocks)
    transf_type = bpy.props.EnumProperty(
        items=[
            ('POINTMATCH',
             'Point Match',
             'Match source vert location to destination'),
            ('VECTORSLIDE',
             'Vector Slide',
             'Moves a target in a direction'),
            ('SCALEMATCHEDGE',
             'Scale Match Edge',
             'Matches edge lengths'),
            ('MKCOLLINEAR',
             'Make Collinear',
             'Make lines parallel'),
            ('AXISROTATE',
             'Axis Rotate',
             'Rotates around an axis'),
            ('MKCOPLANAR',
             'Make Coplanar',
             'Make planes coplanar')
        ],
        name="Transf. Type",
        description="The type of transformation to perform",
        default='POINTMATCH'
    )

    # "Point match" (transformation) data/settings
    pm_pt_one = bpy.props.IntProperty(
        description=(
            "Pointer to an item in the list, the source point"
            " (this point will be 'moved' to match the destination)."
        ),
        default=0
    )
    pm_pt_two = bpy.props.IntProperty(
        description=(
            "Pointer to an item in the list, the destination point"
            " (this is a fixed reference location, where"
            " the source point will be 'moved' to)."
        ),
        default=0
    )
    pm_ln_make_unit_vec = bpy.props.BoolProperty(
        description="Set the move distance equal to one",
        default=False
    )
    pm_ln_flip_direction = bpy.props.BoolProperty(
        description="Flip the move direction",
        default=False
    )
    pm_multiplier = bpy.props.FloatProperty(
        description="Multiply the move by this amount",
        default=1.0,
        precision=6
    )

    # "Make coplanar" (transformation) data/settings
    mcp_src_plane = bpy.props.IntProperty(
        description=(
            "Pointer to an item in the list, the source plane"
            " (this plane will be 'moved' to match the destination)."
        ),
        default=0
    )
    mcp_dest_plane = bpy.props.IntProperty(
        description=(
            "Pointer to an item in the list, the destination plane"
            " (this is a fixed reference location, where"
            " the source plane will be 'moved' to)."
        ),
        default=0
    )
    mcp_flip_normal = bpy.props.BoolProperty(
        description="Flips the normal of the source plane",
        default=False
    )

    # "Make collinear" (transformation) data/settings
    mcl_src_line = bpy.props.IntProperty(
        description=(
            "Pointer to an item in the list, the source line"
            " (this line will be 'moved' to match the destination)."
        ),
        default=0
    )
    mcl_dest_line = bpy.props.IntProperty(
        description=(
            "Pointer to an item in the list, the destination line"
            " (this is a fixed reference location, where"
            " the source line will be 'moved' to)."
        ),
        default=0
    )
    mcl_ln_flip_direction = bpy.props.BoolProperty(
        description="Flip the source line direction",
        default=False
    )

    # "Axis rotate" (transformation) data/settings
    axr_axis = bpy.props.IntProperty(
        description="The axis to rotate around",
        default=0
    )
    axr_amount = bpy.props.FloatProperty(
        description=(
            "How much to rotate around the specified axis (in radians)"
        ),
        default=0,
        precision=6
    )

    # "Vector slide" (transformation) data/settings
    vs_direction = bpy.props.IntProperty(
        description="The direction to move",
        default=0
    )  # This is a list item pointer
    vs_ln_make_unit_vec = bpy.props.BoolProperty(
        description="Make the line's length 1",
        default=False
    )
    vs_ln_flip_direction = bpy.props.BoolProperty(
        description="Flip source line direction",
        default=False
    )
    vs_multiplier = bpy.props.FloatProperty(
        description="Multiply the source line's length by this amount",
        default=1.0,
        precision=6
    )

    # "Scale match edge" (transformation) data/settings
    sme_edge_one = bpy.props.IntProperty(
        description=(
            "Pointer to an item in the list, the source edge"
            " (this edge will be scaled to match"
            " the destination edge's length)."
        ),
        default=0
    )
    sme_edge_two = bpy.props.IntProperty(
        description=(
            "Pointer to an item in the list, the destination edge"
            " (this is a fixed reference edge, used to determine"
            " how much to scale the source edge so that its length"
            " matches the length of this edge)."
        ),
        default=0
    )


# Defines one instance of the addon data (one per scene)
class SPRIGData(bpy.types.PropertyGroup):
    prim_list = bpy.props.CollectionProperty(type=SPRIGPrimitive)
    # stores index of active primitive in my UIList
    active_list_item = bpy.props.IntProperty()
    use_experimental = bpy.props.BoolProperty(
        description=(
            'Mesh transformations are not currently'
            ' supported on objects with non-uniform'
            ' scaling. These are designated experimental'
            ' until non-uniform scaling is supported.'
        )
    )
    
    # Items for the quick operators
    quick_align_pts_show = bpy.props.BoolProperty(
        description=(
            "Expand/collapse the align points operator"
            " in the quick tools panel."
        ),
        default=False
    )
    quick_align_pts_src = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_align_pts_dest = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_align_pts_transf = bpy.props.PointerProperty(type=SPRIGPrimitive)
    
    quick_vector_slide_show = bpy.props.BoolProperty(
        description=(
            "Expand/collapse the vector slide operator"
            " in the quick tools panel."
        ),
        default=False
    )
    quick_vector_slide_src = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_vector_slide_dest = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_vector_slide_transf = bpy.props.PointerProperty(type=SPRIGPrimitive)
    
    quick_scale_match_edge_show = bpy.props.BoolProperty(
        description=(
            "Expand/collapse the scale match edge operator"
            " in the quick tools panel."
        ),
        default=False
    )
    quick_scale_match_edge_src = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_scale_match_edge_dest = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_scale_match_edge_transf = bpy.props.PointerProperty(type=SPRIGPrimitive)
    
    quick_make_collinear_show = bpy.props.BoolProperty(
        description=(
            "Expand/collapse the make collinear operator"
            " in the quick tools panel."
        ),
        default=False
    )
    quick_make_collinear_src = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_make_collinear_dest = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_make_collinear_transf = bpy.props.PointerProperty(type=SPRIGPrimitive)
    
    quick_axis_rotate_show = bpy.props.BoolProperty(
        description=(
            "Expand/collapse the axis rotate operator"
            " in the quick tools panel."
        ),
        default=False
    )
    quick_axis_rotate_src = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_axis_rotate_transf = bpy.props.PointerProperty(type=SPRIGPrimitive)
    
    quick_make_coplanar_show = bpy.props.BoolProperty(
        description=(
            "Expand/collapse the make coplanar operator"
            " in the quick tools panel."
        ),
        default=False
    )
    quick_make_coplanar_src = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_make_coplanar_dest = bpy.props.PointerProperty(type=SPRIGPrimitive)
    quick_make_coplanar_transf = bpy.props.PointerProperty(type=SPRIGPrimitive)


# Basic type selector functionality, derived classes provide
# the "kind" to switch to (target_type attrib)
class ChangeTypeBaseClass(bpy.types.Operator):
    # Todo...add dotted groups to bl_idname's
    bl_idname = "sprig.changetypebaseclass"
    bl_label = "Change type base class"
    bl_description = "The base class for changing types"
    bl_options = {'REGISTER', 'UNDO'}
    target_type = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        active_item.kind = self.target_type

        return {'FINISHED'}


class ChangeTypeToPointPrim(ChangeTypeBaseClass):
    bl_idname = "sprig.changetypetopointprim"
    bl_label = "Change this to a point primitive"
    bl_description = "Makes this item a point primitive"
    bl_options = {'REGISTER', 'UNDO'}
    target_type = 'POINT'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.kind == cls.target_type:
            return False
        return True


class ChangeTypeToLinePrim(ChangeTypeBaseClass):
    bl_idname = "sprig.changetypetolineprim"
    bl_label = "Change this to a line primitive"
    bl_description = "Makes this item a line primitive"
    bl_options = {'REGISTER', 'UNDO'}
    target_type = 'LINE'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.kind == cls.target_type:
            return False
        return True


class ChangeTypeToPlanePrim(ChangeTypeBaseClass):
    bl_idname = "sprig.changetypetoplaneprim"
    bl_label = "Change this to a plane primitive"
    bl_description = "Makes this item a plane primitive"
    bl_options = {'REGISTER', 'UNDO'}
    target_type = 'PLANE'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.kind == cls.target_type:
            return False
        return True


class ChangeTypeToCalcPrim(ChangeTypeBaseClass):
    bl_idname = "sprig.changetypetocalcprim"
    bl_label = "Change this to a calculation primitive"
    bl_description = "Makes this item a calculation primitive"
    bl_options = {'REGISTER', 'UNDO'}
    target_type = 'CALCULATION'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.kind == cls.target_type:
            return False
        return True


class ChangeTypeToTransfPrim(ChangeTypeBaseClass):
    bl_idname = "sprig.changetypetotransfprim"
    bl_label = "Change this to a transformation primitive"
    bl_description = "Makes this item a transformation primitive"
    bl_options = {'REGISTER', 'UNDO'}
    target_type = 'TRANSFORMATION'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.kind == cls.target_type:
            return False
        return True


# Basic transformation type selector functionality (a primitive sub-type),
# derived classes provide the transf. to switch to (target_transf attrib)
class ChangeTransfBaseClass(bpy.types.Operator):
    bl_idname = "sprig.changetransfbaseclass"
    bl_label = "Change transformation base class"
    bl_description = "The base class for changing tranf types"
    bl_options = {'REGISTER', 'UNDO'}
    target_transf = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        active_item.transf_type = self.target_transf

        return {'FINISHED'}


class ChangeTransfToPointMatch(ChangeTransfBaseClass):
    bl_idname = "sprig.changetransftopointmatch"
    bl_label = "Change transformation to point match"
    bl_description = "Change the transformation type to point match"
    bl_options = {'REGISTER', 'UNDO'}
    target_transf = 'POINTMATCH'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.transf_type == cls.target_transf:
            return False
        return True


class ChangeTransfToVectorSlide(ChangeTransfBaseClass):
    bl_idname = "sprig.changetransftovectorslide"
    bl_label = "Change transformation to vector slide"
    bl_description = "Change the transformation type to vector slide"
    bl_options = {'REGISTER', 'UNDO'}
    target_transf = 'VECTORSLIDE'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.transf_type == cls.target_transf:
            return False
        return True


class ChangeTransfToScaleMatchEdge(ChangeTransfBaseClass):
    bl_idname = "sprig.changetransftoscalematchedge"
    bl_label = "Change transformation to scale match edge"
    bl_description = "Change the transformation type to scale match edge"
    bl_options = {'REGISTER', 'UNDO'}
    target_transf = 'SCALEMATCHEDGE'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.transf_type == cls.target_transf:
            return False
        return True


class ChangeTransfToAxisRotate(ChangeTransfBaseClass):
    bl_idname = "sprig.changetransftoaxisrotate"
    bl_label = "Change transformation to axis rotate"
    bl_description = "Change the transformation type to axis rotate"
    bl_options = {'REGISTER', 'UNDO'}
    target_transf = 'AXISROTATE'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.transf_type == cls.target_transf:
            return False
        return True


class ChangeTransfToMkCollinear(ChangeTransfBaseClass):
    bl_idname = "sprig.changetransftomkcollinear"
    bl_label = "Change transformation to make collinear"
    bl_description = "Change the transformation type to make collinear"
    bl_options = {'REGISTER', 'UNDO'}
    target_transf = 'MKCOLLINEAR'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.transf_type == cls.target_transf:
            return False
        return True


class ChangeTransfToMkCoplanar(ChangeTransfBaseClass):
    bl_idname = "sprig.changetransftomkcoplanar"
    bl_label = "Change transformation to make coplanar"
    bl_description = "Change the transformation type to make coplanar"
    bl_options = {'REGISTER', 'UNDO'}
    target_transf = 'MKCOPLANAR'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if active_item.transf_type == cls.target_transf:
            return False
        return True


# Exception when adding new items, if we can't get a unique name
class UniqueNameError(Exception):
    pass


class AddListItem(bpy.types.Operator):
    bl_idname = "sprig.addlistitem"
    bl_label = "Add a new item"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def add_new_named():
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list

        # Add Name.001 or Name.002 (numbers at the end if the name is
        # already in use)
        name_list = {n.name for n in prims}
        name_counter = 0
        num_postfix_group = 1
        base_name = 'Item'
        cur_item_name = base_name
        num_format = '.{0:0>3}'
        keep_naming = True
        while keep_naming:
            name_counter += 1
            cur_item_name = base_name + num_format.format(str(name_counter))
            if num_postfix_group > 16:
                raise UniqueNameError('Cannot add, unique name error.')
            if name_counter == 999:
                name_counter = 0
                base_name += num_format.format('1')
                num_postfix_group += 1

            if not (base_name in name_list):
                cur_item_name = base_name
                keep_naming = False
                continue
            elif cur_item_name in name_list:
                continue
            else:
                keep_naming = False
                continue

        new_item = addon_data.prim_list.add()
        new_item.name = cur_item_name
        return new_item

    def execute(self, context):
        try:
            self.add_new_named()
        except UniqueNameError:
            self.report({'ERROR'}, 'Cannot add item, unique name error.')
            return {'CANCELLED'}

        return {'FINISHED'}


class RemoveListItem(bpy.types.Operator):
    bl_idname = "sprig.removelistitem"
    bl_label = "Remove an item"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list

        if len(prims) == 0:
            self.report({'WARNING'}, "Nothing to remove")
            return {'CANCELLED'}
        else:
            prims.remove(addon_data.active_list_item)
            if len(prims) == 0 or addon_data.active_list_item == 0:
                # ^ The extra or prevents act=0 from going to the else below
                addon_data.active_list_item = 0
            elif addon_data.active_list_item > (len(prims) - 1):
                addon_data.active_list_item = len(prims) - 1
            else:
                addon_data.active_list_item -= 1

        return {'FINISHED'}


class SpecialsAddFromActiveBase(bpy.types.Operator):
    bl_idname = "sprig.specialsaddfromactivebase"
    bl_label = "Specials Menu Item Base Class, Add Geometry Item From Active"
    bl_options = {'REGISTER', 'UNDO'}
    item_kind = None
    vert_attribs_to_set = None
    multiply_by_world_matrix = None
    message_geom_type = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list

        vert_data = GrabFromGeometryBase.return_selected_verts(self)
        if vert_data is None:
            return {'CANCELLED'}
        target_data = dict(zip(self.vert_attribs_to_set, vert_data))

        try:
            new_item = AddListItem.add_new_named()
        except UniqueNameError:
            self.report({'ERROR'}, 'Cannot add item, unique name error.')
            return {'CANCELLED'}
        new_item.kind = self.item_kind

        for key, val in target_data.items():
            setattr(new_item, key, val)

        self.report(
            {'INFO'},
            '{0} \'{1}\' was added'.format(
                self.message_geom_type,
                new_item.name
            )
        )
        return {'FINISHED'}


class SpecialsAddPointFromActiveGlobal(SpecialsAddFromActiveBase):
    bl_idname = "sprig.specialsaddpointfromactiveglobal"
    bl_label = "Point From Active Global"
    bl_options = {'REGISTER', 'UNDO'}
    item_kind = 'POINT'
    message_geom_type = 'Point'
    vert_attribs_to_set = ('point',)
    multiply_by_world_matrix = True


class SpecialsAddLineFromActiveGlobal(SpecialsAddFromActiveBase):
    bl_idname = "sprig.specialsaddlinefromactiveglobal"
    bl_label = "Line From Active Global"
    bl_options = {'REGISTER', 'UNDO'}
    item_kind = 'LINE'
    message_geom_type = 'Line'
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = True


class SpecialsAddPlaneFromActiveGlobal(SpecialsAddFromActiveBase):
    bl_idname = "sprig.specialsaddplanefromactiveglobal"
    bl_label = "Plane From Active Global"
    bl_options = {'REGISTER', 'UNDO'}
    item_kind = 'PLANE'
    message_geom_type = 'Plane'
    vert_attribs_to_set = ('plane_pt_a', 'plane_pt_b', 'plane_pt_c')
    multiply_by_world_matrix = True


# Coordinate grabber, present on all geometry primitives (point, line, plane)
# Todo, design decision: error on too many selected verts or *no*?
class GrabFromGeometryBase(bpy.types.Operator):
    bl_idname = "sprig.grabfromgeometrybase"
    bl_label = "Grab From Geometry Base Class"
    bl_description = (
        "The base class for grabbing point coords from mesh verts."
    )
    bl_options = {'REGISTER', 'UNDO'}
    # For grabbing global coords
    multiply_by_world_matrix = None
    # A tuple of attribute names (strings) that should be set on the sprig
    # primitive (point, line or plane item). The length of this tuple
    # determines how many verts will be grabbed.
    vert_attribs_to_set = None

    def return_selected_verts(self):
        if (bpy.context.active_object and
                type(bpy.context.active_object.data) == bpy.types.Mesh):
            selection = []
            verts_collected = 0
            # Todo, check for a better way to handle/if this is needed
            bpy.ops.object.editmode_toggle()
            bpy.ops.object.editmode_toggle()
            for vert in bpy.context.active_object.data.vertices:
                if verts_collected == len(self.vert_attribs_to_set):
                    break
                if vert.select:
                    if self.multiply_by_world_matrix:
                        selection.append(
                            bpy.context.active_object.matrix_world * vert.co
                        )
                    else:
                        selection.append(vert.co)
                    verts_collected += 1
            if len(selection) == len(self.vert_attribs_to_set):
                return selection
            else:
                self.report({'ERROR'}, 'Not enough vertices selected.')
                return None
        else:
            self.report(
                {'ERROR'},
                'Cannot grab coords: non-mesh or no active object.'
            )
            return None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        # todo: maybe from_quick_op or target_quick_op, rename
        if not hasattr(self, "quick_op_target"):
            active_item = prims[addon_data.active_list_item]
        else:
            if self.quick_op_target == "PMSRC":
                active_item = addon_data.quick_align_pts_src
            elif self.quick_op_target == "PMDEST":
                active_item = addon_data.quick_align_pts_dest

            elif self.quick_op_target == "VSSRC":
                active_item = addon_data.quick_vector_slide_src
                
            elif self.quick_op_target == "SMESRC":
                active_item = addon_data.quick_scale_match_edge_src
            elif self.quick_op_target == "SMEDEST":
                active_item = addon_data.quick_scale_match_edge_dest

            elif self.quick_op_target == "MCLSRC":
                active_item = addon_data.quick_make_collinear_src
            elif self.quick_op_target == "MCLDEST":
                active_item = addon_data.quick_make_collinear_dest

            elif self.quick_op_target == "AXRSRC":
                active_item = addon_data.quick_axis_rotate_src

            elif self.quick_op_target == "MCPSRC":
                active_item = addon_data.quick_make_coplanar_src
            elif self.quick_op_target == "MCPDEST":
                active_item = addon_data.quick_make_coplanar_dest

        vert_data = self.return_selected_verts()
        if vert_data is None:
            return {'CANCELLED'}
        target_data = collections.OrderedDict(
            zip(self.vert_attribs_to_set, vert_data)
        )
        for key, val in target_data.items():
            setattr(active_item, key, val)

        return {'FINISHED'}


# Coordinate grabber, present on all geometry primitives (point, line, plane)
class GrabFromCursorBase(bpy.types.Operator):
    bl_idname = "sprig.grabfromcursorbase"
    bl_label = "Grab From Cursor Base Class"
    bl_description = "Grabs coordinates from 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}
    # String name of (single coordinate) attribute
    vert_attrib_to_set = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        active_item = prims[addon_data.active_list_item]

        setattr(
            active_item,
            self.vert_attrib_to_set,
            bpy.context.scene.cursor_location
        )
        return {'FINISHED'}


# Coordinate sender, present on all geometry primitives (point, line, plane)
class SendCoordToCursorBase(bpy.types.Operator):
    bl_idname = "sprig.sendcoordtocursorbase"
    bl_label = "Send Coord to Cursor Base Class"
    bl_description = "The base class for sending coordinates to the 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    # String name of the primitive attrib to pull coord data from
    source_coord_attrib = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = bpy.context.scene.sprig_data.prim_list
        active_item = prims[addon_data.active_list_item]

        bpy.context.scene.cursor_location = getattr(
            active_item,
            self.source_coord_attrib
        )
        return {'FINISHED'}


class GrabPointFromCursor(GrabFromCursorBase):
    bl_idname = "sprig.grabpointfromcursor"
    bl_label = "Grab From Cursor"
    bl_description = "Grabs coordinates from 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}
    vert_attrib_to_set = 'point'


class GrabPointFromActiveLocal(GrabFromGeometryBase):
    bl_idname = "sprig.grabpointfromactivelocal"
    bl_label = "Grab Local Coordinates From Active Point"
    bl_description = (
        "Grabs local coordinates from selected vertex in edit mode"
        )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('point',)
    multiply_by_world_matrix = False


class GrabPointFromActiveGlobal(GrabFromGeometryBase):
    bl_idname = "sprig.grabpointfromactiveglobal"
    bl_label = "Grab Global Coordinates From Active Point"
    bl_description = (
        "Grabs global coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('point',)
    multiply_by_world_matrix = True


class QuickPointMatchGrabSrc(GrabFromGeometryBase):
    bl_idname = "sprig.quickpointmatchgrabsrc"
    bl_label = "Grab Global Coordinates From Active Point"
    bl_description = (
        "Grabs global coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('point',)
    multiply_by_world_matrix = True
    quick_op_target = "PMSRC"


class QuickPointMatchGrabDest(GrabFromGeometryBase):
    bl_idname = "sprig.quickpointmatchgrabdest"
    bl_label = "Grab Global Coordinates From Active Point"
    bl_description = (
        "Grabs global coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('point',)
    multiply_by_world_matrix = True
    quick_op_target = "PMDEST"


class SendPointToCursor(SendCoordToCursorBase):
    bl_idname = "sprig.sendpointtocursor"
    bl_label = "Sends Point to Cursor"
    bl_description = "Sends Point Coordinates to the 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    source_coord_attrib = 'point'


class GrabLineStartFromCursor(GrabFromCursorBase):
    bl_idname = "sprig.grablinestartfromcursor"
    bl_label = "Grab Line Start From Cursor"
    bl_description = "Grabs line start coordinates from the 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}
    vert_attrib_to_set = 'line_start'


class GrabLineStartFromActiveLocal(GrabFromGeometryBase):
    bl_idname = "sprig.grablinestartfromactivelocal"
    bl_label = "Grab Local Coordinate for Line Start From Active Point"
    bl_description = (
        "Grabs local coordinates for line start from selected vertex"
        "in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target_point_attribute = 'line_start'
    vert_attribs_to_set = ('line_start',)
    multiply_by_world_matrix = False


class GrabLineStartFromActiveGlobal(GrabFromGeometryBase):
    bl_idname = "sprig.grablinestartfromactiveglobal"
    bl_label = "Grab Global Coordinate for Line Start From Active Point"
    bl_description = (
        "Grabs global coordinates for line start from selected vertex"
        "in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start',)
    multiply_by_world_matrix = True


class SendLineStartToCursor(SendCoordToCursorBase):
    bl_idname = "sprig.sendlinestarttocursor"
    bl_label = "Sends Line Start to Cursor"
    bl_description = "Sends Line Start Coordinates to 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    source_coord_attrib = 'line_start'


class GrabLineEndFromCursor(GrabFromCursorBase):
    bl_idname = "sprig.grablineendfromcursor"
    bl_label = "Grab From Cursor"
    bl_description = "Grabs coordinates from 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}
    vert_attrib_to_set = 'line_end'


class GrabLineEndFromActiveLocal(GrabFromGeometryBase):
    bl_idname = "sprig.grablineendfromactivelocal"
    bl_label = "Grab From Active Point"
    bl_description = "Grabs coordinates from selected vertex in edit mode"
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_end',)
    multiply_by_world_matrix = False


class GrabLineEndFromActiveGlobal(GrabFromGeometryBase):
    bl_idname = "sprig.grablineendfromactiveglobal"
    bl_label = "Grab Global Coordinates From Active Point"
    bl_description = (
        "Grabs global coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_end',)
    multiply_by_world_matrix = True


class SendLineEndToCursor(SendCoordToCursorBase):
    bl_idname = "sprig.sendlineendtocursor"
    bl_label = "Sends Line End to Cursor"
    bl_description = "Sends Line End Coordinates to 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    source_coord_attrib = 'line_end'


class GrabAllVertsLineLocal(GrabFromGeometryBase):
    bl_idname = "sprig.graballvertslinelocal"
    bl_label = "Grab Line from Selected Verts"
    bl_description = (
        "Grabs line coordinates from selected vertices in edit mode"
        )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = False


class GrabAllVertsLineGlobal(GrabFromGeometryBase):
    bl_idname = "sprig.graballvertslineglobal"
    bl_label = "Grab Line from Selected Verts"
    bl_description = (
        "Grabs line coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = True


class QuickMakeCollinearGrabSrc(GrabFromGeometryBase):
    bl_idname = "sprig.quickmakecollineargrabsrc"
    bl_label = "Grab Line from Selected Verts"
    bl_description = (
        "Grabs line coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = True
    quick_op_target = "MCLSRC"


class QuickMakeCollinearGrabDest(GrabFromGeometryBase):
    bl_idname = "sprig.quickmakecollineargrabdest"
    bl_label = "Grab Line from Selected Verts"
    bl_description = (
        "Grabs line coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = True
    quick_op_target = "MCLDEST"


class QuickScaleMatchEdgeGrabSrc(GrabFromGeometryBase):
    bl_idname = "sprig.quickscalematchedgegrabsrc"
    bl_label = "Grab Line from Selected Verts"
    bl_description = (
        "Grabs line coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = True
    quick_op_target = "SMESRC"


class QuickScaleMatchEdgeGrabDest(GrabFromGeometryBase):
    bl_idname = "sprig.quickscalematchedgegrabdest"
    bl_label = "Grab Line from Selected Verts"
    bl_description = (
        "Grabs line coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = True
    quick_op_target = "SMEDEST"


class QuickAxisRotateGrabSrc(GrabFromGeometryBase):
    bl_idname = "sprig.quickaxisrotategrabsrc"
    bl_label = "Grab Line from Selected Verts"
    bl_description = (
        "Grabs line coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = True
    quick_op_target = "AXRSRC"


class QuickVectorSlideGrabSrc(GrabFromGeometryBase):
    bl_idname = "sprig.quickvectorslidegrabsrc"
    bl_label = "Grab Line from Selected Verts"
    bl_description = (
        "Grabs line coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('line_start', 'line_end')
    multiply_by_world_matrix = True
    quick_op_target = "VSSRC"


class GrabPlaneAFromCursor(GrabFromCursorBase):
    bl_idname = "sprig.grabplaneafromcursor"
    bl_label = "Grab From Cursor"
    bl_description = "Grabs coordinates from 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}
    vert_attrib_to_set = 'plane_pt_a'


class GrabPlaneAFromActiveLocal(GrabFromGeometryBase):
    bl_idname = "sprig.grabplaneafromactivelocal"
    bl_label = "Grab Local Coordinates From Active Point"
    bl_description = (
        "Grabs local coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_a',)
    multiply_by_world_matrix = False


class GrabPlaneAFromActiveGlobal(GrabFromGeometryBase):
    bl_idname = "sprig.grabplaneafromactiveglobal"
    bl_label = "Grab Global Coordinates From Active Point"
    bl_description = (
        "Grabs global coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_a',)
    multiply_by_world_matrix = True


class SendPlaneAToCursor(SendCoordToCursorBase):
    bl_idname = "sprig.sendplaneatocursor"
    bl_label = "Sends Plane Point A to Cursor"
    bl_description = "Sends Plane Point A Coordinates to 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    source_coord_attrib = 'plane_pt_a'


class GrabPlaneBFromCursor(GrabFromCursorBase):
    bl_idname = "sprig.grabplanebfromcursor"
    bl_label = "Grab From Cursor"
    bl_description = "Grabs coordinates from 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}
    vert_attrib_to_set = 'plane_pt_b'


class GrabPlaneBFromActiveLocal(GrabFromGeometryBase):
    bl_idname = "sprig.grabplanebfromactivelocal"
    bl_label = "Grab Local Coordinates From Active Point"
    bl_description = (
        "Grabs local coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_b',)
    multiply_by_world_matrix = False


class GrabPlaneBFromActiveGlobal(GrabFromGeometryBase):
    bl_idname = "sprig.grabplanebfromactiveglobal"
    bl_label = "Grab Global Coordinates From Active Point"
    bl_description = (
        "Grabs global coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_b',)
    multiply_by_world_matrix = True


class SendPlaneBToCursor(SendCoordToCursorBase):
    bl_idname = "sprig.sendplanebtocursor"
    bl_label = "Sends Plane Point B to Cursor"
    bl_description = "Sends Plane Point B Coordinates to 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    source_coord_attrib = 'plane_pt_b'


class GrabPlaneCFromCursor(GrabFromCursorBase):
    bl_idname = "sprig.grabplanecfromcursor"
    bl_label = "Grab From Cursor"
    bl_description = "Grabs coordinates from 3D cursor"
    bl_options = {'REGISTER', 'UNDO'}
    vert_attrib_to_set = 'plane_pt_c'


class GrabPlaneCFromActiveLocal(GrabFromGeometryBase):
    bl_idname = "sprig.grabplanecfromactivelocal"
    bl_label = "Grab Local Coordinates From Active Point"
    bl_description = (
        "Grabs local coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_c',)
    multiply_by_world_matrix = False


class GrabPlaneCFromActiveGlobal(GrabFromGeometryBase):
    bl_idname = "sprig.grabplanecfromactiveglobal"
    bl_label = "Grab Global Coordinates From Active Point"
    bl_description = (
        "Grabs global coordinates from selected vertex in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_c',)
    multiply_by_world_matrix = True


class SendPlaneCToCursor(bpy.types.Operator):
    bl_idname = "sprig.sendplanectocursor"
    bl_label = "Sends Plane Point C to Cursor"
    bl_description = "Sends Plane Point C Coordinates to 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}
    source_coord_attrib = 'plane_pt_c'


class GrabAllVertsPlaneLocal(GrabFromGeometryBase):
    bl_idname = "sprig.graballvertsplanelocal"
    bl_label = "Grab Plane Local Coordinates from Selected Verts"
    bl_description = (
        "Grabs plane local coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_a', 'plane_pt_b', 'plane_pt_c')
    multiply_by_world_matrix = False


class GrabAllVertsPlaneGlobal(GrabFromGeometryBase):
    bl_idname = "sprig.graballvertsplaneglobal"
    bl_label = "Grab Plane Global Coordinates from Selected Verts"
    bl_description = (
        "Grabs plane global coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_a', 'plane_pt_b', 'plane_pt_c')
    multiply_by_world_matrix = True


class QuickMakeCoplanarGrabSrc(GrabFromGeometryBase):
    bl_idname = "sprig.quickmakecoplanargrabsrc"
    bl_label = "Grab Plane Global Coordinates from Selected Verts"
    bl_description = (
        "Grabs plane global coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_a', 'plane_pt_b', 'plane_pt_c')
    multiply_by_world_matrix = True
    quick_op_target = "MCPSRC"


class QuickMakeCoplanarGrabDest(GrabFromGeometryBase):
    bl_idname = "sprig.quickmakecoplanargrabdest"
    bl_label = "Grab Plane Global Coordinates from Selected Verts"
    bl_description = (
        "Grabs plane global coordinates from selected vertices in edit mode"
    )
    bl_options = {'REGISTER', 'UNDO'}
    vert_attribs_to_set = ('plane_pt_a', 'plane_pt_b', 'plane_pt_c')
    multiply_by_world_matrix = True
    quick_op_target = "MCPDEST"


# Coordinate swapper, present on all geometry primitives
# that have multiple points (line, plane)
class SwapPointsBase(bpy.types.Operator):
    bl_idname = "sprig.swappointsbase"
    bl_label = "Swap Points Base"
    bl_description = "Swap points base class"
    bl_options = {'REGISTER', 'UNDO'}
    targets = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        active_item = prims[addon_data.active_list_item]

        source = getattr(active_item, self.targets[0])
        source = mathutils.Vector(
            (source[0],
             source[1],
             source[2])
        )
        dest = getattr(active_item, self.targets[1])
        dest = mathutils.Vector(
            (dest[0],
             dest[1],
             dest[2])
        )

        setattr(
            active_item,
            self.targets[0],
            dest
        )
        setattr(
            active_item,
            self.targets[1],
            source
        )
        return {'FINISHED'}


class SwapLinePoints(SwapPointsBase):
    bl_idname = "sprig.swaplinepoints"
    bl_label = "Swap Line Points"
    bl_description = "Swap line points"
    bl_options = {'REGISTER', 'UNDO'}
    targets = ('line_start', 'line_end')


class SwapPlaneAPlaneB(SwapPointsBase):
    bl_idname = "sprig.swapplaneaplaneb"
    bl_label = "Swap Plane Point A with Plane Point B"
    bl_description = "Swap plane points A and B"
    bl_options = {'REGISTER', 'UNDO'}
    targets = ('plane_pt_a', 'plane_pt_b')


class SwapPlaneAPlaneC(SwapPointsBase):
    bl_idname = "sprig.swapplaneaplanec"
    bl_label = "Swap Plane Point A with Plane Point C"
    bl_description = "Swap plane points A and C"
    bl_options = {'REGISTER', 'UNDO'}
    targets = ('plane_pt_a', 'plane_pt_c')


class SwapPlaneBPlaneC(SwapPointsBase):
    bl_idname = "sprig.swapplanebplanec"
    bl_label = "Swap Plane Point B with Plane Point C"
    bl_description = "Swap plane points B and C"
    bl_options = {'REGISTER', 'UNDO'}
    targets = ('plane_pt_b', 'plane_pt_c')


# Every x/y/z coordinate component has these functions on each of the
# geometry primitives (lets users move in one direction easily, etc.)
class SetOtherComponentsBase(bpy.types.Operator):
    bl_idname = "sprig.setotherbase"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    # A tuple containing the geometry attribute name (a string), the
    # coord type in ['X', 'Y', 'Z'], and the value to set (currently
    # 0 and 1 are the planned uses for this...to make building one
    # dimensional moves etc. possible)
    target_info = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        active_item = prims[addon_data.active_list_item]

        if self.target_info[1] == 'X':
            setattr(
                active_item,
                self.target_info[0],
                (getattr(active_item, self.target_info[0])[0],
                 self.target_info[2],
                 self.target_info[2]
                 )
            )
        elif self.target_info[1] == 'Y':
            setattr(
                active_item,
                self.target_info[0],
                (self.target_info[2],
                 getattr(active_item, self.target_info[0])[1],
                 self.target_info[2]
                 )
            )
        elif self.target_info[1] == 'Z':
            setattr(
                active_item,
                self.target_info[0],
                (self.target_info[2],
                 self.target_info[2],
                 getattr(active_item, self.target_info[0])[2]
                 )
            )

        return {'FINISHED'}


class ZeroOtherPointX(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherpointx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('point', 'X', 0)


class ZeroOtherPointY(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherpointy"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('point', 'Y', 0)


class ZeroOtherPointZ(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherpointz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('point', 'Z', 0)


class ZeroOtherLineStartX(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherlinestartx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_start', 'X', 0)


class ZeroOtherLineStartY(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherlinestarty"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_start', 'Y', 0)


class ZeroOtherLineStartZ(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherlinestartz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_start', 'Z', 0)


class ZeroOtherLineEndX(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherlineendx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_end', 'X', 0)


class ZeroOtherLineEndY(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherlineendy"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_end', 'Y', 0)


class ZeroOtherLineEndZ(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherlineendz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_end', 'Z', 0)


class ZeroOtherPlanePointAX(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointax"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_a', 'X', 0)


class ZeroOtherPlanePointAY(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointay"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_a', 'Y', 0)


class ZeroOtherPlanePointAZ(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointaz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_a', 'Z', 0)


class ZeroOtherPlanePointBX(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointbx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_b', 'X', 0)


class ZeroOtherPlanePointBY(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointby"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_b', 'Y', 0)


class ZeroOtherPlanePointBZ(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointbz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_b', 'Z', 0)


class ZeroOtherPlanePointCX(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointcx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_c', 'X', 0)


class ZeroOtherPlanePointCY(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointcy"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_c', 'Y', 0)


class ZeroOtherPlanePointCZ(SetOtherComponentsBase):
    bl_idname = "sprig.zerootherplanepointcz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_c', 'Z', 0)


class OneOtherPointX(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherpointx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('point', 'X', 1)


class OneOtherPointY(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherpointy"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('point', 'Y', 1)


class OneOtherPointZ(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherpointz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('point', 'Z', 1)


class OneOtherLineStartX(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherlinestartx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_start', 'X', 1)


class OneOtherLineStartY(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherlinestarty"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_start', 'Y', 1)


class OneOtherLineStartZ(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherlinestartz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_start', 'Z', 1)


class OneOtherLineEndX(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherlineendx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_end', 'X', 1)


class OneOtherLineEndY(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherlineendy"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_end', 'Y', 1)


class OneOtherLineEndZ(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherlineendz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('line_end', 'Z', 1)


class OneOtherPlanePointAX(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointax"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_a', 'X', 1)


class OneOtherPlanePointAY(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointay"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_a', 'Y', 1)


class OneOtherPlanePointAZ(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointaz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_a', 'Z', 1)


class OneOtherPlanePointBX(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointbx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_b', 'X', 1)


class OneOtherPlanePointBY(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointby"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_b', 'Y', 1)


class OneOtherPlanePointBZ(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointbz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_b', 'Z', 1)


class OneOtherPlanePointCX(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointcx"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_c', 'X', 1)


class OneOtherPlanePointCY(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointcy"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_c', 'Y', 1)


class OneOtherPlanePointCZ(SetOtherComponentsBase):
    bl_idname = "sprig.oneotherplanepointcz"
    bl_label = ""
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    target_info = ('plane_pt_c', 'Z', 1)


class ScaleMatchEdgeBase(bpy.types.Operator):
    bl_idname = "sprig.scalematchedgebase"
    bl_label = "Scale Match Edge Base"
    bl_description = "Scale match edge base class"
    bl_options = {'REGISTER', 'UNDO'}
    target = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        previous_mode = bpy.context.active_object.mode
        if hasattr(self, "quick_op_target"):
            active_item = addon_data.quick_scale_match_edge_transf
        else:
            active_item = prims[addon_data.active_list_item]

        if (bpy.context.active_object and
                type(bpy.context.active_object.data) == bpy.types.Mesh):

            if not hasattr(self, "quick_op_target"):
                if (prims[active_item.sme_edge_one].kind != 'LINE' or
                        prims[active_item.sme_edge_two].kind != 'LINE'):
                    self.report(
                        {'ERROR'},
                        ('Wrong operands: scale match edge can only operate on '
                         'two lines')
                    )
                    return {'CANCELLED'}

            if previous_mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            else:
                # else we could already be in edit mode with some stale
                # updates, exiting and reentering forces an update
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.editmode_toggle()

            if hasattr(self, "quick_op_target"):
                bpy.ops.sprig.quickscalematchedgegrabsrc()
                src_edge = (
                    mathutils.Vector(
                        addon_data.quick_scale_match_edge_src.line_end
                    ) -
                    mathutils.Vector(
                        addon_data.quick_scale_match_edge_src.line_start
                    )
                )
                dest_edge = (
                    mathutils.Vector(
                        addon_data.quick_scale_match_edge_dest.line_end
                    ) -
                    mathutils.Vector(
                        addon_data.quick_scale_match_edge_dest.line_start
                    )
                )

            else:
                src_edge = (
                    mathutils.Vector(
                        prims[active_item.sme_edge_one].line_end
                    ) -
                    mathutils.Vector(
                        prims[active_item.sme_edge_one].line_start
                    )
                )
                dest_edge = (
                    mathutils.Vector(
                        prims[active_item.sme_edge_two].line_end
                    ) -
                    mathutils.Vector(
                        prims[active_item.sme_edge_two].line_start
                    )
                )

            if not hasattr(self, "quick_op_target"):
                # Take geom modifiers into account, line one
                if prims[active_item.sme_edge_one].ln_make_unit_vec:
                    src_edge.normalize()
                src_edge *= prims[active_item.sme_edge_one].ln_multiplier

                # Take geom modifiers into account, line two
                if prims[active_item.sme_edge_two].ln_make_unit_vec:
                    dest_edge.normalize()
                dest_edge *= prims[active_item.sme_edge_two].ln_multiplier

            if dest_edge.length == 0 or src_edge.length == 0:
                self.report(
                    {'ERROR'},
                    'Divide by zero error: zero length edge encountered'
                )
                return {'CANCELLED'}
            scale_factor = dest_edge.length/src_edge.length

            if self.target == 'OBJECT':
                bpy.context.active_object.scale = [
                    scale_factor * num
                    for num in bpy.context.active_object.scale
                ]
            else:
                self.report(
                    {'WARNING'},
                    ('Warning/Experimental: mesh transforms'
                     ' on objects with non-uniform scaling'
                     ' are not currently supported.'
                    )
                )
                # Setup matrix for mesh transforms
                match_transf = mathutils.Matrix.Scale(
                    scale_factor,
                    4
                )

                # Init source mesh
                src_mesh = bmesh.new()
                src_mesh.from_mesh(bpy.context.active_object.data)

                if self.target == 'MESHSELECTED':
                    if hasattr(self, "quick_op_target"):
                        if "_sel" not in bpy.context.active_object.vertex_groups:
                            self.report(
                                {'ERROR'},
                                ('Missing vertex group: A vertex group named '
                                 '"_sel" must be present to transform'
                                 'selected vertices with the Quick Tools.'
                                )
                            )
                            return {'CANCELLED'}
                        group_ind = (
                            bpy.context.active_object.vertex_groups["_sel"].index
                        )
                        target_verts = []
                        for vert in bpy.context.active_object.data.vertices:
                            for vgroup in vert.groups:
                                if vgroup.group == group_ind:
                                    target_verts.append(vert.index)
                        # todo, REPORT on no verts in the vert group
                        for v in src_mesh.verts:
                            if v.index in target_verts:
                                v.tag = True
                        src_mesh.transform(
                            match_transf,
                            filter={'TAG'}
                        )
                    else:
                        src_mesh.transform(
                            match_transf,
                            filter={'SELECT'}
                        )
                elif self.target == 'WHOLEMESH':
                    src_mesh.transform(match_transf)

                # write and then release the mesh data
                bpy.ops.object.mode_set(mode='OBJECT')
                src_mesh.to_mesh(bpy.context.active_object.data)
                src_mesh.free()

            # Go back to whatever mode we were in before doing this
            bpy.ops.object.mode_set(mode=previous_mode)

        else:
            self.report(
                {'ERROR'},
                'Cannot transform: non-mesh or no active object.'
            )
            return {'CANCELLED'}

        return {'FINISHED'}


class ScaleMatchEdgeObject(ScaleMatchEdgeBase):
    bl_idname = "sprig.scalematchedgeobject"
    bl_label = "Scale Match Edge Object"
    bl_description = (
        "Scale source object so that source edge matches length of dest edge"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'


class QuickScaleMatchEdgeObject(ScaleMatchEdgeBase):
    bl_idname = "sprig.quickscalematchedgeobject"
    bl_label = "Scale Match Edge Object"
    bl_description = (
        "Scale source object so that source edge matches length of dest edge"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'
    quick_op_target = True


class ScaleMatchEdgeMeshSelected(ScaleMatchEdgeBase):
    bl_idname = "sprig.scalematchedgemeshselected"
    bl_label = "Scale Match Edge Mesh Selected"
    bl_description = (
        "Scale source mesh piece so that source edge matches length "
        "of dest edge"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickScaleMatchEdgeMeshSelected(ScaleMatchEdgeBase):
    bl_idname = "sprig.quickscalematchedgemeshselected"
    bl_label = "Scale Match Edge Whole Mesh"
    bl_description = (
        "Scale source (whole) mesh so that source edge matches length "
        "of dest edge"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class ScaleMatchEdgeWholeMesh(ScaleMatchEdgeBase):
    bl_idname = "sprig.scalematchedgewholemesh"
    bl_label = "Scale Match Edge Whole Mesh"
    bl_description = (
        "Scale source (whole) mesh so that source edge matches length "
        "of dest edge"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickScaleMatchEdgeWholeMesh(ScaleMatchEdgeBase):
    bl_idname = "sprig.quickscalematchedgewholemesh"
    bl_label = "Scale Match Edge Whole Mesh"
    bl_description = (
        "Scale source (whole) mesh so that source edge matches length "
        "of dest edge"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class PointMatchBase(bpy.types.Operator):
    bl_idname = "sprig.pointmatchbase"
    bl_label = "Point Match Base"
    bl_description = "Point match base class"
    bl_options = {'REGISTER', 'UNDO'}
    target = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        previous_mode = bpy.context.active_object.mode
        if not hasattr(self, "quick_op_target"):
            active_item = prims[addon_data.active_list_item]
        else:
            active_item = addon_data.quick_align_pts_transf

        if (bpy.context.active_object and
                type(bpy.context.active_object.data) == bpy.types.Mesh):

            # todo: use a bool check and put on all derived classes
            # instead of hasattr
            if not hasattr(self, 'quick_op_target'):
                if (prims[active_item.pm_pt_one].kind != 'POINT' or
                        prims[active_item.pm_pt_two].kind != 'POINT'):
                    self.report(
                        {'ERROR'},
                        ('Wrong operands: point match can only operate on '
                         'two points')
                    )
                    return {'CANCELLED'}

            # a bmesh can only be initialized in edit mode...todo/better way?
            if previous_mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            else:
                # else we could already be in edit mode with some stale
                # updates, exiting and reentering forces an update
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.editmode_toggle()

            # src either comes from a selected edge (for quick ops)
            # or from the primitive list (regular ops)
            if hasattr(self, 'quick_op_target'):
                bpy.ops.sprig.quickpointmatchgrabsrc()
                src_pt = mathutils.Vector(
                    (addon_data.quick_align_pts_src.point[0],
                     addon_data.quick_align_pts_src.point[1],
                     addon_data.quick_align_pts_src.point[2])
                )
                dest_pt = mathutils.Vector(
                    (addon_data.quick_align_pts_dest.point[0],
                     addon_data.quick_align_pts_dest.point[1],
                     addon_data.quick_align_pts_dest.point[2])
                )

                # Take source geometry modifiers into account
                if addon_data.quick_align_pts_src.pt_make_unit_vec:
                    src_pt.normalize()
                if addon_data.quick_align_pts_src.pt_flip_direction:
                    src_pt.negate()
                src_pt *= addon_data.quick_align_pts_src.pt_multiplier

                # Take dest geometry modifiers into account
                if addon_data.quick_align_pts_dest.pt_make_unit_vec:
                    dest_pt.normalize()
                if addon_data.quick_align_pts_dest.pt_flip_direction:
                    dest_pt.negate()
                dest_pt *= addon_data.quick_align_pts_dest.pt_multiplier

            else:
                src_pt = mathutils.Vector(
                    (prims[active_item.pm_pt_one].point[0],
                     prims[active_item.pm_pt_one].point[1],
                     prims[active_item.pm_pt_one].point[2])
                )
                dest_pt = mathutils.Vector(
                    (prims[active_item.pm_pt_two].point[0],
                     prims[active_item.pm_pt_two].point[1],
                     prims[active_item.pm_pt_two].point[2])
                )

                # Take source geometry modifiers into account
                if prims[active_item.pm_pt_one].pt_make_unit_vec:
                    src_pt.normalize()
                if prims[active_item.pm_pt_one].pt_flip_direction:
                    src_pt.negate()
                src_pt *= prims[active_item.pm_pt_one].pt_multiplier

                # Take dest geometry modifiers into account
                if prims[active_item.pm_pt_two].pt_make_unit_vec:
                    dest_pt.normalize()
                if prims[active_item.pm_pt_two].pt_flip_direction:
                    dest_pt.negate()
                dest_pt *= prims[active_item.pm_pt_two].pt_multiplier

            raw_translation_vector = mathutils.Vector(dest_pt - src_pt)

            # Here we compensate if our active object has been transformed
            # (which would make our translation otherwise not work)
            active_obj_transf = bpy.context.active_object.matrix_world
            inverse_active = active_obj_transf.copy()
            # Undoes the transformation rep. by this matrix
            inverse_active.invert()
            tr, ro, sc = active_obj_transf.decompose()
            # this gives us only the reverse rotation and scale
            # (we don't need the translation correction)
            correction_matrix = (
                inverse_active * mathutils.Matrix.Translation(tr)
            )

            # corrected vector, basis of final transform
            final_translation_vector = (
                correction_matrix * raw_translation_vector
            )

            # Take transform modifiers into account
            if active_item.pm_ln_make_unit_vec:
                final_translation_vector.normalize()
                raw_translation_vector.normalize()
            if active_item.pm_ln_flip_direction:
                final_translation_vector.negate()
                raw_translation_vector.negate()
            final_translation_vector *= active_item.pm_multiplier
            raw_translation_vector *= active_item.pm_multiplier

            if self.target == 'OBJECT':
                bpy.context.active_object.location = (
                    bpy.context.active_object.location +
                    raw_translation_vector
                )
            else:
                self.report(
                    {'WARNING'},
                    ('Warning/Experimental: mesh transforms'
                     ' on objects with non-uniform scaling'
                     ' are not currently supported.'
                    )
                )
                # Setup matrix for mesh transforms
                match_transf = mathutils.Matrix.Translation(
                    final_translation_vector
                )

                # Init source mesh
                src_mesh = bmesh.new()
                src_mesh.from_mesh(bpy.context.active_object.data)

                if self.target == 'MESHSELECTED':
                    if hasattr(self, "quick_op_target"):
                        if "_sel" not in bpy.context.active_object.vertex_groups:
                            self.report(
                                {'ERROR'},
                                ('Missing vertex group: A vertex group named '
                                 '"_sel" must be present to transform'
                                 'selected vertices with the Quick Tools.'
                                )
                            )
                            return {'CANCELLED'}
                        group_ind = (
                            bpy.context.active_object.vertex_groups["_sel"].index
                        )
                        target_verts = []
                        for vert in bpy.context.active_object.data.vertices:
                            for vgroup in vert.groups:
                                if vgroup.group == group_ind:
                                    target_verts.append(vert.index)
                        # todo, REPORT on no verts in the vert group
                        for v in src_mesh.verts:
                            if v.index in target_verts:
                                v.tag = True
                        src_mesh.transform(
                            match_transf,
                            filter={'TAG'}
                        )
                    else:
                        src_mesh.transform(
                            match_transf,
                            filter={'SELECT'}
                        )
                elif self.target == 'WHOLEMESH':
                    src_mesh.transform(match_transf)

                # write and then release the mesh data
                bpy.ops.object.mode_set(mode='OBJECT')
                src_mesh.to_mesh(bpy.context.active_object.data)
                src_mesh.free()

            # Go back to whatever mode we were in before doing this
            bpy.ops.object.mode_set(mode=previous_mode)

        else:
            self.report(
                {'ERROR'},
                'Cannot transform: non-mesh or no active object.'
            )
            return {'CANCELLED'}

        return {'FINISHED'}


class PointMatchObject(PointMatchBase):
    bl_idname = "sprig.pointmatchobject"
    bl_label = "Point Match Object"
    bl_description = (
        "Match the location of one vertex on a mesh object to another"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'


class QuickPointMatchObject(PointMatchBase):
    bl_idname = "sprig.quickpointmatchobject"
    bl_label = "Point Match Object"
    bl_description = (
        "Match the location of one vertex on a mesh object to another"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'
    quick_op_target = True


class PointMatchMeshSelected(PointMatchBase):
    bl_idname = "sprig.pointmatchmeshselected"
    bl_label = "Point Match Mesh Selected"
    bl_description = (
        "Match the location of one vertex on a mesh piece "
        "(the selected verts) to another"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickPointMatchMeshSelected(PointMatchBase):
    bl_idname = "sprig.quickpointmatchmeshselected"
    bl_label = "Point Match Mesh Selected"
    bl_description = (
        "Match the location of one vertex on a mesh piece "
        "(the selected verts) to another"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class PointMatchWholeMesh(PointMatchBase):
    bl_idname = "sprig.pointmatchwholemesh"
    bl_label = "Point Match Mesh"
    bl_description = "Match the location of one vertex on a mesh to another"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickPointMatchWholeMesh(PointMatchBase):
    bl_idname = "sprig.quickpointmatchwholemesh"
    bl_label = "Point Match Mesh"
    bl_description = "Match the location of one vertex on a mesh to another"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class VectorSlideBase(bpy.types.Operator):
    bl_idname = "sprig.vectorslidebase"
    bl_label = "Vector Slide Base"
    bl_description = "Vector slide base class"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        previous_mode = bpy.context.active_object.mode
        if not hasattr(self, "quick_op_target"):
            active_item = prims[addon_data.active_list_item]
        else:
            active_item = addon_data.quick_vector_slide_transf

        if (bpy.context.active_object and
                type(bpy.context.active_object.data) == bpy.types.Mesh):

            if not hasattr(self, "quick_op_target"):
                if prims[active_item.vs_direction].kind != 'LINE':
                    self.report(
                        {'ERROR'},
                        'Wrong operand: vector slide can only operate on a line'
                    )
                    return {'CANCELLED'}

            # a bmesh can only be initialized in edit mode...
            if previous_mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            else:
                # else we could already be in edit mode with some stale
                # updates, exiting and reentering forces an update
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.editmode_toggle()

            # Make the vector specifying the direction and
            # magnitude to slide in
            if hasattr(self, "quick_op_target"):
                direction = (
                    mathutils.Vector(addon_data.quick_vector_slide_src.line_end) -
                    mathutils.Vector(addon_data.quick_vector_slide_src.line_start)
                )
            else:
                direction = (
                    mathutils.Vector(prims[active_item.vs_direction].line_end) -
                    mathutils.Vector(prims[active_item.vs_direction].line_start)
                )

            if not hasattr(self, "quick_op_target"):
                # Take geom modifiers into account
                if prims[active_item.vs_direction].ln_make_unit_vec:
                    direction.normalize()
                if prims[active_item.vs_direction].ln_flip_direction:
                    direction.negate()
                direction *= prims[active_item.vs_direction].ln_multiplier

            # Take transf modifiers into account
            if active_item.vs_ln_make_unit_vec:
                direction.normalize()
            if active_item.vs_ln_flip_direction:
                direction.negate()
            direction *= active_item.vs_multiplier

            # create common vars needed for object and for mesh level transfs
            active_obj_transf = bpy.context.active_object.matrix_world.copy()
            t, r, s, = active_obj_transf.decompose()
            inverse_active = active_obj_transf.copy()
            inverse_active.invert()
            inv_translate, inv_rot, inv_scale = inverse_active.decompose()

            if self.target == 'OBJECT':
                # Do it!
                bpy.context.active_object.location = (
                    bpy.context.active_object.location + direction
                )
            else:
                self.report(
                    {'WARNING'},
                    ('Warning/Experimental: mesh transforms'
                     ' on objects with non-uniform scaling'
                     ' are not currently supported.'
                    )
                )
                # Init source mesh
                src_mesh = bmesh.new()
                src_mesh.from_mesh(bpy.context.active_object.data)

                correction_matrix = (
                    inverse_active * mathutils.Matrix.Translation(t)
                )
                corrected_direction = correction_matrix * direction
                corrected_direction_transf = mathutils.Matrix.Translation(
                    corrected_direction
                )

                if self.target == 'MESHSELECTED':
                    if hasattr(self, "quick_op_target"):
                        if "_sel" not in bpy.context.active_object.vertex_groups:
                            self.report(
                                {'ERROR'},
                                ('Missing vertex group: A vertex group named '
                                 '"_sel" must be present to transform'
                                 'selected vertices with the Quick Tools.'
                                )
                            )
                            return {'CANCELLED'}
                        group_ind = (
                            bpy.context.active_object.vertex_groups["_sel"].index
                        )
                        target_verts = []
                        for vert in bpy.context.active_object.data.vertices:
                            for vgroup in vert.groups:
                                if vgroup.group == group_ind:
                                    target_verts.append(vert.index)
                        # todo, REPORT on no verts in the vert group
                        for v in src_mesh.verts:
                            if v.index in target_verts:
                                v.tag = True
                        src_mesh.transform(
                            corrected_direction_transf,
                            filter={'TAG'}
                        )
                    else:
                        src_mesh.transform(
                            corrected_direction_transf,
                            filter={'SELECT'}
                        )
                elif self.target == 'WHOLEMESH':
                    src_mesh.transform(corrected_direction_transf)

                # write and then release the mesh data
                bpy.ops.object.mode_set(mode='OBJECT')
                src_mesh.to_mesh(bpy.context.active_object.data)
                src_mesh.free()

            # Go back to whatever mode we were in before doing this
            bpy.ops.object.mode_set(mode=previous_mode)

        else:
            self.report(
                {'ERROR'},
                'Cannot transform: non-mesh or no active object.'
            )
            return {'CANCELLED'}

        return {'FINISHED'}


class VectorSlideObject(VectorSlideBase):
    bl_idname = "sprig.vectorslideobject"
    bl_label = "Vector Slide Object"
    bl_description = "Translates a target object (moves in a direction)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'


class QuickVectorSlideObject(VectorSlideBase):
    bl_idname = "sprig.quickvectorslideobject"
    bl_label = "Vector Slide Object"
    bl_description = "Translates a target object (moves in a direction)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'
    quick_op_target = True


class VectorSlideMeshSelected(VectorSlideBase):
    bl_idname = "sprig.vectorslidemeshselected"
    bl_label = "Vector Slide Mesh Piece"
    bl_description = (
        "Translates a target mesh piece (moves selected verts in a direction)"
    )
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class VectorSlideWholeMesh(VectorSlideBase):
    bl_idname = "sprig.vectorslidewholemesh"
    bl_label = "Vector Slide Mesh"
    bl_description = "Translates a target mesh (moves mesh in a direction)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickVectorSlideMeshSelected(VectorSlideBase):
    bl_idname = "sprig.quickvectorslidemeshselected"
    bl_label = "Vector Slide Mesh"
    bl_description = "Translates a target mesh (moves mesh in a direction)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickVectorSlideWholeMesh(VectorSlideBase):
    bl_idname = "sprig.quickvectorslidewholemesh"
    bl_label = "Vector Slide Mesh"
    bl_description = "Translates a target mesh (moves mesh in a direction)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


def scale_mat_from_vec(vec):
    return (
        mathutils.Matrix.Scale(
            vec[0],
            4,
            mathutils.Vector((1, 0.0, 0.0))
        ) *
        mathutils.Matrix.Scale(
            vec[1],
            4,
            mathutils.Vector((0.0, 1, 0.0))
        ) *
        mathutils.Matrix.Scale(
            vec[2],
            4,
            mathutils.Vector((0.0, 0.0, 1))
        )
    )


class AxisRotateBase(bpy.types.Operator):
    bl_idname = "sprig.axisrotatebase"
    bl_label = "Axis Rotate Base"
    bl_description = "Axis rotate base class"
    bl_options = {'REGISTER', 'UNDO'}
    target = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        previous_mode = bpy.context.active_object.mode
        if not hasattr(self, "quick_op_target"):
            active_item = prims[addon_data.active_list_item]
        else:
            active_item = addon_data.quick_axis_rotate_transf

        if (bpy.context.active_object and
                type(bpy.context.active_object.data) == bpy.types.Mesh):

            if not hasattr(self, "quick_op_target"):
                if prims[active_item.axr_axis].kind != 'LINE':
                    self.report(
                        {'ERROR'},
                        ('Wrong operands: acis rotate can only operate on '
                         'a line')
                    )
                    return {'CANCELLED'}

            # a bmesh can only be initialized in edit mode...
            if previous_mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            else:
                # else we could already be in edit mode with some stale
                # updates, exiting and reentering forces an update
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.editmode_toggle()

            # create common vars needed for object and for mesh
            # level transforms
            active_obj_transf = bpy.context.active_object.matrix_world.copy()
            t, r, s, = active_obj_transf.decompose()
            inverse_active = active_obj_transf.copy()
            inverse_active.invert()
            inv_translate, inv_rot, inv_scale = inverse_active.decompose()
            if (bpy.context.scene.unit_settings.system_rotation ==
                    'RADIANS'):
                converted_rot_amount = active_item.axr_amount
            else:
                converted_rot_amount = math.radians(
                    active_item.axr_amount
                )

            if hasattr(self, "quick_op_target"):
                loc_pivot = (
                    inverse_active * mathutils.Vector(
                        addon_data.quick_axis_rotate_src.line_start
                    )
                )
                loc_axis = (
                    inverse_active * mathutils.Vector(
                        addon_data.quick_axis_rotate_src.line_end
                    ) - inverse_active * mathutils.Vector(
                        addon_data.quick_axis_rotate_src.line_start
                    )
                )
                axis = mathutils.Vector(
                    addon_data.quick_axis_rotate_src.line_end
                ) - mathutils.Vector(
                    addon_data.quick_axis_rotate_src.line_start
                )
            else:
                loc_pivot = (
                    inverse_active * mathutils.Vector(
                        prims[active_item.axr_axis].line_start
                    )
                )
                loc_axis = (
                    inverse_active * mathutils.Vector(
                        prims[active_item.axr_axis].line_end
                    ) - inverse_active * mathutils.Vector(
                        prims[active_item.axr_axis].line_start
                    )
                )
                axis = mathutils.Vector(
                    prims[active_item.axr_axis].line_end
                ) - mathutils.Vector(
                    prims[active_item.axr_axis].line_start
                )
            axis_rot = mathutils.Matrix.Rotation(
                converted_rot_amount,
                4,
                axis
            )

            if self.target == 'OBJECT':
                bpy.context.active_object.rotation_euler.rotate(
                    axis_rot
                )
                bpy.context.scene.update()

                new_pivot_loc_global = (
                    bpy.context.active_object.matrix_world * loc_pivot
                )
                if hasattr(self, "quick_op_target"):
                    new_to_old_pivot_loc = (
                        mathutils.Vector(
                            addon_data.quick_axis_rotate_src.line_start
                        ) - new_pivot_loc_global
                    )
                else:
                    new_to_old_pivot_loc = (
                        mathutils.Vector(
                            prims[active_item.axr_axis].line_start
                        ) - new_pivot_loc_global
                    )
                bpy.context.active_object.location += new_to_old_pivot_loc

            else:
                self.report(
                    {'WARNING'},
                    ('Warning/Experimental: mesh transforms'
                     ' on objects with non-uniform scaling'
                     ' are not currently supported.'
                    )
                )
                # do mesh level stuff here
                src_mesh = bmesh.new()
                src_mesh.from_mesh(bpy.context.active_object.data)

                loc_pivot_negated = loc_pivot.copy()
                loc_pivot_negated.negate()

                loc_pivot_to_origin = mathutils.Matrix.Translation(
                    loc_pivot_negated
                )
                loc_pivot_to_origin.resize_4x4()

                loc_rotate = mathutils.Matrix.Rotation(
                    converted_rot_amount,
                    4,
                    loc_axis
                )

                loc_move_back = mathutils.Matrix.Translation(
                    loc_pivot
                )
                loc_move_back.resize_4x4()

                loc_axis_rotate = (
                    loc_move_back *
                    loc_rotate *
                    loc_pivot_to_origin
                )

                if self.target == 'MESHSELECTED':
                    if hasattr(self, "quick_op_target"):
                        if "_sel" not in bpy.context.active_object.vertex_groups:
                            self.report(
                                {'ERROR'},
                                ('Missing vertex group: A vertex group named '
                                 '"_sel" must be present to transform'
                                 'selected vertices with the Quick Tools.'
                                )
                            )
                            return {'CANCELLED'}
                        group_ind = (
                            bpy.context.active_object.vertex_groups["_sel"].index
                        )
                        target_verts = []
                        for vert in bpy.context.active_object.data.vertices:
                            for vgroup in vert.groups:
                                if vgroup.group == group_ind:
                                    target_verts.append(vert.index)
                        # todo, REPORT on no verts in the vert group
                        for v in src_mesh.verts:
                            if v.index in target_verts:
                                v.tag = True
                        src_mesh.transform(
                            loc_axis_rotate,
                            filter={'TAG'}
                        )
                        bpy.ops.object.mode_set(mode='OBJECT')
                        src_mesh.to_mesh(bpy.context.active_object.data)
                    else:
                        src_mesh.transform(
                            loc_axis_rotate,
                            filter={'SELECT'}
                        )
                        bpy.ops.object.mode_set(mode='OBJECT')
                        src_mesh.to_mesh(bpy.context.active_object.data)
                elif self.target == 'WHOLEMESH':
                    src_mesh.transform(loc_axis_rotate)
                    bpy.ops.object.mode_set(mode='OBJECT')
                    src_mesh.to_mesh(bpy.context.active_object.data)

                src_mesh.free()

            # Go back to whatever mode we were in before doing this
            bpy.ops.object.mode_set(mode=previous_mode)

        else:
            self.report(
                {'ERROR'},
                'Cannot transform: non-mesh or no active object.'
            )
            return {'CANCELLED'}

        return {'FINISHED'}


class AxisRotateObject(AxisRotateBase):
    bl_idname = "sprig.axisrotateobject"
    bl_label = "Axis Rotate"
    bl_description = "Rotates around an axis"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'


class QuickAxisRotateObject(AxisRotateBase):
    bl_idname = "sprig.quickaxisrotateobject"
    bl_label = "Axis Rotate"
    bl_description = "Rotates around an axis"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'
    quick_op_target = True


class AxisRotateMeshSelected(AxisRotateBase):
    bl_idname = "sprig.axisrotatemeshselected"
    bl_label = "Axis Rotate"
    bl_description = "Rotates around an axis"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class AxisRotateWholeMesh(AxisRotateBase):
    bl_idname = "sprig.axisrotatewholemesh"
    bl_label = "Axis Rotate"
    bl_description = "Rotates around an axis"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickAxisRotateMeshSelected(AxisRotateBase):
    bl_idname = "sprig.quickaxisrotatemeshselected"
    bl_label = "Axis Rotate"
    bl_description = "Rotates around an axis"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickAxisRotateWholeMesh(AxisRotateBase):
    bl_idname = "sprig.quickaxisrotatewholemesh"
    bl_label = "Axis Rotate"
    bl_description = "Rotates around an axis"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class MakeCollinearBase(bpy.types.Operator):
    bl_idname = "sprig.mkcollinearbase"
    bl_label = "Make Collinear Base"
    bl_description = "Makes collinear base class"
    bl_options = {'REGISTER', 'UNDO'}
    target = None

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        previous_mode = bpy.context.active_object.mode
        if hasattr(self, "quick_op_target"):
            active_item = addon_data.quick_make_collinear_transf
        else:
            active_item = prims[addon_data.active_list_item]

        if (bpy.context.active_object and
                type(bpy.context.active_object.data) == bpy.types.Mesh):

            if not hasattr(self, "quick_op_target"):
                if (prims[active_item.mcl_src_line].kind != 'LINE' or
                        prims[active_item.mcl_dest_line].kind != 'LINE'):
                    self.report(
                        {'ERROR'},
                        ('Wrong operands: make collinear can only operate on '
                         'two lines')
                    )
                    return {'CANCELLED'}

            # a bmesh can only be initialized in edit mode...
            if previous_mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            else:
                # else we could already be in edit mode with some stale
                # updates, exiting and reentering forces an update
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.editmode_toggle()

            if hasattr(self, "quick_op_target"):
                # construct lines from the selected list items
                bpy.ops.sprig.quickmakecollineargrabsrc()
                first_line = (
                    mathutils.Vector(addon_data.quick_make_collinear_src.line_end) -
                    mathutils.Vector(addon_data.quick_make_collinear_src.line_start)
                )
                second_line = (
                    mathutils.Vector(addon_data.quick_make_collinear_dest.line_end) -
                    mathutils.Vector(addon_data.quick_make_collinear_dest.line_start)
                )
                if active_item.mcl_ln_flip_direction:
                    first_line.negate()
                print("FIRSTLINE::", first_line)
                print("SECLINE::", second_line)
            else:
                # construct lines from the selected list items
                first_line = (
                    mathutils.Vector(prims[active_item.mcl_src_line].line_end) -
                    mathutils.Vector(prims[active_item.mcl_src_line].line_start)
                )
                second_line = (
                    mathutils.Vector(prims[active_item.mcl_dest_line].line_end) -
                    mathutils.Vector(prims[active_item.mcl_dest_line].line_start)
                )
                if prims[addon_data.active_list_item].mcl_ln_flip_direction:
                    first_line.negate()

                # Take geom modifiers into account, line one
                if prims[active_item.mcl_src_line].ln_make_unit_vec:
                    first_line.normalize()
                if prims[active_item.mcl_src_line].ln_flip_direction:
                    first_line.negate()
                first_line *= prims[active_item.mcl_src_line].ln_multiplier

                # Take geom modifiers into account, line two
                if prims[active_item.mcl_dest_line].ln_make_unit_vec:
                    second_line.normalize()
                if prims[active_item.mcl_dest_line].ln_flip_direction:
                    second_line.negate()
                second_line *= prims[active_item.mcl_dest_line].ln_multiplier

            # find rotational difference between source and dest lines
            rotational_diff = first_line.rotation_difference(second_line)
            transf_to_parallel_raw = rotational_diff.to_matrix()
            transf_to_parallel_raw.resize_4x4()

            # create common vars needed for object and for mesh
            # level transforms
            active_obj_transf = bpy.context.active_object.matrix_world.copy()
            t, r, s, = active_obj_transf.decompose()
            inverse_active = active_obj_transf.copy()
            inverse_active.invert()
            inv_translate, inv_rot, inv_scale = inverse_active.decompose()

            # put the original line starting point (before the ob was rotated)
            # into the local object space
            if hasattr(self, "quick_op_target"):
                src_pivot_location_local = (
                    inverse_active * mathutils.Vector(
                        addon_data.quick_make_collinear_src.line_start
                    )
                )
            else:
                src_pivot_location_local = (
                    inverse_active * mathutils.Vector(
                        prims[active_item.mcl_src_line].line_start
                    )
                )
            if self.target == 'OBJECT':
                # Do it!

                # rotate active object so line one is parallel linear,
                # position will be corrected after this
                bpy.context.active_object.rotation_euler.rotate(
                    rotational_diff
                )
                bpy.context.scene.update()

                # get final global position of pivot (source line
                # start coords) after object rotation
                final_pivot_location = (
                    bpy.context.active_object.matrix_world *
                    src_pivot_location_local
                )
                # figure out how to translate our object so that the source
                # line actually lies in the same line as dest
                if hasattr(self, "quick_op_target"):
                    final_translation = (
                        mathutils.Vector(
                            addon_data.quick_make_collinear_dest.line_start
                        ) - final_pivot_location
                    )
                else:
                    final_translation = (
                        mathutils.Vector(
                            prims[active_item.mcl_dest_line].line_start
                        ) - final_pivot_location
                    )

                bpy.context.active_object.location = (
                    bpy.context.active_object.location + final_translation
                )
            else:
                self.report(
                    {'WARNING'},
                    ('Warning/Experimental: mesh transforms'
                     ' on objects with non-uniform scaling'
                     ' are not currently supported.'
                    )
                )
                # Init source mesh
                src_mesh = bmesh.new()
                src_mesh.from_mesh(bpy.context.active_object.data)

                if hasattr(self, "quick_op_target"):
                    loc_src_pivot_coords = inverse_active * mathutils.Vector(
                            addon_data.quick_make_collinear_src.line_start
                    )
                else:
                    loc_src_pivot_coords = inverse_active * mathutils.Vector(
                            prims[active_item.mcl_src_line].line_start
                    )
                inverted_loc_src_pivot_coords = loc_src_pivot_coords.copy()
                inverted_loc_src_pivot_coords.negate()
                src_pivot_to_origin = mathutils.Matrix.Translation(
                    inverted_loc_src_pivot_coords
                )
                src_pivot_to_origin = src_pivot_to_origin.to_4x4()

                if hasattr(self, "quick_op_target"):
                    move_to_dest_pivot_translation = (
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_collinear_dest.line_start
                        )
                    )
                else:
                    move_to_dest_pivot_translation = (
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcl_dest_line].line_start
                        )
                    )
                move_to_dest_pivot_transf = mathutils.Matrix.Translation(
                    move_to_dest_pivot_translation
                )
                move_to_dest_pivot_transf = move_to_dest_pivot_transf.to_4x4()

                if hasattr(self, "quick_op_target"):
                    loc_first_line = (
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_collinear_src.line_end
                        ) -
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_collinear_src.line_start
                        )
                    )
                    loc_second_line = (
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_collinear_dest.line_end
                        ) -
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_collinear_dest.line_start
                        )
                    )
                    if active_item.mcl_ln_flip_direction:
                        loc_first_line.negate()
                else:
                    loc_first_line = (
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcl_src_line].line_end
                        ) -
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcl_src_line].line_start
                        )
                    )
                    loc_second_line = (
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcl_dest_line].line_end
                        ) -
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcl_dest_line].line_start
                        )
                    )
                loc_rot_diff = loc_first_line.rotation_difference(
                    loc_second_line
                )
                loc_parallel_linear_transf = loc_rot_diff.to_matrix()
                loc_parallel_linear_transf = (
                    loc_parallel_linear_transf.to_4x4()
                )
                loc_make_collinear = (
                    move_to_dest_pivot_transf *
                    loc_parallel_linear_transf *
                    src_pivot_to_origin
                )

                if self.target == 'MESHSELECTED':
                    if hasattr(self, "quick_op_target"):
                        if "_sel" not in bpy.context.active_object.vertex_groups:
                            self.report(
                                {'ERROR'},
                                ('Missing vertex group: A vertex group named '
                                 '"_sel" must be present to transform'
                                 'selected vertices with the Quick Tools.'
                                )
                            )
                            return {'CANCELLED'}
                        group_ind = (
                            bpy.context.active_object.vertex_groups["_sel"].index
                        )
                        target_verts = []
                        for vert in bpy.context.active_object.data.vertices:
                            for vgroup in vert.groups:
                                if vgroup.group == group_ind:
                                    target_verts.append(vert.index)
                        # todo, REPORT on no verts in the vert group
                        for v in src_mesh.verts:
                            if v.index in target_verts:
                                v.tag = True
                        src_mesh.transform(
                            loc_make_collinear,
                            filter={'TAG'}
                        )
                    else:
                        src_mesh.transform(
                            loc_make_collinear,
                            filter={'SELECT'}
                        )
                elif self.target == 'WHOLEMESH':
                    src_mesh.transform(loc_make_collinear)

                bpy.ops.object.mode_set(mode='OBJECT')
                src_mesh.to_mesh(bpy.context.active_object.data)
                src_mesh.free()

            # Go back to whatever mode we were in before doing this
            bpy.ops.object.mode_set(mode=previous_mode)

        else:
            self.report(
                {'ERROR'},
                'Cannot transform: non-mesh or no active object.'
            )
            return {'CANCELLED'}

        return {'FINISHED'}


class MakeCollinearObject(MakeCollinearBase):
    bl_idname = "sprig.mkcollinearobject"
    bl_label = "Make Collinear"
    bl_description = "Makes lines collinear (in line with each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'


class QuickMakeCollinearObject(MakeCollinearBase):
    bl_idname = "sprig.quickmakecollinearobject"
    bl_label = "Make Collinear"
    bl_description = "Makes lines collinear (in line with each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'
    quick_op_target = True


class MakeCollinearMeshSelected(MakeCollinearBase):
    bl_idname = "sprig.mkcollinearmeshselected"
    bl_label = "Make Collinear"
    bl_description = "Makes lines collinear (in line with each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class MakeCollinearWholeMesh(MakeCollinearBase):
    bl_idname = "sprig.mkcollinearwholemesh"
    bl_label = "Make Collinear"
    bl_description = "Makes lines collinear (in line with each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickMakeCollinearMeshSelected(MakeCollinearBase):
    bl_idname = "sprig.quickmakecollinearmeshselected"
    bl_label = "Make Collinear"
    bl_description = "Makes lines collinear (in line with each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickMakeCollinearWholeMesh(MakeCollinearBase):
    bl_idname = "sprig.quickmakecollinearwholemesh"
    bl_label = "Make Collinear"
    bl_description = "Makes lines collinear (in line with each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class MakeCoplanarBase(bpy.types.Operator):
    bl_idname = "sprig.mkcoplanarbase"
    bl_label = "Make Coplanar base"
    bl_description = "Make coplanar base class"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        previous_mode = bpy.context.active_object.mode
        if not hasattr(self, "quick_op_target"):
            active_item = prims[addon_data.active_list_item]
        else:
            active_item = addon_data.quick_make_coplanar_transf

        if (bpy.context.active_object and
                type(bpy.context.active_object.data) == bpy.types.Mesh):

            if not hasattr(self, "quick_op_target"):
                if (prims[active_item.mcp_src_plane].kind != 'PLANE' or
                        prims[active_item.mcp_dest_plane].kind != 'PLANE'):
                    self.report(
                        {'ERROR'},
                        ('Wrong operands: make coplanar can only operate on '
                         'two planes')
                    )
                    return {'CANCELLED'}

            # a bmesh can only be initialized in edit mode...
            if previous_mode != 'EDIT':
                bpy.ops.object.editmode_toggle()
            else:
                # else we could already be in edit mode with some stale
                # updates, exiting and reentering forces an update
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.editmode_toggle()

            if hasattr(self, "quick_op_target"):
                # construct normal vector for first (source) plane
                bpy.ops.sprig.quickmakecoplanargrabsrc()
                first_pln_ln_BA = (
                    mathutils.Vector(
                        addon_data.quick_make_coplanar_src.plane_pt_a
                    ) -
                    mathutils.Vector(
                        addon_data.quick_make_coplanar_src.plane_pt_b
                    )
                )
                first_pln_ln_BC = (
                    mathutils.Vector(
                        addon_data.quick_make_coplanar_src.plane_pt_c
                    ) -
                    mathutils.Vector(
                        addon_data.quick_make_coplanar_src.plane_pt_b
                    )
                )
                first_normal = first_pln_ln_BA.cross(first_pln_ln_BC)
                # flip first normal's direction if that option is toggled
                if active_item.mcp_flip_normal:
                    first_normal.negate()

                # construct normal vector for second (destination) plane
                second_pln_ln_BA = (
                    mathutils.Vector(
                        addon_data.quick_make_coplanar_dest.plane_pt_a
                    ) -
                    mathutils.Vector(
                        addon_data.quick_make_coplanar_dest.plane_pt_b
                    )
                )
                second_pln_ln_BC = (
                    mathutils.Vector(
                        addon_data.quick_make_coplanar_dest.plane_pt_c
                    ) -
                    mathutils.Vector(
                        addon_data.quick_make_coplanar_dest.plane_pt_b
                    )
                )
                second_normal = second_pln_ln_BA.cross(second_pln_ln_BC)
            else:
                # construct normal vector for first (source) plane
                first_pln_ln_BA = (
                    mathutils.Vector(
                        prims[active_item.mcp_src_plane].plane_pt_a
                    ) -
                    mathutils.Vector(
                        prims[active_item.mcp_src_plane].plane_pt_b
                    )
                )
                first_pln_ln_BC = (
                    mathutils.Vector(
                        prims[active_item.mcp_src_plane].plane_pt_c
                    ) -
                    mathutils.Vector(
                        prims[active_item.mcp_src_plane].plane_pt_b
                    )
                )
                first_normal = first_pln_ln_BA.cross(first_pln_ln_BC)
                # flip first normal's direction if that option is toggled
                if active_item.mcp_flip_normal:
                    first_normal.negate()

                # construct normal vector for second (destination) plane
                second_pln_ln_BA = (
                    mathutils.Vector(
                        prims[active_item.mcp_dest_plane].plane_pt_a
                    ) -
                    mathutils.Vector(
                        prims[active_item.mcp_dest_plane].plane_pt_b
                    )
                )
                second_pln_ln_BC = (
                    mathutils.Vector(
                        prims[active_item.mcp_dest_plane].plane_pt_c
                    ) -
                    mathutils.Vector(
                        prims[active_item.mcp_dest_plane].plane_pt_b
                    )
                )
                second_normal = second_pln_ln_BA.cross(second_pln_ln_BC)

            # find rotational difference between source and dest planes
            rotational_diff = first_normal.rotation_difference(second_normal)
            transf_to_parallel_raw = rotational_diff.to_matrix()
            transf_to_parallel_raw.resize_4x4()

            # create common vars needed for object and for mesh level transfs
            active_obj_transf = bpy.context.active_object.matrix_world.copy()
            t, r, s, = active_obj_transf.decompose()
            inverse_active = active_obj_transf.copy()
            inverse_active.invert()
            inv_translate, inv_rot, inv_scale = inverse_active.decompose()

            # get local coords using active object as basis, in other words,
            # determine coords of the source pivot relative to the active
            # object's origin by reversing the active object's transf from
            # the pivot's coords
            if hasattr(self, "quick_op_target"):
                local_src_pivot_coords = (
                    inverse_active * mathutils.Vector(
                        addon_data.quick_make_coplanar_src.plane_pt_b
                    )
                )
            else:
                local_src_pivot_coords = (
                    inverse_active * mathutils.Vector(
                        prims[active_item.mcp_src_plane].plane_pt_b
                    )
                )

            if self.target == 'OBJECT':
                # Do it!

                # try to rotate the object by the rotational_diff
                bpy.context.active_object.rotation_euler.rotate(
                    rotational_diff
                )
                bpy.context.scene.update()

                # find the new global location of the pivot
                new_active = bpy.context.active_object.matrix_world.copy()
                new_global_src_pivot_coords = (
                    new_active * local_src_pivot_coords
                )
                # figure out how to translate the object (the translation
                # vector) so that the source pivot sits on the destination
                # pivot's location
                # first vec is the global/absolute distance bw the two pivots
                if hasattr(self, "quick_op_target"):
                    final_translation_vector = (
                        mathutils.Vector(
                            addon_data.quick_make_coplanar_dest.plane_pt_b
                        ) - new_global_src_pivot_coords
                    )
                else:
                    final_translation_vector = (
                        mathutils.Vector(
                            prims[active_item.mcp_dest_plane].plane_pt_b
                        ) - new_global_src_pivot_coords
                    )
                bpy.context.active_object.location = (
                    bpy.context.active_object.location +
                    final_translation_vector
                )
                bpy.context.scene.update()

            else:
                self.report(
                    {'WARNING'},
                    ('Warning/Experimental: mesh transforms'
                     ' on objects with non-uniform scaling'
                     ' are not currently supported.'
                    )
                )
                src_mesh = bmesh.new()
                src_mesh.from_mesh(bpy.context.active_object.data)

                if hasattr(self, "quick_op_target"):
                    # Construct planes in local obj space to get rot diff
                    loc_first_pln_ln_BA = (
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_src.plane_pt_a
                        ) -
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_src.plane_pt_b
                        )
                    )
                    loc_first_pln_ln_BC = (
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_src.plane_pt_c
                        ) -
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_src.plane_pt_b
                        )
                    )
                    loc_first_normal = loc_first_pln_ln_BA.cross(
                        loc_first_pln_ln_BC
                    )

                    loc_second_pln_ln_BA = (
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_dest.plane_pt_a
                        ) -
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_dest.plane_pt_b
                        )
                    )
                    loc_second_pln_ln_BC = (
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_dest.plane_pt_c
                        ) -
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_dest.plane_pt_b
                        )
                    )
                    loc_second_normal = loc_second_pln_ln_BA.cross(
                        loc_second_pln_ln_BC
                    )

                    local_dest_pivot_coords = (
                        inverse_active * mathutils.Vector(
                            addon_data.quick_make_coplanar_dest.plane_pt_b
                        )
                    )
                else:
                    # Construct planes in local obj space to get rot diff
                    loc_first_pln_ln_BA = (
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_src_plane].plane_pt_a
                        ) -
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_src_plane].plane_pt_b
                        )
                    )
                    loc_first_pln_ln_BC = (
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_src_plane].plane_pt_c
                        ) -
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_src_plane].plane_pt_b
                        )
                    )
                    loc_first_normal = loc_first_pln_ln_BA.cross(
                        loc_first_pln_ln_BC
                    )

                    loc_second_pln_ln_BA = (
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_dest_plane].plane_pt_a
                        ) -
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_dest_plane].plane_pt_b
                        )
                    )
                    loc_second_pln_ln_BC = (
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_dest_plane].plane_pt_c
                        ) -
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_dest_plane].plane_pt_b
                        )
                    )
                    loc_second_normal = loc_second_pln_ln_BA.cross(
                        loc_second_pln_ln_BC
                    )

                    local_dest_pivot_coords = (
                        inverse_active * mathutils.Vector(
                            prims[active_item.mcp_dest_plane].plane_pt_b
                        )
                    )
                    

                # Move the src pivot to the local origin, so that
                # it's easier to move after rotating
                inverted_local_src_pivot_coords = (
                    local_src_pivot_coords.copy()
                )
                inverted_local_src_pivot_coords.negate()

                loc_rot_diff = loc_first_normal.rotation_difference(
                    loc_second_normal
                )

                loc_transf_to_parallel_raw = loc_rot_diff.to_matrix()
                loc_transf_to_parallel_raw.resize_4x4()

                src_pivot_to_origin = mathutils.Matrix.Translation(
                    inverted_local_src_pivot_coords
                )

                if hasattr(self, "quick_op_target"):
                    move_to_dest_pivot_translation = inverse_active * (
                        mathutils.Vector(
                            addon_data.quick_make_coplanar_dest.plane_pt_b
                        )
                    )
                else:
                    move_to_dest_pivot_translation = inverse_active * (
                        mathutils.Vector(
                            prims[active_item.mcp_dest_plane].plane_pt_b
                        )
                    )

                move_to_dest_pivot_transf = mathutils.Matrix.Translation(
                    local_dest_pivot_coords
                )
                move_to_dest_pivot_transf.resize_4x4()

                mesh_coplanar = (
                    move_to_dest_pivot_transf *
                    loc_transf_to_parallel_raw *
                    src_pivot_to_origin
                )

                if self.target == 'MESHSELECTED':
                    if hasattr(self, "quick_op_target"):
                        if "_sel" not in bpy.context.active_object.vertex_groups:
                            self.report(
                                {'ERROR'},
                                ('Missing vertex group: A vertex group named '
                                 '"_sel" must be present to transform'
                                 'selected vertices with the Quick Tools.'
                                )
                            )
                            return {'CANCELLED'}
                        group_ind = (
                            bpy.context.active_object.vertex_groups["_sel"].index
                        )
                        target_verts = []
                        for vert in bpy.context.active_object.data.vertices:
                            for vgroup in vert.groups:
                                if vgroup.group == group_ind:
                                    target_verts.append(vert.index)
                        # todo, REPORT on no verts in the vert group
                        for v in src_mesh.verts:
                            if v.index in target_verts:
                                v.tag = True
                        src_mesh.transform(
                            mesh_coplanar,
                            filter={'TAG'}
                        )
                    else:
                        src_mesh.transform(
                            mesh_coplanar,
                            filter={'SELECT'}
                        )
                elif self.target == 'WHOLEMESH':
                    src_mesh.transform(mesh_coplanar)

                bpy.ops.object.mode_set(mode='OBJECT')
                src_mesh.to_mesh(bpy.context.active_object.data)

            # Go back to whatever mode we were in before doing this
            bpy.ops.object.mode_set(mode=previous_mode)

        else:
            self.report(
                {'ERROR'},
                "\nCannot transform: non-mesh or no active object."
            )
            return {'CANCELLED'}

        return {'FINISHED'}


class MakeCoplanarObject(MakeCoplanarBase):
    bl_idname = "sprig.mkcoplanarobject"
    bl_label = "Make Coplanar"
    bl_description = "Makes planes coplanar (flat against each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'


class QuickMakeCoplanarObject(MakeCoplanarBase):
    bl_idname = "sprig.quickmakecoplanarobject"
    bl_label = "Make Coplanar"
    bl_description = "Makes planes coplanar (flat against each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'OBJECT'
    quick_op_target = True


class MakeCoplanarMeshSelected(MakeCoplanarBase):
    bl_idname = "sprig.mkcoplanarmeshselected"
    bl_label = "Make Coplanar"
    bl_description = "Makes planes coplanar (flat against each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class MakeCoplanarWholeMesh(MakeCoplanarBase):
    bl_idname = "sprig.mkcoplanarwholemesh"
    bl_label = "Make Coplanar"
    bl_description = "Makes planes coplanar (flat against each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickMakeCoplanarMeshSelected(MakeCoplanarBase):
    bl_idname = "sprig.quickmakecoplanarmeshselected"
    bl_label = "Make Coplanar"
    bl_description = "Makes planes coplanar (flat against each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'MESHSELECTED'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


class QuickMakeCoplanarWholeMesh(MakeCoplanarBase):
    bl_idname = "sprig.quickmakecoplanarwholemesh"
    bl_label = "Make Coplanar"
    bl_description = "Makes planes coplanar (flat against each other)"
    bl_options = {'REGISTER', 'UNDO'}
    target = 'WHOLEMESH'
    quick_op_target = True

    @classmethod
    def poll(cls, context):
        addon_data = bpy.context.scene.sprig_data
        if not addon_data.use_experimental:
            return False
        return True


# Custom list, for displaying combined list of all primitives (Used at top
# of main panel and for item pointers in transformation primitives
class SPRIGList(bpy.types.UIList):

    def draw_item(self,
                  context,
                  layout,
                  data,
                  item,
                  icon,
                  active_data,
                  active_propname
                  ):
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list

        # Check which type of primitive, separate draw code for each
        if item.kind == 'POINT':
            layout.label(item.name, icon="LAYER_ACTIVE")
        elif item.kind == 'LINE':
            layout.label(item.name, icon="MAN_TRANS")
        elif item.kind == 'PLANE':
            layout.label(item.name, icon="OUTLINER_OB_MESH")
        elif item.kind == 'CALCULATION':
            layout.label(item.name, icon="NODETREE")
        elif item.kind == 'TRANSFORMATION':
            layout.label(item.name, icon="MANIPUL")


# Main panel containing almost all the functionality for the addon
class SPRIGGui(bpy.types.Panel):
    bl_idname = "sprig_tools_alpha"
    bl_label = "SPRIG Tools Alpha"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "scene"

    def draw(self, context):
        layout = self.layout
        sprig_data_ptr = bpy.types.AnyType(bpy.context.scene.sprig_data)
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list
        if len(prims) > 0:
            active_item = prims[addon_data.active_list_item]

        # We start with a row that holds the prim list and buttons
        # for adding/subtracting prims (the data management section
        # of the interface)
        sprig_data_mgmt_row = layout.row()
        sprig_items_list = sprig_data_mgmt_row.column()
        sprig_items_list.template_list(
            "SPRIGList",
            "",
            sprig_data_ptr,
            "prim_list",
            sprig_data_ptr,
            "active_list_item",
            type='DEFAULT'
        )
        add_remove_data_col = sprig_data_mgmt_row.column(align=True)
        add_remove_data_col.operator(
            "sprig.addlistitem",
            icon='ZOOMIN',
            text=""
        )
        add_remove_data_col.operator(
            "sprig.removelistitem",
            icon='ZOOMOUT',
            text=""
        )

        # Items below data management section, this consists of either the
        # empty list message or the Primitive type selector (for when the
        # list is not empty, it allow users to choose the type of the
        # current primitive)
        if len(prims) == 0:
            layout.label("Click the + button to add items")
        else:
            basic_item_attribs_col = layout.column()
            basic_item_attribs_col.label("Item Name and Type Selectors:")
            item_name_and_types = basic_item_attribs_col.row(align=True)
            item_name_and_types.prop(
                bpy.types.AnyType(active_item),
                'name',
                ""
            )
            item_name_and_types.operator(
                "sprig.changetypetopointprim",
                icon='LAYER_ACTIVE',
                text=""
            )
            item_name_and_types.operator(
                "sprig.changetypetolineprim",
                icon='MAN_TRANS',
                text=""
            )
            item_name_and_types.operator(
                "sprig.changetypetoplaneprim",
                icon='OUTLINER_OB_MESH',
                text=""
            )
            item_name_and_types.operator(
                "sprig.changetypetocalcprim",
                icon='NODETREE',
                text=""
            )
            item_name_and_types.operator(
                "sprig.changetypetotransfprim",
                icon='MANIPUL',
                text=""
            )
            basic_item_attribs_col.separator()

            # Item-specific UI elements (primitive-specific data like coords
            # for plane points, transformation type etc.)
            item_info_col = layout.column()

            if active_item.kind == 'POINT':
                item_info_col.label("Point Modifiers:")
                item_mods_box = item_info_col.box()
                mods_row_1 = item_mods_box.row()
                mods_row_1.prop(
                    bpy.types.AnyType(active_item),
                    'pt_make_unit_vec',
                    "Set Length Equal to One"
                )
                mods_row_1.prop(
                    bpy.types.AnyType(active_item),
                    'pt_flip_direction',
                    "Flip Direction"
                )
                mods_row_2 = item_mods_box.row()
                mods_row_2.prop(
                    bpy.types.AnyType(active_item),
                    'pt_multiplier',
                    "Multiplier"
                )
                item_info_col.separator()

                item_info_col.label("Point Coordinates:")
                pt_grab_all = item_info_col.row(align=True)
                pt_grab_all.operator(
                    "sprig.grabpointfromcursor",
                    icon='CURSOR',
                    text="Grab Cursor"
                )
                pt_grab_all.operator(
                    "sprig.grabpointfromactivelocal",
                    icon='VERTEXSEL',
                    text="Grab All Local"
                )
                pt_grab_all.operator(
                    "sprig.grabpointfromactiveglobal",
                    icon='WORLD',
                    text="Grab All Global"
                )
                item_info_col.separator()

                item_info_col.label('Pt. Origin:')
                pt_coord_items = item_info_col.split(percentage=.75)
                typein_and_grab = pt_coord_items.column()
                pt_coord_uppers = typein_and_grab.row()

                pt_coord_uppers_leftside = pt_coord_uppers.row(align=True)
                pt_coord_uppers_leftside.alignment = 'LEFT'
                pt_coord_uppers_leftside.label("Send:")
                pt_coord_uppers_leftside.operator(
                    "sprig.sendpointtocursor",
                    icon='CURSOR',
                    text=""
                )

                pt_coord_uppers_rightside = pt_coord_uppers.row(align=True)
                pt_coord_uppers_rightside.alignment = 'RIGHT'
                pt_coord_uppers_rightside.label("Grab:")
                pt_coord_uppers_rightside.operator(
                    "sprig.grabpointfromcursor",
                    icon='CURSOR',
                    text=""
                )
                pt_coord_uppers_rightside.operator(
                    "sprig.grabpointfromactivelocal",
                    icon='VERTEXSEL',
                    text=""
                )
                pt_coord_uppers_rightside.operator(
                    "sprig.grabpointfromactiveglobal",
                    icon='WORLD',
                    text=""
                )
                typein_and_grab.prop(
                    bpy.types.AnyType(active_item),
                    'point',
                    ""
                )

                component_changers = pt_coord_items.row()
                zero_components = component_changers.column(align=True)
                zero_components.label("Set Zeroes:")
                zero_components.operator(
                    "sprig.zerootherpointx",
                    text="X00"
                )
                zero_components.operator(
                    "sprig.zerootherpointy",
                    text="0Y0"
                )
                zero_components.operator(
                    "sprig.zerootherpointz",
                    text="00Z"
                )
                one_components = component_changers.column(align=True)
                one_components.label("Set Ones:")
                one_components.operator(
                    "sprig.oneotherpointx",
                    text="X11"
                )
                one_components.operator(
                    "sprig.oneotherpointy",
                    text="1Y1"
                )
                one_components.operator(
                    "sprig.oneotherpointz",
                    text="11Z"
                )

            elif active_item.kind == 'LINE':
                item_info_col.label("Line Modifiers:")
                item_mods_box = item_info_col.box()
                mods_row_1 = item_mods_box.row()
                mods_row_1.prop(
                    bpy.types.AnyType(active_item),
                    'ln_make_unit_vec',
                    "Set Length Equal to One"
                )
                mods_row_1.prop(
                    bpy.types.AnyType(active_item),
                    'ln_flip_direction',
                    "Flip Direction"
                )
                mods_row_2 = item_mods_box.row()
                mods_row_2.prop(
                    bpy.types.AnyType(active_item),
                    'ln_multiplier',
                    "Multiplier"
                )
                item_info_col.separator()

                item_info_col.label("Line Coordinates:")
                ln_grab_all = item_info_col.row(align=True)
                ln_grab_all.operator(
                    "sprig.graballvertslinelocal",
                    icon='VERTEXSEL',
                    text="Grab All Local"
                )
                ln_grab_all.operator(
                    "sprig.graballvertslineglobal",
                    icon='WORLD',
                    text="Grab All Global"
                )
                item_info_col.separator()

                item_info_col.label("Start:")
                ln_start_items = item_info_col.split(percentage=.75)
                typein_and_grab_start = ln_start_items.column()
                ln_start_uppers = typein_and_grab_start.split(percentage=.33)
                ln_start_swap = ln_start_uppers.row(align=True)
                ln_start_swap.label("Swap:")
                ln_start_swap.operator(
                    "sprig.swaplinepoints",
                    text="End"
                )

                ln_start_uppers_rightside = ln_start_uppers.row(align=True)
                ln_start_uppers_rightside.alignment = 'RIGHT'

                ln_start_uppers_rightside.label("Send:")
                ln_start_uppers_rightside.operator(
                    "sprig.sendlinestarttocursor",
                    icon='CURSOR',
                    text=""
                )

                ln_start_uppers_rightside.label("Grab:")
                ln_start_uppers_rightside.operator(
                    "sprig.grablinestartfromcursor",
                    icon='CURSOR',
                    text=""
                )
                ln_start_uppers_rightside.operator(
                    "sprig.grablinestartfromactivelocal",
                    icon='VERTEXSEL',
                    text=""
                )
                ln_start_uppers_rightside.operator(
                    "sprig.grablinestartfromactiveglobal",
                    icon='WORLD',
                    text=""
                )
                typein_and_grab_start.prop(
                    bpy.types.AnyType(active_item),
                    'line_start',
                    ""
                )
                item_info_col.separator()

                component_changers_start = ln_start_items.row()
                zero_components = component_changers_start.column(align=True)
                zero_components.label("Set Zeroes:")
                zero_components.operator(
                    "sprig.zerootherlinestartx",
                    text="X00"
                )
                zero_components.operator(
                    "sprig.zerootherlinestarty",
                    text="0Y0"
                )
                zero_components.operator(
                    "sprig.zerootherlinestartz",
                    text="00Z"
                )
                one_components = component_changers_start.column(align=True)
                one_components.label("Set Ones:")
                one_components.operator(
                    "sprig.oneotherlinestartx",
                    text="X11"
                )
                one_components.operator(
                    "sprig.oneotherlinestarty",
                    text="1Y1"
                )
                one_components.operator(
                    "sprig.oneotherlinestartz",
                    text="11Z"
                )

                item_info_col.label("End:")
                ln_end_items = item_info_col.split(percentage=.75)
                typein_and_grab_end = ln_end_items.column()
                ln_end_uppers = typein_and_grab_end.split(percentage=.33)
                ln_end_swap = ln_end_uppers.row(align=True)
                ln_end_swap.label("Swap:")
                ln_end_swap.operator(
                    "sprig.swaplinepoints",
                    text="Start"
                )

                ln_end_uppers_rightside = ln_end_uppers.row(align=True)
                ln_end_uppers_rightside.alignment = 'RIGHT'
                ln_end_uppers_rightside.label("Send:")
                ln_end_uppers_rightside.operator(
                    "sprig.sendlineendtocursor",
                    icon='CURSOR',
                    text=""
                )

                ln_end_uppers_rightside.label("Grab:")
                ln_end_uppers_rightside.operator(
                    "sprig.grablineendfromcursor",
                    icon='CURSOR',
                    text=""
                )
                ln_end_uppers_rightside.operator(
                    "sprig.grablineendfromactivelocal",
                    icon='VERTEXSEL',
                    text=""
                )
                ln_end_uppers_rightside.operator(
                    "sprig.grablineendfromactiveglobal",
                    icon='WORLD',
                    text=""
                )
                typein_and_grab_end.prop(
                    bpy.types.AnyType(active_item),
                    'line_end',
                    ""
                )
                item_info_col.separator()

                component_changers_end = ln_end_items.row()
                zero_components = component_changers_end.column(align=True)
                zero_components.label("Set Zeroes:")
                zero_components.operator(
                    "sprig.zerootherlineendx",
                    text="X00"
                )
                zero_components.operator(
                    "sprig.zerootherlineendy",
                    text="0Y0"
                )
                zero_components.operator(
                    "sprig.zerootherlineendz",
                    text="00Z"
                )
                one_components = component_changers_end.column(align=True)
                one_components.label("Set Ones:")
                one_components.operator(
                    "sprig.oneotherlineendx",
                    text="X11"
                )
                one_components.operator(
                    "sprig.oneotherlineendy",
                    text="1Y1"
                )
                one_components.operator(
                    "sprig.oneotherlineendz",
                    text="11Z"
                )

            elif active_item.kind == 'PLANE':
                item_info_col.label("Plane Coordinates:")
                plane_grab_all = item_info_col.row(align=True)
                plane_grab_all.operator(
                    "sprig.graballvertsplanelocal",
                    icon='VERTEXSEL',
                    text="Grab All Local"
                )
                plane_grab_all.operator(
                    "sprig.graballvertsplaneglobal",
                    icon='WORLD',
                    text="Grab All Global"
                )
                item_info_col.separator()

                item_info_col.label("Pt. A:")
                plane_a_items = item_info_col.split(percentage=.75)
                typein_and_grab_plna = plane_a_items.column()
                plane_a_uppers = typein_and_grab_plna.split(percentage=.33)

                plane_a_swap = plane_a_uppers.row(align=True)
                plane_a_swap.label("Swap With:")
                plane_a_swap.operator(
                    "sprig.swapplaneaplaneb",
                    text="B"
                )
                plane_a_swap.operator(
                    "sprig.swapplaneaplanec",
                    text="C"
                )

                plane_a_uppers_rightside = plane_a_uppers.row(align=True)
                plane_a_uppers_rightside.alignment = 'RIGHT'
                plane_a_uppers_rightside.label("Send:")
                plane_a_uppers_rightside.operator(
                    "sprig.sendplaneatocursor",
                    icon='CURSOR',
                    text=""
                )

                plane_a_uppers_rightside.label("Grab:")
                plane_a_uppers_rightside.operator(
                    "sprig.grabplaneafromcursor",
                    icon='CURSOR',
                    text=""
                )
                plane_a_uppers_rightside.operator(
                    "sprig.grabplaneafromactivelocal",
                    icon='VERTEXSEL',
                    text=""
                )
                plane_a_uppers_rightside.operator(
                    "sprig.grabplaneafromactiveglobal",
                    icon='WORLD',
                    text=""
                )
                typein_and_grab_plna.prop(
                    bpy.types.AnyType(active_item),
                    'plane_pt_a',
                    ""
                )
                item_info_col.separator()

                component_changers_plna = plane_a_items.row()
                zero_components_plna = component_changers_plna.column(
                    align=True
                )
                zero_components_plna.label("Set Zeroes:")
                zero_components_plna.operator(
                    "sprig.zerootherplanepointax",
                    text="X00"
                )
                zero_components_plna.operator(
                    "sprig.zerootherplanepointay",
                    text="0Y0"
                )
                zero_components_plna.operator(
                    "sprig.zerootherplanepointaz",
                    text="00Z"
                )
                one_components_plna = component_changers_plna.column(
                    align=True
                )
                one_components_plna.label("Set Ones:")
                one_components_plna.operator(
                    "sprig.oneotherplanepointax",
                    text="X11"
                )
                one_components_plna.operator(
                    "sprig.oneotherplanepointay",
                    text="1Y1"
                )
                one_components_plna.operator(
                    "sprig.oneotherplanepointaz",
                    text="11Z"
                )

                item_info_col.label("Pt. B (Pivot):")
                plane_b_items = item_info_col.split(percentage=.75)
                typein_and_grab_plnb = plane_b_items.column()
                plane_b_uppers = typein_and_grab_plnb.split(percentage=.33)
                plane_b_swap = plane_b_uppers.row(align=True)
                plane_b_swap.label("Swap With:")
                plane_b_swap.operator(
                    "sprig.swapplaneaplaneb",
                    text="A"
                )
                plane_b_swap.operator(
                    "sprig.swapplanebplanec",
                    text="C"
                )

                plane_b_uppers_rightside = plane_b_uppers.row(align=True)
                plane_b_uppers_rightside.alignment = 'RIGHT'
                plane_b_uppers_rightside.label("Send:")
                plane_b_uppers_rightside.operator(
                    "sprig.sendplanebtocursor",
                    icon='CURSOR',
                    text=""
                )

                plane_b_uppers_rightside.label("Grab:")
                plane_b_uppers_rightside.operator(
                    "sprig.grabplanebfromcursor",
                    icon='CURSOR',
                    text=""
                )
                plane_b_uppers_rightside.operator(
                    "sprig.grabplanebfromactivelocal",
                    icon='VERTEXSEL',
                    text=""
                )
                plane_b_uppers_rightside.operator(
                    "sprig.grabplanebfromactiveglobal",
                    icon='WORLD',
                    text=""
                )
                typein_and_grab_plnb.prop(
                    bpy.types.AnyType(active_item),
                    'plane_pt_b',
                    ""
                )
                item_info_col.separator()

                component_changers_plnb = plane_b_items.row()
                zero_components_plnb = component_changers_plnb.column(
                    align=True
                )
                zero_components_plnb.label("Set Zeroes:")
                zero_components_plnb.operator(
                    "sprig.zerootherplanepointbx",
                    text="X00"
                )
                zero_components_plnb.operator(
                    "sprig.zerootherplanepointby",
                    text="0Y0"
                )
                zero_components_plnb.operator(
                    "sprig.zerootherplanepointbz",
                    text="00Z"
                )
                one_components_plnb = component_changers_plnb.column(
                    align=True
                )
                one_components_plnb.label("Set Ones:")
                one_components_plnb.operator(
                    "sprig.oneotherplanepointbx",
                    text="X11"
                )
                one_components_plnb.operator(
                    "sprig.oneotherplanepointby",
                    text="1Y1"
                )
                one_components_plnb.operator(
                    "sprig.oneotherplanepointbz",
                    text="11Z"
                )

                item_info_col.label("Pt. C:")
                plane_c_items = item_info_col.split(percentage=.75)
                typein_and_grab_plnc = plane_c_items.column()
                plane_c_uppers = typein_and_grab_plnc.split(percentage=.33)
                plane_c_swap = plane_c_uppers.row(align=True)
                plane_c_swap.label("Swap With:")
                plane_c_swap.operator(
                    "sprig.swapplaneaplanec",
                    text="A"
                )
                plane_c_swap.operator(
                    "sprig.swapplanebplanec",
                    text="B"
                )

                plane_c_uppers_rightside = plane_c_uppers.row(align=True)
                plane_c_uppers_rightside.alignment = 'RIGHT'
                plane_c_uppers_rightside.label("Send:")
                plane_c_uppers_rightside.operator(
                    "sprig.sendplanectocursor",
                    icon='CURSOR',
                    text=""
                )

                plane_c_uppers_rightside.label("Grab:")
                plane_c_uppers_rightside.operator(
                    "sprig.grabplanecfromcursor",
                    icon='CURSOR',
                    text=""
                )
                plane_c_uppers_rightside.operator(
                    "sprig.grabplanecfromactivelocal",
                    icon='VERTEXSEL',
                    text=""
                )
                plane_c_uppers_rightside.operator(
                    "sprig.grabplanecfromactiveglobal",
                    icon='WORLD',
                    text=""
                )
                typein_and_grab_plnc.prop(
                    bpy.types.AnyType(active_item),
                    'plane_pt_c',
                    ""
                )

                component_changers_plnc = plane_c_items.row()
                zero_components_plnc = component_changers_plnc.column(
                    align=True
                )
                zero_components_plnc.label("Set Zeroes:")
                zero_components_plnc.operator(
                    "sprig.zerootherplanepointcx",
                    text="X00"
                )
                zero_components_plnc.operator(
                    "sprig.zerootherplanepointcy",
                    text="0Y0"
                )
                zero_components_plnc.operator(
                    "sprig.zerootherplanepointcz",
                    text="00Z"
                )
                one_components_plnc = component_changers_plnc.column(
                    align=True
                )
                one_components_plnc.label("Set Ones:")
                one_components_plnc.operator(
                    "sprig.oneotherplanepointcx",
                    text="X11"
                )
                one_components_plnc.operator(
                    "sprig.oneotherplanepointcy",
                    text="1Y1"
                )
                one_components_plnc.operator(
                    "sprig.oneotherplanepointcz",
                    text="11Z"
                )

            elif active_item.kind == 'CALCULATION':
                item_info_col.label("Coming soon.")

            elif active_item.kind == 'TRANSFORMATION':
                item_info_col.label("Transformation Type Selectors:")
                transf_types = item_info_col.row(align=True)
                transf_types.operator(
                    "sprig.changetransftopointmatch",
                    icon='ROTATECOLLECTION',
                    text="Point Match"
                )
                transf_types.operator(
                    "sprig.changetransftovectorslide",
                    icon='CURVE_PATH',
                    text="Vector Slide"
                )
                transf_types.operator(
                    "sprig.changetransftoscalematchedge",
                    icon='FULLSCREEN_ENTER',
                    text="ScaleMatchEdge"
                )
                transf_types.operator(
                    "sprig.changetransftomkcollinear",
                    icon='SNAP_EDGE',
                    text="Make Collinear"
                )
                transf_types.operator(
                    "sprig.changetransftoaxisrotate",
                    icon='FORCE_MAGNETIC',
                    text="Axis Rotate"
                )
                transf_types.operator(
                    "sprig.changetransftomkcoplanar",
                    icon='MOD_ARRAY',
                    text="Make Coplanar"
                )
                item_info_col.separator()

                apply_buttons_header = item_info_col.row()
                if active_item.transf_type == 'POINTMATCH':
                    apply_buttons_header.label('Apply Point Match to:')
                    apply_buttons = item_info_col.split(percentage=.33)
                    apply_buttons.operator(
                        "sprig.pointmatchobject",
                        icon='NONE',
                        text="Object"
                    )
                    mesh_appliers = apply_buttons.row(align=True)
                    mesh_appliers.operator(
                        "sprig.pointmatchmeshselected",
                        icon='NONE',
                        text="Mesh Piece"
                    )
                    mesh_appliers.operator(
                        "sprig.pointmatchwholemesh",
                        icon='NONE',
                        text=" Whole Mesh"
                    )
                elif active_item.transf_type == 'VECTORSLIDE':
                    apply_buttons_header.label('Apply Vector Slide to:')
                    apply_buttons = item_info_col.split(percentage=.33)
                    apply_buttons.operator(
                        "sprig.vectorslideobject",
                        icon='NONE',
                        text="Object"
                    )
                    mesh_appliers = apply_buttons.row(align=True)
                    mesh_appliers.operator(
                        "sprig.vectorslidemeshselected",
                        icon='NONE', text="Mesh Piece"
                    )
                    mesh_appliers.operator(
                        "sprig.vectorslidewholemesh",
                        icon='NONE',
                        text="Whole Mesh"
                    )
                elif active_item.transf_type == 'SCALEMATCHEDGE':
                    apply_buttons_header.label('Apply Scale Match Edge to:')
                    apply_buttons = item_info_col.split(percentage=.33)
                    apply_buttons.operator(
                        "sprig.scalematchedgeobject",
                        icon='NONE',
                        text="Object"
                    )
                    mesh_appliers = apply_buttons.row(align=True)
                    mesh_appliers.operator(
                        "sprig.scalematchedgemeshselected",
                        icon='NONE', text="Mesh Piece"
                    )
                    mesh_appliers.operator(
                        "sprig.scalematchedgewholemesh",
                        icon='NONE',
                        text="Whole Mesh"
                    )
                elif active_item.transf_type == 'AXISROTATE':
                    apply_buttons_header.label('Apply Axis Rotate to:')
                    apply_buttons = item_info_col.split(percentage=.33)
                    apply_buttons.operator(
                        "sprig.axisrotateobject",
                        icon='NONE',
                        text="Object"
                    )
                    mesh_appliers = apply_buttons.row(align=True)
                    mesh_appliers.operator(
                        "sprig.axisrotatemeshselected",
                        icon='NONE', text="Mesh Piece"
                    )
                    mesh_appliers.operator(
                        "sprig.axisrotatewholemesh",
                        icon='NONE',
                        text="Whole Mesh"
                    )
                elif active_item.transf_type == 'MKCOLLINEAR':
                    apply_buttons_header.label('Apply Make Collinear to:')
                    apply_buttons = item_info_col.split(percentage=.33)
                    apply_buttons.operator(
                        "sprig.mkcollinearobject",
                        icon='NONE',
                        text="Object"
                    )
                    mesh_appliers = apply_buttons.row(align=True)
                    mesh_appliers.operator(
                        "sprig.mkcollinearmeshselected",
                        icon='NONE',
                        text="Mesh Piece"
                    )
                    mesh_appliers.operator(
                        "sprig.mkcollinearwholemesh",
                        icon='NONE',
                        text="Whole Mesh"
                    )
                elif active_item.transf_type == 'MKCOPLANAR':
                    apply_buttons_header.label('Apply Make Coplanar to:')
                    apply_buttons = item_info_col.split(percentage=.33)
                    apply_buttons.operator(
                        "sprig.mkcoplanarobject",
                        icon='NONE',
                        text="Object"
                    )
                    mesh_appliers = apply_buttons.row(align=True)
                    mesh_appliers.operator(
                        "sprig.mkcoplanarmeshselected",
                        icon='NONE',
                        text="Mesh Piece"
                    )
                    mesh_appliers.operator(
                        "sprig.mkcoplanarwholemesh",
                        icon='NONE',
                        text="Whole Mesh"
                    )
                item_info_col.separator()
                experiment_toggle= apply_buttons_header.column()
                experiment_toggle.prop(
                        addon_data,
                        'use_experimental',
                        'Enable Experimental Mesh Ops.'
                )

                active_transf = bpy.types.AnyType(active_item)

                # Todo, add scale match edge mods
                if (active_item.transf_type != 'SCALEMATCHEDGE' and
                                active_item.transf_type != 'AXISROTATE'):
                    item_info_col.label('Transformation Modifiers:')
                    item_mods_box = item_info_col.box()
                    mods_row_1 = item_mods_box.row()
                    mods_row_2 = item_mods_box.row()
                if active_item.transf_type == "POINTMATCH":
                    mods_row_1.prop(
                        active_transf,
                        'pm_ln_make_unit_vec',
                        'Set Length Equal to One'
                    )
                    mods_row_1.prop(
                        active_transf,
                        'pm_ln_flip_direction',
                        'Flip Direction'
                    )
                    mods_row_2.prop(
                        active_transf,
                        'pm_multiplier',
                        'Multiplier'
                    )
                if active_item.transf_type == "VECTORSLIDE":
                    item_info_col.label('Item Modifiers:')
                    mods_row_1.prop(
                        active_transf,
                        'vs_ln_make_unit_vec',
                        "Set Length Equal to One"
                    )
                    mods_row_1.prop(
                        active_transf,
                        'vs_ln_flip_direction',
                        "Flip Direction"
                    )
                    mods_row_2.prop(
                        active_transf,
                        'vs_multiplier',
                        "Multiplier"
                    )
                if active_item.transf_type == "MKCOLLINEAR":
                    mods_row_1.prop(
                        active_transf,
                        'mcl_ln_flip_direction',
                        "Flip Direction"
                    )
                if active_item.transf_type == "MKCOPLANAR":
                    mods_row_1.prop(
                        active_transf,
                        'mcp_flip_normal',
                        "Flip Source Normal"
                    )
                item_info_col.separator()

                # Designate operands for the transformation by pointing to
                # other primitive items in the main list. The indices are
                # stored on each primitive item
                if active_item.transf_type == "POINTMATCH":
                    item_info_col.label("Source Point")
                    item_info_col.template_list(
                        "SPRIGList",
                        "pm_pt_one_list",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "pm_pt_one",
                        type='DEFAULT'
                    )
                    item_info_col.separator()
                    item_info_col.label("Destination Point")
                    item_info_col.template_list(
                        "SPRIGList",
                        "pm_pt_two_list",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "pm_pt_two",
                        type='DEFAULT'
                    )
                if active_item.transf_type == "VECTORSLIDE":
                    item_info_col.label("Source Line")
                    item_info_col.template_list(
                        "SPRIGList",
                        "vs_targetLineList",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "vs_direction",
                        type='DEFAULT'
                    )
                if active_item.transf_type == "SCALEMATCHEDGE":
                    item_info_col.label("Source Edge")
                    item_info_col.template_list(
                        "SPRIGList",
                        "sme_src_edgelist",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "sme_edge_one",
                        type='DEFAULT'
                    )
                    item_info_col.separator()
                    item_info_col.label("Destination Edge")
                    item_info_col.template_list(
                        "SPRIGList",
                        "sme_dest_edgelist",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "sme_edge_two",
                        type='DEFAULT'
                    )
                if active_item.transf_type == "AXISROTATE":
                    item_info_col.label("Axis")
                    item_info_col.template_list(
                        "SPRIGList",
                        "axr_src_axis",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "axr_axis",
                        type='DEFAULT'
                    )
                    item_info_col.separator()
                    item_info_col.prop(
                        active_transf,
                        'axr_amount',
                        'Amount'
                    )
                if active_item.transf_type == "MKCOLLINEAR":
                    item_info_col.label("Source Line")
                    item_info_col.template_list(
                        "SPRIGList",
                        "mcl_src_linelist",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "mcl_src_line",
                        type='DEFAULT'
                    )
                    item_info_col.separator()
                    item_info_col.label("Destination Line")
                    item_info_col.template_list(
                        "SPRIGList",
                        "mcl_dest_linelist",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "mcl_dest_line",
                        type='DEFAULT'
                    )
                if active_item.transf_type == "MKCOPLANAR":
                    item_info_col.label("Source Plane")
                    item_info_col.template_list(
                        "SPRIGList",
                        "mcp_src_planelist",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "mcp_src_plane",
                        type='DEFAULT'
                    )
                    item_info_col.separator()
                    item_info_col.label("Destination Plane")
                    item_info_col.template_list(
                        "SPRIGList",
                        "mcp_dest_planelist",
                        sprig_data_ptr,
                        "prim_list",
                        active_transf,
                        "mcp_dest_plane",
                        type='DEFAULT'
                    )


class QuickTools(bpy.types.Panel):
    bl_idname = "sprig_tools_alpha_quick_panel"
    bl_label = "Quick Transforms"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "SPRIG Tools"

    def draw(self, context):
        layout = self.layout
        sprig_data_ptr = bpy.types.AnyType(bpy.context.scene.sprig_data)
        addon_data = bpy.context.scene.sprig_data
        prims = addon_data.prim_list

        align_pts_gui = layout.box()
        apg_top = align_pts_gui.row()
        apg_top.prop(
            sprig_data_ptr,
            'quick_align_pts_show',
            icon="TRIA_RIGHT" if not \
            addon_data.quick_align_pts_show else "TRIA_DOWN",
            icon_only=True,
            emboss=False
        )
        apg_top.label(
            "Align Points" if not \
            addon_data.quick_align_pts_show else "Align Points:",
            icon="ROTATECOLLECTION"
        )
        if addon_data.quick_align_pts_show:
            # align_pts_gui.label("Destination:")
            pm_grab_row = align_pts_gui.row()
            pm_grab_row.operator(
                    "sprig.quickpointmatchgrabdest",
                    icon='WORLD',
                    text="Grab Destination"
            )
            # align_pts_gui.prop(
                # addon_data.quick_align_pts_dest,
                # 'point',
                # ""
            # )
            align_pts_gui.label("Operator settings:")
            pm_mods = align_pts_gui.box()
            pm_box_row1 = pm_mods.row()
            pm_box_row1.prop(
                addon_data.quick_align_pts_transf,
                'pm_ln_make_unit_vec',
                'Set Length to 1'
            )
            pm_box_row1.prop(
                addon_data.quick_align_pts_transf,
                'pm_ln_flip_direction',
                'Flip Direction'
            )
            pm_box_row2 = pm_mods.row()
            pm_box_row2.prop(
                addon_data.quick_align_pts_transf,
                'pm_multiplier',
                'Multiplier'
            )
            pm_apply_header = align_pts_gui.row()
            pm_apply_header.label("Apply to:")
            pm_apply_header.prop(
                addon_data,
                'use_experimental',
                'Enable Experimental Mesh Ops.'
            )
            pm_apply_items = align_pts_gui.split(percentage=.33)
            pm_apply_items.operator(
                "sprig.quickpointmatchobject",
                text="Object"
            )
            pm_mesh_apply_items = pm_apply_items.row(align=True)
            pm_mesh_apply_items.operator(
                "sprig.quickpointmatchmeshselected",
                text="Mesh Piece"
            )
            pm_mesh_apply_items.operator(
                "sprig.quickpointmatchwholemesh",
                text="Whole Mesh"
            )
        layout.separator()
        
        make_cl_gui = layout.box()
        mcl_top = make_cl_gui.row()
        mcl_top.prop(
            sprig_data_ptr,
            'quick_make_collinear_show',
            icon="TRIA_RIGHT" if not \
            addon_data.quick_make_collinear_show else "TRIA_DOWN",
            icon_only=True,
            emboss=False
        )
        mcl_top.label(
            "Align Lines" if not \
            addon_data.quick_make_collinear_show else "Align Lines:",
            icon="SNAP_EDGE"
        )
        if addon_data.quick_make_collinear_show:
            # make_cl_gui.label("Destination:")
            mcl_grab_row = make_cl_gui.row()
            mcl_grab_row.operator(
                    "sprig.quickmakecollineargrabdest",
                    icon='WORLD',
                    text="Grab Destination"
            )
            # make_cl_gui.prop(
                # addon_data.quick_align_pts_dest,
                # 'point',
                # ""
            # )
            make_cl_gui.label("Operator settings:")
            mcl_mods = make_cl_gui.box()
            mcl_mods_row1 = mcl_mods.row()
            mcl_mods_row1.prop(
                addon_data.quick_make_collinear_transf,
                'mcl_ln_flip_direction',
                'Flip Direction'
            )
            mcl_apply_header = make_cl_gui.row()
            mcl_apply_header.label("Apply to:")
            mcl_apply_header.prop(
                addon_data,
                'use_experimental',
                'Enable Experimental Mesh Ops.'
            )
            mcl_apply_items = make_cl_gui.split(percentage=.33)
            mcl_apply_items.operator(
                "sprig.quickmakecollinearobject",
                text="Object"
            )
            mcl_mesh_apply_items = mcl_apply_items.row(align=True)
            mcl_mesh_apply_items.operator(
                "sprig.quickmakecollinearmeshselected",
                text="Mesh Piece"
            )
            mcl_mesh_apply_items.operator(
                "sprig.quickmakecollinearwholemesh",
                text="Whole Mesh"
            )
        layout.separator()
        
        make_cp_gui = layout.box()
        mcp_top = make_cp_gui.row()
        mcp_top.prop(
            sprig_data_ptr,
            'quick_make_coplanar_show',
            icon="TRIA_RIGHT" if not \
            addon_data.quick_make_coplanar_show else "TRIA_DOWN",
            icon_only=True,
            emboss=False
        )
        mcp_top.label(
            "Align Planes" if not \
            addon_data.quick_make_coplanar_show else "Align Planes:",
            icon="MOD_ARRAY"
        )
        if addon_data.quick_make_coplanar_show:
            # make_cp_gui.label("Destination:")
            mcp_grab_row = make_cp_gui.row()
            mcp_grab_row.operator(
                    "sprig.quickmakecoplanargrabdest",
                    icon='WORLD',
                    text="Grab Destination"
            )
            # make_cp_gui.prop(
                # addon_data.quick_
                # 'point',
                # ""
            # )
            make_cp_gui.label("Operator settings:")
            mcp_mods = make_cp_gui.box()
            mcp_mods_row1 = mcp_mods.row()
            mcp_mods_row1.prop(
                addon_data.quick_make_coplanar_transf,
                'mcp_flip_normal',
                'Flip Normal'
            )
            mcp_apply_header = make_cp_gui.row()
            mcp_apply_header.label("Apply to:")
            mcp_apply_header.prop(
                addon_data,
                'use_experimental',
                'Enable Experimental Mesh Ops.'
            )
            mcp_apply_items = make_cp_gui.split(percentage=.33)
            mcp_apply_items.operator(
                "sprig.quickmakecoplanarobject",
                text="Object"
            )
            mcp_mesh_apply_items = mcp_apply_items.row(align=True)
            mcp_mesh_apply_items.operator(
                "sprig.quickmakecoplanarmeshselected",
                text="Mesh Piece"
            )
            mcp_mesh_apply_items.operator(
                "sprig.quickmakecoplanarwholemesh",
                text="Whole Mesh"
            )
        layout.separator()
        
        sme_gui = layout.box()
        sme_top = sme_gui.row()
        sme_top.prop(
            sprig_data_ptr,
            'quick_scale_match_edge_show',
            icon="TRIA_RIGHT" if not \
            addon_data.quick_scale_match_edge_show else "TRIA_DOWN",
            icon_only=True,
            emboss=False
        )
        sme_top.label(
            "Match Edge Scale" if not \
            addon_data.quick_scale_match_edge_show else "Match Edge Scale:",
            icon="MOD_ARRAY"
        )
        if addon_data.quick_scale_match_edge_show:
            sme_grab_row = sme_gui.row()
            sme_grab_row.operator(
                    "sprig.quickscalematchedgegrabdest",
                    icon='WORLD',
                    text="Grab Destination"
            )
            # sme_gui.label("Operator settings:")
            # sme_mods = sme_gui.box()
            # sme_mods_row1 = sme_mods.row()
            # sme_mods_row1.prop(
                # addon_data.quick_make_coplanar_transf,
                # 'sme_',
                # 'Flip Normal'
            # )
            sme_apply_header = sme_gui.row()
            sme_apply_header.label("Apply to:")
            sme_apply_header.prop(
                addon_data,
                'use_experimental',
                'Enable Experimental Mesh Ops.'
            )
            sme_apply_items = sme_gui.split(percentage=.33)
            sme_apply_items.operator(
                "sprig.quickscalematchedgeobject",
                text="Object"
            )
            sme_mesh_apply_items = sme_apply_items.row(align=True)
            sme_mesh_apply_items.operator(
                "sprig.quickscalematchedgemeshselected",
                text="Mesh Piece"
            )
            sme_mesh_apply_items.operator(
                "sprig.quickscalematchedgewholemesh",
                text="Whole Mesh"
            )
        layout.separator()
        
        axr_gui = layout.box()
        axr_top = axr_gui.row()
        axr_top.prop(
            sprig_data_ptr,
            'quick_axis_rotate_show',
            icon="TRIA_RIGHT" if not \
            addon_data.quick_axis_rotate_show else "TRIA_DOWN",
            icon_only=True,
            emboss=False
        )
        axr_top.label(
            "Axis Rotate" if not \
            addon_data.quick_axis_rotate_show else "Axis Rotate:",
            icon="MOD_ARRAY"
        )
        if addon_data.quick_axis_rotate_show:
            axr_grab_row = axr_gui.row()
            axr_grab_row.operator(
                    "sprig.quickaxisrotategrabsrc",
                    icon='WORLD',
                    text="Grab Axis"
            )
            axr_gui.label("Operator settings:")
            axr_mods = axr_gui.box()
            axr_mods_row1 = axr_mods.row()
            axr_mods_row1.prop(
                addon_data.quick_axis_rotate_transf,
                'axr_amount',
                'Amount'
            )
            axr_apply_header = axr_gui.row()
            axr_apply_header.label("Apply to:")
            axr_apply_header.prop(
                addon_data,
                'use_experimental',
                'Enable Experimental Mesh Ops.'
            )
            axr_apply_items = axr_gui.split(percentage=.33)
            axr_apply_items.operator(
                "sprig.quickaxisrotateobject",
                text="Object"
            )
            axr_mesh_apply_items = axr_apply_items.row(align=True)
            axr_mesh_apply_items.operator(
                "sprig.quickaxisrotatemeshselected",
                text="Mesh Piece"
            )
            axr_mesh_apply_items.operator(
                "sprig.quickaxisrotatewholemesh",
                text="Whole Mesh"
            )
        layout.separator()

        vs_gui = layout.box()
        vs_top = vs_gui.row()
        vs_top.prop(
            sprig_data_ptr,
            'quick_vector_slide_show',
            icon="TRIA_RIGHT" if not \
            addon_data.quick_vector_slide_show else "TRIA_DOWN",
            icon_only=True,
            emboss=False
        )
        vs_top.label(
            "Vector Slide" if not \
            addon_data.quick_vector_slide_show else "Vector Slide:",
            icon="MOD_ARRAY"
        )
        if addon_data.quick_vector_slide_show:
            vs_grab_row = vs_gui.row()
            vs_grab_row.operator(
                    "sprig.quickvectorslidegrabsrc",
                    icon='WORLD',
                    text="Grab Source"
            )
            vs_gui.label("Operator settings:")
            vs_mods = vs_gui.box()
            vs_box_row1 = vs_mods.row()
            vs_box_row1.prop(
                addon_data.quick_vector_slide_transf,
                'vs_ln_make_unit_vec',
                'Set Length to 1'
            )
            vs_box_row1.prop(
                addon_data.quick_vector_slide_transf,
                'vs_ln_flip_direction',
                'Flip Direction'
            )
            vs_box_row2 = vs_mods.row()
            vs_box_row2.prop(
                addon_data.quick_vector_slide_transf,
                'vs_multiplier',
                'Multiplier'
            )
            vs_apply_header = vs_gui.row()
            vs_apply_header.label("Apply to:")
            vs_apply_header.prop(
                addon_data,
                'use_experimental',
                'Enable Experimental Mesh Ops.'
            )
            vs_apply_items = vs_gui.split(percentage=.33)
            vs_apply_items.operator(
                "sprig.quickvectorslideobject",
                text="Object"
            )
            vs_mesh_apply_items = vs_apply_items.row(align=True)
            vs_mesh_apply_items.operator(
                "sprig.quickvectorslidemeshselected",
                text="Mesh Piece"
            )
            vs_mesh_apply_items.operator(
                "sprig.quickvectorslidewholemesh",
                text="Whole Mesh"
            )


def specials_menu_items(self, context):
    self.layout.separator()
    self.layout.label('Add SPRIG items')
    self.layout.operator('sprig.specialsaddpointfromactiveglobal')
    self.layout.operator('sprig.specialsaddlinefromactiveglobal')
    self.layout.operator('sprig.specialsaddplanefromactiveglobal')
    self.layout.separator()


def register():
    # Make custom classes available inside blender via bpy.types
    bpy.utils.register_module(__name__)

    # Extend the scene class here to include the addon data
    bpy.types.Scene.sprig_data = bpy.props.PointerProperty(type=SPRIGData)

    bpy.types.VIEW3D_MT_object_specials.append(specials_menu_items)
    bpy.types.VIEW3D_MT_edit_mesh_specials.append(specials_menu_items)


def unregister():
    del bpy.types.Scene.sprig_data
    bpy.types.VIEW3D_MT_object_specials.remove(specials_menu_items)
    bpy.types.VIEW3D_MT_edit_mesh_specials.remove(specials_menu_items)

    # Remove custom classes from blender's bpy.types
    bpy.utils.unregister_module(__name__)


if __name__ == "__main__":
    register()
