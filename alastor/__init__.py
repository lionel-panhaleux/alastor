from .api import create_app

application = create_app()


def main():
    application.run()
