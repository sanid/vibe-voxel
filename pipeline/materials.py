"""Voxel material ids, shared by the voxelizer, tree synthesizer and chunk writer.

Id 0 is air. Ids are stored in uint8 matrices, so the set stays under 256.
"""

MATERIALS = {
    "air": 0,
    "ground": 1,
    "building": 2,
    "wall": 3,
    "roof": 4,
    "trunk": 5,
    "crown_linden": 6,   # Tilia: Winter- and Sommerlinde, the most common street tree
    "crown_plane": 7,    # Platanus
    "crown_oak": 8,      # Quercus
    "crown_other": 9,    # everything else in the inventory
    "beacon": 10,        # red obstruction light on tall towers (emissive)
}

CROWN_BY_GENUS = {
    "Tilia": "crown_linden",
    "Platanus": "crown_plane",
    "Quercus": "crown_oak",
}
