from router import register_routers
from utils.custom_exception import register_exception_handler


def init_main(app):
    register_exception_handler(app)
    register_routers(app)
