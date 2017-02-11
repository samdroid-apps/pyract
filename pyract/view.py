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

import sys
from gi.repository import Gtk, Gdk, GObject
from typing import Union, List

from .model import Observable


class Node(tuple):
    def __new__(cls, type_, **kwargs):
        return super(Node, cls).__new__(cls, (type_, kwargs))

    def __init__(self, type_, **props):
        self.type = type_
        self.props = props
        # Almost a tuple, but we have this nice mutable instance prop
        self.instance = None

    def __repr__(self):
        return '<Node<{}.{}> {} {}>'.format(
            self.type.__module__, self.type.__name__,
            self.instance, self.props)


def _node_list_single_widget(nl):
        widgets = []
        for node in (nl or []):
            widgets.extend(node.instance.get_widgets())

        if len(widgets) > 1:
            raise ChildrenFormatException(
                'Node list {} should have 1 widget, '
                'got {}'.format(nl, widgets))

        return widgets[0] if len(widgets) else None


class BaseComponent(GObject.GObject):
    updated_signal = GObject.Signal('updated')

    def __init__(self, **props):
        super().__init__()

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
        super().__init__()
        self._props = {}
        self._type = type_
        self._instance = type_()

        self.update(props.items())
        if not issubclass(self._type, Gtk.Popover):
            # visible=True is a default prop
            self.update([('visible', True)])

    def update(self, updated_list=[]):
        for k, v in updated_list:
            if k.startswith('signal__'):
                # TODO: Unbind old handler
                if v is not None:
                    self._instance.connect(k[8:], v)
            elif k.startswith('child__'):
                continue # We don't handle the child props ourself
            elif k == 'auto_grab_focus':
                if v:
                    self._setup_auto_grab_focus()
            elif k == 'class_names':
                self._handle_class_names(v)
            elif k == 'size_groups':
                self._handle_size_groups(v)
            elif k == 'children':
                self._handle_children(v)
            elif k.startswith('____'):
                continue
            else:
                self.set_property(k, v)
            self._props[k] = v
        self.updated_signal.emit()

    def set_property(self, k, v):
        if k == 'popover' and issubclass(self._type, Gtk.MenuButton):
            self._instance.set_property(k, _node_list_single_widget(v))
        elif k == 'image' and issubclass(self._type, Gtk.Button):
            self._instance.set_property(k, _node_list_single_widget(v))
        else:
            self._instance.set_property(k, v)

    def __realize_cb(self, instance):
        instance.grab_focus()

    def _setup_auto_grab_focus(self):
        if self._instance.get_realized():
            self._instance.grab_focus()
        else:
            self._instance.connect('realize', self.__realize_cb)

    def _handle_class_names(self, new):
        old = self._props.get('class_names', [])
        sc = self._instance.get_style_context()

        for cn in old:
            if cn not in new:
                sc.remove_class(cn)
        for cn in new:
            if cn not in old:
                sc.add_class(cn)

    def _handle_size_groups(self, new):
        old = self._props.get('size_groups', [])
        for sg in old:
            if sg not in new:
                sg.remove_widget(self._instance)
        for sg in new:
            if sg not in old:
                sg.add_widget(self._instance)

    def _handle_children(self, child_items):
        children = []
        for node in child_items:
            children.extend(node.instance.get_widgets())

        if issubclass(self._type, Gtk.Bin):
            if issubclass(self._type, Gtk.Window):
                children = []
                headers = []
                for node in child_items:
                    if node.props.get('child__is_header'):
                        headers.extend(node.instance.get_widgets())
                    else:
                        children.extend(node.instance.get_widgets())

                if len(headers) > 1:
                    raise ChildrenFormatException(
                        'A window may only have 1 header widget, '
                        'got {}'.format(headers))
                if len(headers) == 1:
                    self._instance.set_titlebar(headers[0])

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
        elif issubclass(self._type, Gtk.FlowBox):
            # Don't try and sort things while we are changing the children
            self._instance.set_sort_func(None)

            old = self._instance.get_children()
            for old_child in old:
                if old_child not in children:
                    self._instance.remove(old_child)
            for i, child in enumerate(children):
                if child not in old:
                    if not isinstance(child, Gtk.FlowBoxChild):
                        raise ChildrenFormatException(
                            'FlowBox children must be Gtk.FlowBoxChild, '
                            'got {}'.format(child))
                    self._instance.add(child)
                child.__flowbox_index = i

            def _flowbox_sort(a, b):
                return a.__flowbox_index - b.__flowbox_index

            self._instance.set_sort_func(_flowbox_sort)
            self._instance.invalidate_sort()
        elif issubclass(self._type, Gtk.HeaderBar):
            start = []
            end = []
            for node in child_items:
                if node.props.get('child__is_end'):
                    end.extend(node.instance.get_widgets())
                else:
                    start.extend(node.instance.get_widgets())

            # This is broken if children move from start->end
            old = self._instance.get_children()
            for old_child in old:
                if old_child not in children:
                    self._instance.remove(old_child)
            for child in start:
                if child not in old:
                    self._instance.pack_start(child)
            for child in end:
                if child not in old:
                    self._instance.pack_end(child)
        else:
            if len(children):
                raise ChildrenFormatException(
                    'Widget {} should have 0 children, got {}'.format(
                        self._type, children))

    def get_widgets(self):
        return [self._instance]

    def destroy(self):
        self._instance.destroy()
        # FIXME: Destroy props['popover'], props['image'] when needed
        for child in (self._props.get('children') or []):
            child.instance.destroy()




