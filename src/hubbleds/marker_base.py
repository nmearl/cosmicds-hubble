from enum import EnumMeta


class MarkerBase(metaclass=EnumMeta):

    @classmethod
    def next(cls, step):
        return cls(step.value + 1)

    @classmethod
    def previous(cls, step):
        return cls(step.value - 1)

    @classmethod
    def first(cls):
        return cls(1)

    @classmethod
    def last(cls):
        return cls(len(cls))
    
    @classmethod
    # Check if the given marker is inclusively within the start and end markers specified.
    def is_between(cls, marker, start, end):
        return marker.value >= start.value and \
               marker.value <= end.value