import logging
import requests

import astropy.units as u
from astropy.coordinates import SkyCoord
from cosmicds.components.table import Table
from cosmicds.phases import CDSState
from cosmicds.registries import register_stage
from cosmicds.utils import load_template, API_URL
from echo import CallbackProperty, add_callback, ignore_callback
from traitlets import default, Bool

from ..components import DistanceSidebar, DistanceTool, DosDontsSlideShow
from ..data_management import *
from ..stage import HubbleStage
from ..utils import DISTANCE_CONSTANT, GALAXY_FOV, HUBBLE_ROUTE_PATH, IMAGE_BASE_URL, distance_from_angular_size, format_fov

log = logging.getLogger()


class StageState(CDSState):
    intro = CallbackProperty(True)
    galaxy = CallbackProperty({})
    galaxy_selected = CallbackProperty(False)
    galaxy_dist = CallbackProperty(None)
    dos_donts_opened = CallbackProperty(False)
    make_measurement = CallbackProperty(False)
    angsizes_total = CallbackProperty(0)
    distances_total = CallbackProperty(0)

    marker = CallbackProperty("")
    indices = CallbackProperty({})
    advance_marker = CallbackProperty(True)
    image_location_distance = CallbackProperty(f"{IMAGE_BASE_URL}/stage_two_distance")
    image_location_dosdonts = CallbackProperty(f"{IMAGE_BASE_URL}/stage_two_dos_donts")
    distance_sidebar = CallbackProperty(False)
    n_meas = CallbackProperty(0)
    show_ruler = CallbackProperty(False)
    meas_theta = CallbackProperty(0)
    distance_calc_count = CallbackProperty(0)
    
    # distance calc component variables
    distance_const = CallbackProperty(DISTANCE_CONSTANT)
    
    # stage 3 complete component variables
    stage_3_complete = CallbackProperty(False)

    markers = CallbackProperty([
        'ang_siz1',
        'cho_row1',
        'ang_siz2',
        'ang_siz2b',
        'ang_siz3',
        'ang_siz4',
        'ang_siz5',
        'ang_siz5a',
        'ang_siz6',
        'rep_rem1',
        'est_dis1',
        'est_dis2',
        'cho_row2',
        'est_dis3',
        'est_dis4',
        'fil_rem1',
        'two_com1',
    ])

    step_markers = CallbackProperty([
        'ang_siz1',
        'est_dis1'
    ])

    csv_highlights = CallbackProperty([
        'ang_siz1',
        'ang_siz2',
        'ang_siz2b',
        'ang_siz3',
        'ang_siz4',
        'ang_siz5',
        'ang_siz6',
        'rep_rem1',
        'est_dis1',
        'est_dis2',
    ])

    table_highlights = CallbackProperty([
        'cho_row1',
        'cho_row2',
        'est_dis3',
        'est_dis4',
        'fil_rem1',
        'two_com1',
    ])

    _NONSERIALIZED_PROPERTIES = [
        'markers', 'indices', 'step_markers',
        'csv_highlights', 'table_highlights',
        'distances_total', 'image_location'
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.marker = self.markers[0]
        self.indices = {marker: idx for idx, marker in enumerate(self.markers)}

    def marker_before(self, marker):
        return self.indices[self.marker] < self.indices[marker]

    def move_marker_forward(self, marker_text, _value=None):
        index = min(self.markers.index(marker_text) + 1, len(self.markers) - 1)
        self.marker = self.markers[index]
    
    def marker_after(self, marker):
        return self.indices[self.marker] > self.indices[marker]

    def marker_reached(self, marker):
        return self.indices[self.marker] >= self.indices[marker]

    def marker_index(self, marker):
        return self.indices[marker]


@register_stage(story="hubbles_law", index=3, steps=[
    "MEASURE SIZE",
    "ESTIMATE DISTANCE"
])
class StageTwo(HubbleStage):
    show_team_interface = Bool(False).tag(sync=True)
    START_COORDINATES = SkyCoord(213 * u.deg, 61 * u.deg, frame='icrs')

    _state_cls = StageState

    @default('template')
    def _default_template(self):
        return load_template("stage_3.vue", __file__)

    @default('stage_icon')
    def _default_stage_icon(self):
        return "2"

    @default('title')
    def _default_title(self):
        return "Galaxy Distances"

    @default('subtitle')
    def _default_subtitle(self):
        return "Perhaps a small blurb about this stage"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        dosdonts_slideshow = DosDontsSlideShow(self.stage_state.image_location_dosdonts)
        self.add_component(dosdonts_slideshow, label='py-dosdonts-slideshow')
        dosdonts_slideshow.observe(self._dosdonts_opened, names=['opened'])

        add_callback(self.stage_state, 'stage_3_complete', self._on_stage_complete)
        
        self.show_team_interface = self.app_state.show_team_interface

        self.add_component(DistanceTool(), label="py-distance-tool")

        add_distances_tool = \
            dict(id="update-distances",
                 icon="mdi-tape-measure",
                 tooltip="Fill in distances",
                 disabled=True,
                 activate=self.update_distances)
        distance_table = Table(self.session,
                               data=self.get_data(STUDENT_MEASUREMENTS_LABEL),
                               glue_components=[NAME_COMPONENT,
                                                ANGULAR_SIZE_COMPONENT,
                                                DISTANCE_COMPONENT],
                               key_component=NAME_COMPONENT,
                               names=['Galaxy Name',
                                      'θ (arcsec)',
                                      'Distance (Mpc)'],
                               title='My Galaxies',
                               selected_color=self.table_selected_color(
                                   self.app_state.dark_mode),
                               use_subset_group=False,
                               single_select=True,
                               tools=[add_distances_tool])

        self.add_widget(distance_table, label="distance_table")
        distance_table.observe(
            self.distance_table_selected_change, names=["selected"])
        
        example_galaxy_distance_table = Table(self.session,
                               data=self.get_data(EXAMPLE_GALAXY_MEASUREMENTS),
                               glue_components=[NAME_COMPONENT,
                                                ANGULAR_SIZE_COMPONENT,
                                                DISTANCE_COMPONENT],
                               key_component=NAME_COMPONENT,
                               names=['Galaxy Name',
                                      'θ (arcsec)',
                                      'Distance (Mpc)'],
                               title='Example Galaxy',
                               selected_color=self.table_selected_color(
                                   self.app_state.dark_mode),
                               use_subset_group=False,
                               single_select=True)

        self.add_widget(example_galaxy_distance_table, label="example_galaxy_distance_table")
        example_galaxy_distance_table.observe(
            self.distance_table_selected_change, names=["selected"])

        self.add_component(DistanceSidebar(self.stage_state),
                           label="py-distance-sidebar")
        self.distance_tool.observe(self._angular_size_update,
                                   names=["angular_size"])
        self.distance_tool.observe(self._angular_height_update,
                                   names=["angular_height"])
        self.distance_tool.observe(self._ruler_click_count_update,
                                   names=['ruler_click_count'])
        self.distance_tool.observe(self._measurement_count_update,
                                   names=['measurement_count'])
        self.distance_sidebar.angular_height = format_fov(
            self.distance_tool.angular_height)

        self.distance_tool.observe(self._distance_tool_flagged,
                                   names=["flagged"])

        add_callback(self.stage_state, 'galaxy', self._on_galaxy_changed)
        add_callback(self.stage_state, 'show_ruler', self._show_ruler_changed)

        # Callbacks
        add_callback(self.stage_state, 'marker',
                     self._on_marker_update, echo_old=True)
        add_callback(self.story_state, 'step_index',
                     self._on_step_index_update)
        self.trigger_marker_update_cb = True

        add_callback(self.stage_state, 'make_measurement',
                     self._make_measurement)
        add_callback(self.stage_state, 'distance_calc_count',
                     self.add_student_distance)
        
       
        # ang_siz2 -> cho_row1, est_dis3 -> cho_row2
        for marker in ['ang_siz2', 'est_dis3']:
            if self.stage_state.marker_reached(marker):
                marker_index = self.stage_state.markers.index(marker)
                new_index = marker_index - 1
                self.stage_state.marker = self.stage_state.marker[new_index]
        
    def _on_marker_update(self, old, new):
        if not self.trigger_marker_update_cb:
            return
        markers = self.stage_state.markers
        if new not in markers:
            new = markers[0]
            self.stage_state.marker = new
        if old not in markers:
            old = markers[0]
        advancing = markers.index(new) > markers.index(old)
        if new in self.stage_state.step_markers and advancing:
            self.story_state.step_complete = True
            self.story_state.step_index = self.stage_state.step_markers.index(
                new)
        if advancing and (new == "cho_row1" or new == "cho_row2"):
            self.distance_table.selected = []
            self.distance_tool.widget.center_on_coordinates(
                self.START_COORDINATES, instant=True)
            self.distance_tool.reset_canvas()
            # need to turn off ruler marker also.
            # and start stage 2 at the start coordinates

    def _on_step_index_update(self, index):
        # If we aren't on this stage, ignore
        if self.story_state.stage_index != self.index:
            return

        # Change the marker without firing the associated stage callback
        # We can't just use ignore_callback, since other stuff (i.e. the frontend)
        # may depend on marker callbacks
        self.trigger_marker_update_cb = False
        index = min(index, len(self.stage_state.step_markers) - 1)
        self.stage_state.marker = self.stage_state.step_markers[index]
        self.trigger_marker_update_cb = True

    def _dosdonts_opened(self, msg):
        self.stage_state.dos_donts_opened = msg["new"]

    def distance_table_selected_change(self, change):
        selected = change["new"]
        if not selected or selected == change["old"]:
            return

        index = self.distance_table.index
        data = self.distance_table.glue_data
        galaxy = {x.label: data[x][index] for x in data.main_components}
        self.distance_tool.reset_canvas()
        self.distance_tool.go_to_location(galaxy["ra"], galaxy["decl"],
                                          fov=GALAXY_FOV)

        self.distance_tool.reset_brightness_contrast() # reset the style of viewer
        
        self.stage_state.galaxy = galaxy
        self.stage_state.galaxy_dist = None
        self.distance_tool.measuring_allowed = bool(galaxy)
        self.stage_state.meas_theta = data[ANGULAR_SIZE_COMPONENT][index]

        if self.stage_state.marker == 'cho_row1' or self.stage_state.marker == 'cho_row2':
            self.stage_state.move_marker_forward(self.stage_state.marker)
            self.stage_state.galaxy_selected = True

    def _angular_size_update(self, change):
        new_ang_size = change["new"]
        if new_ang_size != 0 and new_ang_size is not None:
            self._make_measurement()

    def _angular_height_update(self, change):
        self.distance_sidebar.angular_height = format_fov(change["new"])

    def _ruler_click_count_update(self, change):
        if change["new"] == 1:
            self.stage_state.marker = 'ang_siz4'  # auto-advance guideline if it's the first ruler click

    def _measurement_count_update(self, change):
        if change["new"] == 1:
            self.stage_state.marker = 'ang_siz5'  # auto-advance guideline if it's the first measurement made

    def _show_ruler_changed(self, show):
        self.distance_tool.show_ruler = show

    def _on_galaxy_changed(self, galaxy):
        self.distance_tool.galaxy_selected = bool(galaxy)

    def _make_measurement(self):
        galaxy = self.stage_state.galaxy
        index = self.get_data_indices(STUDENT_MEASUREMENTS_LABEL, NAME_COMPONENT,
                                      lambda x: x == galaxy["name"],
                                      single=True)
        angular_size = self.distance_tool.angular_size
        # ang_size_deg = angular_size.value
        # distance = round(MILKY_WAY_SIZE_MPC * 180 / (ang_size_deg * pi))
        # angular_size_as = round(angular_size.to(u.arcsec).value)

        index = self.distance_table.index
        if index is None:
            return
        data = self.distance_table.glue_data
        curr_value = data[ANGULAR_SIZE_COMPONENT][index]

        if curr_value is None:
            self.stage_state.angsizes_total = self.stage_state.angsizes_total + 1

        # self.stage_state.galaxy_dist = distance
        # self.update_data_value(STUDENT_MEASUREMENTS_LABEL, DISTANCE_COMPONENT, distance, index)
        # self.update_data_value(STUDENT_MEASUREMENTS_LABEL, ANGULAR_SIZE_COMPONENT, angular_size_as, index)

        self.stage_state.meas_theta = round(angular_size.to(u.arcsec).value)
        self.update_data_value(STUDENT_MEASUREMENTS_LABEL, ANGULAR_SIZE_COMPONENT,
                               self.stage_state.meas_theta, index)
        self.story_state.update_student_data()
        with ignore_callback(self.stage_state, 'make_measurement'):
            self.stage_state.make_measurement = False

    def _distance_tool_flagged(self, change):
        if not change["new"]:
            return
        

        galaxy = self.state.galaxy
        if galaxy["id"]:
            data = {"galaxy_id": int(galaxy["id"])}
        else:
            name = galaxy["name"]
            if not name.endswith(".fits"):
                name += ".fits"
            data = {"galaxy_name": name}
        requests.post(f"{API_URL}/{HUBBLE_ROUTE_PATH}/mark-tileload-bad",
                      json=data)

        index = self.distance_table.index
        if index is None:
            return
        item = self.distance_table.selected[0]
        galaxy_name = item["name"]
        self.remove_measurement(galaxy_name)
        self.distance_tool.flagged = False

    def add_student_distance(self, _args=None):
        index = self.distance_table.index
        if index is None:
            return
        distance = distance_from_angular_size(self.stage_state.meas_theta)
        self.update_data_value(STUDENT_MEASUREMENTS_LABEL, DISTANCE_COMPONENT, distance,
                               index)
        self.story_state.update_student_data()
        if self.stage_state.distance_calc_count == 1:  # as long as at least one thing has been measured, tool is enabled. But if students want to loop through calculation by hand they can.
            self.enable_distance_tool(True)
        self.get_distance_count()

    def update_distances(self, table, tool=None):
        data = table.glue_data
        for item in table.items:
            index = table.indices_from_items([item])[0]
            if index is not None and data[DISTANCE_COMPONENT][index] is None:
                theta = data[ANGULAR_SIZE_COMPONENT][index]
                if theta is None:
                    continue
                distance = round(DISTANCE_CONSTANT / theta, 0)
                self.update_data_value(STUDENT_MEASUREMENTS_LABEL, DISTANCE_COMPONENT,
                                       distance, index)
        self.story_state.update_student_data()
        if tool is not None:
            table.update_tool(tool)
        self.get_distance_count()

    def vue_update_distances(self, _args):
        self.update_distances(self.distance_table)

    def vue_add_distance_data_point(self, _args=None):
        self.stage_state.make_measurement = True

    def enable_distance_tool(self, enable):
        if enable:
            tool = self.distance_table.get_tool("update-distances")
            tool["disabled"] = False
            self.distance_table.update_tool(tool)
    
    def get_distance_count(self):
        student_measurements = self.get_data(STUDENT_MEASUREMENTS_LABEL)
        distances = student_measurements[DISTANCE_COMPONENT]
        self.stage_state.distances_total = distances[distances != None].size

    @property
    def distance_sidebar(self):
        return self.get_component("py-distance-sidebar")

    @property
    def distance_tool(self):
        return self.get_component("py-distance-tool")

    @property
    def distance_table(self):
        return self.get_widget("distance_table")

    @property
    def last_guideline(self):
        return self.get_component('guideline-stage-3-complete')

    def _on_stage_complete(self, complete):
        if complete:
            self.story_state.stage_index = 4

            # We need to do this so that the stage will be moved forward every
            # time the button is clicked, not just the first
            self.last_guideline.stage_3_complete = False