class Component(BaseComponent):
    def __init__(self, **props):
        super().__init__()
        self.props = {}
        self.state = None
        self._rendered_yet = False

        self._subtreelist = None
        self.update(props.items())

    def _observable_changed_cb(self, observable):
        self.update()

    def update(self, updated_list=[]):
        for k, v in updated_list:
            if k.startswith('child__'):
                continue  # We don't handle the child props ourself

            old = self.props.get(k)
            if isinstance(old, Observable):
                old.disconnect_by_func(self._observable_changed_cb)

            self.props[k] = v
            if isinstance(v, Observable):
                v.changed_signal.connect(self._observable_changed_cb)

        if not self._rendered_yet:
            if hasattr(type(self), 'State'):
                state_cls = getattr(type(self), 'State')
                self.state = state_cls()
            self.before_first_render(**self.props)
            if self.state is not None:
                self.state.changed_signal.connect(self._observable_changed_cb)
            self._rendered_yet = True

        new = self.render(**self.props)
        self._subtreelist = render_treelist(self._subtreelist, new)
        self.updated_signal.emit()

    def before_first_render(self, **props) -> None:
        pass

    def render(self, **props) -> Union[Node, List[Node]]:
        return []

    def _get_subtreelist(self):
        stl = (self._subtreelist or [])
        if isinstance(stl, Node):
            stl = [stl]
        return stl

    def get_widgets(self):
        widgets = []
        for node in self._get_subtreelist():
            widgets.extend(node.instance.get_widgets())
        return widgets

    def destroy(self):
        for node in self._get_subtreelist():
            node.instance.destroy()


def treeitem_to_key(i, v):
    type, props = v
    return '{}:{}.{}'.format(
        props.get('key') or i, type.__module__, type.__name__)


def children_keys_dict(children):
    d = {}
    for i, v in enumerate(children):
        d[treeitem_to_key(i, v)] = v
    return d


_EXCLUDED_KEYS = {'ref', 'key'}


def _get_to_inflate_for_type(type_) -> List[str]:
    l = ['children']
    if issubclass(type_, Gtk.Widget):
        if issubclass(type_, Gtk.MenuButton):
            l.append('popover')
        if issubclass(type_, Gtk.Button):
            l.append('image')
    return l


def prop_values_equal(a, b):
    if a == b:
        return True
    return False


def render_tree(old, new):
    # Split the tree input
    old_type, old_props = old or (None, {})
    instance = old.instance if old else None
    new_type, new_props = new

    to_inflate = _get_to_inflate_for_type(new_type)
    for k in to_inflate:
        old = old_props.get(k, [])
        new = new_props.get(k, [])
        v = render_treelist(old, new)
        if v:
            new_props[k] = v

    if old_type == new_type:
        changes = []
        for k in old_props.keys():
            if k in _EXCLUDED_KEYS:
                continue
            if k not in new_props:
                changes.append((k, None))
        for k, v in new_props.items():
            if k in _EXCLUDED_KEYS:
                continue
            if not prop_values_equal(old_props.get(k), v):
                changes.append((k, v))
        if changes:
            instance.update(changes)
    else:
        if instance is not None:
            instance.destroy()

        p = {k: v for k, v in new_props.items() if k not in _EXCLUDED_KEYS}
        if issubclass(new_type, Gtk.Widget):
            instance = GtkComponent(new_type, **p)
        else:
            instance = new_type(**p)

        if new_props.get('ref'):
            new_props['ref'](instance)

    node = Node(new_type, **new_props)
    node.instance = instance
    return node


def render_treelist(old, new):
    old = old or []
    if isinstance(old, Node):
        old = [old]
    if isinstance(new, Node):
        new = [new]
    old_keys = children_keys_dict(old)
    new_keys = children_keys_dict(new)
    ret = []

    for k, v in old_keys.items():
        if k not in new_keys:
            if v.instance is not None:
                v.instance.destroy()
    for i, v in enumerate(new):
        k = treeitem_to_key(i, v)
        ret.append(render_tree(old_keys.get(k), v))

    return ret


class _PyractApplication(Gtk.Application):
    def __init__(self, node, app_id):
        super().__init__(application_id=app_id)
        self._node = node

    def do_activate(self):
        type_, kwargs = self._node
        instance = type_(**kwargs)
        self._updated_cb(instance)
        instance.updated_signal.connect(self._updated_cb)

    def _updated_cb(self, instance):
        for widget in instance.get_widgets():
            if isinstance(widget, Gtk.ApplicationWindow) and widget:
                self.add_window(widget)


def run(node, app_id):
    app = _PyractApplication(node, app_id)
    app.run(sys.argv)


def load_css(data):
    css_prov = Gtk.CssProvider()
    css_prov.load_from_data(data.encode('utf8'))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_prov,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
