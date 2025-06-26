""" This function converts calibration files to records for Player mode """
import pandas as pd


target_drone_name = 'Mavic 2-2.4G'
all_drones = ['Mavic 2-2.4G', 'DJI-2.4G', 'Autel-2.4G', 'FPV-2.4G', 'Xiaomi-2.4G', 'Mavic Mini-2.4G',
              'Mavic 2-5.8G', 'DJI-5.8G', 'Autel-5.8G', 'FPV-5.8G', 'Xiaomi-5.8G', 'Mavic Mini-5.8G']

drone_index = all_drones.index(target_drone_name)

# чтение калибровочного файла
df = pd.read_csv('../calibration_records/calibr_record 11-06-25.txt', sep='\t', header=None)

result = []
# Создание выходной структуры
for row in df.itertuples(index=False):
    angle = row[0]
    antenna_levels = row[1:7]  # Значения от антенн
    drone_name = row[7]
    if drone_name != target_drone_name:
        continue  # пропускаем строки других дронов

    for i, value in enumerate(antenna_levels):
        values = [1] * len(all_drones)
        values[drone_index] = int(value)
        result.append({
            'antenna': i + 1,
            'values': values
        })

# Сохраняем в текстовый файл построчно
with open('../records/converted.txt', 'w') as f:
    for entry in result:
        f.write(str(entry) + '\n')
print('New file saved successful!')
