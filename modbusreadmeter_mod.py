import argparse
from statistics import mean
from sys import exit
from time import perf_counter
from datetime import datetime

import minimalmodbus
import serial

DEFAULT_CIRCLES = 300
DEFAULT_BAUD_RATE = 115200
DEFAULT_PORT_NAME = '/dev/ttyS1'
DEFAULT_REGISTERS = ['1']
DEFAULT_ADDRESSES = ['1']


class Measurement:

    def __init__(self, args: dict) -> None:
        for key, value in args.items():
            setattr(self, key, value)
        # print(f'Args{args}')

        self.port_params = {'port': self.port,
                            'baudrate': self.baud_rate,
                            'parity': self.parity,
                            'bytesize': self.bytesize,
                            'stopbits': self.stop_bits,
                            'timeout': 1
                            }
        
        self.registers = [int(register) for register in self.registers[0].split(',')]
        self.device_addresses = [int(register) for register in self.device_addresses[0].split(',')]

        print(f'Адреса устройств для чтения: {self.device_addresses}',
              f'Регистры для чтения:         {self.registers}',
              f'Циклов чтения:               {self.circles}',
              f'Параметры порта:             ', end='', sep='\n')

        print(*map(lambda item: f'{item[0]}: {item[-1]}'.capitalize(), self.port_params.items()),
              sep='\n                             ')

        self.count_dict = {}
        self.results = []
        self.errors = 0
        self.time_delta = None
        self.serial = None

    def check_serial_port(self) -> None:
        print('Проверка порта...            ', end='')
        try:
            self.serial = serial.Serial(**self.port_params)
            print('Тест порта успешно')
        except serial.SerialException as error:
           # print('ошибка', error.strerror.capitalize(), sep='\n')
            print('Тест порта ошибка (укажите другой порт через параметр -D)', error)
            exit(1)
       
    def do_tests(self) -> None:
        gavg_req_speed = 0

        print(f'Начинаем опрос датчиков...')
        for test in range(self.circles):
            avg_req_speed = self.read_all_devices()
            if self.verbose:
                print(f'Цикл прогона: {test + 1} из {self.circles}',
                      f'Средняя моментальная скорость запроса: {avg_req_speed}',
                      '', sep='\n')
            gavg_req_speed += avg_req_speed

        self.serial.close()

        if len(self.count_dict) >= 3:
            keys = list(self.count_dict.keys())
            del self.count_dict[keys[0]]
            del self.count_dict[keys[-1]]
            
            print(f'Итоговый словарь:{self.count_dict}')
   
            average_speed_ms = round(1000 / mean(self.count_dict.values()), 2)
            average_speed_ms_unit = round(average_speed_ms / len(self.registers), 2)
            gavg_req_speed = round(gavg_req_speed / self.circles, 2)

            print(f'Средняя скорость запроса ВСЕХ регистров в ms: {average_speed_ms}',
                  f'Скорость одного датчика в ms:                 {average_speed_ms_unit}',
                  f'Скорость одного опроса ВСЕХ датчиков:         {gavg_req_speed}',
                  f'Всего ошибок:                                 {self.errors}', sep='\n')
        else:
            print('Мало данных для определение скорости, необходимо увеличить количество циклов')
            exit()

    def read_all_devices(self) -> float:
        speed_sum = 0

        for device_address in self.device_addresses:
            instrument = minimalmodbus.Instrument(self.serial, device_address)
            speed = self.read_device_data(instrument, device_address)
            speed_sum += speed
        return speed_sum / len(self.device_addresses)

    def read_device_data(self, instrument: minimalmodbus.Instrument, device_address: int) -> int:
        self.results = []

        try:
            start_time = perf_counter()
            for register in self.registers:
                self.results.append(instrument.read_register(register, functioncode=3))
            timestamp = perf_counter()
            speed = int((timestamp - start_time) * 1000)

            current_moment = datetime.now().minute*60 + datetime.now().second
            
            if current_moment in self.count_dict:
                self.count_dict[current_moment]+=1
            else:
                self.count_dict[current_moment]=1

            # if not self.time_delta:
            #     self.time_delta = current_sec - 1
            # current_sec -= self.time_delta

            # self.count_dict[current_sec] = self.count_dict.get(current_sec, 0) + 1

            if self.verbose:
                print(
                    f'Номер словаря: {current_moment}:{self.count_dict}; Результат из устройства {device_address}: {self.results[-1]};'
                    f' Скорость запроса в ms: {speed}', end='\n')
            return speed

        except minimalmodbus.ModbusException as error:
            self.errors += 1
            print(f'Ошибка чтения из устройства {device_address}: {error}')
            return 0


def main():
    parser = argparse.ArgumentParser(
        description='Измеритель скорости Modbus RTU. Параметры с ключиком -h. По умолчанию /dev/ttyS1, 1152008E1')

    parser.add_argument('-D', '--port',
                        type=str, default=DEFAULT_PORT_NAME, help='Название порта')
    parser.add_argument('-b', '--baud_rate',
                        type=int, default=DEFAULT_BAUD_RATE, help='Скорость передачи данных')
    parser.add_argument('-d', '--bytesize',
                        type=int, default=8, help='Размер байта')
    parser.add_argument('-p', '--parity',
                        type=str, default='E', choices=['N', 'E', 'O', 'M', 'S'], help='Бит четности')
    parser.add_argument('-s', '--stop_bits',
                        type=int, default=1, help='Количество стоп-бит')
    parser.add_argument('-c', '--circles',
                        type=int, default=DEFAULT_CIRCLES, help='Количество циклов полного опроса устройства')
    parser.add_argument('-a', '--device_addresses',
                        type=str, default=DEFAULT_REGISTERS, nargs='*', help='Адреса устройств для чтения (через ,)')
    parser.add_argument('-r', '--registers',
                        type=str, default=DEFAULT_ADDRESSES, nargs='*', help='Регистры для чтения (через ,)')
    parser.add_argument('-v', '--verbose',
                        action='store_true', help='Включить подробный вывод')

    args = parser.parse_args()
    worker = Measurement(vars(args))
    worker.check_serial_port()
    worker.do_tests()


if __name__ == '__main__':
    main()
