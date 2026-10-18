import json
import os
import random
import time

class CTSTestGenerator:
    """Генератор тестовых сценариев различной сложности для CTS компилятора."""
    
    def __init__(self, seed: int | None = None):
        # Если seed не передан, используем системное время для динамической генерации.
        if seed is None:
            seed = int(time.time() * 1000) % 2**32
        random.seed(seed)
        
        # Общие библиотеки буферов и параметры физики (согласно ТЗ)
        self.buffers = [
            {"id": "BUF_STD", "type": "standard", "input_capacitance": 0.5, "output_resistance": 50.0, "intrinsic_delay": 0.15, "drive_strength": 1.0, "available": True},
            {"id": "BUF_MID", "type": "mid", "input_capacitance": 1.0, "output_resistance": 25.0, "intrinsic_delay": 0.20, "drive_strength": 2.0, "available": True},
            {"id": "BUF_LARGE", "type": "large", "input_capacitance": 2.0, "output_resistance": 10.0, "intrinsic_delay": 0.30, "drive_strength": 4.0, "available": True}
        ]
        self.wire_model = {
            "unit_capacitance": 0.2,
            "unit_resistance": 0.05,
            "unit_length": 1.0,
            "model": "elmore"
        }
        self.optimization = {
            "objective": "min_skew",
            "secondary_objective": "min_power",
            "max_iterations": 20,
            "convergence_tol": 1e-4,
            "skew_target": 0.05,
            "power_weight": 0.1,
            "delay_weight": 0.9
        }

    def generate_case(self, filename: str, num_sinks: int, chip_size: int = 2000, grid_size: int = 10):
        """Создает и сохраняет один тестовый JSON файл со свободными случайными координатами."""
        
        # Задаем параметры кристалла
        design = {
            "chip_width": chip_size,
            "chip_height": chip_size,
            "grid_size": grid_size
        }
        
        # Источник тактовой частоты по центру верхней границы кристалла (без выравнивания по сетке)
        clock_source = {
            "id": "CLK_SRC",
            "x": float(chip_size // 2),
            "y": float(chip_size),
            "pin_id": "CLK_PIN",
            "input_capacitance": 0.0,
            "fixed": True
        }
        
        # Алгоритмические параметры сборки дерева
        tree_params = {
            "algorithm": "median_partition",
            "max_fanout": 4,
            "min_sinks_for_partition": 2,
            "max_depth": 12 if num_sinks > 500 else 10,
            "partition_criterion": "balanced_capacitance",
            "partition_axis": "auto",
            "median_type": "geometric_median",
            "buffer_insertion": True,
            "buffer_selection": "size_by_load",
            "min_buffer_input_cap": 0.5,
            "snaking_allowed": True,
            "wire_snaking_limit": 0.2,
            "obstacle_aware": False
        }
        
        # Генерация случайных потребителей (Sinks) без привязки к границам и сетке
        sinks = []
        for i in range(1, num_sinks + 1):
            # Координаты могут принимать любые абсолютно случайные значения
            x_coord = random.randint(0, chip_size)
            y_coord = random.randint(0, chip_size)
            
            # Случайная емкость затвора триггера от 2.0 до 6.0 фФ
            cap = round(random.uniform(2.0, 6.0), 1)
            
            sinks.append({
                "id": f"S{i}",
                "x": float(x_coord),
                "y": float(y_coord),
                "pin_id": f"S{i}_PIN",
                "capacitance": cap,
                "required_arrival_time": 3.0 if num_sinks > 500 else 2.5,
                "fixed": True
            })
            
        # Формируем итоговую структуру JSON
        config_data = {
            "design": design,
            "clock_source": clock_source,
            "sinks": sinks,
            "buffers": self.buffers,
            "wire_model": self.wire_model,
            "tree_params": tree_params,
            "optimization": self.optimization
        }
        
        # Убедимся, что папка существует, и запишем файл
        os.makedirs("tests", exist_ok=True)
        filepath = os.path.join("tests", filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
            
        print(f"-> УСПЕХ: сгенерирован тест {filepath} ({num_sinks} терминалов) со случайными координатами.")

if __name__ == "__main__":
    # Инициализируем генератор случайным seed на основе времени для динамических данных
    generator = CTSTestGenerator(seed=None)
    
    print("=" * 40)
    print("ГЕНЕРАЦИЯ СЛУЧАЙНЫХ ТЕСТОВЫХ НАБОРОВ CTS")
    print("=" * 40)
    
    # Генерация профилей сложности согласно спецификации ТЗ
    generator.generate_case("test_easy.json", num_sinks=10)       
    generator.generate_case("test_medium.json", num_sinks=100)     
    generator.generate_case("test_hard.json", num_sinks=500)       
    generator.generate_case("test_stress.json", num_sinks=1000)    
    
    print("=" * 40)
