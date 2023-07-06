# nuitka-project: --standalone
# nuitka-project: --include-data-file=./icon.png=icon.png
# nuitka-project: --include-data-dir=./frontend=frontend
# nuitka-project-if: {OS} in ('Windows'):
#     nuitka-project: --mingw64
#     nuitka-project: --plugin-enable=tk-inter
#     nuitka-project: --windows-disable-console
#     nuitka-project: --windows-icon-from-ico=./icon.ico
#     nuitka-project: --windows-company-name=-
#     nuitka-project: --windows-product-name=Wishing Well
#     nuitka-project: --windows-file-description=Wishing Well
#     nuitka-project: --windows-product-version=1.4.0

import logging
import bottle

from wishing_well.util import set_up_logging, get_usable_port
from wishing_well.server import Server

set_up_logging()
port = get_usable_port()
Server(bottle, port)
logging.info('Quitting')
