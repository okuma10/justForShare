bl_info = {
    "name": "Display Keyframe Range",
    "blender": (2, 80, 0),
    "category": "Animation",
    "author": "okuma_10",
    "version": (1, 0, 0),
    "description": "Displays a rectangle with range value between two(or more) selected keyframes",
    "support": "COMMUNITY",
}

import bpy
import gpu 
import blf
import functools
from gpu_extras.batch import batch_for_shader


#  ╭──────────────────────────────────────────────────────────╮
#  │                        Font Data                         │
#  ╰──────────────────────────────────────────────────────────╯
font_info = {
    "font_id":0,
    "handler": None,
    "wh":[0,0]
}
font_path = "G:\\Fonts\\ttf-iosevka-15.6.3\\iosevka-bold.ttf"
font_info["font_id"] = blf.load(font_path)

#  ╭──────────────────────────────────────────────────────────╮
#  │                       Main Context                       │
#  ╰──────────────────────────────────────────────────────────╯
class KFN_Context():
    def __init__(self):
        self.dopesheet = None
        self.dpsheet_canvas = None
        self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        self.first_draw = 1

        
        areas = bpy.context.window_manager.windows[0].screen.areas 
        for i,area in enumerate(areas):
            if area.type == 'DOPESHEET_EDITOR' and area.ui_type != 'TIMELINE':
                self.dopesheet = area
                for region in area.regions:
                    if region.type == 'WINDOW':
                        print("OK")
                        self.dpsheet_canvas = region

kfn_context = KFN_Context()

#  ╭──────────────────────────────────────────────────────────╮
#  │                     Helper functions                     │
#  ╰──────────────────────────────────────────────────────────╯
#  ────────────── Get list of selected keyframes ──────────────
def get_selected_keyframes():
    keyframes = []
    for area in bpy.context.window_manager.windows[0].screen.areas:

        if area.type == 'DOPESHEET_EDITOR':
            if area.spaces[0].ui_mode == 'GPENCIL':
                print(f"Area is {area.spaces[0].ui_mode}")
                found_keyframes = []
                pencils = [pencil for pencil in bpy.context.selected_objects if pencil.type == 'GPENCIL']
                for pencil in pencils:
                    print(f"{pencil.name}")
                    layers = [layer for layer in pencil.data.layers]
                    for layer in layers:
                        sel_keyframes = [keyframe.frame_number for keyframe in layer.frames if keyframe.select]
                        found_keyframes.extend(sel_keyframes)
                keyframes = list(set(found_keyframes))

            elif area.spaces[0].ui_mode == 'DOPESHEET':
                print(f"Area is {area.spaces[0].ui_mode}")
                objects = [object for object in bpy.context.selected_objects]
                found_keyframes = []
                for object in objects:
                    print(f"{object.name}")
                    fcurves = [fcurve for fcurve in object.animation_data.action.fcurves]
                    for fcurve in fcurves:
                        sel_keyframes = [keyframe.co.x for keyframe in fcurve.keyframe_points if keyframe.select_control_point]
                        found_keyframes.extend(sel_keyframes)
                keyframes = list(set(found_keyframes))
    print(f"{keyframes}") 
    return keyframes

#  ─────────────── Generate rectangle verticies ───────────────
def gen_rectangle(x,y,w,h,allign):
    verts = None
    half_w = w/2
    half_h = h/2
    if allign == "C":
        verts = ((x-half_w, y-half_h),
                 (x+half_w, y-half_h),
                 (x+half_w, y+half_h),
                 (x-half_w, y+half_h))
    return verts

#  ─────────────────────── Vert Buffer ───────────────────────
# vbuf = gpu.types.Buffer('FLOAT',[2,4])
# vbuf_format  = gpu.types.GPUVertFormat()
# vbuf_format.attr_add(id="pos",comp_type="F32",len=2,fetch_mode="FLOAT")
# gpu_vert_buf = gpu.types.GPUVertBuf(vbuf_format, 4) 
#  ────────────────────────── Shader ──────────────────────────
#  ────────────────────────── Batch ──────────────────────────
# gpu_batch    = gpu.types.GPUBatch(type="TRI_FAN",buf=gpu_vert_buf)
# gpu_batch.program_set(shader)

ui_scale = bpy.context.preferences.view.ui_scale

