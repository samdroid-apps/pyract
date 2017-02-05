# Copyright 2017 Sam Parkinson <sam@sam.today>
#
# This file is part of Pyract.
#
# Pyract is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pyract is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Pyract.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Gtk
from pyract.view import run, Component, Node, load_css
from pyract.model import ObservableModel, ObservableValue, ModelField


# Let's create a model to back our application.  Since it is Observable, it
# will tell pyract to re-render our UI when it changes.
class AppModel(ObservableModel):
    # The ModelField tells the model to create us an ObservableValue and set
    # to 0.  ObservableValues lets us re-render the UI when the value changes.
    counter = ModelField(ObservableValue, 0)

    def increment(self):
        self.counter.value = self.counter.value + 1


# Components are similar to in React.
class AppComponent(Component):
    # Our render method can return a Node or list of Nodes.
    def render(self, model: AppModel):
        # Nodes are a type followed by kwargs.  When a component is
        # re-rendered, then the Node trees get diffed and only the changed
        # Nodes and properties are updated.
        # The type is either a Gtk.Widget or pyract.Component subclass.
        # "signal__" props are the same as connecting a GObject signal
        return Node(Gtk.Window, signal__destroy=Gtk.main_quit,
                    title='My Counter App',
                    children=[
            Node(Gtk.Box, orientation=Gtk.Orientation.VERTICAL,
                 children=[
                # The class_names prop adds the appropriate classes
                Node(Gtk.Label, class_names=['counter-label'],
                     label=str(model.counter.value)),
                Node(Gtk.Button, label='Increment Counter',
                     class_names=['suggested-action', 'bottom-button'],
                     # Hide the button when the counter gets to ten
                     visible=model.counter.value < 10,
                     signal__clicked=self._button_clicked_cb),
                # Add a reset button, but only show it when counter == 10
                Node(Gtk.Button, label='Reset',
                     class_names=['destructive-action', 'bottom-button'],
                     visible=model.counter.value >= 10,
                     signal__clicked=self._reset_clicked_cb)
            ])
        ])

    # Signal handlers are just like in normal Gtk+
    def _button_clicked_cb(self, button):
        # Access the props using self.props
        self.props['model'].increment()

    def _reset_clicked_cb(self, button):
        self.props['model'].counter.value = 0


# Adding CSS is really easy:
load_css('''
.counter-label {
    font-size: 100px;
    padding: 20px;
}
.bottom-button {
    margin: 10px;
}
''')


# The run function works just like constructing a Node, but it enters
# the mainloop and runs the app!
run(AppComponent, model=AppModel())
