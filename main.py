import launcher
import configparser
import os

#CONFIG_PATH = '/home/akjpi/Desktop/assbot/AssassinScheduleSystem/config.ini'
CONFIG_PATH = '/home/akj/Projects/assbot/assThreeOh/config.ini'

def main():
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    launcher.launch(config)

if __name__ == '__main__':
    main()

