# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import sys
import bpy
import math
import mathutils
import bmesh
import copy
import bpy_extras
import collections
from .. import handleutility
from .. import draw_util
from ..QMesh import *
from .subtool import SubTool

class SubToolMove(SubTool) :
    name = "MoveTool"

    def __init__(self,op,startTarget,startMousePos) :
        super().__init__(op)
        self.currentTarget = startTarget
        self.snapTarget = ElementItem.Empty()
        self.startMousePos = copy.copy(startTarget.coord)
        self.mouse_pos = startMousePos.copy()
        self.startPos = startTarget.hitPosition.copy()
        self.target_verts = [ v for v in startTarget.verts ]
        if self.bmo.is_mirror_mode :
            self.mirror_verts = [ v for v in [ self.bmo.find_mirror(v) for v in startTarget.verts ] if v != None ]
            same = set(self.mirror_verts) & set(self.target_verts)
            self.target_verts = [ v for v in self.target_verts if (v not in same) or v.co.x >= 0.0 ]
            self.mirror_verts = [ v for v in self.mirror_verts if (v not in same) or v.co.x < 0.0 ]
        else :
            self.mirror_verts = []
        self.target_verts = [ (v,v.co.copy()) for v in self.target_verts ]
        self.mirror_verts = [ (v,v.co.copy()) for v in self.mirror_verts ]

        self.normal_ray = handleutility.Ray( self.startPos , startTarget.normal ).world_to_object( self.bmo.obj )
        self.normal_ray.origin = self.startPos
        self.screen_space_plane = handleutility.Plane.from_screen( bpy.context , startTarget.hitPosition )
        self.move_plane = self.screen_space_plane
        self.move_type = 'FREE'
        self.move_color = ( 1.0 , 1.0 ,1.0 ,1.0  )
        self.ChangeRay(op.move_type )
        self.repeat = False
        self.MoveTo( bpy.context , self.mouse_pos )
        self.bmo.UpdateMesh(False)
        self.is_snap = False

        # ignore snap target
        self.ignoreSnapTarget = []
        if self.currentTarget.isVert :
            self.ignoreSnapTarget = [self.currentTarget.element]
#               self.ignoreSnapTarget.extend( self.currentTarget.element.link_faces )
            self.ignoreSnapTarget.extend( self.currentTarget.element.link_edges )
