import launcher
import configparser

CONFIG_PATH = 'config.ini'


def main():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)

    launcher.launch(config)


if __name__ == "__main__":
    main()