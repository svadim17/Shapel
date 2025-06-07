from collections import namedtuple
from loguru import logger

Packet_levels = namedtuple('Packet_levels', ['antenna', 'values'])
Packet_spectrum = namedtuple('Packet_spectrum', ['antenna', 'values'])
Data_for_peleng = namedtuple('Data_for_peleng', ['max_antenna', 'max_value',
                                                 'nearest_antenna', 'nearest_value'])
Peleng = namedtuple('Peleng', ['name', 'color', 'angle', 'power'])
Peleng_new = namedtuple('Peleng_new', ['name', 'color', 'angle', 'power'])
Sector_levels = namedtuple('Sector_levels', ['antenna', 'names', 'colors', 'levels'])


class Dron():
    def __init__(self, dict_name, conf: dict):
        self.dict_name = 'dict_name'
        self.name = 'basic-name'
        self.color = [0, 0, 0]
        self.gains = []
        self.frequency = 0
        self.update(dict_name, conf)

    def update(self, dict_name, conf):
        try:
            self.dict_name = dict_name
            self.name = conf['name']
            self.color = conf['color']
            self.gains = list(conf['gains'])
            self.frequency = conf['frequency']
        except KeyError:
            logger.exception('Incorrect Drons config file')

    def collect(self) -> dict:
        return {self.dict_name:
                    {'name': self.name,
                     'gains': self.gains,
                     'color': self.color,
                     'frequency': self.frequency}
                }

    def __repr__(self):
        return f'{self.__class__}: {self.dict_name}'
