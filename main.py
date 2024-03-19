import launcher
import configparser
import os

CONFIG_PATH = '/home/akjpi/Desktop/assbot/AssassinScheduleSystem/config.ini'

def main():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    launcher.launch(config)

if __name__ == '__main__':
    main()

