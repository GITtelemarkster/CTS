import json
import os
from typing import Dict, Any, Tuple
from models import ClockSource, Sink, BufferType, WireModel


def round_to_grid(coord: float, grid_size: float) -> float:
    """Округляет координату до ближайшего шага сетки grid_size"""
    if grid_size <= 0:
        return coord
    return round(coord / grid_size) * grid_size

class CTSParser:
    """Класс для загрузки и валидации входных данных CTS проекта"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.grid_size = 1.0
        self.chip_width = 0.0
        self.chip_height = 0.0
        
        # Списки и объекты для хранения распарсенных данных
        self.clock_source: ClockSource = None
        self.sinks: list[Sink] = []
        self.buffers: dict[str, BufferType] = {}  # Храним как словарь для быстрого поиска по ID
        self.wire_model: WireModel = None
        self.tree_params: Dict[str, Any] = {}
        self.optimization_params: Dict[str, Any] = {}

    def parse(self) -> Tuple[ClockSource, list[Sink], dict[str, BufferType], WireModel, Dict[str, Any], Dict[str, Any]]:
        """
        Основной метод парсинга. 
        Загружает JSON, применяет сетку координат и возвращает кортеж объектов.
        """
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"Входной файл конфигурации не найден: {self.filepath}")

        with open(self.filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 1. Чтение параметров кристалла (Design)
        design = data.get("design", {})
        self.grid_size = float(design.get("grid_size", 1.0))
        self.chip_width = float(design.get("chip_width", 2000.0))
        self.chip_height = float(design.get("chip_height", 2000.0))

        # 2. Парсинг источника синхронизации (Clock Source)
        src_data = data["clock_source"]
        src_x = round_to_grid(float(src_data["x"]), self.grid_size)
        src_y = round_to_grid(float(src_data["y"]), self.grid_size)
        
        self.clock_source = ClockSource(
            id=src_data["id"],
            x=src_x,
            y=src_y,
            pin_id=src_data["pin_id"],
            input_capacitance=float(src_data["input_capacitance"]),
            fixed=src_data.get("fixed", True)
        )
        self.validate_bounds(self.clock_source.x, self.clock_source.y, self.clock_source.id)

        # 3. Парсинг потребителей (Sinks)
        for sink_data in data.get("sinks", []):
            sk_x = round_to_grid(float(sink_data["x"]), self.grid_size)
            sk_y = round_to_grid(float(sink_data["y"]), self.grid_size)
            
            sink_obj = Sink(
                id=sink_data["id"],
                x=sk_x,
                y=sk_y,
                pin_id=sink_data["pin_id"],
                capacitance=float(sink_data["capacitance"]),
                required_arrival_time=float(sink_data["required_arrival_time"]),
                fixed=sink_data.get("fixed", True)
            )
            self.validate_bounds(sink_obj.x, sink_obj.y, sink_obj.id)
            self.sinks.append(sink_obj)

        # 4. Парсинг доступных буферов (Buffers)
        for buf_data in data.get("buffers", []):
            buf_obj = BufferType(
                id=buf_data["id"],
                type=buf_data["type"],
                input_capacitance=float(buf_data["input_capacitance"]),
                output_resistance=float(buf_data["output_resistance"]),
                intrinsic_delay=float(buf_data["intrinsic_delay"]),
                drive_strength=float(buf_data["drive_strength"]),
                available=buf_data.get("available", True)
            )
            # Добавляем в словарь только доступные буферы
            if buf_obj.available:
                self.buffers[buf_obj.id] = buf_obj

        # 5. Парсинг модели проводов (Wire Model)
        wm_data = data["wire_model"]
        self.wire_model = WireModel(
            unit_capacitance=float(wm_data["unit_capacitance"]),
            unit_resistance=float(wm_data["unit_resistance"]),
            unit_length=float(wm_data["unit_length"]),
            model=wm_data.get("model", "elmore").lower()
        )

        # 6. Сохранение сырых параметров алгоритма и оптимизации
        self.tree_params = data.get("tree_params", {})
        self.optimization_params = data.get("optimization", {})

        return (
            self.clock_source, 
            self.sinks, 
            self.buffers, 
            self.wire_model, 
            self.tree_params, 
            self.optimization_params
        )

    def validate_bounds(self, x: float, y: float, entity_id: str):
        """Проверяет, что объект не вышел за границы кристалла"""
        if not (0 <= x <= self.chip_width) or not (0 <= y <= self.chip_height):
            raise ValueError(
                f"Элемент '{entity_id}' находится вне границ кристалла! "
                f"Координаты: ({x}, {y}), Размер кристалла: {self.chip_width}x{self.chip_height}"
            )