def draw(kfn_context):
    #╭──────────────────────────────────────────────────────────╮
    #│                           Init                           │
    #╰──────────────────────────────────────────────────────────╯
    canvas = kfn_context.dpsheet_canvas
    if kfn_context.first_draw:
        # TODO: optimize the gpu drawing with the cretion of VertBuffer, Batch, Shader.
        #       where we only update the buffer that VertBuffer referrs to, and not regenerate
        #       a whole new batch each frame
        print("This is the first draw call - Init")
        kfn_context.first_draw = not kfn_context.first_draw
    # Get currently selected keyframes / selected object only
    keyframes = get_selected_keyframes()
    keyframes.sort()
    print(keyframes)
    # return
    #╭───────────────────────────────────────────╮
    #│ View2d projection of Keyframe coordinates │
    #╰───────────────────────────────────────────╯
    view2d = canvas.view2d
    y_offset = -32 * ui_scale
    p_keyf1 = list( view2d.view_to_region(keyframes[0] ,y_offset ,clip=False) ) #projected keyframe1 co
    p_keyf2 = list( view2d.view_to_region(keyframes[-1],y_offset ,clip=False) ) #projected keyframe2 co
    # ╭────────────────────────────────────────────────────────────────────────╮
    # │ clamp projection, in case the keyframe gets outside the clipping space │
    # ╰────────────────────────────────────────────────────────────────────────╯
    if p_keyf1[0] < 0                     : p_keyf1[0] = 0
    elif p_keyf1[0] > canvas.width: p_keyf1[0] = canvas.width
    if p_keyf2[0] < 0                     : p_keyf2[0] = 0
    elif p_keyf2[0] > canvas.width: p_keyf2[0] = canvas.width
    #╭───────────╮
    #│ Draw Data │
    #╰───────────╯
    distance = (p_keyf2[0] - p_keyf1[0])
    pos     = [(distance/2 ) + p_keyf1[0], p_keyf1[1]]
    size    =    distance 
    vertices= gen_rectangle( *pos, size-1,15,"C")
    indices = ((0, 1, 2), (2, 0, 3))
    
    # vbuf = vertices
    # try:
    #     gpu_vert_buf.attr_fill(id="pos",data=vbuf)
    # except:pass
    #╭───────────╮
    #│ Font Data │
    #╰───────────╯
    distance_str    = f"{int(keyframes[-1]-keyframes[0])}"
    font_info["wh"] = blf.dimensions(font_info["font_id"],distance_str) # calculate the font string width
    blf.position(font_info["font_id"], pos[0]-(font_info["wh"][0]//2), pos[1]-(font_info["wh"][1]//2),0) #set position
    blf.size(font_info["font_id"], 12.0) # set size
    #╭──────╮
    #│ Draw │]
    #╰──────╯
    batch = batch_for_shader(kfn_context.shader, 'TRIS', {"pos": vertices}, indices=indices)
    blf.color(font_info["font_id"], 1,1,1,1)
    kfn_context.shader.uniform_float("color", (0.847, 0.106, 0.376, 1.0))
    batch.draw(kfn_context.shader)
    # shader.uniform_float("color", (0.118, 0.533, 0.898, 1.0))
    # gpu_batch.draw()
    blf.draw(font_info["font_id"], distance_str )

#  ──────────────────── End Draw function ────────────────────
def end_draw(space,handle):
    space.draw_handler_remove(handle, 'WINDOW')
    kfn_context.dpsheet_canvas.tag_redraw()



#  ╭──────────────────────────────────────────────────────────╮
#  │                      Operator Class                      │
#  ╰──────────────────────────────────────────────────────────╯
class kfn_KfDistance(bpy.types.Operator):
    bl_idname = "scene.kf_distance"
    bl_label  = "Keyframe Distance"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        global kfn_context
        areas = bpy.data.window_managers[0].windows[0].screen.areas 
        
        for i,area in enumerate(areas):
            if area.type == 'DOPESHEET_EDITOR' and area.ui_type != 'TIMELINE':
                kfn_context.dopesheet = area
                for region in area.regions:
                    if region.type == 'WINDOW':
                        kfn_context.dpsheet_canvas = region
        return self.execute(context)

        
    def execute(self, context):
        global kfn_context
        draw_handle = kfn_context.dopesheet.spaces[0].draw_handler_add(draw, (kfn_context,), 'WINDOW', 'POST_PIXEL')
        kfn_context.dpsheet_canvas.tag_redraw()
        bpy.app.timers.register(functools.partial(end_draw, kfn_context.dopesheet.spaces[0], draw_handle), first_interval=5)
        return {'FINISHED'}



def register():
    bpy.utils.register_class(kfn_KfDistance)
    INF = "\033[38;2;255;235;59m\033[48;2;0;0;0m"
    SUCC = "\033[38;2;118;255;3m\033[48;2;0;0;0m"
    RS = "\033[0m"
    print(f"{INF} Display Keyframe Range operator {RS}{SUCC}  {RS}")
def unregister():
    bpy.utils.unregister_class(kfn_KfDistance)
# draw_handle = kfn_KfDistance.dopesheet.spaces[0].draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')
# kfn_KfDistance.dpsheet_canvas.tag_redraw()


# bpy.app.timers.register(functools.partial(end_draw,kfn_context.dopesheet.spaces[0], draw_handle), first_interval=5)
