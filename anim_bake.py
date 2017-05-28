import pymel.core as pm
import maya.cmds as cmds

"""
Anim Bake is to simplify making global changes to cycle animations that have been built with infinity curves offset
from each other. Standard Maya baking and copying of curves does not preserve tangent information, so this script
saves that info before baking and restores it after the bake, keeping the curves identical before and after.

In addition, the tool has settings to automatically bake all animation layers, as well as trim the animation to the
time range.

Author: Eric Luhta
"""

class AnimBake():
    """
    Class for holding data and functions to do the bake and track desired options.

    Attributes:
        time_range : tuple of first and last frames taken from the Maya timeline
        anim_length : the length of the animation in frames
        curves : a list of all the animation curve names
        child_layers : a list of anim layers if present
        bake_all_layers : option to bake anim layers instead of just current layer
        has_anim_layers : stores if anim layers are present
        BUFFER : anim_length * 2 that's used to overshoot time range before/after to make sure all keys are captured
        SET_KEYS_AT : a list used to keep the first and last keys, -/+ 1 respectively. Used for setting keys that
                        preserve Maya's tangent information

    """

    def __init__(self, bake_all_layers=False, buffer_multiplier=2):
        self.time_range = (pm.playbackOptions(q=True, min=True), pm.playbackOptions(q=True, max=True))
        self.anim_length = abs(self.time_range[1] - self.time_range[0])
        self.curves = pm.findKeyframe(curve=True)
        self.child_layers = None
        self.bake_all_layers = bake_all_layers
        self.has_anim_layers = self.check_anim_layers()

        self.BUFFER = self.anim_length * buffer_multiplier
        self.SET_KEYS_AT = [self.time_range[0] - 1, self.time_range[1] + 1, self.time_range[0], self.time_range[1]]


    def get_first_last_keys(self, curve):
        '''
        :param curve: the anim curve to get the first and last keys from
        :return: tuple of first and last frames of the curve
        '''
        first_key = pm.findKeyframe(curve, which='first')
        last_key = pm.findKeyframe(curve, which='last')
        return (first_key, last_key)


    def check_anim_layers(self):
        '''
        checks if anim layers exist and if so, puts the names of them in the attribute

        :return: if anim layers are present or not
        '''
        self.base_anim_layer = cmds.animLayer(q=True, root=True)
        found_layer = False
        
        # if the BaseAnimation layer exists check if there are other child layers
        if self.base_anim_layer is not None:
            self.child_layers = cmds.animLayer(self.base_anim_layer, q=True, children=True)

            if (self.child_layers is not None) and (len(self.child_layers) > 0):
                found_layer = True
            
        return found_layer


    def add_all_layer_curves(self):
        '''
        Goes through all layers and adds their anim curves to the master list to be baked

        :return: None
        '''
        if self.has_anim_layers:
            self.curves = [curve for curve in cmds.listHistory(pdo=True,
                                                          lf=False) if
                      cmds.nodeType(curve, i=True)[0] == 'animCurve']

    def curves_exist(self):
        '''
        Makes sure list of curves isn't empty, otherwise stop and display a warning
        :return: self.curves is not empty
        '''
        if self.curves is not None:
            return True
        else:
            pm.warning('No curves to bake')
            return False

    def bake_curves(self):
        '''
        Checks all the keyframe tangent information of the first and last keys, then makes sure its identical
        between them

        :return: None
        '''
        if self.curves_exist():
            for curve in self.curves:
                keys = self.get_first_last_keys(curve)

                # get the correct tangent weights/angles on the first and last keys of the curve
                first_tangent = pm.keyTangent(curve, q=True, outWeight=True, time=(keys[0],))[0]
                first_angle = pm.keyTangent(curve, q=True, outAngle=True, time=(keys[0],))[0]
                last_tangent = pm.keyTangent(curve, q=True, inWeight=True, time=(keys[1],))[0]
                last_angle = pm.keyTangent(curve, q=True, inAngle=True, time=(keys[1],))[0]

                # check all the tangents and make sure they are the same on the first/last keys
                tangent_opts = {'inWeight' : last_tangent,
                                'inAngle' : last_angle,
                                'outWeight' : first_tangent,
                                'outAngle' : first_angle }

                for key in keys:
                    pm.keyTangent(curve, edit=True, time=(key,), lock=False, **tangent_opts)

                # bake the curve
                pm.bakeResults(curve, time=(self.time_range[0] - self.BUFFER, self.time_range[1] + self.BUFFER),
                               sac=True)

    
    def trim_bake_to_timerange(self):
        '''
        Cuts down the curves to the range of the timeline while keeping tangents intact

        :return: None
        '''
        # set keys at the start/end of the range and one frame outside to create a BUFFER
        if self.curves_exist():
            for curve in self.curves:
                for key in self.SET_KEYS_AT:
                    pm.setKeyframe(curve, insert=True, time=key)

                # delete the extraneous keys
                pm.cutKey(curve, clear=True, time=(self.time_range[0]-self.BUFFER, self.time_range[0]-1))
                pm.cutKey(curve, clear=True, time=(self.time_range[1]+1, self.time_range[1]+self.BUFFER))

def setup_bake(bake_layers, trim_curves):
    '''
    Initial setup to convert options from ui. Separated out so script can be called directly through commands.
    :param bake_layers:  should we bake all the layers or not
    :param trim_curves:  shoule we trim curves to the time range or not
    :return: None
    '''
    bake_layers = bake_layers.getValue()
    trim_curves = trim_curves.getValue()
    do_bake(bake_layers, trim_curves)

def do_bake(bake_layers, trim_curves):
    '''
    Create a class to do the operations, check the options, and DO IT

    :param bake_layers: should we bake all the layers or not
    :param trim_curves: should we trim curves to the time range or not
    :return: None
    '''
    if len(pm.ls(selection=True)):
        bake = AnimBake(bake_layers)

        if bake_layers:
            bake.add_all_layer_curves()

        bake.bake_curves()

        if trim_curves:
            bake.trim_bake_to_timerange()
    else:
        pm.warning('[anim_bake.py] Nothing selected.')
    
    
# Interface

def window_ui():
    """Tool window and UI """
    windowID = "anim_bake"

    if pm.window(windowID, exists=True):
        pm.deleteUI(windowID)

    tool_window = pm.window(windowID, title="Anim Bake", width=200, height=50, mnb=False, mxb=False, sizeable=True)
    main_layout = pm.rowColumnLayout(width=200, height=50)

    # Main tool tab
    top_layout = pm.rowColumnLayout(nc=2, w=200, h=20, cw=[(1, 90), (2, 110)])
    bake_layers = pm.checkBox(label='use all layers', v=False)
    trim_curves = pm.checkBox(label='trim curves?', v=True)
    pm.setParent('..')
    pm.button(label="DO IT", bgc=(.969, .922, .145), c=pm.Callback(setup_bake, bake_layers, trim_curves), w=50)
    pm.showWindow(tool_window)