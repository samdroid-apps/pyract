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

import json
from gi.repository import GObject
from typing import Generic, Union, Dict, List


PopoType = Union[str, int, float, bool, dict, list]


class Observable(GObject.GObject):
    changed_signal = GObject.Signal('changed')

    def serialize(self) -> PopoType:
        raise NotImplimentedError()

    def deserialize(self, value: PopoType):
        raise NotImplimentedError()


class ObservableValue(Observable):
    def __init__(self, value):
        super().__init__()
        self._value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        if self._value == new_value:
            return
        self._value = new_value
        self.changed_signal.emit()

    def serialize(self) -> PopoType:
        return self.value

    def deserialize(self, value: PopoType):
        self.value = value


class ObservableModel(Observable):
    def __init__(self, **kwargs):
        super().__init__()

        for k, v in vars(type(self)).items():
            if isinstance(v, ModelField):
                setattr(self, k, v.create())

        for k, v in kwargs.items():
            getattr(self, k).value = v

    def _attribute_changed_cb(self, value):
        self.changed_signal.emit()

    def __setattr__(self, k, new):
        old = None
        if hasattr(self, k):
            old = getattr(self, k)
            if isinstance(old, Observable) and old != getattr(type(self), k):
                old.disconnect_by_func(self._attribute_changed_cb)

                if not isinstance(new, Observable):
                    raise ValueError(
                        'Can not replace observable key {} with '
                        'non-observable object {}'.format(k, new))
                
        if isinstance(new, Observable):
            new.changed_signal.connect(self._attribute_changed_cb)

            if old != new:
                self.changed_signal.emit()
        super().__setattr__(k, new)

    def serialize(self) -> Dict[str, PopoType]:
        ret = {}
        for k, v in vars(type(self)).items():
            if isinstance(v, ModelField):
                ret[k] = getattr(self, k).serialize()
        return ret

    def serialize_to_path(self, path):
        j = self.serialize()
        with open(path, 'w') as f:
            json.dump(j, f)

    def deserialize(self, value: Dict[str, PopoType]):
        for k, v in value.items():
            getattr(self, k).deserialize(v)

    def deserialize_from_path(self, path):
        with open(path) as f:
            j = json.load(f)
        self.deserialize(j)


class ModelField():
    def __init__(self, type_, *args, **kwargs):
        self._type = type_
        self._args = args
        self._kwargs = kwargs

        if not issubclass(type_, Observable):
            raise ValueError('ModelFields type_ must be Observable subclass')

    def create(self):
        return self._type(*self._args, **self._kwargs)


class ObservableList(ObservableValue):
    def __init__(self, type_, value=None, *args, **kwargs):
        super().__init__(value or [], *args, **kwargs)
        self._type = type_
        for v in self.value:
            v.changed_signal.connect(self._item_changed_cb)

    def _item_changed_cb(self, item):
        self.changed_signal.emit()

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        assert(isinstance(new_value, list))
        if self._value == new_value:
            return
        for item in new_value:
            if item not in self._value:
                item.changed_signal.connect(self._item_changed_cb)
        for item in self._value:
            if item not in new_value:
                item.disconnect_by_func(self._item_changed_cb)

    def __getitem__(self, y):  return self.value[y]
    def __iter__(self):  return iter(self.value)
    def __len__(self):  return len(self.value)
    def __bool__(self):  return bool(self.value)

    def append(self, item):
        self.value.append(item)
        item.changed_signal.connect(self._item_changed_cb)
        self.changed_signal.emit()

    def clear(self):
        for item in self:
            item.disconnect_by_func(self._item_changed_cb)
        self.value.clear()
        self.changed_signal.emit()

    def pop(self, index=None):
        item  = self.value.pop(index)
        item.disconnect_by_func(self._item_changed_cb)
        self.changed_signal.emit()
        return item

    def serialize(self) -> List[PopoType]:
        return [v.serialize() for v in self]

    def deserialize(self, value: List[PopoType]):
        self.clear()
        for v in value:
            ins = self._type()
            ins.deserialize(v)
            self.append(ins)
