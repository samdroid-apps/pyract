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

from gi.repository import Gtk, Gdk
from typing import Union, List

from .model import Observable


_INSTANCE = '____instance____'


class Node(tuple):
    def __new__(cls, type_, **kwargs):
        return super(Node, cls).__new__(cls, (type_, kwargs))

    def __init__(self, type_, **props):
        self.type = type_
        self.props = props


class BaseComponent():
    def __init__(self, **props):
        pass

    def update(self, updated_list=[]):
        pass

    def destroy(self):
        pass

    def get_widgets(self):
        return []


class RenderException(Exception):
    pass

class ChildrenFormatException(RenderException):
    pass


class GtkComponent(BaseComponent):
    def __init__(self, type_, **props):
        self._props = {}
        self._type = type_
        self._instance = type_()

        # visible=True is a default prop
        self.update([('visible', True)])
        self.update(props.items())

    def update(self, updated_list=[]):
        for k, v in updated_list:
            if k.startswith('signal__'):
                # TODO: Unbind old handler
                if v is not None:
                    self._instance.connect(k[8:], v)
            elif k == 'class_names':
                self._handle_class_names(v)
            elif k == 'children':
                self._handle_children(v)
            elif k.startswith('____'):
                continue
            else:
                self._instance.set_property(k, v)

    def _handle_class_names(self, class_names):
        old = self._props.get('class_names', [])
        sc = self._instance.get_style_context()

        for cn in old:
            if cn not in class_names:
                sc.remove_class(cn)
        for cn in class_names:
            if cn not in old:
                sc.add_class(cn)

    def _handle_children(self, child_items):
        children = []
        for t, props in child_items:
            children.extend(props[_INSTANCE].get_widgets())

        if issubclass(self._type, Gtk.Bin):
            if len(children) == 1:
                if self._instance.get_child() != children[0]:
                    old = self._instance.get_child()
                    if old:
                        self._instance.remove(old)
                    self._instance.add(children[0])
            else:
                raise ChildrenFormatException(
                    'GtkBin subclass {} should only have 1 child, got {}'.format(
                        self._type, children))
        elif issubclass(self._type, Gtk.Box):
            old = self._instance.get_children()
            for old_child in old:
                if old_child not in children:
                    self._instance.remove(old_child)
            for i, child in enumerate(children):
                if child not in old:
                    self._instance.add(child)
                self._instance.reorder_child(child, i)
        else:
            if len(children):
                raise ChildrenFormatException(
                    'Widget {} should have 0 children, got {}'.format(
                        self._type, children))

    def get_widgets(self):
        return [self._instance]

    def destroy(self):
        self._instance.destory()




class Component(BaseComponent):
    def __init__(self, **props):
        self.props = {}
        self._subtreelist = None
        self.update(props.items())

    def _observable_changed_cb(self, observable):
        self.update()

    def update(self, updated_list=[]):
        for k, v in updated_list:
            old = self.props.get(k)
            if isinstance(old, Observable):
                old.disconnect_by_func(self._observable_changed_cb)

            self.props[k] = v
            if isinstance(v, Observable):
                v.changed_signal.connect(self._observable_changed_cb)

        new = self.render(**self.props)
        if isinstance(new, Node):
            new = [new]
        self._subtreelist = render_treelist(self._subtreelist, new)

    def render(self, **props) -> Union[Node, List[Node]]:
        return []

    def get_widgets(self):
        widgets = []
        for t, props in (self._subtreelist or []):
            widgets.extend(props[_INSTANCE].get_widgets())
        return widgets



def treeitem_to_key(i, v):
    type, props = v
    return '{}:{}.{}'.format(
        props.get('key') or i, type.__module__, type.__name__)


def children_keys_dict(children):
    d = {}
    for i, v in enumerate(children):
        d[treeitem_to_key(i, v)] = v
    return d


def render_tree(old, new):
    # Split the tree input
    old_type, old_props = old or (None, {})
    # Get the instance so that we can transition it to the new tree
    instance = old_props.get(_INSTANCE)
    if _INSTANCE in old_props:
        del old_props[_INSTANCE]
    new_type, new_props = new

    # Make sure that we have _INSTANCES for the 'children' prop
    old_children = old_props.get('children', [])
    new_children = new_props.get('children', [])
    children = render_treelist(old_children, new_children)

    if old_type == new_type:
        changes = []
        for k in old_props.keys():
            if k.startswith('____'):
                continue
            if k not in new_props:
                changes.append((k, None))
        for k, v in new_props.items():
            if k.startswith('____'):
                continue
            if old_props.get(k) != v:
                changes.append((k, v))
        if changes:
            instance.update(changes)
    else:
        if instance is not None:
            instance.destroy()

        if issubclass(new_type, Gtk.Widget):
            instance = GtkComponent(new_type, **new_props)
        else:
            instance = new_type(**new_props)

    new_props[_INSTANCE] = instance
    return Node(new_type, **new_props)


def render_treelist(old, new):
    # Make sure that we have _INSTANCES for the 'children' prop
    old = old or []
    old_keys = children_keys_dict(old)
    new_keys = children_keys_dict(new)
    ret = []

    for k, v in old_keys.items():
        if k not in new_keys:
            # TODO
            print('Destroy child', v)
    for i, v in enumerate(new):
        k = treeitem_to_key(i, v)
        ret.append(render_tree(old_keys.get(k), v))

    return new


def run(type_, **kwargs):
    instance = type_(**kwargs)
    Gtk.main()


def load_css(data):
    css_prov = Gtk.CssProvider()
    css_prov.load_from_data(data.encode('utf8'))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_prov,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
