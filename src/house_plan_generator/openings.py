"""One opening definition for drawing and the strict concept review."""
def door_interval(room, door, plan):
    span = room['width_ft'] if door['side'] in {'north', 'south'} else room['depth_ft']
    if plan.get('door_offset_convention') == 'start':
        return door['offset_ft'], door['offset_ft'] + door['width_ft']
    # Preserve existing catalogue presentation while new concepts use explicit starts.
    width = min(3.5 if door['id'] == 'entrance' else 3.0, span * .6)
    center = min(max(door['offset_ft'], width / 2 + .1), span - width / 2 - .1)
    return center - width / 2, center + width / 2


def door_swing(room, door, plan):
    """Inward swing in drawing coordinates (positive y is south).

    `hinge=end` puts the hinge at the far end of the explicit opening.
    The swept bounding rectangle is conservative; it is not the full free path.
    """
    start, end = door_interval(room, door, plan)
    side = door['side']
    at_end = door.get('hinge', 'start') == 'end'
    offset = end if at_end else start
    x, y = room['x_ft'], room['y_ft']
    x2, y2 = x + room['width_ft'], y + room['depth_ft']
    hinge = {'north': (x + offset, y), 'south': (x + offset, y2),
             'west': (x, y + offset), 'east': (x2, y + offset)}[side]
    dx, dy = {'north': (0, 1), 'south': (0, -1),
              'west': (1, 0), 'east': (-1, 0)}[side]
    width = end - start
    leaf = (hinge[0] + dx * width, hinge[1] + dy * width)
    angles = {'north': ((0, 90), (90, 180)), 'south': ((270, 360), (180, 270)),
              'west': ((0, 90), (270, 360)), 'east': ((90, 180), (180, 270))}[side][at_end]
    bounds = {'north': (x+start,y,x+end,y+width), 'south': (x+start,y2-width,x+end,y2),
              'west': (x,y+start,x+width,y+end), 'east': (x2-width,y+start,x2,y+end)}[side]
    return {'hinge_ft': hinge, 'leaf_ft': leaf, 'arc_degrees': angles, 'bounds_ft': bounds}