#                for face in self.currentTarget.element.link_faces :
#                    self.ignoreSnapTarget.extend( face.verts )
            if self.currentTarget.mirror is not None :
                self.ignoreSnapTarget.append( self.currentTarget.mirror )
                self.ignoreSnapTarget.extend( self.currentTarget.mirror.link_edges )
        elif self.currentTarget.isEdge :
            self.ignoreSnapTarget = [self.currentTarget.element ]
            self.ignoreSnapTarget.extend( self.currentTarget.element.verts[0].link_edges )
            self.ignoreSnapTarget.extend( self.currentTarget.element.verts[1].link_edges )
            for face in self.currentTarget.element.link_faces :
                self.ignoreSnapTarget.extend( face.edges )

            if self.currentTarget.mirror is not None :
                self.ignoreSnapTarget.append( self.currentTarget.mirror )

    def OnUpdate( self , context , event ) :
        if event.type == 'MOUSEMOVE':
            self.MoveTo( context , self.mouse_pos )

            self.is_snap = False
            dist = self.preferences.distance_to_highlight
            if self.currentTarget.isVert and self.move_ray == None :# and ( self.currentTarget.element.is_manifold is False or self.currentTarget.element.is_boundary )  :
                self.snapTarget = self.bmo.PickElement( self.mouse_pos , dist , self.ignoreSnapTarget , elements = ['VERT'] )

                if self.snapTarget.isVert \
                        and self.currentTarget.element != self.snapTarget.element \
                        and (self.operator.fix_to_x_zero and self.currentTarget.is_x_zero and self.snapTarget.is_x_zero is False ) is False :
                    self.is_snap = True
                    self.currentTarget.element.co = self.snapTarget.element.co
                    if self.currentTarget.mirror is not None :
                        self.currentTarget.mirror.co = self.bmo.mirror_pos(self.currentTarget.element.co)
                else :
                    self.snapTarget = ElementItem.Empty()

                if self.currentTarget.mirror is not None :
                    if self.bmo.check_near(self.currentTarget.element.co ,self.currentTarget.mirror.co ) :
                        x_zero = self.bmo.zero_pos(self.currentTarget.element.co)
                        self.currentTarget.element.co = x_zero
                        self.currentTarget.mirror.co = x_zero
                        self.is_snap = True
                else :
                    if self.bmo.is_mirror_mode :
                        mp = self.bmo.mirror_pos( self.currentTarget.element.co )
                        if self.bmo.check_near(self.currentTarget.element.co , mp ) :
                            self.currentTarget.element.co = self.bmo.zero_pos(mp)
                            self.is_snap = True
            elif self.currentTarget.isEdge and self.move_ray == None :
                self.snapTarget = self.bmo.PickElement( self.mouse_pos , dist , edgering=True , backface_culling = True , elements=['EDGE'] , ignore=self.ignoreSnapTarget ) 
                if self.snapTarget.isEdge :
                    p0 = self.bmo.local_to_2d( self.currentTarget.element.verts[0].co )
                    p1 = self.bmo.local_to_2d( self.currentTarget.element.verts[1].co )
                    t0 = self.bmo.local_to_2d( self.snapTarget.element.verts[0].co )
                    t1 = self.bmo.local_to_2d( self.snapTarget.element.verts[1].co )
                    if (p0-t0).length + (p1-t1).length < (p0-t1).length + (p1-t0).length :
                        self.currentTarget.element.verts[0].co = self.snapTarget.element.verts[0].co
                        self.currentTarget.element.verts[1].co = self.snapTarget.element.verts[1].co
                    else :
                        self.currentTarget.element.verts[0].co = self.snapTarget.element.verts[1].co
                        self.currentTarget.element.verts[1].co = self.snapTarget.element.verts[0].co
                    if self.currentTarget.mirror is not None :
                        self.currentTarget.mirror.verts[0].co = self.bmo.mirror_pos(self.currentTarget.element.verts[1].co)
                        self.currentTarget.mirror.verts[1].co = self.bmo.mirror_pos(self.currentTarget.element.verts[0].co)

                if self.currentTarget.mirror is not None :
                    if self.bmo.is_x0_snap( self.currentTarget.hitPosition ) :
                        self.currentTarget.element.verts[0].co = self.bmo.zero_pos(self.currentTarget.element.verts[0].co)
                        self.currentTarget.element.verts[1].co = self.bmo.zero_pos(self.currentTarget.element.verts[1].co)
                        self.currentTarget.mirror.verts[0].co = self.bmo.zero_pos(self.currentTarget.mirror.verts[0].co)
                        self.currentTarget.mirror.verts[1].co = self.bmo.zero_pos(self.currentTarget.mirror.verts[1].co)


            self.bmo.UpdateMesh(False)
        elif event.type == 'LEFTMOUSE' : 
            if event.value == 'RELEASE' :
                threshold = bpy.context.scene.tool_settings.double_threshold
                verts = set( [ v[0] for v in self.target_verts] ) | set( [ v[0] for v in self.mirror_verts] )
                if self.snapTarget.isVert :
                    verts.add( self.snapTarget.element )
                bmesh.ops.automerge( self.bmo.bm , verts = list(verts) , dist = threshold )
                self.bmo.UpdateMesh()

                return 'FINISHED'
        elif event.type == 'WHEELUPMOUSE' :
            a = { 'FREE' : 'X' , 'X' : 'Y'  , 'Y' : 'Z' , 'Z' : 'NORMAL' , 'NORMAL' : 'FREE' }
            self.ChangeRay( a[self.move_type] )
        elif event.type == 'WHEELDOWNMOUSE' :
            a = { 'FREE' : 'NORMAL' , 'X' : 'FREE' , 'Y' : 'X' , 'Z' : 'Y' , 'NORMAL' : 'Z' }
            self.ChangeRay( a[self.move_type] )
        elif event.value == 'PRESS' :
            if self.repeat == False :
                if event.type == 'X' :
                    self.ChangeRay( 'X' )
                elif event.type == 'Y' :
                    self.ChangeRay( 'Y' )
                elif event.type == 'Z' :
                    self.ChangeRay( 'Z' )
                elif event.type == 'N' :
                    self.ChangeRay( 'NORMAL'  )
                elif event.type == 'T' :
                    self.ChangeRay( 'TANGENT'  )
            self.repeat = True
        elif event.value == 'RELEASE' :
            self.repeat = False

        self.debugStr = str(self.snapTarget.element)

        return 'RUNNING_MODAL'

    def OnDraw( self , context  ) :
        if self.is_snap :
            size = self.preferences.highlight_vertex_size
            pos = handleutility.location_3d_to_region_2d( self.bmo.local_to_world_pos( self.currentTarget.element.co ) )
            draw_util.draw_circle2D( pos , size + 1.5 , (1,1,1,1) , False )

    def OnDraw3D( self , context  ) :
        self.currentTarget.Draw( self.bmo.obj , self.color_highlight()  , self.preferences )
        if self.snapTarget.isNotEmpty :
            self.snapTarget.Draw( self.bmo.obj , self.color_highlight() , self.preferences )

        if self.move_ray != None :
            v1 = self.move_ray.origin + self.move_ray.vector * 10000.0 
            v2 = self.move_ray.origin - self.move_ray.vector * 10000.0 
            draw_util.draw_lines3D( context , (v1,v2) , self.move_color , 1.0 , 0.2 )

    def ChangeRay( self , move_type ) :
        self.move_ray = None
        self.move_plane = self.screen_space_plane
        self.move_color = ( 1.0 , 1.0 ,1.0 ,1.0  )

        if self.operator.fix_to_x_zero and self.currentTarget.is_x_zero:
            plane = handleutility.Plane( mathutils.Vector((0,0,0) ) ,  mathutils.Vector((1,0,0) ) ).object_to_world( self.bmo.obj )
            plane.origin = self.startPos
