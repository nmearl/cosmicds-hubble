import ipyvuetify as v
from pathlib import Path
from traitlets import Int, Bool, Unicode, List, Instance
from cosmicds.utils import load_template
from glue_jupyter.state_traitlets_helpers import GlueState
from ipywidgets import widget_serialization, DOMWidget


# theme_colors()

class HubbleExp(v.VuetifyTemplate):
    template = load_template(
        "hubble_exp_universe_slideshow.vue", __file__, traitlet=True).tag(sync=True)
    step = Int(0).tag(sync=True)
    length = Int(3).tag(sync=True)
    dialog = Bool(False).tag(sync=True)
    currentTitle = Unicode("").tag(sync=True)
    state = GlueState().tag(sync=True)
    maxStepCompleted = Int(0).tag(sync=True)
    interactSteps = List([1]).tag(sync=True)
    layer_viewer = Instance(DOMWidget).tag(sync=True, **widget_serialization)

    _titles = [
        "Hubble's Discovery",
        "A Running Race",
        "Runner's Velocities vs. Distances",
    ]
    _default_title = "Hubble's Discovery"

    def __init__(self, stage_state, layer_viewer, *args, **kwargs):
        self.state = stage_state
        self.currentTitle = self._default_title
        self.layer_viewer = layer_viewer

        def update_title(change):
            index = change["new"]
            print("step:", index)
            if index in range(len(self._titles)):
                self.currentTitle = self._titles[index]
            else:
                self.currentTitle = self._default_title

        self.observe(update_title, names=["step"])

        super().__init__(*args, **kwargs)
