"""The Archive: a read-only viewer for the game's story, records and media.

It reads the imported game files (revision 0) and the master data, builds one
SQLite index, and serves pages from it. Nothing here touches the save.
"""