#           self.move_plane = plane

        if move_type == self.move_type :
            self.move_ray = None
            move_type = 'FREE'
        if move_type == 'X' :
            self.move_ray = handleutility.Ray( self.startPos , mathutils.Vector( (1,0,0) ) )
            self.move_color = ( 1.0 , 0.0 ,0.0 ,1.0  )
        elif move_type == 'Y' :
            self.move_ray = handleutility.Ray( self.startPos , mathutils.Vector( (0,1,0) ) )
            self.move_color = ( 0.0 , 1.0 ,0.0 ,1.0  )
        elif move_type == 'Z' :
            self.move_ray = handleutility.Ray( self.startPos , mathutils.Vector( (0,0,1) ) )
            self.move_color = ( 0.0 , 0.0 ,1.0 ,1.0  )
        elif move_type == 'NORMAL' :
            self.move_ray = self.normal_ray
            self.move_color = ( 1.0 , 1.0 ,1.0 ,1.0  )
        elif move_type == 'TANGENT' :
            self.move_plane = handleutility.Plane( self.startPos , self.normal_ray.vector )

        self.move_type = move_type

    def MoveTo( self ,context ,  mouse_pos ) :
        move = mathutils.Vector( (0.0,0.0,0.0) )

        if self.move_ray != None :
            ray = handleutility.Ray.from_screen( context , mouse_pos )
            p0 , p1 , d = self.move_ray.distance( ray )

            move = ( p0 - self.move_ray.origin )
        elif self.move_plane != None :
            rayS = handleutility.Ray.from_screen( context , self.startMousePos )
            rayG = handleutility.Ray.from_screen( context , mouse_pos )
            vS = self.move_plane.intersect_ray( rayS )
            vG = self.move_plane.intersect_ray( rayG )

            move = (vG - vS)

        self.currentTarget.hitPosition = self.startPos + move

        for vert in self.target_verts :
            p = self.bmo.obj.matrix_world @ vert[1]
            p = p + move
            p = self.bmo.obj.matrix_world.inverted() @ p
            if self.operator.fix_to_x_zero and self.bmo.is_x_zero_pos( vert[1] ) :
                p.x = 0.0

            self.bmo.set_positon( vert[0] , p , False )

        for vert in self.mirror_verts :
            p = self.bmo.obj.matrix_world @ self.bmo.mirror_pos(vert[1])
            p = p + move
            p = self.bmo.obj.matrix_world.inverted() @ p
            p = self.bmo.mirror_pos(p)
            if self.operator.fix_to_x_zero and self.bmo.is_x_zero_pos( vert[1] ) :
                p.x = 0.0
            self.bmo.set_positon( vert[0] , p , False )
            